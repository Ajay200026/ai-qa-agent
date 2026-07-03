"""Login As Profile library service (max 5 per project)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.login_as_profile import LoginAsProfile
from app.schemas.libraries import LoginAsProfileCreate, LoginAsProfileUpdate

MAX_PER_PROJECT = 5


class LoginAsProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_project(self, project_id: UUID) -> list[LoginAsProfile]:
        result = await self.db.execute(
            select(LoginAsProfile)
            .where(LoginAsProfile.project_id == project_id)
            .order_by(LoginAsProfile.sort_order, LoginAsProfile.created_at)
        )
        return list(result.scalars().all())

    async def get(self, profile_id: UUID) -> LoginAsProfile:
        row = await self.db.get(LoginAsProfile, profile_id)
        if not row:
            raise NotFoundError("LoginAsProfile", profile_id)
        return row

    async def create(self, data: LoginAsProfileCreate) -> LoginAsProfile:
        count = await self._count(data.project_id)
        if count >= MAX_PER_PROJECT:
            raise BadRequestError(
                f"Maximum {MAX_PER_PROJECT} login-as profiles per project"
            )
        row = LoginAsProfile(
            project_id=data.project_id,
            name=data.name.strip(),
            bottler_id=data.bottler_id.strip(),
            onboarding_role=data.onboarding_role.strip(),
            match_hints=data.match_hints.model_dump(mode="json") if data.match_hints else None,
            enabled=data.enabled,
            sort_order=data.sort_order,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def update(self, profile_id: UUID, data: LoginAsProfileUpdate) -> LoginAsProfile:
        row = await self.get(profile_id)
        payload = data.model_dump(exclude_unset=True)
        if "match_hints" in payload:
            mh = data.match_hints
            payload["match_hints"] = mh.model_dump(mode="json") if mh else None
        for key, value in payload.items():
            setattr(row, key, value)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete(self, profile_id: UUID) -> None:
        row = await self.get(profile_id)
        await self.db.delete(row)

    async def _count(self, project_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(LoginAsProfile)
            .where(LoginAsProfile.project_id == project_id)
        )
        return int(result.scalar_one())
