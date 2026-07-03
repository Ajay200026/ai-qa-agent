"""Read-only Salesforce SOQL client used for customer targeting auto-fill."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID
from xml.sax.saxutils import escape as xml_escape

import httpx

from app.models.salesforce_org import AuthMethod, SalesforceOrg
from app.schemas.customer_target import SoqlAccountRow, SoqlQueryResponse
from app.schemas.login_as import SoqlUserRow

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


SOQL_API_VERSION = "v59.0"
SOAP_API_VERSION = "59.0"
_DEFAULT_TIMEOUT = 30.0
_TOKEN_TTL_SECONDS = 30 * 60
_MAX_LIMIT = 50

_FORBIDDEN_PATTERNS = [
    re.compile(r";", re.IGNORECASE),
    re.compile(r"\b(UPDATE|DELETE|INSERT|UPSERT|MERGE)\b", re.IGNORECASE),
]
_SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_FROM_RE = re.compile(r"\bFROM\s+([A-Za-z0-9_]+)\b", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)

_ALLOWED_OBJECTS = {"Account", "User"}


class SoqlError(Exception):
    """Base error."""


class SoqlValidationError(SoqlError):
    """Raised when the supplied SOQL is rejected by the allow-list."""


class SoqlAuthError(SoqlError):
    """Raised when authentication to Salesforce fails."""


class SoqlExecutionError(SoqlError):
    """Raised when Salesforce returns an error for an otherwise valid query."""


@dataclass
class _SessionToken:
    access_token: str
    instance_url: str
    expires_at: float

    def is_valid(self) -> bool:
        return time.monotonic() < self.expires_at


_token_cache: dict[UUID, _SessionToken] = {}
_token_lock = asyncio.Lock()


def _normalize_login_url(login_url: str) -> str:
    url = (login_url or "").strip().rstrip("/")
    if not url:
        return "https://login.salesforce.com"
    if not url.startswith("http"):
        url = f"https://{url}"
    return url


def validate_soql(soql: str, *, limit: int) -> tuple[str, str]:
    """Validate that the SOQL is single-statement, SELECT-only, against Account.

    Returns (cleaned_soql, object_name).
    """
    if not soql or not soql.strip():
        raise SoqlValidationError("SOQL query is empty")

    cleaned = soql.strip()
    if "\x00" in cleaned:
        raise SoqlValidationError("SOQL contains invalid characters")

    if not _SELECT_RE.match(cleaned):
        raise SoqlValidationError("Only SELECT statements are allowed")

    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(cleaned):
            raise SoqlValidationError("SOQL contains forbidden tokens (;, UPDATE, DELETE, ...)")

    from_match = _FROM_RE.search(cleaned)
    if not from_match:
        raise SoqlValidationError("SOQL must contain a FROM clause")
    object_name = from_match.group(1)
    if object_name not in _ALLOWED_OBJECTS:
        raise SoqlValidationError(
            f"Object '{object_name}' is not allowed. Allowed: {sorted(_ALLOWED_OBJECTS)}"
        )

    limit_match = _LIMIT_RE.search(cleaned)
    if limit_match:
        existing_limit = int(limit_match.group(1))
        if existing_limit > _MAX_LIMIT:
            raise SoqlValidationError(f"LIMIT must be <= {_MAX_LIMIT}")
    else:
        cleaned = f"{cleaned} LIMIT {min(limit, _MAX_LIMIT)}"

    return cleaned, object_name


def _api_password(credentials: dict[str, Any]) -> str:
    """Password for SOAP/API login — appends security token when stored separately."""
    password = credentials.get("password") or ""
    token = (credentials.get("security_token") or "").strip()
    if not token:
        return password
    if password.endswith(token):
        return password
    return f"{password}{token}"


async def _session_from_browser(page: Page, org: SalesforceOrg) -> _SessionToken | None:
    """Reuse the active Playwright Salesforce session (no SOAP / security token)."""
    try:
        cookies = await page.context.cookies()
    except Exception as exc:
        logger.debug("browser_session.cookie_read_failed %s", exc)
        return None

    sid = None
    cookie_instance: str | None = None
    for cookie in cookies:
        if cookie.get("name") != "sid" or not cookie.get("value"):
            continue
        sid = cookie["value"]
        domain = (cookie.get("domain") or "").lstrip(".")
        if domain.endswith(".salesforce.com"):
            cookie_instance = f"https://{domain}"
        break

    if not sid:
        return None

    instance_url = (org.instance_url or "").strip().rstrip("/") or cookie_instance
    if not instance_url:
        for pattern in (
            r"(https://[a-z0-9-]+\.my\.salesforce\.com)",
            r"(https://[a-z0-9-]+\.salesforce\.com)",
        ):
            match = re.search(pattern, page.url or "", re.I)
            if match:
                instance_url = match.group(1)
                break

    if not instance_url or "lightning.force.com" in instance_url:
        logger.warning(
            "browser_session.missing_instance_url org_id=%s page_url=%s",
            org.id,
            (page.url or "")[:120],
        )
        return None

    logger.info("salesforce_query.using_browser_session instance=%s", instance_url)
    return _SessionToken(
        access_token=sid,
        instance_url=instance_url,
        expires_at=time.monotonic() + 15 * 60,
    )


async def _soap_login(
    login_url: str,
    username: str,
    password: str,
) -> tuple[str, str]:
    """Perform SOAP login. Returns (session_id, instance_base_url)."""
    endpoint = f"{_normalize_login_url(login_url)}/services/Soap/u/{SOAP_API_VERSION}"
    body = f"""<?xml version="1.0" encoding="utf-8" ?>
<env:Envelope xmlns:xsd="http://www.w3.org/2001/XMLSchema"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
              xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
  <env:Body>
    <n1:login xmlns:n1="urn:partner.soap.sforce.com">
      <n1:username>{xml_escape(username)}</n1:username>
      <n1:password>{xml_escape(password)}</n1:password>
    </n1:login>
  </env:Body>
</env:Envelope>"""
    headers = {
        "Content-Type": "text/xml; charset=UTF-8",
        "SOAPAction": "login",
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(endpoint, content=body.encode("utf-8"), headers=headers)
    if resp.status_code >= 400:
        snippet = resp.text[:500]
        raise SoqlAuthError(f"SOAP login failed ({resp.status_code}): {snippet}")

    text = resp.text
    sid_match = re.search(r"<sessionId>([^<]+)</sessionId>", text)
    server_match = re.search(r"<serverUrl>([^<]+)</serverUrl>", text)
    if not sid_match or not server_match:
        raise SoqlAuthError("SOAP login response missing sessionId/serverUrl")
    session_id = sid_match.group(1)
    server_url = server_match.group(1)
    # Strip path to derive instance base URL.
    instance_base = re.match(r"^(https?://[^/]+)", server_url)
    if not instance_base:
        raise SoqlAuthError("Could not derive instance URL from SOAP login response")
    return session_id, instance_base.group(1)


async def _get_session(
    org: SalesforceOrg,
    credentials: dict[str, Any],
    *,
    force_refresh: bool = False,
) -> _SessionToken:
    async with _token_lock:
        cached = _token_cache.get(org.id)
        if cached and cached.is_valid() and not force_refresh:
            return cached

        if org.auth_method == AuthMethod.OAUTH:
            token = credentials.get("access_token")
            instance_url = credentials.get("instance_url") or org.instance_url
            refresh_token = credentials.get("refresh_token")
            if force_refresh and refresh_token:
                from app.services.salesforce_oauth import refresh_oauth_access_token

                refreshed = await refresh_oauth_access_token(org.login_url, refresh_token)
                token = refreshed["access_token"]
                credentials["access_token"] = token
                if refreshed.get("instance_url"):
                    instance_url = refreshed["instance_url"]
                    credentials["instance_url"] = instance_url
            if not token or not instance_url:
                raise SoqlAuthError("OAuth org is missing access_token or instance_url")
            session = _SessionToken(
                access_token=token,
                instance_url=instance_url.rstrip("/"),
                expires_at=time.monotonic() + _TOKEN_TTL_SECONDS,
            )
        else:
            username = credentials.get("username")
            password = _api_password(credentials)
            if not username or not password:
                raise SoqlAuthError("Credentials org is missing username/password")
            session_id, instance_base = await _soap_login(org.login_url, username, password)
            session = _SessionToken(
                access_token=session_id,
                instance_url=instance_base,
                expires_at=time.monotonic() + _TOKEN_TTL_SECONDS,
            )

        _token_cache[org.id] = session
        return session


def _invalidate(org_id: UUID) -> None:
    _token_cache.pop(org_id, None)


def _extract_user_row(record: dict[str, Any]) -> SoqlUserRow:
    return SoqlUserRow(
        user_id=record.get("Id") or record.get("id") or "",
        name=record.get("Name"),
        username=record.get("Username"),
        bottler=record.get("cfs_ob__Bottler__c"),
        role=record.get("cfs_ob__Onboarding_Role__c"),
        raw={k: v for k, v in record.items() if k != "attributes"},
    )


def _extract_account_row(record: dict[str, Any]) -> SoqlAccountRow:
    customer_number = record.get("cfs_ob__u_CustomerNumber__c")
    account_number = record.get("AccountNumber")
    return SoqlAccountRow(
        account_number=account_number,
        customer_number=customer_number or account_number,
        account_name=record.get("Name"),
        sales_office=record.get("cfs_ob__u_SalesOffice__c"),
        account_group=record.get("cfs_ob__u_CustomerAccountGroup__c"),
        distribution_channel=record.get("cfs_ob__u_DistributionChannel__c"),
        bottler=record.get("cfs_ob__Bottler__c"),
        raw={k: v for k, v in record.items() if k != "attributes"},
    )


class SoqlClient:
    """Tiny SOQL client — prefers browser session, falls back to stored credentials."""

    def __init__(
        self,
        org: SalesforceOrg,
        credentials: dict[str, Any],
        *,
        page: Page | None = None,
    ):
        self.org = org
        self.credentials = credentials
        self.page = page

    async def _resolve_session(self) -> _SessionToken:
        if self.page is not None:
            browser_session = await _session_from_browser(self.page, self.org)
            if browser_session is not None:
                return browser_session
        return await _get_session(self.org, self.credentials)

    async def _raw_query(self, soql: str, *, limit: int) -> dict[str, Any]:
        cleaned, _object = validate_soql(soql, limit=limit)
        session = await self._resolve_session()
        url = f"{session.instance_url}/services/data/{SOQL_API_VERSION}/query"
        params = {"q": cleaned}
        headers = {
            "Authorization": f"Bearer {session.access_token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 401:
                _invalidate(self.org.id)
                if self.org.auth_method == AuthMethod.OAUTH and self.credentials.get("refresh_token"):
                    session = await _get_session(
                        self.org, self.credentials, force_refresh=True
                    )
                else:
                    session = await self._resolve_session()
                headers["Authorization"] = f"Bearer {session.access_token}"
                resp = await client.get(url, params=params, headers=headers)
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except Exception:
                payload = resp.text[:500]
            raise SoqlExecutionError(
                f"Salesforce returned {resp.status_code}: {payload}"
            )
        return resp.json()

    async def query_users(self, soql: str, *, limit: int = 1) -> list[SoqlUserRow]:
        """Execute a SOQL query against the User object and return typed rows."""
        body = await self._raw_query(soql, limit=limit)
        return [_extract_user_row(r) for r in body.get("records", [])]

    async def query(self, soql: str, *, limit: int = 5) -> SoqlQueryResponse:
        body = await self._raw_query(soql, limit=limit)
        records = [_extract_account_row(r) for r in body.get("records", [])]
        return SoqlQueryResponse(
            total_size=body.get("totalSize", len(records)),
            records=records,
            done=body.get("done", True),
        )
