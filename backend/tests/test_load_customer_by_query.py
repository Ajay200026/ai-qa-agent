"""load_customer_by_saved_query tests with mocked REST SOQL."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.automation.pages.data_change_page import DataChangePage
from app.schemas.customer_target import SoqlAccountRow, SoqlQueryResponse


def test_load_customer_by_saved_query_uses_rest_api_result():
    page = MagicMock()
    org = SimpleNamespace(id=uuid4())
    dc = DataChangePage(page, org=org, credentials={"username": "a", "password": "b"})

    row = SoqlAccountRow(account_number="0601234567", account_name="Test Co")
    response = SoqlQueryResponse(total_size=1, records=[row])
    dc.load_customer = AsyncMock()
    dc.is_customer_loaded = AsyncMock(side_effect=[False, True])
    client = MagicMock()
    client.query = AsyncMock(return_value=response)

    with patch(
        "app.automation.pages.data_change_page.SoqlClient",
        return_value=client,
    ):
        result = asyncio.run(
            dc.load_customer_by_saved_query(
                soql_text="SELECT AccountNumber FROM Account LIMIT 1"
            )
        )

    assert result == "0601234567"
    dc.load_customer.assert_awaited_once()
    call_kwargs = dc.load_customer.await_args.kwargs
    assert call_kwargs["customer_number"] == "0601234567"


def test_load_customer_by_saved_query_skips_soql_when_customer_number_set():
    page = MagicMock()
    org = SimpleNamespace(id=uuid4())
    dc = DataChangePage(page, org=org, credentials={"username": "a", "password": "b"})
    dc.load_customer = AsyncMock()
    dc.is_customer_loaded = AsyncMock(side_effect=[False, True])

    with patch("app.automation.pages.data_change_page.SoqlClient") as client_cls:
        result = asyncio.run(
            dc.load_customer_by_saved_query(
                soql_text="SELECT AccountNumber FROM Account LIMIT 1",
                customer_number="0608888888",
                account_number="0608888888",
                sales_office="S003",
            )
        )
        client_cls.assert_not_called()

    assert result == "0608888888"
    dc.load_customer.assert_awaited_once()
    call_kwargs = dc.load_customer.await_args.kwargs
    assert call_kwargs["customer_number"] == "0608888888"
    assert call_kwargs["sales_office"] == "S003"
