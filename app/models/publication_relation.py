import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUIDType


class PublicationRelation(Base):
    __tablename__ = "publication_relations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(), nullable=False, index=True,
        comment="UUID de la publication cible — peut ne pas être dans KAKAPO"
    )
    target_doi: Mapped[str | None] = mapped_column(
        String(256), nullable=True, index=True,
        comment="DOI de la cible pour résolution future"
    )
    target_title: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="Titre déclaré si la cible n'est pas certifiée"
    )
    relation_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="cites",
        comment="cites | extends | contradicts | replicates"
    )
    target_certified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True si target_id correspond à une publication certifiée dans KAKAPO"
    )
    declared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source: Mapped["Publication"] = relationship(  # noqa: F821
        "Publication", foreign_keys=[source_id], back_populates="relations_out"
    )
