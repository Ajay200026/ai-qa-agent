"""Add customer_target on scenarios; action_params + notes on execution_steps."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_customer_target"
down_revision = "004_test_pack_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scenarios",
        sa.Column("customer_target", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "execution_steps",
        sa.Column("action_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "execution_steps",
        sa.Column("notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("execution_steps", "notes")
    op.drop_column("execution_steps", "action_params")
    op.drop_column("scenarios", "customer_target")
