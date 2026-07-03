"""Login-as profile library service tests."""

import asyncio
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError
from app.schemas.libraries import LoginAsProfileCreate
from app.services.login_as_profile_service import LoginAsProfileService, MAX_PER_PROJECT


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class FakeDB:
    def __init__(self, count=0):
        self.count = count
        self.added = []

    async def execute(self, stmt):
        return FakeResult(self.count)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def refresh(self, obj):
        obj.id = uuid4()


def test_max_five_profiles():
    db = FakeDB(count=MAX_PER_PROJECT)
    service = LoginAsProfileService(db)
    data = LoginAsProfileCreate(
        project_id=uuid4(),
        name="Requestor",
        bottler_id="5000",
        onboarding_role="Requestor",
    )
    with pytest.raises(BadRequestError):
        asyncio.run(service.create(data))
