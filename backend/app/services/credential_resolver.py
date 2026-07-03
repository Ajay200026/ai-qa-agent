"""Resolve Salesforce credentials by role and bottler."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.salesforce_org import SalesforceOrg
from app.services.salesforce_service import SalesforceService


class CredentialResolver:
    def __init__(self, db: AsyncSession, default_org_id: UUID):
        self.db = db
        self.default_org_id = default_org_id
        self.sf_service = SalesforceService(db)
        self._cache: dict[str, dict[str, Any]] = {}

    async def resolve(
        self,
        *,
        role: str | None = None,
        bottler: str | None = None,
        org_map: dict[str, UUID] | None = None,
    ) -> tuple[dict[str, Any], str, str, str | None]:
        """Return (credentials, login_url, auth_method, instance_url). Raises if blocked."""
        key = self._identity_key(role, bottler)
        if key in self._cache:
            cached = self._cache[key]
            return cached["credentials"], cached["login_url"], cached["auth_method"], cached.get("instance_url")

        org_id = self._lookup_org_id(key, org_map)
        if org_id is None:
            org = await self._find_org_by_metadata(role, bottler)
            org_id = org.id if org else self.default_org_id

        org = await self.sf_service.get_org(org_id)
        if role or bottler:
            if org.role and role and org.role.lower() not in role.lower() and role.lower() not in org.role.lower():
                pass  # soft match
            if org.bottler and bottler:
                code = self._bottler_code(bottler)
                if code and org.bottler != code and org.bottler not in bottler:
                    org_meta = await self._find_org_by_metadata(role, bottler)
                    if org_meta:
                        org = org_meta

        creds = self.sf_service.get_decrypted_credentials(org)
        result = {
            "credentials": creds,
            "login_url": org.login_url,
            "auth_method": org.auth_method,
            "instance_url": org.instance_url,
        }
        self._cache[key] = result
        return creds, org.login_url, org.auth_method, org.instance_url

    def block_reason(self, role: str | None, bottler: str | None, org_map: dict[str, UUID] | None) -> str | None:
        key = self._identity_key(role, bottler)
        if key == "default":
            return None
        if self._lookup_org_id(key, org_map) is not None:
            return None
        # Will still try metadata match + default org in resolve()
        return None

    async def _find_org_by_metadata(self, role: str | None, bottler: str | None) -> SalesforceOrg | None:
        code = self._bottler_code(bottler or "")
        stmt = select(SalesforceOrg)
        result = await self.db.execute(stmt)
        orgs = list(result.scalars().all())
        for org in orgs:
            if code and org.bottler == code:
                if not role or not org.role or role.lower() in (org.role or "").lower():
                    return org
        for org in orgs:
            if role and org.role and role.lower() in org.role.lower():
                return org
        return None

    @staticmethod
    def _identity_key(role: str | None, bottler: str | None) -> str:
        parts = []
        if role:
            parts.append(role.strip().lower())
        if bottler:
            parts.append(bottler.strip().lower())
        return "|".join(parts) or "default"

    @staticmethod
    def _bottler_code(bottler: str) -> str | None:
        m = re.search(r"(\d{4})", bottler)
        return m.group(1) if m else None

    @staticmethod
    def _lookup_org_id(key: str, org_map: dict[str, UUID] | None) -> UUID | None:
        if not org_map:
            return None
        if key in org_map:
            return org_map[key]
        if "default" in org_map and key == "default":
            return org_map["default"]
        return None
