"""Deterministic identity discovery from test pack content (no LLM)."""

from __future__ import annotations

from app.schemas.login_as import IdentityPreviewItem, IdentityPreviewResponse
from app.workflows.test_table_parser import parse_test_pack


def preview_identities_from_content(content: str) -> IdentityPreviewResponse:
    pack = parse_test_pack(content or "")
    grouped: dict[tuple[str | None, str | None], list[str]] = {}

    for tc in pack.test_cases:
        bottler = (tc.bottler or pack.bottler or "").strip() or None
        role = (tc.role or "").strip() or None
        key = (bottler, role)
        grouped.setdefault(key, []).append(tc.tc_id)

    identities = [
        IdentityPreviewItem(bottler=bottler, role=role, tc_ids=sorted(tc_ids))
        for (bottler, role), tc_ids in sorted(
            grouped.items(),
            key=lambda item: (item[0][0] or "", item[0][1] or ""),
        )
    ]

    return IdentityPreviewResponse(
        identities=identities,
        pack_bottler=pack.bottler,
    )
