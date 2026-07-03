import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import decrypt_credentials, encrypt_credentials
from app.models.salesforce_org import AuthMethod, OrgStatus, OrgType, SalesforceOrg
from app.repositories.salesforce_org_repository import SalesforceOrgRepository
from app.schemas.salesforce import SalesforceOrgCreate, SalesforceOrgUpdate

LOGIN_URL_BY_TYPE = {
    OrgType.PRODUCTION: "https://login.salesforce.com",
    OrgType.SANDBOX: "https://test.salesforce.com",
    OrgType.SCRATCH: "https://test.salesforce.com",
}


def resolve_login_url(org_type: str, custom_login_url: str | None = None) -> str:
    if org_type == OrgType.CUSTOM:
        if not custom_login_url or not custom_login_url.strip():
            raise ValidationError("Custom org type requires a login URL")
        return custom_login_url.strip().rstrip("/")
    return LOGIN_URL_BY_TYPE.get(org_type, LOGIN_URL_BY_TYPE[OrgType.SANDBOX])


def resolve_org_type_from_instance(instance_url: str, fallback: str) -> str:
    if ".scratch." in instance_url.lower():
        return OrgType.SCRATCH
    return fallback


class SalesforceService:
    def __init__(self, db: AsyncSession):
        self.repo = SalesforceOrgRepository(db)

    def _build_credentials_payload(
        self,
        *,
        auth_method: str,
        username: str | None = None,
        password: str | None = None,
        security_token: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        instance_url: str | None = None,
    ) -> str:
        if auth_method == AuthMethod.CREDENTIALS:
            if not username or not password:
                raise ValidationError("Username and password required for credentials auth")
            payload: dict = {"username": username, "password": password}
            if security_token:
                payload["security_token"] = security_token
        elif auth_method == AuthMethod.OAUTH:
            if not access_token or not instance_url:
                raise ValidationError("Access token and instance URL required for OAuth auth")
            payload = {
                "access_token": access_token,
                "instance_url": instance_url,
            }
            if refresh_token:
                payload["refresh_token"] = refresh_token
            if username:
                payload["username"] = username
        else:
            raise ValidationError(f"Unsupported auth method: {auth_method}")
        try:
            return encrypt_credentials(json.dumps(payload))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    async def _apply_default_flag(self, project_id: UUID, org: SalesforceOrg, is_default: bool) -> None:
        if is_default:
            await self.repo.clear_default_for_project(project_id, except_org_id=org.id)
            org.is_default = True
        elif org.is_default and not is_default:
            org.is_default = False

    async def create_org(self, data: SalesforceOrgCreate) -> SalesforceOrg:
        login_url = data.login_url or resolve_login_url(data.org_type)
        org = SalesforceOrg(
            project_id=data.project_id,
            name=data.name,
            org_type=data.org_type,
            login_url=login_url,
            auth_method=data.auth_method,
            encrypted_credentials=self._build_credentials_payload(
                auth_method=data.auth_method,
                username=data.username,
                password=data.password,
                security_token=data.security_token,
                access_token=data.access_token,
                refresh_token=data.refresh_token,
                instance_url=data.instance_url,
            ),
            instance_url=data.instance_url,
            role=data.role,
            bottler=data.bottler,
            salesforce_username=data.username if data.auth_method == AuthMethod.CREDENTIALS else None,
            status=OrgStatus.DISCONNECTED,
            is_default=data.is_default,
        )
        created = await self.repo.create(org)
        if data.is_default:
            await self._apply_default_flag(data.project_id, created, True)
            await self.repo.db.flush()
        return created

    async def create_oauth_org(
        self,
        *,
        project_id: UUID,
        name: str,
        org_type: str,
        login_url: str,
        instance_url: str,
        access_token: str,
        refresh_token: str | None,
        username: str | None = None,
        role: str | None = None,
        bottler: str | None = None,
        is_default: bool = False,
    ) -> SalesforceOrg:
        resolved_org_type = resolve_org_type_from_instance(instance_url, org_type)
        org = SalesforceOrg(
            project_id=project_id,
            name=name,
            org_type=resolved_org_type,
            login_url=login_url,
            auth_method=AuthMethod.OAUTH,
            encrypted_credentials=self._build_credentials_payload(
                auth_method=AuthMethod.OAUTH,
                access_token=access_token,
                refresh_token=refresh_token,
                instance_url=instance_url,
                username=username,
            ),
            instance_url=instance_url.rstrip("/"),
            salesforce_username=username,
            role=role,
            bottler=bottler,
            status=OrgStatus.CONNECTED,
            is_default=is_default,
            last_validated_at=datetime.now(UTC),
        )
        created = await self.repo.create(org)
        if is_default:
            await self._apply_default_flag(project_id, created, True)
            await self.repo.db.flush()
        return created

    async def list_by_project(self, project_id: UUID) -> list[SalesforceOrg]:
        return await self.repo.list_by_project(project_id)

    async def get_org(self, org_id: UUID) -> SalesforceOrg:
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("SalesforceOrg", org_id)
        return org

    def get_decrypted_credentials(self, org: SalesforceOrg) -> dict:
        if not org.encrypted_credentials:
            raise ValidationError("Org has no stored credentials")
        return json.loads(decrypt_credentials(org.encrypted_credentials))

    def update_encrypted_credentials(self, org: SalesforceOrg, creds: dict) -> None:
        org.encrypted_credentials = encrypt_credentials(json.dumps(creds))

    async def update_org(self, org_id: UUID, data: SalesforceOrgUpdate) -> SalesforceOrg:
        org = await self.get_org(org_id)
        payload = data.model_dump(exclude_unset=True)

        credential_fields = {
            "username",
            "password",
            "security_token",
            "access_token",
            "refresh_token",
        }
        cred_updates = {k: payload.pop(k) for k in list(payload) if k in credential_fields}

        if "org_type" in payload and "login_url" not in payload:
            if payload["org_type"] != OrgType.CUSTOM:
                payload["login_url"] = resolve_login_url(payload["org_type"])

        for key, value in payload.items():
            setattr(org, key, value)

        if cred_updates:
            creds = self.get_decrypted_credentials(org)
            creds.update({k: v for k, v in cred_updates.items() if v is not None})
            if org.auth_method == AuthMethod.OAUTH:
                if cred_updates.get("access_token"):
                    creds["access_token"] = cred_updates["access_token"]
                if cred_updates.get("refresh_token"):
                    creds["refresh_token"] = cred_updates["refresh_token"]
                if payload.get("instance_url"):
                    creds["instance_url"] = payload["instance_url"]
            else:
                for field in ("username", "password", "security_token"):
                    if field in cred_updates and cred_updates[field] is not None:
                        creds[field] = cred_updates[field]
                if cred_updates.get("username"):
                    org.salesforce_username = cred_updates["username"]
            self.update_encrypted_credentials(org, creds)

        if data.is_default is True:
            await self._apply_default_flag(org.project_id, org, True)
        elif data.is_default is False:
            org.is_default = False

        await self.repo.db.flush()
        return org

    async def delete_org(self, org_id: UUID) -> None:
        org = await self.get_org(org_id)
        count = await self.repo.count_executions(org_id)
        if count > 0:
            raise ConflictError(
                f"Cannot delete org '{org.name}': {count} execution(s) reference it"
            )
        await self.repo.delete(org)

    async def validate_org(self, org_id: UUID) -> tuple[bool, str]:
        org = await self.get_org(org_id)
        try:
            creds = self.get_decrypted_credentials(org)
            if org.auth_method == AuthMethod.CREDENTIALS:
                if not creds.get("username"):
                    raise ValidationError("Missing username in credentials")
                message = "Org credentials validated successfully"
            elif org.auth_method == AuthMethod.OAUTH:
                access_token = creds.get("access_token")
                instance_url = creds.get("instance_url") or org.instance_url
                if not access_token or not instance_url:
                    raise ValidationError("Missing OAuth credentials")
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        f"{instance_url.rstrip('/')}/services/oauth2/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                if resp.status_code >= 400:
                    raise ValidationError(f"OAuth token invalid ({resp.status_code})")
                username = resp.json().get("preferred_username")
                if username:
                    org.salesforce_username = username
                    creds["username"] = username
                    self.update_encrypted_credentials(org, creds)
                message = (
                    f"OAuth connection valid"
                    + (f" — connected as {username}" if username else "")
                )
            else:
                raise ValidationError(f"Unsupported auth method: {org.auth_method}")
            org.status = OrgStatus.CONNECTED
            org.last_validated_at = datetime.now(UTC)
            await self.repo.db.flush()
            return True, message
        except Exception as exc:
            org.status = OrgStatus.ERROR
            await self.repo.db.flush()
            return False, str(exc)

    async def list_connected(self) -> list[SalesforceOrg]:
        return await self.repo.list_connected()
