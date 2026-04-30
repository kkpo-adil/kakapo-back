from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str, bind) -> bool:
    inspector = sa.inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def _index_exists(name: str, bind) -> bool:
    inspector = sa.inspect(bind)
    for table in inspector.get_table_names():
        for idx in inspector.get_indexes(table):
            if idx["name"] == name:
                return True
    return False


def upgrade():
    bind = op.get_bind()

    if not _column_exists("publications", "kpt_status", bind):
        op.add_column("publications", sa.Column("kpt_status", sa.String(16), nullable=False, server_default="certified"))
    if not _column_exists("publications", "source_origin", bind):
        op.add_column("publications", sa.Column("source_origin", sa.String(64), nullable=False, server_default="direct_deposit"))
    if not _column_exists("publications", "hal_id", bind):
        op.add_column("publications", sa.Column("hal_id", sa.String(64), nullable=True))
    if not _column_exists("publications", "opted_out_at", bind):
        op.add_column("publications", sa.Column("opted_out_at", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists("kpts", "is_indexed", bind):
        op.add_column("kpts", sa.Column("is_indexed", sa.Boolean, nullable=False, server_default="false"))
    if not _column_exists("trust_scores", "is_indexation_score", bind):
        op.add_column("trust_scores", sa.Column("is_indexation_score", sa.Boolean, nullable=False, server_default="false"))

    if not _index_exists("ix_publications_kpt_status", bind):
        op.create_index("ix_publications_kpt_status", "publications", ["kpt_status"])
    if not _index_exists("ix_publications_source_origin", bind):
        op.create_index("ix_publications_source_origin", "publications", ["source_origin"])
    if not _index_exists("ix_publications_hal_id", bind):
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
