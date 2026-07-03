from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SalesforceOrgCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    org_type: str = "sandbox"
    login_url: str
    auth_method: str = "credentials"
    username: str | None = None
    password: str | None = None
    security_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    instance_url: str | None = None
    role: str | None = None
    bottler: str | None = None
    is_default: bool = False


class SalesforceOrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    org_type: str | None = None
    login_url: str | None = None
    instance_url: str | None = None
    role: str | None = None
    bottler: str | None = None
    is_default: bool | None = None
    username: str | None = None
    password: str | None = None
    security_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None


class SalesforceOrgResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    org_type: str
    login_url: str
    auth_method: str
    instance_url: str | None
    status: str
    role: str | None = None
    bottler: str | None = None
    is_default: bool = False
    salesforce_username: str | None = None
    last_validated_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SalesforceValidateResponse(BaseModel):
    org_id: UUID
    valid: bool
    message: str


class SalesforceOAuthStartRequest(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    org_type: str = "sandbox"
    login_url: str | None = None
    role: str | None = None
    bottler: str | None = None
    is_default: bool = False


class SalesforceOAuthStartResponse(BaseModel):
    authorization_url: str
    state: str
    redirect_session: str


class SalesforceOAuthCallbackRequest(BaseModel):
    state: str
    code: str


class SalesforceOAuthCallbackResponse(BaseModel):
    org: SalesforceOrgResponse
