import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AzureConnectionStatus(str, enum.Enum):
    CONNECTED = "connected"
    ERROR = "error"


class AzureDevOpsConnection(Base):
    __tablename__ = "azure_devops_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_url: Mapped[str] = mapped_column(String(512), nullable=False)
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_pat: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=AzureConnectionStatus.CONNECTED.value)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    repos: Mapped[list["KnowledgeRepo"]] = relationship(
        "KnowledgeRepo", back_populates="azure_connection"
    )
