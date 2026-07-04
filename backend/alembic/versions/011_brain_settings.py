"""Brain settings and RCA analysis column."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "011_brain_settings"
down_revision = "010_knowledge_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brain_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_mode", sa.String(16), nullable=False, server_default="single"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("reports", sa.Column("rca_analysis", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "rca_analysis")
    op.drop_table("brain_settings")
