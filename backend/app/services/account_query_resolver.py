"""Resolve a saved Account Query to one account row with round-robin rotation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from playwright.async_api import Page

from app.schemas.customer_target import SoqlAccountRow
from app.schemas.libraries import AccountQueryUpdate, MatchHints
from app.services.account_query_service import AccountQueryService
from app.services.salesforce_query import SoqlClient, SoqlError

logger = logging.getLogger(__name__)

ROTATION_LIMIT = 50


@dataclass(frozen=True)
class ResolvedAccount:
    account_id: str | None = None
    account_number: str | None = None
    customer_number: str | None = None
    account_name: str | None = None
    sales_office: str | None = None
    account_group: str | None = None
    distribution_channel: str | None = None
    bottler: str | None = None
    pick_index: int = 0
    total_records: int = 0

    @classmethod
    def from_row(cls, row: SoqlAccountRow, *, pick_index: int, total: int) -> ResolvedAccount:
        customer_number = row.customer_number or row.account_number
        account_id = row.raw.get("Id") if row.raw else None
        return cls(
            account_id=account_id,
            account_number=row.account_number,
            customer_number=customer_number,
            account_name=row.account_name,
            sales_office=row.sales_office,
            account_group=row.account_group,
            distribution_channel=row.distribution_channel,
            bottler=row.bottler,
            pick_index=pick_index,
            total_records=total,
        )

    def search_number(self) -> str | None:
        return self.customer_number or self.account_number

    def to_step_params(self, soql_text: str, *, include_sales_office: bool = True) -> dict[str, Any]:
        return {
            k: v
            for k, v in {
                "soql_text": soql_text,
                "account_number": self.account_number,
                "customer_number": self.customer_number,
                "account_name": self.account_name,
                "sales_office": self.sales_office if include_sales_office else None,
                "account_group": self.account_group,
                "distribution_channel": self.distribution_channel,
                "resolved": True,
            }.items()
            if v is not None and v != ""
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_number": self.account_number,
            "customer_number": self.customer_number,
            "account_name": self.account_name,
            "sales_office": self.sales_office,
            "account_group": self.account_group,
            "distribution_channel": self.distribution_channel,
            "bottler": self.bottler,
            "pick_index": self.pick_index,
            "total_records": self.total_records,
        }


async def resolve_account_query(
    org,
    credentials: dict[str, Any],
    page: Page,
    account_query: dict[str, Any],
    *,
    db=None,
) -> ResolvedAccount:
    """Fetch up to 50 rows, pick one via round-robin cursor, persist next index."""
    soql_text = (account_query.get("soql_text") or "").strip()
    if not soql_text:
        raise SoqlError("Account query has no SOQL text")

    client = SoqlClient(org=org, credentials=credentials, page=page)
    result = await client.query(soql_text, limit=ROTATION_LIMIT)
    if not result.records:
        raise SoqlError("Account SOQL query returned no rows")

    hints = dict(account_query.get("match_hints") or {})
    cursor = int(hints.get("next_account_index") or 0)
    pick_index = cursor % len(result.records)
    row = result.records[pick_index]
    resolved = ResolvedAccount.from_row(
        row, pick_index=pick_index, total=len(result.records)
    )

    logger.info(
        "account_query_resolver picked index %s/%s account=%s office=%s",
        pick_index,
        len(result.records),
        resolved.search_number(),
        resolved.sales_office,
    )

    query_id = account_query.get("id")
    if query_id and db is not None:
        hints["next_account_index"] = cursor + 1
        await AccountQueryService(db).update(
            UUID(str(query_id)),
            AccountQueryUpdate(match_hints=MatchHints(**hints)),
        )
        if "match_hints" not in account_query or account_query["match_hints"] is None:
            account_query["match_hints"] = {}
        account_query["match_hints"]["next_account_index"] = cursor + 1

    return resolved
