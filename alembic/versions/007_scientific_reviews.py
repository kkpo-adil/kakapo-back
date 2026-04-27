from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("scientific_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("publication_id", sa.String(36), sa.ForeignKey("publications.id"), nullable=False),
        sa.Column("reviewer_orcid", sa.String(64), nullable=False),
        sa.Column("reviewer_name", sa.String(255), nullable=False),
        sa.Column("reviewer_institution", sa.String(255), nullable=True),
        sa.Column("methodology_score", sa.Integer, nullable=False),
        sa.Column("data_score", sa.Integer, nullable=False),
        sa.Column("reproducibility_score", sa.Integer, nullable=False),
        sa.Column("clarity_score", sa.Integer, nullable=False),
        sa.Column("global_score", sa.Float, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("flag", sa.String(50), nullable=False, server_default="none"),
        sa.Column("is_conflict_of_interest", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_same_institution", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scientific_reviews_publication_id", "scientific_reviews", ["publication_id"])
    op.create_index("ix_scientific_reviews_reviewer_orcid", "scientific_reviews", ["reviewer_orcid"])


def downgrade():
    op.drop_table("scientific_reviews")
