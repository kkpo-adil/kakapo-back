import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator


class PublicationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    abstract: str | None = None
    source: str | None = Field(
        None, description="hal | arxiv | direct | other"
    )
    doi: str | None = None
    authors_raw: Any | None = Field(
        None, description="List of author objects or raw string"
    )
    institution_raw: str | None = None
    submitted_at: datetime | None = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str | None) -> str | None:
        allowed = {"hal", "arxiv", "direct", "other", None}
        if v is not None and v not in allowed:
            raise ValueError(f"source must be one of {allowed - {None}}")
        return v


class PublicationRead(BaseModel):
    id: uuid.UUID
    title: str
    abstract: str | None
    source: str | None
    file_path: str | None
    file_hash: str | None
    doi: str | None
    authors_raw: Any | None
    institution_raw: str | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    kpt_status: str = "certified"
    source_origin: str = "direct_deposit"
    hal_id: str | None = None
    opted_out_at: datetime | None = None

    model_config = {"from_attributes": True}


class PublicationList(BaseModel):
    total: int
    items: list[PublicationRead]
