"""add search indexes

Revision ID: 012
Revises: 011
"""
from alembic import op
import sqlalchemy as sa

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    try:
        op.create_index('ix_pub_title_trgm', 'publications', ['title'], postgresql_using='gin',
            postgresql_ops={'title': 'gin_trgm_ops'})
    except Exception:
        pass
    try:
        op.create_index('ix_pub_kpt_status', 'publications', ['kpt_status'])
    except Exception:
        pass
    try:
        op.create_index('ix_pub_source_origin', 'publications', ['source_origin'])
    except Exception:
        pass


def downgrade():
    try:
        op.drop_index('ix_pub_title_trgm')
    except Exception:
        pass
