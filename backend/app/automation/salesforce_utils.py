import re


def normalize_app_name(raw: str | None) -> str:
    """Map LLM/UI labels like 'App Launcher (waffle icon)' to the real app name."""
    if not raw:
        return "Onboarding"
    cleaned = raw.strip()
    lower = cleaned.lower()
    if "onboarding" in lower:
        return "Onboarding"
    if "waffle" in lower or "app launcher" in lower or "launcher" in lower:
        return "Onboarding"
    return cleaned


def step_also_opens_onboarding(description: str | None, target: str | None) -> bool:
    """Detect when the LLM merged 'open launcher + open onboarding' into one step."""
    text = f"{description or ''} {target or ''}".lower()
    return "onboarding" in text and any(k in text for k in ("launcher", "navigate", "waffle"))


def normalize_tab_name(raw: str | None) -> str:
    if not raw:
        return "Customer_Life_Cycle_Queues"
    lower = raw.lower().replace(" ", "_")
    if "queue" in lower or "customer" in lower and "lifecycle" in lower:
        return "Customer_Life_Cycle_Queues"
    return raw.strip()
