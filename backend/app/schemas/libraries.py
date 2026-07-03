"""Pydantic schemas for Account Query and Login As Profile libraries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MatchHints(BaseModel):
    bottler: str | None = None
    account_group: str | None = None
    distribution_channel: str | None = None
    role: str | None = None
    tags: list[str] = Field(default_factory=list)
    next_account_index: int = 0

    model_config = {"extra": "ignore"}


class AccountQueryCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    soql_text: str = Field(min_length=1)
    match_hints: MatchHints | None = None
    sort_order: int = 0


class AccountQueryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    soql_text: str | None = Field(default=None, min_length=1)
    match_hints: MatchHints | None = None
    sort_order: int | None = None


class AccountQueryResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    soql_text: str
    match_hints: MatchHints | None = None
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginAsProfileCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    bottler_id: str = Field(min_length=1, max_length=32)
    onboarding_role: str = Field(min_length=1, max_length=128)
    match_hints: MatchHints | None = None
    enabled: bool = True
    sort_order: int = 0


class LoginAsProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    bottler_id: str | None = Field(default=None, min_length=1, max_length=32)
    onboarding_role: str | None = Field(default=None, min_length=1, max_length=128)
    match_hints: MatchHints | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class LoginAsProfileResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    bottler_id: str
    onboarding_role: str
    match_hints: MatchHints | None = None
    enabled: bool
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendRequest(BaseModel):
    test_pack_content: str = ""
    project_id: UUID


class RecommendationItem(BaseModel):
    id: UUID
    name: str
    score: int = 0
    reason: str | None = None


class RecommendResponse(BaseModel):
    recommended: RecommendationItem | None = None
    alternatives: list[RecommendationItem] = Field(default_factory=list)
