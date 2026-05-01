import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.publication import Publication
from app.models.kpt import KPT
from app.services.hal_ingestor import ingest_batch, IngestReport

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["Ingest"])

ADMIN_TOKEN = os.environ.get("KAKAPO_ADMIN_TOKEN", "")


def require_admin(x_admin_token: str = Header(...)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Admin token invalide")


class IngestRequest(BaseModel):
    query: str
    max_results: int = 1000
    domains: list[str] | None = None
    year_from: int | None = None
    year_to: int | None = None


class IngestReportResponse(BaseModel):
    total_fetched: int
    total_created: int
    total_skipped_existing: int
    total_failed: int
    errors: list[str]
    duration_seconds: float


@router.post("/hal", response_model=IngestReportResponse)
def ingest_hal(body: IngestRequest, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    report = ingest_batch(
        db=db,
        query=body.query,
        max_results=body.max_results,
        domains=body.domains,
        year_from=body.year_from,
        year_to=body.year_to,
    )
    return IngestReportResponse(**report.__dict__)


@router.get("/hal/status")
def ingest_status(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    total_indexed = db.query(func.count(Publication.id)).filter(Publication.kpt_status == "indexed").scalar()
    total_certified = db.query(func.count(Publication.id)).filter(Publication.kpt_status == "certified").scalar()

    domain_rows = (
        db.query(Publication.institution_raw, func.count(Publication.id))
        .filter(Publication.kpt_status == "indexed")
        .group_by(Publication.institution_raw)
        .order_by(func.count(Publication.id).desc())
        .limit(5)
        .all()
    )

    return {
        "total_indexed_publications": total_indexed,
        "total_certified_publications": total_certified,
        "last_ingestion_at": datetime.now(timezone.utc).isoformat(),
        "top_5_domains_indexed": [{"domain": r[0], "count": r[1]} for r in domain_rows],
    }

@router.post("/seed-certified")
def seed_certified_publications(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    import sys
    sys.path.insert(0, "/app")
    from scripts.seed_certified import seed
    seed(db)
    from sqlalchemy import func as sqlfunc
    total = db.query(sqlfunc.count(Publication.id)).filter(Publication.kpt_status == "certified").scalar()
    return {"status": "ok", "certified_total": total}
