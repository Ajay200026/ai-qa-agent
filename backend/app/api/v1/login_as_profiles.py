from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.schemas.libraries import (
    LoginAsProfileCreate,
    LoginAsProfileResponse,
    LoginAsProfileUpdate,
    RecommendRequest,
    RecommendResponse,
)
from app.services.login_as_profile_service import LoginAsProfileService
from app.services.recommendation_service import recommend_login_as_profiles

router = APIRouter()


@router.get("", response_model=list[LoginAsProfileResponse])
async def list_login_as_profiles(
    project_id: UUID, db: DbSession, current_user: CurrentUser
):
    service = LoginAsProfileService(db)
    return await service.list_by_project(project_id)


@router.post("", response_model=LoginAsProfileResponse, status_code=201)
async def create_login_as_profile(
    data: LoginAsProfileCreate, db: DbSession, current_user: CurrentUser
):
    service = LoginAsProfileService(db)
    try:
        row = await service.create(data)
        await db.commit()
        return row
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/{profile_id}", response_model=LoginAsProfileResponse)
async def update_login_as_profile(
    profile_id: UUID,
    data: LoginAsProfileUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    service = LoginAsProfileService(db)
    try:
        row = await service.update(profile_id, data)
        await db.commit()
        return row
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/{profile_id}", status_code=204)
async def delete_login_as_profile(
    profile_id: UUID, db: DbSession, current_user: CurrentUser
):
    service = LoginAsProfileService(db)
    try:
        await service.delete(profile_id)
        await db.commit()
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/recommend", response_model=RecommendResponse)
async def recommend_login_as_profile(
    payload: RecommendRequest, db: DbSession, current_user: CurrentUser
):
    return await recommend_login_as_profiles(
        db, payload.project_id, payload.test_pack_content
    )
