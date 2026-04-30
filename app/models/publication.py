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
