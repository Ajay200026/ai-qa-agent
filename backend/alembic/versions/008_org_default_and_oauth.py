"""Add is_default flag to salesforce_orgs."""

from alembic import op
import sqlalchemy as sa

revision = "008_org_default_and_oauth"
down_revision = "007_query_identity_libraries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "salesforce_orgs",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("salesforce_orgs", "is_default")
