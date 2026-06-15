"""Request type options shown in the New (+) menu on Customer Life Cycle Queues."""

REQUEST_MODULE_OPTIONS: tuple[str, ...] = (
    "NEW DSD CUSTOMER",
    "NEW FSV CUSTOMER",
    "CUSTOMER SUPPRESSION",
    "CUSTOMER UNSUPPRESSION",
    "EMPLOYEE REASSIGNMENT",
    "NEW CLASSIC FOODS",
    "EQUIPMENT CHANGE REQUEST",
    "NEW MICRO MARKET",
    "NEW DATA CHANGE",
    "NEW PAYER",
    "FULL ROUTE SWAP",
    "MASS REQUEST",
    "NEW DRIVER REQUEST",
    "NEW EMPLOYEE REASSIGNMENT",
)

# Friendly / scenario text → exact menu label
MODULE_ALIASES: dict[str, str] = {
    "data change": "NEW DATA CHANGE",
    "data change module": "NEW DATA CHANGE",
    "data change request": "NEW DATA CHANGE",
    "new data change": "NEW DATA CHANGE",
    "dsd customer": "NEW DSD CUSTOMER",
    "new dsd customer": "NEW DSD CUSTOMER",
    "fsv customer": "NEW FSV CUSTOMER",
    "new fsv customer": "NEW FSV CUSTOMER",
    "customer suppression": "CUSTOMER SUPPRESSION",
    "customer unsuppression": "CUSTOMER UNSUPPRESSION",
    "employee reassignment": "EMPLOYEE REASSIGNMENT",
    "new classic foods": "NEW CLASSIC FOODS",
    "equipment change": "EQUIPMENT CHANGE REQUEST",
    "equipment change request": "EQUIPMENT CHANGE REQUEST",
    "new micro market": "NEW MICRO MARKET",
    "new payer": "NEW PAYER",
    "full route swap": "FULL ROUTE SWAP",
    "mass request": "MASS REQUEST",
    "new driver request": "NEW DRIVER REQUEST",
    "new employee reassignment": "NEW EMPLOYEE REASSIGNMENT",
}


def normalize_request_module(raw: str | None, default: str = "NEW DATA CHANGE") -> str:
    if not raw:
        return default
    cleaned = raw.strip()
    upper = cleaned.upper()

    if upper in REQUEST_MODULE_OPTIONS:
        return upper

    lower = cleaned.lower()
    if lower in MODULE_ALIASES:
        return MODULE_ALIASES[lower]

    for alias, label in MODULE_ALIASES.items():
        if alias in lower:
            return label

    for option in REQUEST_MODULE_OPTIONS:
        if option.lower() in lower or lower in option.lower():
            return option

    return default
