import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OrgType(StrEnum):
    PRODUCTION = "production"
    SANDBOX = "sandbox"
    CUSTOM = "custom"
    SCRATCH = "scratch"


class AuthMethod(StrEnum):
    CREDENTIALS = "credentials"
    OAUTH = "oauth"


class OrgStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class SalesforceOrg(Base):
    __tablename__ = "salesforce_orgs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_type: Mapped[str] = mapped_column(String(50), default=OrgType.SCRATCH, nullable=False)
    login_url: Mapped[str] = mapped_column(String(512), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(50), default=AuthMethod.CREDENTIALS)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    instance_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=OrgStatus.DISCONNECTED)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bottler: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    salesforce_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    project: Mapped["Project"] = relationship("Project", back_populates="salesforce_orgs")
    executions: Mapped[list["Execution"]] = relationship("Execution", back_populates="org")
