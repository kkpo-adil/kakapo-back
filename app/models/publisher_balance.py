from sqlalchemy import ForeignKey, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUIDType
import uuid
from datetime import datetime


class PublisherBalance(Base):
    __tablename__ = "publisher_balances"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    publisher_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("publishers.id"), unique=True, nullable=False)
    kpt_costs_pending: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0, nullable=False)
    revenue_generated: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0, nullable=False)
    revenue_share_paid: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0, nullable=False)
    last_settlement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    publisher: Mapped["Publisher"] = relationship("Publisher", back_populates="balance")

    @property
    def revenue_share_pending(self) -> float:
        pct = float(self.publisher.revenue_share_pct) if self.publisher else 30.0
        raw = float(self.revenue_generated) * pct / 100 - float(self.kpt_costs_pending)
        return max(0.0, raw)
