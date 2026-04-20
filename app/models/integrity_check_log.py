from sqlalchemy import String, ForeignKey, Enum as SAEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUIDType
import enum
import uuid
from datetime import datetime


class IntegrityResult(str, enum.Enum):
    match = "match"
    mismatch = "mismatch"
    not_found = "not_found"


class IntegrityCheckLog(Base):
    __tablename__ = "integrity_check_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    kpt_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, ForeignKey("kpts.id"), nullable=True, index=True)
    requester_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    submitted_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[IntegrityResult] = mapped_column(
        SAEnum(IntegrityResult, name="integrity_result"), nullable=False, index=True
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
