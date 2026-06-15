import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import decrypt_credentials, encrypt_credentials
from app.models.salesforce_org import AuthMethod, OrgStatus, SalesforceOrg
from app.repositories.salesforce_org_repository import SalesforceOrgRepository
from app.schemas.salesforce import SalesforceOrgCreate


class SalesforceService:
    def __init__(self, db: AsyncSession):
        self.repo = SalesforceOrgRepository(db)

    def _build_credentials_payload(self, data: SalesforceOrgCreate) -> str:
        if data.auth_method == AuthMethod.CREDENTIALS:
            if not data.username or not data.password:
                raise ValidationError("Username and password required for credentials auth")
            payload = {"username": data.username, "password": data.password}
        elif data.auth_method == AuthMethod.OAUTH:
            if not data.access_token or not data.instance_url:
                raise ValidationError("Access token and instance URL required for OAuth auth")
            payload = {"access_token": data.access_token, "instance_url": data.instance_url}
        else:
            raise ValidationError(f"Unsupported auth method: {data.auth_method}")
        try:
            return encrypt_credentials(json.dumps(payload))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    async def create_org(self, data: SalesforceOrgCreate) -> SalesforceOrg:
        org = SalesforceOrg(
            project_id=data.project_id,
            name=data.name,
            org_type=data.org_type,
            login_url=data.login_url,
            auth_method=data.auth_method,
            encrypted_credentials=self._build_credentials_payload(data),
            instance_url=data.instance_url,
            status=OrgStatus.DISCONNECTED,
        )
        return await self.repo.create(org)

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

    async def validate_org(self, org_id: UUID) -> tuple[bool, str]:
        org = await self.get_org(org_id)
        try:
            creds = self.get_decrypted_credentials(org)
            if org.auth_method == AuthMethod.CREDENTIALS:
                if not creds.get("username"):
                    raise ValidationError("Missing username in credentials")
            elif org.auth_method == AuthMethod.OAUTH:
                if not creds.get("access_token") or not creds.get("instance_url"):
                    raise ValidationError("Missing OAuth credentials")
            org.status = OrgStatus.CONNECTED
            org.last_validated_at = datetime.now(UTC)
            await self.repo.db.flush()
            return True, "Org credentials validated successfully"
        except Exception as exc:
            org.status = OrgStatus.ERROR
            await self.repo.db.flush()
            return False, str(exc)

    async def list_connected(self) -> list[SalesforceOrg]:
        return await self.repo.list_connected()
