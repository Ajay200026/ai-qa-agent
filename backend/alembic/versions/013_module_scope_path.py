"""Alembic migration: add scope_path to knowledge_modules for folder-scoped scanning."""

from alembic import op
import sqlalchemy as sa

revision = "013_module_scope_path"
down_revision = "012_azure_devops_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_modules", sa.Column("scope_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_modules", "scope_path")
