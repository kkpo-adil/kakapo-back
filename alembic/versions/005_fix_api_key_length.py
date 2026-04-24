from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("ai_client_profiles", "api_key",
        existing_type=sa.String(64),
        type_=sa.String(72),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column("ai_client_profiles", "api_key",
        existing_type=sa.String(72),
        type_=sa.String(64),
        existing_nullable=False,
    )
