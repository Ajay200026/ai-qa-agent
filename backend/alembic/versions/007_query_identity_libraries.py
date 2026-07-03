"""Add account_queries and login_as_profiles libraries; scenario FK refs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007_query_identity_libraries"
down_revision = "006_login_as_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("soql_text", sa.Text(), nullable=False),
        sa.Column("match_hints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_account_queries_project_id", "account_queries", ["project_id"])

    op.create_table(
        "login_as_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("bottler_id", sa.String(32), nullable=False),
        sa.Column("onboarding_role", sa.String(128), nullable=False),
        sa.Column("match_hints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_login_as_profiles_project_id", "login_as_profiles", ["project_id"])

    op.add_column(
        "scenarios",
        sa.Column(
            "account_query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account_queries.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "scenarios",
        sa.Column(
            "login_as_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("login_as_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("scenarios", "login_as_profile_id")
    op.drop_column("scenarios", "account_query_id")
    op.drop_index("ix_login_as_profiles_project_id", table_name="login_as_profiles")
    op.drop_table("login_as_profiles")
    op.drop_index("ix_account_queries_project_id", table_name="account_queries")
    op.drop_table("account_queries")
