from dataclasses import dataclass
from enum import StrEnum


class LocatorStrategy(StrEnum):
    ROLE = "role"
    LABEL = "label"
    PLACEHOLDER = "placeholder"
    TEXT = "text"
    TEST_ID = "test_id"


@dataclass(frozen=True)
class LocatorDef:
    strategy: LocatorStrategy
    value: str
    role: str | None = None
    exact: bool = False


LOCATORS: dict[str, LocatorDef] = {
    # Login page
    "login.username": LocatorDef(LocatorStrategy.LABEL, "Username"),
    "login.password": LocatorDef(LocatorStrategy.LABEL, "Password"),
    "login.submit": LocatorDef(LocatorStrategy.ROLE, "Log In to Sandbox", role="button"),
    "login.submit_prod": LocatorDef(LocatorStrategy.ROLE, "Log In", role="button"),
    # App launcher
    "app_launcher.button": LocatorDef(LocatorStrategy.ROLE, "App Launcher", role="button"),
    "app_launcher.search": LocatorDef(LocatorStrategy.PLACEHOLDER, "Search apps and items..."),
    "app_launcher.onboarding": LocatorDef(LocatorStrategy.TEXT, "Onboarding", exact=True),
    # Customer Life Cycle Queues
    "onboarding.customer_lifecycle_tab": LocatorDef(
        LocatorStrategy.ROLE, "Customer_Life_Cycle_Queues", role="tab"
    ),
    "customer_lifecycle.new_button": LocatorDef(LocatorStrategy.ROLE, "New", role="button"),
    "customer_lifecycle.data_change_request": LocatorDef(
        LocatorStrategy.TEXT, "NEW DATA CHANGE", exact=True
    ),
    "customer_lifecycle.data_change_option": LocatorDef(
        LocatorStrategy.TEXT, "Data Change", exact=True
    ),
    # Data Change Request flow
    "data_change.customer_search": LocatorDef(LocatorStrategy.PLACEHOLDER, "Search customer..."),
    "data_change.customer_number": LocatorDef(LocatorStrategy.LABEL, "Customer Name/Number"),
    "data_change.search_button": LocatorDef(LocatorStrategy.ROLE, "Search", role="button"),
    "data_change.customer_details_tab": LocatorDef(
        LocatorStrategy.ROLE, "Customer Details", role="tab"
    ),
    "data_change.primary_group": LocatorDef(LocatorStrategy.LABEL, "Primary Group"),
    "data_change.submit": LocatorDef(LocatorStrategy.ROLE, "Submit", role="button"),
    # Legacy / optional fields
    "data_change.module_selection": LocatorDef(LocatorStrategy.LABEL, "Module Selection"),
    "data_change.sales_office": LocatorDef(LocatorStrategy.LABEL, "Sales Office"),
    "data_change.save_draft": LocatorDef(LocatorStrategy.ROLE, "Save Draft", role="button"),
    "data_change.success_toast": LocatorDef(LocatorStrategy.TEXT, "Draft saved"),
    "data_change.submit_success": LocatorDef(LocatorStrategy.TEXT, "success"),
    "data_change.loading_spinner": LocatorDef(LocatorStrategy.ROLE, "Loading", role="status"),
    # Generic
    "generic.toast_message": LocatorDef(LocatorStrategy.ROLE, "status", role="status"),
}


def get_locator(name: str) -> LocatorDef:
    if name not in LOCATORS:
        raise KeyError(f"Locator '{name}' not found in registry")
    return LOCATORS[name]
