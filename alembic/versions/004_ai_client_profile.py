from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_client_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_name", sa.String(255), nullable=False),
        sa.Column("contact_email", sa.String(255), nullable=False, unique=True),
        sa.Column("api_key", sa.String(72), nullable=False, unique=True),
        sa.Column("plan_type", sa.String(50), nullable=False, server_default="compliance_starter"),
        sa.Column("monthly_quota", sa.Integer, nullable=False, server_default="100000"),
        sa.Column("quota_used_current_month", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overage_policy", sa.String(50), nullable=False, server_default="graceful"),
        sa.Column("price_per_query", sa.Numeric(10, 6), nullable=False, server_default="0.002"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_client_profiles_contact_email", "ai_client_profiles", ["contact_email"], unique=True)
    op.create_index("ix_ai_client_profiles_api_key", "ai_client_profiles", ["api_key"], unique=True)
    op.create_table("query_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ai_client_id", sa.String(36), sa.ForeignKey("ai_client_profiles.id"), nullable=False),
        sa.Column("endpoint", sa.String(100), nullable=False),
        sa.Column("doi_queried", sa.String(255), nullable=True),
        sa.Column("kpt_id_returned", sa.String(128), nullable=True),
        sa.Column("result", sa.String(50), nullable=False),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("is_cached", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("billed_amount", sa.Numeric(10, 8), nullable=False, server_default="0"),
        sa.Column("queried_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_query_logs_ai_client_id", "query_logs", ["ai_client_id"])


def downgrade():
    op.drop_table("query_logs")
    op.drop_table("ai_client_profiles")
