import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, Boolean, DateTime, Enum as SAEnum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUIDType


class ReviewFlag(str, enum.Enum):
    none = "none"
    non_reproducible = "non_reproducible"
    missing_data = "missing_data"
    conflict_of_interest = "conflict_of_interest"
    suspected_duplicate = "suspected_duplicate"


class ScientificReview(Base):
    __tablename__ = "scientific_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("publications.id"), nullable=False, index=True)
    reviewer_orcid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reviewer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewer_institution: Mapped[str | None] = mapped_column(String(255), nullable=True)

    methodology_score: Mapped[int] = mapped_column(Integer, nullable=False)
    data_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reproducibility_score: Mapped[int] = mapped_column(Integer, nullable=False)
    clarity_score: Mapped[int] = mapped_column(Integer, nullable=False)

    global_score: Mapped[float] = mapped_column(Float, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    flag: Mapped[ReviewFlag] = mapped_column(SAEnum(ReviewFlag, name="review_flag"), default=ReviewFlag.none, nullable=False)

    is_conflict_of_interest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_same_institution: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
