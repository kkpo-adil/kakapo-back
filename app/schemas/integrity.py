import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.integrity_check_log import IntegrityResult


class IntegrityVerifyRequest(BaseModel):
    doi: str = Field(..., description="DOI de la publication")
    content_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 du contenu soumis")
    requester_id: uuid.UUID | None = None
    ip_address: str | None = None


class IntegrityVerifyResponse(BaseModel):
    status: IntegrityResult
    message: str
    kpt_id: uuid.UUID | None = None
    version: int | None = None
    score: int | None = None
    certified_at: datetime | None = None

    model_config = {"from_attributes": True}


class IntegrityCheckLogRead(BaseModel):
    id: uuid.UUID
    kpt_id: uuid.UUID | None
    requester_id: uuid.UUID | None
    submitted_hash: str
    expected_hash: str | None
    result: IntegrityResult
    checked_at: datetime
    ip_address: str | None

    model_config = {"from_attributes": True}
