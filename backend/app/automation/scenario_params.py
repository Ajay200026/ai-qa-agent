import re

from app.automation.combobox import AUTO_PICK
from app.automation.request_modules import normalize_request_module
from app.schemas.agent import PlannedStep


def scenario_text(state: dict) -> str:
    parts = [
        state.get("scenario_name", ""),
        state.get("scenario_description", ""),
        state.get("acceptance_criteria", ""),
        state.get("test_case_content", ""),
        state.get("regression_content", ""),
    ]
    return "\n".join(p for p in parts if p and p != "N/A")


def is_tc_dc_scenario(text: str) -> bool:
    lower = text.lower()
    return (
        "tc_dc" in lower
        or ("primary group" in lower and "data change" in lower)
        or ("sales office" in lower and "customer number" in lower)
    )


def parse_create_request_params(text: str) -> dict[str, str]:
    params: dict[str, str] = {}
    select_patterns = [
        r"select\s+['\"]?([^'\".\n]+?)['\"]?(?:\s+module)?(?:\.|,|$|\s+and\b)",
        r"choose\s+['\"]?([^'\".\n]+?)['\"]?(?:\.|,|$|\s+and\b)",
    ]
    for pattern in select_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            option = match.group(1).strip()
            skip = {"an existing customer", "existing customer", "customer", "the first customer"}
            if option.lower() not in skip and "customer" not in option.lower()[:12]:
                params["menu_option"] = normalize_request_module(option)
                break

    if re.search(r"click\s+(?:the\s+)?['\"]?New['\"]?", text, re.IGNORECASE):
        params["button_label"] = "New"
    return params


def parse_sales_office(text: str) -> str | None:
    match = re.search(r"sales\s+office\s*[=:]\s*['\"]?([^'\".\n\s]+)['\"]?", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def parse_customer_number(text: str) -> str | None:
    match = re.search(
        r"customer\s+number\s*[=:]\s*['\"]?([^'\".\n\s]+)['\"]?",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def parse_request_module(text: str) -> str:
    """Parse request module from scenario — returns exact New-menu label e.g. NEW DATA CHANGE."""
    field = re.search(
        r"request\s+module\s*[=:]\s*['\"]?([^'\".\n]+?)['\"]?(?:\.|,|$|\n)",
        text,
        re.IGNORECASE,
    )
    if field:
        return normalize_request_module(field.group(1))

    explicit = re.search(
        r"(?:select|choose|pick)\s+(?:the\s+)?['\"]?(NEW\s+[A-Z\s]+|CUSTOMER\s+[A-Z]+|EQUIPMENT\s+[A-Z\s]+|FULL\s+ROUTE\s+SWAP|MASS\s+REQUEST|EMPLOYEE\s+REASSIGNMENT)['\"]?",
        text,
        re.IGNORECASE,
    )
    if explicit:
        return normalize_request_module(explicit.group(1))

    if re.search(r"data\s+change", text, re.IGNORECASE):
        return "NEW DATA CHANGE"
    return "NEW DATA CHANGE"


def parse_primary_group(text: str) -> str | None:
    patterns = [
        r"primary\s+group\s+(?:to|as|with)\s+(?:the\s+)?(?:desired\s+)?value\s*['\"]?([^'\".\n]+?)['\"]?",
        r"primary\s+group\s+(?:to|as|=|:)\s*['\"]?([^'\".\n]+?)['\"]?",
        r"update\s+primary\s+group\s+(?:to|with)\s*['\"]?([^'\".\n]+?)['\"]?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value.lower() not in {"the desired value", "desired value"}:
                return value
    return None


def build_tc_dc_steps(state: dict) -> list[PlannedStep]:
    """Map TC_DC_001-style test cases to executable Playwright steps."""
    text = scenario_text(state)
    office = parse_sales_office(text) or AUTO_PICK
    customer = parse_customer_number(text)
    request_module = parse_request_module(text)
    primary_group = parse_primary_group(text) or "Default"
    create_params = parse_create_request_params(text)

    office_label = (
        "Select any available Sales Office"
        if office == AUTO_PICK
        else f"Select Sales Office = {office}"
    )

    steps_after_module: list[PlannedStep] = [
        PlannedStep(
            seq=5,
            name=office_label,
            action="select_sales_office",
            params={"office": office},
        ),
    ]

    if customer:
        steps_after_module.append(
            PlannedStep(
                seq=6,
                name=f"Enter Customer Number = {customer}",
                action="enter_customer_number",
                params={"customer_number": customer},
            )
        )
        next_seq = 7
    else:
        steps_after_module.append(
            PlannedStep(
                seq=6,
                name="Open customer search field",
                action="open_customer_search",
                params={},
            )
        )
        next_seq = 7

    # Post-login org lands on Queues — skip App Launcher / Onboarding navigation (TC steps 2–5).
    return [
        PlannedStep(seq=1, name="Login to Salesforce", action="login", params={}),
        PlannedStep(
            seq=2,
            name="Open Customer Life Cycle Queues",
            action="open_queues",
            params={},
        ),
        PlannedStep(
            seq=3,
            name="Click New",
            action="click_new_button",
            params={"button_label": create_params.get("button_label", "New")},
        ),
        PlannedStep(
            seq=4,
            name=f"Select {request_module} from New menu",
            action="select_request_module",
            params={"module_option": request_module},
        ),
        *steps_after_module,
        PlannedStep(
            seq=next_seq,
            name="Wait for customer search dropdown",
            action="wait_for_customer_dropdown",
            params={},
        ),
        PlannedStep(
            seq=next_seq + 1,
            name="Select first customer from dropdown",
            action="select_first_customer",
            params={},
        ),
        PlannedStep(seq=next_seq + 2, name="Click Search", action="search", params={}),
        PlannedStep(
            seq=next_seq + 3,
            name="Wait for customer data to load",
            action="wait_for_data",
            params={},
        ),
        PlannedStep(
            seq=next_seq + 4,
            name="Navigate to Customer Details",
            action="open_customer_details",
            params={},
        ),
        PlannedStep(
            seq=next_seq + 5,
            name="Update Primary Group",
            action="modify_primary_group",
            params={"primary_group": primary_group},
        ),
        PlannedStep(seq=next_seq + 6, name="Click Submit", action="submit", params={}),
    ]


def enrich_steps_from_scenario(steps: list[PlannedStep], state: dict) -> list[PlannedStep]:
    text = scenario_text(state)
    if not text.strip():
        return steps

    create_params = parse_create_request_params(text)
    customer_number = parse_customer_number(text)
    primary_group = parse_primary_group(text)
    office = parse_sales_office(text)

    enriched: list[PlannedStep] = []
    for step in steps:
        params = dict(step.params)

        if step.action == "create_data_change_request":
            params.setdefault("button_label", create_params.get("button_label", "New"))
            params.setdefault(
                "menu_option",
                create_params.get("menu_option") or parse_request_module(text),
            )
        if step.action == "click_new_button":
            params.setdefault("button_label", create_params.get("button_label", "New"))
        if step.action == "search_select_customer" and customer_number:
            params.setdefault("customer_query", customer_number)
        if step.action == "enter_customer_number" and customer_number:
            params.setdefault("customer_number", customer_number)
        if step.action == "select_sales_office":
            params.setdefault("office", office or AUTO_PICK)
        if step.action == "modify_primary_group" and primary_group:
            params.setdefault("primary_group", primary_group)
        if step.action == "select_request_module":
            params["module_option"] = normalize_request_module(
                params.get("module_option") or parse_request_module(text)
            )
        if step.action == "select_module":
            params["module"] = parse_request_module(text)

        enriched.append(step.model_copy(update={"params": params}))

    return enriched
