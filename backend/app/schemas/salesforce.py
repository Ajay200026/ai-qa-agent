from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class SalesforceOrgCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    org_type: str = "scratch"
    login_url: str
    auth_method: str = "credentials"
    username: str | None = None
    password: str | None = None
    access_token: str | None = None
    instance_url: str | None = None


class SalesforceOrgResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    org_type: str
    login_url: str
    auth_method: str
    instance_url: str | None
    status: str
    last_validated_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SalesforceValidateResponse(BaseModel):
    org_id: UUID
    valid: bool
    message: str
