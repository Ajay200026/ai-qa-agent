"""LoginResolver unit tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.login_as import SoqlUserRow
from app.services.login_resolver import (
    LoginResolver,
    LoginResolverError,
    LoginResolverNoUserError,
    build_user_lookup_soql,
)
from app.services.salesforce_query import SoqlAuthError, SoqlExecutionError


def _org():
    return SimpleNamespace(
        id=uuid4(),
        login_url="https://test.salesforce.com",
        auth_method="credentials",
        instance_url="https://example.my.salesforce.com",
    )


def _page():
    mock = MagicMock()
    mock.url = "https://example.lightning.force.com/lightning/page/home"
    mock.context.service_workers = []
    mock.context.new_page = AsyncMock()
    return mock


def test_build_user_lookup_soql_escapes_quotes_and_filters_active():
    soql = build_user_lookup_soql("5000", "Requestor")
    assert "FROM User" in soql
    assert "IsActive = true" in soql
    assert "cfs_ob__Bottler__c = '5000'" in soql
    assert "cfs_ob__Onboarding_Role__c = 'Requestor'" in soql


def test_soql_auth_failure_raises():
    resolver = LoginResolver(_page(), _org(), {"username": "a", "password": "b"}, execution_id=uuid4())
    client = MagicMock()
    client.query_users = AsyncMock(side_effect=SoqlAuthError("bad creds"))

    with patch("app.services.login_resolver.SoqlClient", return_value=client):
        with pytest.raises(LoginResolverError) as exc:
            asyncio.run(resolver.login_as("5000", "Requestor"))
    assert "authentication" in str(exc.value).lower()


def test_empty_user_id_raises_no_user():
    resolver = LoginResolver(_page(), _org(), {}, execution_id=uuid4())
    client = MagicMock()
    client.query_users = AsyncMock(return_value=[SoqlUserRow(user_id="", name="Ghost")])

    with patch("app.services.login_resolver.SoqlClient", return_value=client):
        with pytest.raises(LoginResolverNoUserError):
            asyncio.run(resolver.login_as("5000", "Requestor"))


def test_resolves_and_impersonates_via_rest_soql():
    resolver = LoginResolver(_page(), _org(), {}, execution_id=uuid4())
    client = MagicMock()
    client.query_users = AsyncMock(
        return_value=[
            SoqlUserRow(
                user_id="005xx000001",
                name="Test User",
                username="test@example.com",
                bottler="5000",
                role="Requestor",
            )
        ]
    )

    with patch("app.services.login_resolver.SoqlClient", return_value=client):
        with patch.object(
            LoginResolver, "_open_user_record", new_callable=AsyncMock
        ) as open_mock:
            with patch.object(
                LoginResolver, "_click_login_button", new_callable=AsyncMock
            ) as login_mock:
                with patch.object(
                    LoginResolver, "_wait_for_impersonation_ready", new_callable=AsyncMock
                ):
                    result = asyncio.run(resolver.login_as("5000", "Requestor"))

    assert result.success is True
    assert result.user_id == "005xx000001"
    open_mock.assert_awaited_once()
    assert open_mock.await_args.args[0].user_id == "005xx000001"
    login_mock.assert_awaited_once()


def test_soql_execution_failure_raises():
    resolver = LoginResolver(_page(), _org(), {}, execution_id=uuid4())
    client = MagicMock()
    client.query_users = AsyncMock(side_effect=SoqlExecutionError("invalid field"))

    with patch("app.services.login_resolver.SoqlClient", return_value=client):
        with pytest.raises(LoginResolverError) as exc:
            asyncio.run(resolver.login_as("5000", "Requestor"))
    assert "SOQL" in str(exc.value)


def test_cache_skips_second_lookup():
    execution_id = uuid4()
    resolver = LoginResolver(_page(), _org(), {}, execution_id=execution_id)

    with patch.object(resolver, "_resolve_user", new_callable=AsyncMock) as resolve_mock:
        from app.schemas.login_as import ResolvedUser

        resolve_mock.return_value = ResolvedUser(
            user_id="005xx",
            name="Cached",
            bottler="5000",
            role="Requestor",
        )
        resolver._open_user_record = AsyncMock()
        resolver._click_login_button = AsyncMock()
        resolver._wait_for_impersonation_ready = AsyncMock()
        resolver._verify_impersonation_active = AsyncMock(return_value=True)

        asyncio.run(resolver.login_as("5000", "Requestor"))
        asyncio.run(resolver.login_as("5000", "Requestor"))

        resolve_mock.assert_awaited_once()


def test_cache_reimpersonates_when_banner_missing():
    execution_id = uuid4()
    resolver = LoginResolver(_page(), _org(), {}, execution_id=execution_id)

    with patch.object(resolver, "_resolve_user", new_callable=AsyncMock) as resolve_mock:
        from app.schemas.login_as import ResolvedUser

        resolve_mock.return_value = ResolvedUser(
            user_id="005xx",
            name="NE Requestor",
            username="requestor5000@generic.com",
            bottler="5000",
            role="Requestor",
        )
        resolver._open_user_record = AsyncMock()
        resolver._click_login_button = AsyncMock()
        resolver._wait_for_impersonation_ready = AsyncMock()
        verify = AsyncMock(side_effect=[False])
        resolver._verify_impersonation_active = verify

        asyncio.run(resolver.login_as("5000", "Requestor"))
        asyncio.run(resolver.login_as("5000", "Requestor"))

        assert resolve_mock.await_count == 2
