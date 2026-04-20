import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class KPTIssueRequest(BaseModel):
    publication_id: uuid.UUID
    orcid_authors: list[str] | None = Field(
        None, description="List of ORCID URIs for each author"
    )
    ror_institution: str | None = Field(
        None, description="ROR identifier for the institution"
    )
    dataset_hashes: list[str] | None = Field(
        None, description="SHA-256 hashes of associated datasets"
    )


class KPTRead(BaseModel):
    id: uuid.UUID
    kpt_id: str
    publication_id: uuid.UUID
    content_hash: str
    version: int
    status: str
    issued_at: datetime
    metadata_json: dict[str, Any] | None

    model_config = {"from_attributes": True}


class KPTVerifyResponse(BaseModel):
    valid: bool
    kpt_id: str
    status: str
    content_hash: str
    stored_hash: str
    message: str


class KPTStatusUpdate(BaseModel):
    status: str = Field(..., description="challenged | revoked | superseded")

    def validate_status(self) -> None:
        allowed = {"challenged", "revoked", "superseded"}
        if self.status not in allowed:
            raise ValueError(f"status must be one of {allowed}")
