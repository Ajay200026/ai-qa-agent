from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_firebase_uid(self, firebase_uid: str) -> User | None:
        result = await self.db.execute(select(User).where(User.firebase_uid == firebase_uid))
        return result.scalar_one_or_none()

    async def create_user(self, email: str, hashed_password: str, role: str = "developer") -> User:
        user = User(email=email, hashed_password=hashed_password, role=role)
        return await self.create(user)

    async def create_firebase_user(self, email: str, firebase_uid: str, role: str = "developer") -> User:
        user = User(email=email, firebase_uid=firebase_uid, hashed_password=None, role=role)
        return await self.create(user)

    async def link_firebase_uid(self, user: User, firebase_uid: str) -> User:
        user.firebase_uid = firebase_uid
        await self.db.flush()
        await self.db.refresh(user)
        return user
