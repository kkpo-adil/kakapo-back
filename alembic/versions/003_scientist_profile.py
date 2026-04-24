from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("scientist_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("orcid_id", sa.String(32), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("primary_domain", sa.String(100), nullable=True),
        sa.Column("affiliation_raw", sa.String(500), nullable=True),
        sa.Column("institution_ror", sa.String(255), nullable=True),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("orcid_access_token", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scientist_profiles_orcid_id", "scientist_profiles", ["orcid_id"], unique=True)


def downgrade():
    op.drop_table("scientist_profiles")
