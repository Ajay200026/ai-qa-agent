"""User detail page URL helpers for Login As."""

from app.automation.pages.user_detail_page import (
    build_classic_user_detail_url,
    build_manage_users_url,
    is_lightning_user_record_url,
    lightning_base_url,
    pick_global_search_terms,
)


def test_lightning_base_url_scratch_org():
    assert (
        lightning_base_url("https://paas-coldbrew-8678.scratch.my.salesforce.com")
        == "https://paas-coldbrew-8678.scratch.lightning.force.com"
    )


def test_build_manage_users_url():
    url = build_manage_users_url(
        "https://paas-coldbrew-8678.scratch.my.salesforce.com",
        "005HF0000051bzQYAQ",
    )
    assert url.endswith("/lightning/setup/ManageUsers/page?address=/005HF0000051bzQYAQ")


def test_build_classic_user_detail_url():
    url = build_classic_user_detail_url(
        "https://paas-coldbrew-8678.scratch.my.salesforce.com",
        "005HF0000051bzQYAQ",
    )
    assert (
        url
        == "https://paas-coldbrew-8678.scratch.my.salesforce.com/005HF0000051bzQYAQ?noredirect=1&isUserEntityOverride=1"
    )


def test_is_lightning_user_record_url():
    assert is_lightning_user_record_url(
        "https://paas-coldbrew-8678.scratch.lightning.force.com/lightning/r/User/005HF0000051bzQYAQ/view"
    )
    assert not is_lightning_user_record_url(
        "https://example.lightning.force.com/lightning/setup/ManageUsers/page?address=/005"
    )


def test_pick_global_search_terms_prefers_display_name():
    assert pick_global_search_terms("NE Requestor", "shivakb@coreflexsolutions.com") == [
        "NE Requestor",
        "shivakb@coreflexsolutions.com",
    ]
    assert pick_global_search_terms(None, "user@example.com") == ["user@example.com"]
