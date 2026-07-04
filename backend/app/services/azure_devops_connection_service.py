"""Azure DevOps connection management (PAT)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_credentials, encrypt_credentials
from app.models.azure_devops import AzureConnectionStatus, AzureDevOpsConnection
from app.repositories.azure_devops_repository import AzureDevOpsConnectionRepository
from app.services.azure_devops_service import AzureDevOpsClient, parse_organization_url


class AzureDevOpsConnectionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AzureDevOpsConnectionRepository(db)

    async def connect(
        self, owner_id: UUID, name: str, organization_url: str, pat: str
    ) -> AzureDevOpsConnection:
        base_url, org_name = parse_organization_url(organization_url)
        client = AzureDevOpsClient(base_url, pat.strip())
        await client.validate()

        connection = AzureDevOpsConnection(
            owner_id=owner_id,
            name=name.strip(),
            organization_url=base_url,
            organization_name=org_name,
            encrypted_pat=encrypt_credentials(pat.strip()),
            status=AzureConnectionStatus.CONNECTED.value,
            last_validated_at=datetime.now(UTC),
        )
        created = await self.repo.create(connection)
        await self.db.commit()
        return created

    async def list_connections(self, owner_id: UUID) -> list[AzureDevOpsConnection]:
        return await self.repo.list_by_owner(owner_id)

    async def get_connection(
        self, connection_id: UUID, owner_id: UUID
    ) -> AzureDevOpsConnection | None:
        return await self.repo.get_owned(connection_id, owner_id)

    async def delete_connection(self, connection_id: UUID, owner_id: UUID) -> None:
        conn = await self.repo.get_owned(connection_id, owner_id)
        if not conn:
            raise ValueError("Connection not found")
        await self.repo.delete(conn)
        await self.db.commit()

    async def validate_connection(self, connection_id: UUID, owner_id: UUID) -> AzureDevOpsConnection:
        conn = await self.repo.get_owned(connection_id, owner_id)
        if not conn:
            raise ValueError("Connection not found")
        pat = decrypt_credentials(conn.encrypted_pat)
        client = AzureDevOpsClient(conn.organization_url, pat)
        try:
            await client.validate()
            conn.status = AzureConnectionStatus.CONNECTED.value
            conn.last_validated_at = datetime.now(UTC)
        except ValueError:
            conn.status = AzureConnectionStatus.ERROR.value
            raise
        finally:
            await self.repo.update(conn)
            await self.db.commit()
        return conn

    def client_for(self, connection: AzureDevOpsConnection) -> AzureDevOpsClient:
        pat = decrypt_credentials(connection.encrypted_pat)
        return AzureDevOpsClient(connection.organization_url, pat)
