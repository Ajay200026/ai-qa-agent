import re

from app.automation.combobox import AUTO_PICK, is_auto_pick
from app.automation.request_modules import normalize_request_module
from app.schemas.agent import PlannedStep
from app.schemas.login_as import LoginAsTarget


def _resolve_scenario_login_as(state: dict) -> LoginAsTarget | None:
    profile = state.get("login_as_profile")
    if isinstance(profile, dict) and profile.get("bottler_id") and profile.get("onboarding_role"):
        return LoginAsTarget(
            bottler_id=str(profile["bottler_id"]),
            onboarding_role=str(profile["onboarding_role"]),
            enabled=profile.get("enabled", True),
        )
    raw = state.get("login_as_target")
    if not raw:
        return None
    try:
        target = (
            raw if isinstance(raw, LoginAsTarget) else LoginAsTarget.model_validate(raw)
        )
    except Exception:
        return None
    if not target.enabled or not target.bottler_id or not target.onboarding_role:
        return None
    return target.normalized()


def splice_login_as_step(
    steps: list[PlannedStep], state: dict
) -> list[PlannedStep]:
    """Insert a `login_as` step after the first `login` step when configured.

    Renumbers downstream steps so seq numbers stay contiguous.
    """
    target = _resolve_scenario_login_as(state)
    if not target:
        return steps

    # Idempotent: don't double-insert if a login_as step already exists.
    if any(step.action == "login_as" for step in steps):
        return steps

    login_idx = next((i for i, s in enumerate(steps) if s.action == "login"), None)
    if login_idx is None:
        return steps

    inserted = PlannedStep(
        seq=steps[login_idx].seq + 1,
        name=f"Impersonate {target.onboarding_role}@{target.bottler_id}",
        action="login_as",
        params={
            "bottler_id": target.bottler_id,
            "onboarding_role": target.onboarding_role,
        },
    )

    result: list[PlannedStep] = []
    for i, step in enumerate(steps):
        result.append(step)
        if i == login_idx:
            result.append(inserted)

    # Renumber seq to keep them contiguous starting at the original first seq.
    base_seq = steps[0].seq if steps else 1
    for idx, step in enumerate(result):
        step.seq = base_seq + idx
    return result


def apply_account_query_to_steps(
    steps: list[PlannedStep], state: dict
) -> list[PlannedStep]:
    """Replace load_customer with load_customer_by_query when a saved query is set."""
    account_query = state.get("account_query")
    if not account_query or not isinstance(account_query, dict):
        return steps
    soql_text = account_query.get("soql_text")
    if not soql_text:
        return steps

    result: list[PlannedStep] = []
    for step in steps:
        if step.action == "load_customer":
            hints = account_query.get("match_hints") or {}
            result.append(
                PlannedStep(
                    seq=step.seq,
                    name=f"Load customer via query: {account_query.get('name', 'saved')}",
                    action="load_customer_by_query",
                    params={
                        k: v
                        for k, v in {
                            "soql_text": soql_text,
                            "account_group": hints.get("account_group"),
                            "distribution_channel": hints.get("distribution_channel"),
                            "sales_office": hints.get("sales_office"),
                        }.items()
                        if v
                    },
                )
            )
        else:
            result.append(step)
    return result


def is_explicit_customer(value: str | None) -> bool:
    """True when the plan names a specific customer (not __first__ / __any__)."""
    if not value or not str(value).strip():
        return False
    if str(value).strip().lower() == "__first__":
        return False
    return not is_auto_pick(value)


def is_explicit_office(value: str | None) -> bool:
    return bool(value) and not is_auto_pick(value)


def should_pair_sales_office(steps: list[PlannedStep]) -> bool:
    """Sales office is chosen first only when the plan specifies both office and customer."""
    select_step = next((s for s in steps if s.action == "select_sales_office"), None)
    load_step = next(
        (s for s in steps if s.action in ("load_customer", "load_customer_by_query")),
        None,
    )
    if not select_step or not load_step:
        return False
    plan_office = select_step.params.get("office")
    plan_customer = load_step.params.get("customer_number") or load_step.params.get(
        "account_number"
    )
    return is_explicit_office(plan_office) and is_explicit_customer(plan_customer)


def patch_steps_with_resolved_account(
    steps: list[PlannedStep],
    resolved,
    *,
    soql_text: str,
) -> list[PlannedStep]:
    """Patch load_customer from a resolved row; pair sales office only when plan had both."""
    pair_office = should_pair_sales_office(steps)
    extra = resolved.to_step_params(soql_text, include_sales_office=pair_office)
    search = resolved.search_number()
    result: list[PlannedStep] = []
    for step in steps:
        if step.action == "select_sales_office":
            if not pair_office:
                continue
            if resolved.sales_office:
                params = {**step.params, "office": resolved.sales_office}
                result.append(step.model_copy(update={"params": params}))
            else:
                result.append(step)
        elif step.action == "load_customer_by_query":
            params = {**step.params, **extra}
            result.append(step.model_copy(update={"params": params}))
        elif step.action == "load_customer" and extra.get("soql_text"):
            params = {**step.params, **extra}
            if search and not params.get("customer_number"):
                params["customer_number"] = search
            result.append(
                step.model_copy(
                    update={
                        "action": "load_customer_by_query",
                        "params": params,
                    }
                )
            )
        else:
            result.append(step)
    return result


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
    customer_target = state.get("customer_target") or {}
    bottler_id = (
        customer_target.get("bottler")
        or (state.get("login_as_profile") or {}).get("bottler_id")
        or (state.get("login_as_target") or {}).get("bottler_id")
        or (state.get("org") or {}).get("bottler") if isinstance(state.get("org"), dict) else None
    )
    office = (
        customer_target.get("sales_office")
        or parse_sales_office(text)
        or AUTO_PICK
    )
    customer = customer_target.get("account_number") or parse_customer_number(text)
    account_group = customer_target.get("account_group")
    distribution_channel = customer_target.get("distribution_channel")
    account_name = customer_target.get("account_name")
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
            params={"office": office, "bottler_id": bottler_id},
        ),
        PlannedStep(
            seq=6,
            name="Load customer from search field",
            action="load_customer",
            params={
                k: v
                for k, v in {
                    "customer_number": customer,
                    "account_group": account_group,
                    "distribution_channel": distribution_channel,
                    "sales_office": office if office != AUTO_PICK else None,
                    "account_name": account_name,
                }.items()
                if v
            },
        ),
    ]
    next_seq = 7

    # Post-login org lands on Queues — skip App Launcher / Onboarding navigation (TC steps 2–5).
    return [
        PlannedStep(seq=1, name="Login to Salesforce", action="login", params={}),
        PlannedStep(
            seq=2,
            name="Open Customer Life Cycle | Queue",
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
            name="Navigate to Customer Details",
            action="open_customer_details",
            params={},
        ),
        PlannedStep(
            seq=next_seq + 1,
            name="Update Primary Group",
            action="modify_primary_group",
            params={"primary_group": primary_group},
        ),
        PlannedStep(seq=next_seq + 2, name="Click Submit", action="submit", params={}),
    ]


def enrich_steps_from_scenario(steps: list[PlannedStep], state: dict) -> list[PlannedStep]:
    text = scenario_text(state)
    if not text.strip():
        return steps

    create_params = parse_create_request_params(text)
    customer_number = parse_customer_number(text)
    primary_group = parse_primary_group(text)
    office = parse_sales_office(text)
    login_profile = state.get("login_as_profile") or {}
    login_target = state.get("login_as_target") or {}
    bottler_id = (
        (state.get("customer_target") or {}).get("bottler")
        or login_profile.get("bottler_id")
        or login_target.get("bottler_id")
    )

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
            if bottler_id:
                params.setdefault("bottler_id", str(bottler_id))
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
