import uuid
from datetime import datetime
from pydantic import BaseModel


class TrustScoreRead(BaseModel):
    id: uuid.UUID
    publication_id: uuid.UUID
    score: float
    source_score: float
    completeness_score: float
    freshness_score: float
    citation_score: float
    dataset_score: float
    scoring_version: str
    scored_at: datetime

    model_config = {"from_attributes": True}
