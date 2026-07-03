from app.knowledge.data_change_field_registry import (
    get_required_fields_for_bottler,
    load_data_change_fields,
    resolve_automation_type,
    section_to_tab_label,
)


def test_loads_field_configs():
    fields = load_data_change_fields()
    assert len(fields) > 50
    assert any(f.required_bottler_ids for f in fields)


def test_primary_group_is_search_lookup():
    assert resolve_automation_type("Primary Group") == "lookup"


def test_customer_lookup_alias():
    from app.knowledge.data_change_field_registry import get_field_by_label

    field = get_field_by_label("Customer Number")
    assert field is not None
    assert field.automation_type == "lookup"


def test_payment_options_required_for_5000():
    required = get_required_fields_for_bottler("5000")
    labels = {f.label for f in required}
    assert "Payment Options" in labels
    assert "Terms of Payment" in labels


def test_section_to_tab_label_ar():
    assert section_to_tab_label("AR_FIELDS") == "Account Receivable"
    assert section_to_tab_label("CUSTOMER_DETAILS") == "Customer Details"
