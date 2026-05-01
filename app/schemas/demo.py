import uuid
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


class CitedKPT(BaseModel):
    kpt_id: str
    kpt_status: Literal["certified", "indexed"]
    title: str
    publisher: str | None
    publication_date: str
    doi: str | None
    hash_kpt: str
    trust_score: int | None
    indexation_score: int | None
    source_label: str
    url_kakapo: str


class DemoResult(BaseModel):
    question: str
    mode: Literal["kakapo", "raw"]
    answer_text: str
    cited_kpts: list[CitedKPT]
    tool_calls_count: int
    latency_ms: int
    estimated_cost_usd: float
    input_tokens: int
    output_tokens: int
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DemoQueryRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1000)
    with_kakapo: bool = True


class DemoExportRequest(BaseModel):
    request_id: str
