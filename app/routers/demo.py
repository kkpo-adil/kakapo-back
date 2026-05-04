import os
import hashlib
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from cachetools import TTLCache
from app.database import get_db
from app.routers.ingest import require_admin
from app.schemas.demo import DemoQueryRequest, DemoExportRequest, DemoResult
from app.services import demo_orchestrator, pdf_export

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demo", tags=["Demo"])

_cache: TTLCache = TTLCache(maxsize=256, ttl=300)
_rate_limit: dict = {}
RATE_LIMIT = int(os.environ.get("DEMO_RATE_LIMIT_PER_MINUTE", "10"))


def _check_rate_limit(ip: str):
    now = time.time()
    window = _rate_limit.get(ip, [])
    window = [t for t in window if now - t < 60]
    if len(window) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit atteint. Réessayez dans une minute.")
    window.append(now)
    _rate_limit[ip] = window


def _cache_key(question: str, with_kakapo: bool) -> str:
    return hashlib.sha256(f"{question}|{with_kakapo}".encode()).hexdigest()


@router.get("/health")
def demo_health(db: Session = Depends(get_db)):
    from app.models.publication import Publication
    from sqlalchemy import func as sqlfunc
    anthropic_ok = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    try:
        catalog_size = db.query(sqlfunc.count(Publication.id)).scalar()
        db_ok = True
    except Exception:
        db_ok = False
        catalog_size = 0
    return {
        "anthropic_ok": anthropic_ok,
        "db_ok": db_ok,
        "catalog_size": catalog_size,
        "ready_for_demo": anthropic_ok and db_ok and catalog_size > 0,
    }


@router.post("/query", response_model=DemoResult)
def demo_query(body: DemoQueryRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    key = _cache_key(body.question, body.with_kakapo)
    if key in _cache:
        logger.info(f"Cache hit for question: {body.question[:50]}")
        return _cache[key]

    result = demo_orchestrator.run_demo_query(
        db=db,
        question=body.question,
        with_kakapo=body.with_kakapo,
    )
    _cache[key] = result
    return result


@router.post("/export")
def demo_export(body: DemoExportRequest, db: Session = Depends(get_db)):
    matched = None
    for cached in _cache.values():
        if isinstance(cached, DemoResult) and cached.request_id == body.request_id:
            matched = cached
            break

    if not matched:
        raise HTTPException(status_code=404, detail="Session expirée ou introuvable. Relancez la démo.")

    pdf_bytes, info = pdf_export.generate_signed_pdf(matched)

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{info.filename}"'},
    )

@router.post("/clear-cache")
def clear_cache(_: str = Depends(require_admin)):
    _cache.clear()
    return {"status": "ok", "message": "Cache cleared"}
