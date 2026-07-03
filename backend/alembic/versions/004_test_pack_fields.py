"""Add role/bottler to orgs and test_pack_content to scenarios."""

from alembic import op
import sqlalchemy as sa

revision = "004_test_pack_fields"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("salesforce_orgs", sa.Column("role", sa.String(100), nullable=True))
    op.add_column("salesforce_orgs", sa.Column("bottler", sa.String(20), nullable=True))
    op.add_column("scenarios", sa.Column("test_pack_content", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scenarios", "test_pack_content")
    op.drop_column("salesforce_orgs", "bottler")
    op.drop_column("salesforce_orgs", "role")
