from alembic import op

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_publication_doi_active
        ON publications (doi)
        WHERE doi IS NOT NULL
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_publication_doi_active")
