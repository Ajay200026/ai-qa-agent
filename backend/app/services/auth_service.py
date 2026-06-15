from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.firebase import verify_firebase_token
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserLogin, UserRegister


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def register(self, data: UserRegister) -> User:
        existing = await self.repo.get_by_email(data.email)
        if existing:
            raise ConflictError("Email already registered")
        hashed = get_password_hash(data.password)
        return await self.repo.create_user(data.email, hashed)

    async def login(self, data: UserLogin) -> tuple[User, str]:
        user = await self.repo.get_by_email(data.email)
        if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")
        token = create_access_token(str(user.id))
        return user, token

    async def get_or_create_firebase_user(self, id_token: str) -> User:
        try:
            decoded = verify_firebase_token(id_token)
        except Exception as exc:
            raise UnauthorizedError(f"Invalid Firebase token: {exc}") from exc

        firebase_uid = decoded.get("uid") or decoded.get("sub") or decoded.get("user_id")
        email = decoded.get("email")
        if not firebase_uid:
            raise UnauthorizedError("Firebase token missing user id")
        if not email:
            raise UnauthorizedError("Firebase token missing email — ensure Email/Password sign-in is enabled")

        user = await self.repo.get_by_firebase_uid(firebase_uid)
        if user:
            return user

        existing = await self.repo.get_by_email(email)
        if existing:
            return await self.repo.link_firebase_uid(existing, firebase_uid)

        return await self.repo.create_firebase_user(email, firebase_uid)

    async def get_user(self, user_id) -> User | None:
        return await self.repo.get_by_id(user_id)
