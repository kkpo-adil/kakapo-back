import uuid
import secrets
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Numeric, DateTime, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUIDType
import enum


class PlanType(str, enum.Enum):
    starter_llm = "starter_llm"
    scale_llm = "scale_llm"
    enterprise_llm = "enterprise_llm"
    compliance_starter = "compliance_starter"
    compliance_pro = "compliance_pro"
    compliance_enterprise = "compliance_enterprise"


class OveragePolicy(str, enum.Enum):
    graceful = "graceful"
    rate_limit = "rate_limit"


PLAN_QUOTAS = {
    PlanType.starter_llm: 50_000_000,
    PlanType.scale_llm: 200_000_000,
    PlanType.enterprise_llm: -1,
    PlanType.compliance_starter: 100_000,
    PlanType.compliance_pro: 500_000,
    PlanType.compliance_enterprise: -1,
}

PLAN_PRICES = {
    PlanType.starter_llm: 0.0004,
    PlanType.scale_llm: 0.0003,
    PlanType.enterprise_llm: 0.0001,
    PlanType.compliance_starter: 0.002,
    PlanType.compliance_pro: 0.0015,
    PlanType.compliance_enterprise: 0.001,
}


class AIClientProfile(Base):
    __tablename__ = "ai_client_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    api_key: Mapped[str] = mapped_column(String(72), nullable=False, unique=True, index=True)
    plan_type: Mapped[PlanType] = mapped_column(SAEnum(PlanType, name="plan_type"), default=PlanType.compliance_starter, nullable=False)
    monthly_quota: Mapped[int] = mapped_column(Integer, default=100_000, nullable=False)
    quota_used_current_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overage_policy: Mapped[OveragePolicy] = mapped_column(SAEnum(OveragePolicy, name="overage_policy"), default=OveragePolicy.graceful, nullable=False)
    price_per_query: Mapped[float] = mapped_column(Numeric(10, 6), default=0.002, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    query_logs: Mapped[list["QueryLog"]] = relationship("QueryLog", back_populates="ai_client")

    @staticmethod
    def generate_api_key() -> str:
        return "kk_" + secrets.token_hex(32)
