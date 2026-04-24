import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Numeric, DateTime, Enum as SAEnum, Integer, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUIDType
import enum


class QueryResult(str, enum.Enum):
    match = "match"
    mismatch = "mismatch"
    not_found = "not_found"
    error = "error"


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    ai_client_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("ai_client_profiles.id"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    doi_queried: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kpt_id_returned: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[QueryResult] = mapped_column(SAEnum(QueryResult, name="query_result"), nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_cached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    billed_amount: Mapped[float] = mapped_column(Numeric(10, 8), default=0.0, nullable=False)
    queried_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ai_client: Mapped["AIClientProfile"] = relationship("AIClientProfile", back_populates="query_logs")
