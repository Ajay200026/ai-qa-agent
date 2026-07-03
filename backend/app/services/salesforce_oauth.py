"""Salesforce OAuth 2.0 web flow with PKCE (VS Code-style org authorize)."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.core.exceptions import BadRequestError
from app.services.salesforce_oauth_redirect import (
    SF_CLI_REDIRECT_PATH,
    oauth_redirect_server,
)
from app.services.salesforce_service import resolve_login_url

SF_CLI_CLIENT_ID = "PlatformCLI"
SF_CLI_REDIRECT_URI = f"http://localhost:1717{SF_CLI_REDIRECT_PATH}"

logger = logging.getLogger(__name__)

_OAUTH_STATE_TTL_SECONDS = 10 * 60
_DEFAULT_TIMEOUT = 30.0


@dataclass
class _OAuthPending:
    project_id: UUID
    name: str
    org_type: str
    login_url: str
    role: str | None
    bottler: str | None
    is_default: bool
    code_verifier: str
    created_at: float = field(default_factory=time.monotonic)


_pending_states: dict[str, _OAuthPending] = {}
_REDIRECT_SESSION_TTL_SECONDS = 5 * 60
_redirect_sessions: dict[str, tuple[str, float]] = {}


def _purge_redirect_sessions() -> None:
    now = time.monotonic()
    expired = [
        key
        for key, (_, created_at) in _redirect_sessions.items()
        if now - created_at > _REDIRECT_SESSION_TTL_SECONDS
    ]
    for key in expired:
        _redirect_sessions.pop(key, None)


def create_authorize_redirect_session(authorization_url: str) -> str:
    _purge_redirect_sessions()
    session_id = secrets.token_urlsafe(24)
    _redirect_sessions[session_id] = (authorization_url, time.monotonic())
    return session_id


def consume_authorize_redirect_session(session_id: str) -> str:
    _purge_redirect_sessions()
    entry = _redirect_sessions.pop(session_id, None)
    if entry is None:
        raise BadRequestError("Invalid or expired OAuth redirect — try again from Salesforce Orgs")
    return entry[0]


def _purge_expired_states() -> None:
    now = time.monotonic()
    expired = [
        key
        for key, value in _pending_states.items()
        if now - value.created_at > _OAUTH_STATE_TTL_SECONDS
    ]
    for key in expired:
        _pending_states.pop(key, None)


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def uses_sf_cli_redirect(redirect_uri: str | None = None) -> bool:
    uri = (redirect_uri or get_settings().salesforce_oauth_redirect_uri).rstrip("/")
    return uri == SF_CLI_REDIRECT_URI.rstrip("/")


def _oauth_settings() -> tuple[str, str, str]:
    settings = get_settings()
    client_id = settings.salesforce_oauth_client_id.strip() or SF_CLI_CLIENT_ID
    client_secret = settings.salesforce_oauth_client_secret or ""
    redirect_uri = settings.salesforce_oauth_redirect_uri.strip() or SF_CLI_REDIRECT_URI
    return client_id, client_secret, redirect_uri


def _is_public_oauth_client(client_id: str, client_secret: str) -> bool:
    """PlatformCLI and other PKCE public clients must not send client_secret."""
    if client_id == SF_CLI_CLIENT_ID:
        return True
    return not client_secret.strip()


def _token_request_data(
    *,
    client_id: str,
    client_secret: str,
    **fields: str,
) -> dict[str, str]:
    data = {"client_id": client_id, **fields}
    if not _is_public_oauth_client(client_id, client_secret):
        data["client_secret"] = client_secret
    return data


async def ensure_oauth_redirect_server() -> None:
    """Start localhost:1717 listener when using the SF CLI callback URL."""
    if not uses_sf_cli_redirect():
        return
    settings = get_settings()
    origin = settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:3000"
    oauth_redirect_server.configure(frontend_origin=origin)
    try:
        await oauth_redirect_server.start()
    except RuntimeError as exc:
        logger.warning("OAuth redirect server not available: %s", exc)


async def start_oauth_flow(
    *,
    project_id: UUID,
    name: str,
    org_type: str,
    login_url: str | None = None,
    role: str | None = None,
    bottler: str | None = None,
    is_default: bool = False,
) -> tuple[str, str, str]:
    """Return (authorization_url, state, redirect_session)."""
    await ensure_oauth_redirect_server()
    client_id, _client_secret, redirect_uri = _oauth_settings()
    resolved_login = login_url or resolve_login_url(org_type)
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)

    _purge_expired_states()
    _pending_states[state] = _OAuthPending(
        project_id=project_id,
        name=name,
        org_type=org_type,
        login_url=resolved_login,
        role=role,
        bottler=bottler,
        is_default=is_default,
        code_verifier=verifier,
    )

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "refresh_token api web",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "login",
    }
    authorization_url = f"{resolved_login.rstrip('/')}/services/oauth2/authorize?{urlencode(params)}"
    redirect_session = create_authorize_redirect_session(authorization_url)
    return authorization_url, state, redirect_session


async def exchange_oauth_code(*, state: str, code: str) -> dict[str, Any]:
    """Exchange authorization code for tokens and return org creation payload."""
    _purge_expired_states()
    pending = _pending_states.pop(state, None)
    if pending is None:
        raise BadRequestError("Invalid or expired OAuth state — restart authorization")

    client_id, client_secret, redirect_uri = _oauth_settings()
    token_url = f"{pending.login_url.rstrip('/')}/services/oauth2/token"
    data = _token_request_data(
        client_id=client_id,
        client_secret=client_secret,
        grant_type="authorization_code",
        code=code,
        redirect_uri=redirect_uri,
        code_verifier=pending.code_verifier,
    )

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(token_url, data=data)

    if resp.status_code >= 400:
        snippet = resp.text[:500]
        raise BadRequestError(f"OAuth token exchange failed ({resp.status_code}): {snippet}")

    body = resp.json()
    access_token = body.get("access_token")
    instance_url = body.get("instance_url")
    refresh_token = body.get("refresh_token")
    if not access_token or not instance_url:
        raise BadRequestError("OAuth response missing access_token or instance_url")

    # Fetch identity for username (optional)
    username: str | None = None
    identity_urls: list[str] = []
    if body.get("id"):
        identity_urls.append(str(body["id"]))
    if instance_url:
        identity_urls.append(f"{instance_url.rstrip('/')}/services/oauth2/userinfo")
    for identity_url in identity_urls:
        if username:
            break
        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                id_resp = await client.get(
                    identity_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if id_resp.status_code < 400:
                username = id_resp.json().get("preferred_username") or id_resp.json().get("username")
        except Exception as exc:
            logger.debug("oauth.userinfo_failed url=%s err=%s", identity_url, exc)

    return {
        "project_id": pending.project_id,
        "name": pending.name,
        "org_type": pending.org_type,
        "login_url": pending.login_url,
        "instance_url": instance_url.rstrip("/"),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "username": username,
        "role": pending.role,
        "bottler": pending.bottler,
        "is_default": pending.is_default,
    }


async def refresh_oauth_access_token(
    login_url: str,
    refresh_token: str,
) -> dict[str, str]:
    """Refresh OAuth access token. Returns dict with access_token and optional instance_url."""
    client_id, client_secret, _redirect_uri = _oauth_settings()
    token_url = f"{login_url.rstrip('/')}/services/oauth2/token"
    data = _token_request_data(
        client_id=client_id,
        client_secret=client_secret,
        grant_type="refresh_token",
        refresh_token=refresh_token,
    )
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(token_url, data=data)
    if resp.status_code >= 400:
        raise BadRequestError(f"OAuth refresh failed ({resp.status_code}): {resp.text[:500]}")
    body = resp.json()
    access_token = body.get("access_token")
    if not access_token:
        raise BadRequestError("OAuth refresh response missing access_token")
    result: dict[str, str] = {"access_token": access_token}
    if body.get("instance_url"):
        result["instance_url"] = body["instance_url"].rstrip("/")
    return result
