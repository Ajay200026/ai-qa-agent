"""Customer targeting schema used by scenarios for deterministic customer load."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CustomerSearchStrategy(StrEnum):
    BY_NUMBER = "by_number"
    BY_NAME = "by_name"
    BY_SOQL = "by_soql"


class CustomerTarget(BaseModel):
    """Sensitive customer payload. NEVER serialize to an LLM prompt."""

    account_number: str | None = None
    account_name: str | None = None
    sales_office: str | None = None
    account_group: str | None = None
    distribution_channel: str | None = None
    search_strategy: CustomerSearchStrategy = CustomerSearchStrategy.BY_NUMBER
    soql_query: str | None = None
    soql_resolved_at: datetime | None = None
    bottler: str | None = None

    model_config = {"extra": "ignore"}

    def is_resolvable(self) -> bool:
        return bool(self.account_number) or bool(self.soql_query) or bool(self.account_name)

    def needs_soql_resolution(self) -> bool:
        if not self.soql_query:
            return False
        return not self.account_number


class SoqlQueryRequest(BaseModel):
    soql: str = Field(min_length=1, max_length=8000)
    limit: int = Field(default=5, ge=1, le=50)


class SoqlAccountRow(BaseModel):
    account_number: str | None = None
    customer_number: str | None = None
    account_name: str | None = None
    sales_office: str | None = None
    account_group: str | None = None
    distribution_channel: str | None = None
    bottler: str | None = None
    raw: dict = Field(default_factory=dict)


class SoqlQueryResponse(BaseModel):
    total_size: int = 0
    records: list[SoqlAccountRow] = Field(default_factory=list)
    users: list[dict] = Field(default_factory=list)
    done: bool = True
