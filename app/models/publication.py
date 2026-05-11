import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import UUIDType


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="hal | arxiv | direct | other"
    )
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="SHA-256 hex"
    )
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    authors_raw: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of author objects"
    )
    institution_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    kpt_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="certified", index=True)
    source_origin: Mapped[str] = mapped_column(String(64), nullable=False, server_default="direct_deposit", index=True)
    hal_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, unique=True)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    keywords_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of keywords from source")
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Full text content of the publication")
    references_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of structured references")
    citations_count: Mapped[int | None] = mapped_column(nullable=True, comment="Number of citations")
    downloads_count: Mapped[int | None] = mapped_column(nullable=True, comment="Number of downloads")
    views_count: Mapped[int | None] = mapped_column(nullable=True, comment="Number of views")
    altmetric_score: Mapped[float | None] = mapped_column(nullable=True, comment="Altmetric attention score")
    impact_factor: Mapped[float | None] = mapped_column(nullable=True, comment="Journal impact factor")
    mesh_terms_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of MeSH terms")
    concepts_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of OpenAlex concepts with scores")
    funding_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of funding sources")
    orcid_authors_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of authors with ORCID")
    license: Mapped[str | None] = mapped_column(nullable=True, comment="Publication license e.g. CC-BY-4.0")
    language: Mapped[str | None] = mapped_column(nullable=True, comment="Publication language")
    article_type: Mapped[str | None] = mapped_column(nullable=True, comment="Article type: RCT, review, case report, etc.")
    figures_count: Mapped[int | None] = mapped_column(nullable=True, comment="Number of figures")
    tables_count: Mapped[int | None] = mapped_column(nullable=True, comment="Number of tables")
    supplementary_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON array of supplementary materials URLs")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    kpts: Mapped[list["KPT"]] = relationship(
        "KPT", back_populates="publication", cascade="all, delete-orphan"
    )
    trust_scores: Mapped[list["TrustScore"]] = relationship(
        "TrustScore", back_populates="publication", cascade="all, delete-orphan"
    )


    relations_out: Mapped[list["PublicationRelation"]] = relationship(  # noqa: F821
        "PublicationRelation",
        foreign_keys="PublicationRelation.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
