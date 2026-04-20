from sqlalchemy import String, Numeric, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUIDType
import enum
import uuid
from datetime import datetime


class PublisherStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    terminated = "terminated"


class ContractType(str, enum.Enum):
    prepaid = "prepaid"
    deferred = "deferred"
    revenue_share_only = "revenue_share_only"


class Publisher(Base):
    __tablename__ = "publishers"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[PublisherStatus] = mapped_column(
        SAEnum(PublisherStatus, name="publisher_status"), default=PublisherStatus.active, nullable=False
    )
    contract_type: Mapped[ContractType] = mapped_column(
        SAEnum(ContractType, name="contract_type"), default=ContractType.revenue_share_only, nullable=False
    )
    revenue_share_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=30.0, nullable=False)
    kpt_unit_cost: Mapped[float] = mapped_column(Numeric(10, 4), default=0.15, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    publications: Mapped[list["PublicationV2"]] = relationship("PublicationV2", back_populates="publisher")
    balance: Mapped["PublisherBalance"] = relationship("PublisherBalance", back_populates="publisher", uselist=False)
