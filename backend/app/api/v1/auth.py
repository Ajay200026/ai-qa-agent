from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: UserRegister, db: DbSession):
    service = AuthService(db)
    try:
        user = await service.register(data)
        return user
    except AppException as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: DbSession):
    service = AuthService(db)
    try:
        _, token = await service.login(data)
        return TokenResponse(access_token=token)
    except AppException as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser):
    return current_user
