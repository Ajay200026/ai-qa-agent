import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    owner: Mapped["User"] = relationship("User", back_populates="projects")
    salesforce_orgs: Mapped[list["SalesforceOrg"]] = relationship(
        "SalesforceOrg", back_populates="project"
    )
    scenarios: Mapped[list["Scenario"]] = relationship("Scenario", back_populates="project")
    account_queries: Mapped[list["AccountQuery"]] = relationship(
        "AccountQuery", back_populates="project"
    )
    login_as_profiles: Mapped[list["LoginAsProfile"]] = relationship(
        "LoginAsProfile", back_populates="project"
    )
