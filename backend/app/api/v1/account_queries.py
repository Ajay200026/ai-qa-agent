from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.schemas.libraries import (
    AccountQueryCreate,
    AccountQueryResponse,
    AccountQueryUpdate,
    RecommendRequest,
    RecommendResponse,
)
from app.services.account_query_service import AccountQueryService
from app.services.recommendation_service import recommend_account_queries

router = APIRouter()


@router.get("", response_model=list[AccountQueryResponse])
async def list_account_queries(
    project_id: UUID, db: DbSession, current_user: CurrentUser
):
    service = AccountQueryService(db)
    return await service.list_by_project(project_id)


@router.post("", response_model=AccountQueryResponse, status_code=201)
async def create_account_query(
    data: AccountQueryCreate, db: DbSession, current_user: CurrentUser
):
    service = AccountQueryService(db)
    try:
        row = await service.create(data)
        await db.commit()
        return row
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/{query_id}", response_model=AccountQueryResponse)
async def update_account_query(
    query_id: UUID,
    data: AccountQueryUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    service = AccountQueryService(db)
    try:
        row = await service.update(query_id, data)
        await db.commit()
        return row
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/{query_id}", status_code=204)
async def delete_account_query(
    query_id: UUID, db: DbSession, current_user: CurrentUser
):
    service = AccountQueryService(db)
    try:
        await service.delete(query_id)
        await db.commit()
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/recommend", response_model=RecommendResponse)
async def recommend_account_query(
    payload: RecommendRequest, db: DbSession, current_user: CurrentUser
):
    return await recommend_account_queries(
        db, payload.project_id, payload.test_pack_content
    )
