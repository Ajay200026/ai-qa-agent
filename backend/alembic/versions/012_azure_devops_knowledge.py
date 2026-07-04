"""Alembic migration: Azure DevOps connections and knowledge repo Azure fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "012_azure_devops_knowledge"
down_revision = "011_brain_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "azure_devops_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("organization_url", sa.String(512), nullable=False),
        sa.Column("organization_name", sa.String(255), nullable=False),
        sa.Column("encrypted_pat", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="connected"),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_azure_devops_connections_owner_id",
        "azure_devops_connections",
        ["owner_id"],
    )

    op.add_column(
        "knowledge_repos",
        sa.Column("source_type", sa.String(16), nullable=False, server_default="local"),
    )
    op.add_column(
        "knowledge_repos",
        sa.Column("azure_connection_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column("knowledge_repos", sa.Column("azure_project", sa.String(255), nullable=True))
    op.add_column("knowledge_repos", sa.Column("azure_repo", sa.String(255), nullable=True))
    op.add_column("knowledge_repos", sa.Column("azure_repo_id", sa.String(64), nullable=True))
    op.add_column("knowledge_repos", sa.Column("branch", sa.String(255), nullable=True))
    op.add_column("knowledge_repos", sa.Column("last_synced_commit", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_knowledge_repos_azure_connection",
        "knowledge_repos",
        "azure_devops_connections",
        ["azure_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("knowledge_repos", "path", server_default="")


def downgrade() -> None:
    op.drop_constraint("fk_knowledge_repos_azure_connection", "knowledge_repos", type_="foreignkey")
    op.drop_column("knowledge_repos", "last_synced_commit")
    op.drop_column("knowledge_repos", "branch")
    op.drop_column("knowledge_repos", "azure_repo_id")
    op.drop_column("knowledge_repos", "azure_repo")
    op.drop_column("knowledge_repos", "azure_project")
    op.drop_column("knowledge_repos", "azure_connection_id")
    op.drop_column("knowledge_repos", "source_type")
    op.drop_index("ix_azure_devops_connections_owner_id", table_name="azure_devops_connections")
    op.drop_table("azure_devops_connections")
