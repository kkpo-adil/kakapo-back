import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.publisher import PublisherStatus, ContractType


class PublisherCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    contract_type: ContractType = ContractType.revenue_share_only
    revenue_share_pct: float = Field(30.0, ge=0, le=100)
    kpt_unit_cost: float = Field(0.15, ge=0)


class PublisherUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    status: PublisherStatus | None = None
    contract_type: ContractType | None = None
    revenue_share_pct: float | None = Field(None, ge=0, le=100)
    kpt_unit_cost: float | None = Field(None, ge=0)


class PublisherRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: PublisherStatus
    contract_type: ContractType
    revenue_share_pct: float
    kpt_unit_cost: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PublisherBalanceRead(BaseModel):
    id: uuid.UUID
    publisher_id: uuid.UUID
    kpt_costs_pending: float
    revenue_generated: float
    revenue_share_paid: float
    revenue_share_pending: float
    last_settlement_at: datetime | None

    model_config = {"from_attributes": True}
