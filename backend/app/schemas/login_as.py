"""Schemas for Login Resolver / impersonation flows.

All payloads here are sensitive (carry usernames / SF user IDs). The privacy
guard treats their presence as a signal to bypass the LLM.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _key(bottler: str | None, role: str | None) -> str:
    return f"{(_norm(bottler) or '').lower()}|{(_norm(role) or '').lower()}"


class LoginAsTarget(BaseModel):
    """Identity to impersonate after the admin login."""

    bottler_id: str = Field(min_length=1)
    onboarding_role: str = Field(min_length=1)
    enabled: bool = True

    model_config = {"extra": "ignore"}

    def normalized(self) -> "LoginAsTarget":
        return LoginAsTarget(
            bottler_id=(_norm(self.bottler_id) or ""),
            onboarding_role=(_norm(self.onboarding_role) or ""),
            enabled=self.enabled,
        )

    def cache_key(self) -> str:
        return _key(self.bottler_id, self.onboarding_role)


class IdentityMapEntry(BaseModel):
    """User-defined override for a (bottler, role) pair detected in a test pack."""

    bottler: str = Field(min_length=1)
    role: str = Field(min_length=1)
    override_bottler: str | None = None
    override_role: str | None = None
    enabled: bool = True

    model_config = {"extra": "ignore"}

    def matches(self, bottler: str | None, role: str | None) -> bool:
        return _key(self.bottler, self.role) == _key(bottler, role)

    def effective(self) -> tuple[str, str]:
        return (
            _norm(self.override_bottler) or self.bottler,
            _norm(self.override_role) or self.role,
        )


class IdentityMap(BaseModel):
    entries: list[IdentityMapEntry] = Field(default_factory=list)

    model_config = {"extra": "ignore"}

    def find(self, bottler: str | None, role: str | None) -> IdentityMapEntry | None:
        for entry in self.entries:
            if entry.matches(bottler, role):
                return entry
        return None


class ResolvedUser(BaseModel):
    user_id: str
    name: str | None = None
    username: str | None = None
    bottler: str | None = None
    role: str | None = None


class ImpersonationResult(ResolvedUser):
    success: bool = True


class SoqlUserRow(BaseModel):
    user_id: str
    name: str | None = None
    username: str | None = None
    bottler: str | None = None
    role: str | None = None
    raw: dict = Field(default_factory=dict)


class IdentityPreviewRequest(BaseModel):
    test_pack_content: str = Field(min_length=1)


class IdentityPreviewItem(BaseModel):
    bottler: str | None = None
    role: str | None = None
    tc_ids: list[str] = Field(default_factory=list)


class IdentityPreviewResponse(BaseModel):
    identities: list[IdentityPreviewItem] = Field(default_factory=list)
    pack_bottler: str | None = None
