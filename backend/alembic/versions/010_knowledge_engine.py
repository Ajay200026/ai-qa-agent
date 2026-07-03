"""Knowledge engine tables for Salesforce module indexing."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "010_knowledge_engine"
down_revision = "009_org_salesforce_username"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_repos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "knowledge_modules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repo_id",
            UUID(as_uuid=True),
            sa.ForeignKey("knowledge_repos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("scan_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("scan_error", sa.Text(), nullable=True),
        sa.Column("stats", JSONB(), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_modules_repo_id", "knowledge_modules", ["repo_id"])
    op.create_table(
        "knowledge_entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "module_id",
            UUID(as_uuid=True),
            sa.ForeignKey("knowledge_modules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("extracted", JSONB(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("business_rules", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_entities_module_id", "knowledge_entities", ["module_id"])
    op.create_index("ix_knowledge_entities_entity_type", "knowledge_entities", ["entity_type"])
    op.create_index("ix_knowledge_entities_name", "knowledge_entities", ["name"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_entities_name", table_name="knowledge_entities")
    op.drop_index("ix_knowledge_entities_entity_type", table_name="knowledge_entities")
    op.drop_index("ix_knowledge_entities_module_id", table_name="knowledge_entities")
    op.drop_table("knowledge_entities")
    op.drop_index("ix_knowledge_modules_repo_id", table_name="knowledge_modules")
    op.drop_table("knowledge_modules")
    op.drop_table("knowledge_repos")
