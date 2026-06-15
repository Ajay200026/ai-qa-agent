import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    template_key: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("workflow_templates.key"), nullable=True
    )
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    business_actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    expected_results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    test_case_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    regression_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    project: Mapped["Project"] = relationship("Project", back_populates="scenarios")
    executions: Mapped[list["Execution"]] = relationship("Execution", back_populates="scenario")
