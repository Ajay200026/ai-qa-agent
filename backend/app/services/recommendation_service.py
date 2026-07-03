"""Deterministic recommendation of library entries from test pack content."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_query import AccountQuery
from app.models.login_as_profile import LoginAsProfile
from app.schemas.libraries import RecommendationItem, RecommendResponse
from app.services.account_query_service import AccountQueryService
from app.services.login_as_profile_service import LoginAsProfileService
from app.workflows.test_table_parser import parse_test_pack


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _score_hints(
    hints: dict | None,
    *,
    bottler: str | None,
    role: str | None,
    account_group: str | None = None,
    distribution_channel: str | None = None,
    text_blob: str = "",
) -> tuple[int, str]:
    if not hints:
        return 0, ""
    score = 0
    reasons: list[str] = []
    hb = hints.get("bottler")
    if hb and bottler and _norm(hb) == _norm(bottler):
        score += 3
        reasons.append(f"bottler={bottler}")
    hr = hints.get("role")
    if hr and role and _norm(hr) == _norm(role):
        score += 3
        reasons.append(f"role={role}")
    hag = hints.get("account_group")
    if hag and account_group and _norm(hag) == _norm(account_group):
        score += 2
        reasons.append(f"account_group={account_group}")
    hdc = hints.get("distribution_channel")
    if hdc and distribution_channel and _norm(hdc) == _norm(distribution_channel):
        score += 2
        reasons.append(f"distribution_channel={distribution_channel}")
    for tag in hints.get("tags") or []:
        if tag and _norm(tag) in _norm(text_blob):
            score += 1
            reasons.append(f"tag={tag}")
    return score, ", ".join(reasons)


def _pack_context(content: str) -> dict:
    pack = parse_test_pack(content or "")
    roles = {_norm(tc.role) for tc in pack.test_cases if tc.role}
    bottlers = {_norm(tc.bottler or pack.bottler) for tc in pack.test_cases}
    bottlers.discard("")
    roles.discard("")
    primary_role = next(iter(roles), None)
    primary_bottler = pack.bottler or (next(iter(bottlers), None))
    return {
        "pack": pack,
        "role": primary_role,
        "bottler": primary_bottler,
        "text_blob": content.lower(),
    }


def rank_account_queries(
    queries: list[AccountQuery], content: str
) -> RecommendResponse:
    ctx = _pack_context(content)
    scored: list[RecommendationItem] = []
    for q in queries:
        score, reason = _score_hints(
            q.match_hints,
            bottler=ctx["bottler"],
            role=None,
            text_blob=ctx["text_blob"],
        )
        if ctx["bottler"] and _norm(q.name) in ctx["text_blob"]:
            score += 1
        scored.append(
            RecommendationItem(id=q.id, name=q.name, score=score, reason=reason or None)
        )
    scored.sort(key=lambda x: (-x.score, x.name))
    recommended = scored[0] if scored and scored[0].score > 0 else (scored[0] if scored else None)
    alts = [s for s in scored[1:4] if s.id != (recommended.id if recommended else None)]
    return RecommendResponse(recommended=recommended, alternatives=alts)


def rank_login_as_profiles(
    profiles: list[LoginAsProfile], content: str
) -> RecommendResponse:
    ctx = _pack_context(content)
    scored: list[RecommendationItem] = []
    for p in profiles:
        if not p.enabled:
            continue
        score, reason = _score_hints(
            p.match_hints,
            bottler=ctx["bottler"] or p.bottler_id,
            role=ctx["role"],
            text_blob=ctx["text_blob"],
        )
        if ctx["role"] and _norm(p.onboarding_role) == ctx["role"]:
            score += 2
            reason = (reason + ", role match").strip(", ")
        if ctx["bottler"] and _norm(p.bottler_id) == _norm(ctx["bottler"]):
            score += 2
        scored.append(
            RecommendationItem(id=p.id, name=p.name, score=score, reason=reason or None)
        )
    scored.sort(key=lambda x: (-x.score, x.name))
    recommended = scored[0] if scored and scored[0].score > 0 else (scored[0] if scored else None)
    alts = [s for s in scored[1:4] if s.id != (recommended.id if recommended else None)]
    return RecommendResponse(recommended=recommended, alternatives=alts)


async def recommend_account_queries(
    db: AsyncSession, project_id: UUID, content: str
) -> RecommendResponse:
    queries = await AccountQueryService(db).list_by_project(project_id)
    return rank_account_queries(queries, content)


async def recommend_login_as_profiles(
    db: AsyncSession, project_id: UUID, content: str
) -> RecommendResponse:
    profiles = await LoginAsProfileService(db).list_by_project(project_id)
    return rank_login_as_profiles(profiles, content)


def resolve_profile_dict_for_tc(
    profiles: list[dict],
    *,
    tc_bottler: str | None,
    tc_role: str | None,
    default_profile: dict | None,
    pack_text: str = "",
) -> dict | None:
    """Pick best login-as profile dict for a test case."""
    enabled = [p for p in profiles if p.get("enabled", True)]
    if not enabled:
        return default_profile if default_profile and default_profile.get("enabled", True) else None

    best: dict | None = None
    best_score = -1
    for p in enabled:
        score, _ = _score_hints(
            p.get("match_hints"),
            bottler=tc_bottler or p.get("bottler_id"),
            role=tc_role,
            text_blob=pack_text,
        )
        if tc_role and _norm(p.get("onboarding_role")) == _norm(tc_role):
            score += 3
        if tc_bottler and _norm(p.get("bottler_id")) == _norm(tc_bottler):
            score += 3
        if score > best_score:
            best_score = score
            best = p

    if best_score > 0 and best:
        return best
    return default_profile if default_profile and default_profile.get("enabled", True) else None
