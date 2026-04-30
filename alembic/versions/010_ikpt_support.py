from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("publications", sa.Column("kpt_status", sa.String(16), nullable=False, server_default="certified"))
    op.add_column("publications", sa.Column("source_origin", sa.String(64), nullable=False, server_default="direct_deposit"))
    op.add_column("publications", sa.Column("hal_id", sa.String(64), nullable=True))
    op.add_column("publications", sa.Column("opted_out_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kpts", sa.Column("is_indexed", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("trust_scores", sa.Column("is_indexation_score", sa.Boolean, nullable=False, server_default="false"))

    op.create_index("ix_publications_kpt_status", "publications", ["kpt_status"])
    op.create_index("ix_publications_source_origin", "publications", ["source_origin"])
    op.create_index("ix_publications_hal_id", "publications", ["hal_id"], unique=True,
                    postgresql_where=sa.text("hal_id IS NOT NULL"))


def downgrade():
    op.drop_index("ix_publications_hal_id", "publications")
    op.drop_index("ix_publications_source_origin", "publications")
    op.drop_index("ix_publications_kpt_status", "publications")
    op.drop_column("trust_scores", "is_indexation_score")
    op.drop_column("kpts", "is_indexed")
    op.drop_column("publications", "opted_out_at")
    op.drop_column("publications", "hal_id")
    op.drop_column("publications", "source_origin")
    op.drop_column("publications", "kpt_status")
