"""Tests for required field auto-fill."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.required_field_filler import fill_missing_fields


@patch("app.services.required_field_filler.get_field_value", new_callable=AsyncMock, return_value="")
def test_fill_missing_fields_calls_set_field_with_any(mock_get_value):
    page = MagicMock()
    field_actions = MagicMock()
    field_actions.set_field = AsyncMock(return_value="Net 30")
    data_change_page = MagicMock()
    data_change_page.open_form_tab = AsyncMock()

    logs = asyncio.run(
        fill_missing_fields(
            page,
            ["Payment Options"],
            bottler_id="5000",
            field_actions=field_actions,
            data_change_page=data_change_page,
        )
    )

    field_actions.set_field.assert_awaited_once_with(
        "Payment Options", "__any__", "combobox"
    )
    assert any("Payment Options" in line for line in logs)
    data_change_page.open_form_tab.assert_awaited_once_with("Account Receivable")
