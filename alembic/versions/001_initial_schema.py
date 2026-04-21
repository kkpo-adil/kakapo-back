from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("publishers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("contract_type", sa.String(50), nullable=False, server_default="revenue_share_only"),
        sa.Column("revenue_share_pct", sa.Numeric(5, 2), nullable=False, server_default="30.0"),
        sa.Column("kpt_unit_cost", sa.Numeric(10, 4), nullable=False, server_default="0.15"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_publishers_slug", "publishers", ["slug"], unique=True)
    op.create_table("publications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("doi", sa.String(255), nullable=False, unique=True),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("journal", sa.String(500), nullable=True),
        sa.Column("publisher_id", sa.String(36), sa.ForeignKey("publishers.id"), nullable=False),
        sa.Column("publication_type", sa.String(50), nullable=False, server_default="journal_article"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed_at_crossref", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retraction_status", sa.String(50), nullable=False, server_default="none"),
        sa.Column("retracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retraction_source", sa.String(500), nullable=True),
    )
    op.create_index("ix_publications_doi", "publications", ["doi"], unique=True)
    op.create_table("kpts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("publication_id", sa.String(36), sa.ForeignKey("publications.id"), nullable=False),
        sa.Column("doi", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("certified_by", sa.String(255), nullable=True),
        sa.Column("payment_status", sa.String(50), nullable=False, server_default="paid"),
        sa.Column("cost_amount", sa.Numeric(10, 4), nullable=False, server_default="0.15"),
        sa.Column("superseded_by_id", sa.String(36), sa.ForeignKey("kpts.id"), nullable=True),
        sa.Column("supersedes_id", sa.String(36), sa.ForeignKey("kpts.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(500), nullable=True),
        sa.Column("revocation_source", sa.String(500), nullable=True),
        sa.Column("preprint_published_version_id", sa.String(36), sa.ForeignKey("kpts.id"), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.CheckConstraint("version >= 1", name="ck_kpt_version_positive"),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_kpt_score_range"),
    )
    op.create_index("ix_kpts_content_hash", "kpts", ["content_hash"])
    op.create_index("ix_kpts_doi", "kpts", ["doi"])
    op.create_index("ix_kpts_publication_id", "kpts", ["publication_id"])
    op.create_index("ix_kpts_status", "kpts", ["status"])
    op.create_table("trust_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("publication_id", sa.String(36), sa.ForeignKey("publications.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("source_score", sa.Integer(), nullable=True),
        sa.Column("completeness_score", sa.Integer(), nullable=True),
        sa.Column("freshness_score", sa.Integer(), nullable=True),
        sa.Column("citation_score", sa.Integer(), nullable=True),
        sa.Column("dataset_score", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table("publication_relations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("publications.id"), nullable=False),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("publications.id"), nullable=False),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table("publisher_balances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("publisher_id", sa.String(36), sa.ForeignKey("publishers.id"), nullable=False, unique=True),
        sa.Column("kpt_costs_pending", sa.Numeric(12, 4), nullable=False, server_default="0.0"),
        sa.Column("revenue_generated", sa.Numeric(12, 4), nullable=False, server_default="0.0"),
        sa.Column("revenue_share_paid", sa.Numeric(12, 4), nullable=False, server_default="0.0"),
        sa.Column("last_settlement_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table("integrity_check_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kpt_id", sa.String(36), sa.ForeignKey("kpts.id"), nullable=True),
        sa.Column("requester_id", sa.String(36), nullable=True),
        sa.Column("submitted_hash", sa.String(64), nullable=False),
        sa.Column("expected_hash", sa.String(64), nullable=True),
        sa.Column("result", sa.String(50), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index("ix_integrity_check_logs_kpt_id", "integrity_check_logs", ["kpt_id"])
    op.create_index("ix_integrity_check_logs_result", "integrity_check_logs", ["result"])


def downgrade():
    op.drop_table("integrity_check_logs")
    op.drop_table("publisher_balances")
    op.drop_table("publication_relations")
    op.drop_table("trust_scores")
    op.drop_table("kpts")
    op.drop_table("publications")
    op.drop_table("publishers")
