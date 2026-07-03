"""LLM privacy guard tests."""

from app.core.privacy import is_sensitive_scenario, redact_state, redact_text


def test_is_sensitive_when_customer_target_set():
    assert is_sensitive_scenario({"customer_target": {"account_number": "0605467903"}})
    assert is_sensitive_scenario({"inputs": {"CustomerNumber": "0605467903"}})
    assert not is_sensitive_scenario({"inputs": {"Other": "x"}})
    assert not is_sensitive_scenario({})


def test_is_sensitive_when_account_query_set():
    assert is_sensitive_scenario({"account_query": {"soql_text": "SELECT Id FROM Account"}})
    assert is_sensitive_scenario({"account_query_id": "00000000-0000-0000-0000-000000000001"})
    assert is_sensitive_scenario({"login_as_profile": {"bottler_id": "5000"}})


def test_is_sensitive_when_login_as_configured():
    assert is_sensitive_scenario({"login_as_target": {"bottler_id": "5000", "onboarding_role": "Requestor"}})
    assert is_sensitive_scenario({"identity_map": {"entries": [{"bottler": "5000", "role": "Requestor"}]}})


def test_redact_state_strips_customer_target_and_numbers():
    state = {
        "customer_target": {"account_number": "0605467903", "account_name": "ACME"},
        "inputs": {"CustomerNumber": "0605467903", "Other": "ok"},
        "scenario_description": "Run for customer 0605467903 in K045",
        "_private": {"soql_rows": [{"AccountNumber": "0605467903"}]},
    }
    safe = redact_state(state)
    assert safe["customer_target"] == "<REDACTED>"
    assert safe["inputs"]["CustomerNumber"] == "<REDACTED>"
    assert safe["inputs"]["Other"] == "ok"
    assert "0605467903" not in safe["scenario_description"]
    assert "<REDACTED>" in safe["scenario_description"]
    assert safe["_private"] == "<REDACTED>"


def test_redact_text_replaces_numbers():
    text = "Pick account 0605467903 today"
    out = redact_text(text, {"customer_target": {"account_number": "0605467903"}})
    assert "0605467903" not in out
    assert "<REDACTED>" in out
