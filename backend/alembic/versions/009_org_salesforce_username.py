"""Add salesforce_username to salesforce_orgs for OAuth identity display."""

from alembic import op
import sqlalchemy as sa

revision = "009_org_salesforce_username"
down_revision = "008_org_default_and_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "salesforce_orgs",
        sa.Column("salesforce_username", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("salesforce_orgs", "salesforce_username")
