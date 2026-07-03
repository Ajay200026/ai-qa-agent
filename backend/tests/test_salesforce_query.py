"""SOQL allow-list validation tests."""

import pytest

from app.services.salesforce_query import SoqlValidationError, validate_soql


def test_empty_query_rejected():
    with pytest.raises(SoqlValidationError):
        validate_soql("", limit=5)


def test_non_select_rejected():
    with pytest.raises(SoqlValidationError):
        validate_soql("UPDATE Account SET Name='x'", limit=5)


def test_semicolon_rejected():
    with pytest.raises(SoqlValidationError):
        validate_soql("SELECT Id FROM Account; DROP TABLE foo", limit=5)


def test_disallowed_object_rejected():
    with pytest.raises(SoqlValidationError):
        validate_soql("SELECT Id FROM Opportunity", limit=5)


def test_limit_too_large_rejected():
    with pytest.raises(SoqlValidationError):
        validate_soql("SELECT Id FROM Account LIMIT 100", limit=5)


def test_default_limit_appended():
    cleaned, obj = validate_soql("SELECT Id FROM Account", limit=5)
    assert obj == "Account"
    assert "LIMIT 5" in cleaned


def test_user_object_allowed():
    cleaned, obj = validate_soql(
        "SELECT Id, Username FROM User WHERE cfs_ob__Bottler__c = '5000' LIMIT 1",
        limit=1,
    )
    assert obj == "User"
    assert "FROM User" in cleaned


def test_passthrough_when_limit_present():
    cleaned, _ = validate_soql("SELECT Id FROM Account LIMIT 20", limit=5)
    assert "LIMIT 20" in cleaned


def test_api_password_appends_security_token():
    from app.services.salesforce_query import _api_password

    assert _api_password({"password": "secret", "security_token": "ABC123"}) == "secretABC123"
    assert _api_password({"password": "secretABC123", "security_token": "ABC123"}) == "secretABC123"
    assert _api_password({"password": "secret"}) == "secret"
