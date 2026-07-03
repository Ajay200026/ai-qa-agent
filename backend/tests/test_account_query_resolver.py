"""Account query resolver: rotation, step patching, pre-resolved load."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.automation.scenario_params import patch_steps_with_resolved_account
from app.schemas.agent import PlannedStep
from app.schemas.customer_target import SoqlAccountRow, SoqlQueryResponse
from app.services.account_query_resolver import ResolvedAccount, resolve_account_query


def _rows(*numbers: str) -> list[SoqlAccountRow]:
    return [
        SoqlAccountRow(
            account_number=n,
            customer_number=f"C{n}",
            sales_office=f"S{n[-3:]}",
            account_group="Z001",
            raw={"Id": f"id-{n}"},
        )
        for n in numbers
    ]


def test_rotation_advances_cursor():
    query_id = uuid4()
    account_query = {
        "id": str(query_id),
        "soql_text": "SELECT Id FROM Account LIMIT 3",
        "match_hints": {"next_account_index": 0},
    }
    org = SimpleNamespace(id=uuid4())
    page = MagicMock()
    db = MagicMock()

    responses = [
        SoqlQueryResponse(records=_rows("0601111111", "0602222222", "0603333333")),
        SoqlQueryResponse(records=_rows("0601111111", "0602222222", "0603333333")),
        SoqlQueryResponse(records=_rows("0601111111", "0602222222", "0603333333")),
    ]
    client = MagicMock()
    client.query = AsyncMock(side_effect=responses)

    update_mock = AsyncMock()
    with (
        patch(
            "app.services.account_query_resolver.SoqlClient",
            return_value=client,
        ),
        patch(
            "app.services.account_query_resolver.AccountQueryService"
        ) as svc_cls,
    ):
        svc_cls.return_value.update = update_mock

        r0 = asyncio.run(
            resolve_account_query(org, {}, page, account_query, db=db)
        )
        r1 = asyncio.run(
            resolve_account_query(org, {}, page, account_query, db=db)
        )
        r2 = asyncio.run(
            resolve_account_query(org, {}, page, account_query, db=db)
        )

    assert r0.pick_index == 0
    assert r0.customer_number == "C0601111111"
    assert r0.sales_office == "S111"
    assert r1.pick_index == 1
    assert r2.pick_index == 2
    assert update_mock.await_count == 3
    assert account_query["match_hints"]["next_account_index"] == 3


def test_patch_steps_skips_office_when_plan_is_any():
    resolved = ResolvedAccount(
        account_number="0601234567",
        customer_number="0601234567",
        sales_office="S003",
        account_group="Z001",
        pick_index=0,
        total_records=5,
    )
    steps = [
        PlannedStep(
            seq=5,
            name="Office",
            action="select_sales_office",
            params={"office": "__any__"},
        ),
        PlannedStep(
            seq=6,
            name="Load",
            action="load_customer_by_query",
            params={"soql_text": "SELECT Id FROM Account"},
        ),
    ]
    patched = patch_steps_with_resolved_account(
        steps, resolved, soql_text="SELECT Id FROM Account"
    )
    assert not any(s.action == "select_sales_office" for s in patched)
    load = next(s for s in patched if s.action == "load_customer_by_query")
    assert load.params["customer_number"] == "0601234567"
    assert "sales_office" not in load.params
    assert load.params["resolved"] is True


def test_patch_steps_pairs_office_when_plan_has_both():
    resolved = ResolvedAccount(
        account_number="0601234567",
        customer_number="0601234567",
        sales_office="S003",
        account_group="Z001",
        pick_index=0,
        total_records=5,
    )
    steps = [
        PlannedStep(
            seq=5,
            name="Office",
            action="select_sales_office",
            params={"office": "S001"},
        ),
        PlannedStep(
            seq=6,
            name="Load",
            action="load_customer_by_query",
            params={
                "soql_text": "SELECT Id FROM Account",
                "customer_number": "0601234567",
            },
        ),
    ]
    patched = patch_steps_with_resolved_account(
        steps, resolved, soql_text="SELECT Id FROM Account"
    )
    office_step = next(s for s in patched if s.action == "select_sales_office")
    load = next(s for s in patched if s.action == "load_customer_by_query")
    assert office_step.params["office"] == "S003"
    assert load.params["customer_number"] == "0601234567"
    assert load.params["sales_office"] == "S003"


def test_load_customer_skips_soql_when_pre_resolved():
    from app.automation.pages.data_change_page import DataChangePage

    page = MagicMock()
    org = SimpleNamespace(id=uuid4())
    dc = DataChangePage(page, org=org, credentials={"username": "a", "password": "b"})
    dc.load_customer = AsyncMock()
    dc.is_customer_loaded = AsyncMock(side_effect=[False, True])

    with patch("app.automation.pages.data_change_page.SoqlClient") as client_cls:
        result = asyncio.run(
            dc.load_customer_by_saved_query(
                soql_text="SELECT AccountNumber FROM Account LIMIT 1",
                customer_number="0609999999",
                sales_office="S007",
            )
        )
        client_cls.assert_not_called()

    assert result == "0609999999"
    dc.load_customer.assert_awaited_once()
    assert dc.load_customer.await_args.kwargs["customer_number"] == "0609999999"
    assert dc.load_customer.await_args.kwargs["sales_office"] == "S007"
