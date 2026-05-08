import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUIDType


class VOPartyType(str, enum.Enum):
    scientist = "scientist"
    editor = "editor"
    institution = "institution"


class VOTransaction(Base):
    __tablename__ = "vo_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("publications.id"), nullable=False, index=True)
    kpt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    question: Mapped[str] = mapped_column(String(1000), nullable=False)
    consumer_segment: Mapped[str] = mapped_column(String(50), nullable=False, default="demo")
    total_amount_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0.40)
    kakapo_amount_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0.16)
    party_amount_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0.24)
    party_type: Mapped[VOPartyType] = mapped_column(SAEnum(VOPartyType, name="vo_party_type"), nullable=False, default=VOPartyType.scientist)
    party_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    publication: Mapped["Publication"] = relationship("Publication")
