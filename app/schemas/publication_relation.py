import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class RelationCreate(BaseModel):
    target_id: uuid.UUID | None = None
    target_doi: str | None = None
    target_title: str | None = None
    relation_type: str = Field("cites", description="cites | extends | contradicts | replicates")


class RelationRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    target_doi: str | None
    target_title: str | None
    relation_type: str
    target_certified: bool
    declared_at: datetime

    model_config = {"from_attributes": True}


class RelatedPublication(BaseModel):
    id: str
    title: str | None
    doi: str | None
    relation_type: str
    certified: bool
    trust_score: float | None = None
