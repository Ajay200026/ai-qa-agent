"""Recommendation service tests."""

from types import SimpleNamespace
from uuid import uuid4

from app.services.recommendation_service import (
    rank_account_queries,
    rank_login_as_profiles,
    resolve_profile_dict_for_tc,
)


def _query(name: str, bottler: str | None = None):
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        match_hints={"bottler": bottler} if bottler else None,
    )


def _profile(name: str, role: str, bottler: str):
    return {
        "id": str(uuid4()),
        "name": name,
        "bottler_id": bottler,
        "onboarding_role": role,
        "enabled": True,
        "match_hints": {"role": role, "bottler": bottler},
    }


SAMPLE_PACK = """
US-21153 Tests
Bottler: 5000
TC-01 — Requestor test
Role: Requestor
| Step | Action |
| 1 | Login |

TC-02 — Finance test
Role: Finance
| Step | Action |
| 1 | Login |
"""


def test_rank_account_queries_by_bottler():
    queries = [_query("Default"), _query("5000 Accounts", "5000")]
    result = rank_account_queries(queries, SAMPLE_PACK)
    assert result.recommended is not None
    assert result.recommended.name == "5000 Accounts"


def test_rank_login_as_profiles():
    profiles = [
        SimpleNamespace(
            id=uuid4(),
            name="Finance",
            bottler_id="5000",
            onboarding_role="Finance",
            enabled=True,
            match_hints={"role": "Finance"},
        ),
        SimpleNamespace(
            id=uuid4(),
            name="Requestor",
            bottler_id="5000",
            onboarding_role="Requestor",
            enabled=True,
            match_hints={"role": "Requestor"},
        ),
    ]
    result = rank_login_as_profiles(profiles, SAMPLE_PACK)
    assert result.recommended is not None


def test_resolve_profile_dict_for_tc():
    profiles = [_profile("Finance", "Finance", "5000"), _profile("Requestor", "Requestor", "5000")]
    picked = resolve_profile_dict_for_tc(
        profiles,
        tc_bottler="5000",
        tc_role="Finance",
        default_profile=None,
    )
    assert picked is not None
    assert picked["onboarding_role"] == "Finance"
