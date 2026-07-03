"""Salesforce org service tests."""

import pytest

from app.services.salesforce_service import resolve_login_url, resolve_org_type_from_instance


def test_resolve_login_url_production():
    assert resolve_login_url("production") == "https://login.salesforce.com"


def test_resolve_login_url_sandbox():
    assert resolve_login_url("sandbox") == "https://test.salesforce.com"


def test_resolve_login_url_custom_requires_url():
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        resolve_login_url("custom", None)

    assert (
        resolve_login_url("custom", "https://mydomain.my.salesforce.com")
        == "https://mydomain.my.salesforce.com"
    )


def test_resolve_org_type_scratch_from_instance():
    assert (
        resolve_org_type_from_instance(
            "https://paas-coldbrew-8678.scratch.my.salesforce.com",
            "sandbox",
        )
        == "scratch"
    )
    assert resolve_org_type_from_instance("https://mycompany.my.salesforce.com", "sandbox") == "sandbox"
