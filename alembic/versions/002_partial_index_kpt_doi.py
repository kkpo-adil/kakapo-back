from alembic import op

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE UNIQUE INDEX uq_kpt_doi_active
        ON kpts (doi)
        WHERE status IN ('active', 'active_preprint')
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_kpt_doi_active")
