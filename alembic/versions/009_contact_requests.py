from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "contact_requests" not in inspector.get_table_names():
        op.create_table("contact_requests",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("segment", sa.String(50), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("payload", sa.Text, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_contact_requests_segment", "contact_requests", ["segment"])


def downgrade():
    op.drop_table("contact_requests")
