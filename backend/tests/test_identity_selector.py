"""Identity selector resolution tests."""

from app.schemas.login_as import IdentityMap, IdentityMapEntry, LoginAsTarget
from app.services.identity_selector import resolve_identity


def test_explicit_override_wins():
    imap = IdentityMap(
        entries=[
            IdentityMapEntry(
                bottler="5000",
                role="Requestor",
                override_bottler="5001",
                override_role="Finance",
            )
        ]
    )
    target = resolve_identity(
        tc_bottler="5000",
        tc_role="Requestor",
        identity_map=imap,
        default=None,
    )
    assert target is not None
    assert target.bottler_id == "5001"
    assert target.onboarding_role == "Finance"


def test_raw_tc_values_when_no_map_entry():
    target = resolve_identity(
        tc_bottler="5000",
        tc_role="GM",
        identity_map=None,
        default=None,
    )
    assert target == LoginAsTarget(bottler_id="5000", onboarding_role="GM", enabled=True)


def test_scenario_default_when_tc_missing_role():
    default = LoginAsTarget(
        bottler_id="5000", onboarding_role="Requestor", enabled=True
    )
    target = resolve_identity(
        tc_bottler=None,
        tc_role=None,
        identity_map=None,
        default=default,
    )
    assert target == default


def test_disabled_entry_returns_none():
    imap = IdentityMap(
        entries=[
            IdentityMapEntry(bottler="5000", role="Requestor", enabled=False)
        ]
    )
    assert (
        resolve_identity(
            tc_bottler="5000",
            tc_role="Requestor",
            identity_map=imap,
            default=LoginAsTarget(
                bottler_id="5000", onboarding_role="Requestor", enabled=True
            ),
        )
        is None
    )


def test_case_insensitive_map_match():
    imap = IdentityMap(
        entries=[
            IdentityMapEntry(
                bottler="5000",
                role="requestor",
                override_role="Finance",
            )
        ]
    )
    target = resolve_identity(
        tc_bottler="5000",
        tc_role="REQUESTOR",
        identity_map=imap,
        default=None,
    )
    assert target is not None
    assert target.onboarding_role == "Finance"
