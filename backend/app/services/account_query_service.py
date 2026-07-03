"""Account Query library service (max 5 per project)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.account_query import AccountQuery
from app.schemas.libraries import AccountQueryCreate, AccountQueryUpdate

MAX_PER_PROJECT = 5


class AccountQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_project(self, project_id: UUID) -> list[AccountQuery]:
        result = await self.db.execute(
            select(AccountQuery)
            .where(AccountQuery.project_id == project_id)
            .order_by(AccountQuery.sort_order, AccountQuery.created_at)
        )
        return list(result.scalars().all())

    async def get(self, query_id: UUID) -> AccountQuery:
        row = await self.db.get(AccountQuery, query_id)
        if not row:
            raise NotFoundError("AccountQuery", query_id)
        return row

    async def create(self, data: AccountQueryCreate) -> AccountQuery:
        count = await self._count(data.project_id)
        if count >= MAX_PER_PROJECT:
            raise BadRequestError(
                f"Maximum {MAX_PER_PROJECT} account queries per project"
            )
        row = AccountQuery(
            project_id=data.project_id,
            name=data.name.strip(),
            soql_text=data.soql_text.strip(),
            match_hints=data.match_hints.model_dump(mode="json") if data.match_hints else None,
            sort_order=data.sort_order,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def update(self, query_id: UUID, data: AccountQueryUpdate) -> AccountQuery:
        row = await self.get(query_id)
        payload = data.model_dump(exclude_unset=True)
        if "match_hints" in payload:
            mh = data.match_hints
            payload["match_hints"] = mh.model_dump(mode="json") if mh else None
        for key, value in payload.items():
            setattr(row, key, value)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete(self, query_id: UUID) -> None:
        row = await self.get(query_id)
        await self.db.delete(row)

    async def _count(self, project_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(AccountQuery)
            .where(AccountQuery.project_id == project_id)
        )
        return int(result.scalar_one())
