"""Azure DevOps API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AzureConnectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    organization_url: str = Field(..., min_length=1)
    pat: str = Field(..., min_length=1)


class AzureConnectionResponse(BaseModel):
    id: UUID
    name: str
    organization_url: str
    organization_name: str
    status: str
    last_validated_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AzureProjectItem(BaseModel):
    id: str
    name: str


class AzureRepoItem(BaseModel):
    id: str
    name: str
    default_branch: str


class AzureBranchListResponse(BaseModel):
    branches: list[str]
