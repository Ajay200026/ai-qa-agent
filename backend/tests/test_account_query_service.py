"""Account query library service tests."""

import asyncio
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError
from app.schemas.libraries import AccountQueryCreate
from app.services.account_query_service import AccountQueryService, MAX_PER_PROJECT


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


def test_max_five_enforced():
    db = FakeDB(count=MAX_PER_PROJECT)
    service = AccountQueryService(db)
    data = AccountQueryCreate(
        project_id=uuid4(),
        name="Test",
        soql_text="SELECT Id FROM Account LIMIT 1",
    )
    with pytest.raises(BadRequestError):
        asyncio.run(service.create(data))


def test_create_under_limit():
    db = FakeDB(count=2)
    service = AccountQueryService(db)
    data = AccountQueryCreate(
        project_id=uuid4(),
        name="AR Payer",
        soql_text="SELECT Id, AccountNumber FROM Account LIMIT 5",
    )
    row = asyncio.run(service.create(data))
    assert row.name == "AR Payer"
    assert len(db.added) == 1
