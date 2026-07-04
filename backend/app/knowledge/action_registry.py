"""Map QA automation actions to code graph fields and modules."""

ACTION_SECTION_MAP = {
    "login": "login",
    "open_queues": "customer_lifecycle",
    "create_data_change_request": "customer_lifecycle",
    "search_select_customer": "data_change",
    "open_customer_details": "data_change",
    "modify_primary_group": "data_change",
    "submit": "data_change",
    "click_new_button": "customer_lifecycle",
    "select_request_module": "customer_lifecycle",
    "open_customer_search": "data_change",
    "validate_expected": "validation",
    "set_field": "data_change",
    "wait_for_customer_dropdown": "data_change",
    "select_first_customer": "data_change",
    "open_app_launcher": "app_launcher",
    "open_app": "onboarding",
    "open_tab": "customer_lifecycle",
    "click_new": "customer_lifecycle",
    "select_module": "data_change",
    "select_sales_office": "data_change",
    "enter_customer_number": "data_change",
    "search": "data_change",
    "wait_for_data": "data_change",
    "save_draft": "data_change",
}

ACTION_FIELD_MAP = {
    "modify_primary_group": "primary_group",
    "search_select_customer": "customer_number",
    "select_module": "module_selection",
    "select_sales_office": "sales_office",
    "enter_customer_number": "customer_number",
    "set_field": "field",
}

MODULE_HINTS = {
    "data_change": "DataChange",
    "onboarding": "Onboarding",
    "customer_lifecycle": "customerLifecycle",
}


def resolve_field_for_action(action: str, action_params: dict | None = None) -> str | None:
    if action_params and action_params.get("field"):
        return str(action_params["field"])
    return ACTION_FIELD_MAP.get(action)


def resolve_module_hint(action: str) -> str | None:
    section = ACTION_SECTION_MAP.get(action)
    if section:
        return MODULE_HINTS.get(section)
    return None
