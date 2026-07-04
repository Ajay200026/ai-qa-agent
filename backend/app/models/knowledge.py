import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RepoSourceType(str, enum.Enum):
    LOCAL = "local"
    AZURE = "azure"


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    SCANNING = "scanning"
    COMPLETED = "completed"
    FAILED = "failed"


class KnowledgeRepo(Base):
    __tablename__ = "knowledge_repos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(16), default=RepoSourceType.AZURE.value)
    azure_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("azure_devops_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    azure_project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    azure_repo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    azure_repo_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    azure_connection: Mapped["AzureDevOpsConnection | None"] = relationship(
        "AzureDevOpsConnection", back_populates="repos"
    )
    modules: Mapped[list["KnowledgeModule"]] = relationship(
        "KnowledgeModule", back_populates="repo", cascade="all, delete-orphan"
    )


class KnowledgeModule(Base):
    __tablename__ = "knowledge_modules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_repos.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    scan_status: Mapped[str] = mapped_column(String(32), default=ScanStatus.PENDING.value)
    scan_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    repo: Mapped["KnowledgeRepo"] = relationship("KnowledgeRepo", back_populates="modules")
    entities: Mapped[list["KnowledgeEntity"]] = relationship(
        "KnowledgeEntity", back_populates="module", cascade="all, delete-orphan"
    )


class KnowledgeEntity(Base):
    __tablename__ = "knowledge_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_modules.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_rules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    module: Mapped["KnowledgeModule"] = relationship("KnowledgeModule", back_populates="entities")
