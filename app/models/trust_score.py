import uuid
from datetime import datetime

from sqlalchemy import Float, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import UUIDType


class TrustScore(Base):
    __tablename__ = "trust_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(), primary_key=True, default=uuid.uuid4
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, comment="Global 0.0–1.0")
    source_score: Mapped[float] = mapped_column(Float, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False)
    citation_score: Mapped[float] = mapped_column(Float, nullable=False)
    dataset_score: Mapped[float] = mapped_column(Float, nullable=False)
    scoring_version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="1.0"
    )
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    publication: Mapped["Publication"] = relationship(
        "Publication", back_populates="trust_scores"
    )
