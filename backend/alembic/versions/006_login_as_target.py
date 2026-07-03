"""Add login_as_target and identity_map to scenarios."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006_login_as_target"
down_revision = "005_customer_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scenarios",
        sa.Column("login_as_target", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "scenarios",
        sa.Column("identity_map", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scenarios", "identity_map")
    op.drop_column("scenarios", "login_as_target")
