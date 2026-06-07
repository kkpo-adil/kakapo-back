import os
import hashlib
import logging
import time
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from cachetools import TTLCache
from app.database import get_db
from app.routers.ingest import require_admin
from app.schemas.demo import DemoQueryRequest, DemoExportRequest, DemoResult
from app.services import demo_orchestrator, pdf_export

logger = logging.getLogger(__name__)
_async_jobs: dict = {}
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
    try:
        from sqlalchemy import inspect as sqlinspect
        inspector = sqlinspect(db.bind)
        has_ct = 'clinical_trials' in inspector.get_table_names()
        if has_ct:
            from sqlalchemy import text as sqlt
            ct_size = db.execute(sqlt('SELECT COUNT(*) FROM clinical_trials')).scalar() or 0
        else:
            ct_size = 0
    except Exception:
        ct_size = 0
    return {
        "anthropic_ok": anthropic_ok,
        "db_ok": db_ok,
        "catalog_size": catalog_size,
        "clinical_trials_size": ct_size,
        "total_size": catalog_size + ct_size,
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


@router.post("/query/stream")
def demo_query_stream(body: DemoQueryRequest, request: Request, db: Session = Depends(get_db)):
    import json as _json
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    def event_generator():
        try:
            for ev in demo_orchestrator.run_demo_query_stream(db=db, question=body.question):
                name = ev.get("event", "message")
                payload = _json.dumps(ev.get("data", {}), default=str)
                yield f"event: {name}\ndata: {payload}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            err = _json.dumps({"message": str(e)})
            yield f"event: error\ndata: {err}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


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

@router.post("/query/async")
async def demo_query_async(
    body: DemoQueryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    import uuid as _uuid
    job_id = str(_uuid.uuid4())
    _async_jobs[job_id] = {"status": "processing", "result": None}
    
    async def run():
        try:
            result = await orchestrator.run_demo_query(
                question=body.question,
                with_kakapo=body.with_kakapo,
                db=db,
            )
            _async_jobs[job_id] = {"status": "done", "result": result.model_dump()}
        except Exception as e:
            _async_jobs[job_id] = {"status": "error", "error": str(e)}
    
    background_tasks.add_task(run)
    return {"job_id": job_id, "status": "processing"}


@router.get("/query/async/{job_id}")
def demo_query_result(job_id: str):
    job = _async_jobs.get(job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/stream")
def demo_stream(db: Session = Depends(get_db)):
    from sqlalchemy import text as sqlt
    try:
        recent_ct = db.execute(sqlt("""
            SELECT nct_id, theme, kpt_id, title,
                   EXTRACT(EPOCH FROM (NOW() - ingested_at))::int as secs_ago
            FROM clinical_trials
            WHERE ingested_at IS NOT NULL
            ORDER BY ingested_at DESC
            LIMIT 5
        """)).all()
        ct_items = [
            {
                "type": "trial",
                "ref": r[0],
                "label": r[1] or "other",
                "nct_id": r[0],
                "theme": r[1],
                "kpt_id": r[2],
                "title": r[3][:60] if r[3] else "",
                "secs_ago": int(r[4]) if r[4] is not None else 0,
            }
            for r in recent_ct
        ]
        recent_pub = db.execute(sqlt("""
            SELECT
                COALESCE(NULLIF(p.doi, ''), p.hal_id, SUBSTRING(p.id::text FROM 1 FOR 18)) as ref,
                p.source as label,
                k.kpt_id,
                p.title,
                EXTRACT(EPOCH FROM (NOW() - p.created_at))::int as secs_ago
            FROM publications p
            JOIN kpts k ON k.publication_id = p.id
            WHERE p.created_at IS NOT NULL
              AND p.created_at > NOW() - INTERVAL '7 days'
            ORDER BY p.created_at DESC
            LIMIT 5
        """)).all()
        pub_items = [
            {
                "type": "publication",
                "ref": r[0] or "",
                "label": r[1] or "",
                "nct_id": r[0] or "",
                "theme": r[1] or "",
                "kpt_id": r[2],
                "title": r[3][:60] if r[3] else "",
                "secs_ago": int(r[4]) if r[4] is not None else 0,
            }
            for r in recent_pub
        ]
        recent = sorted(ct_items + pub_items, key=lambda x: x["secs_ago"])[:10]
    except Exception:
        recent = []
    try:
        theme_rows = db.execute(sqlt("""
            SELECT theme, COUNT(*) as n FROM clinical_trials
            WHERE theme IS NOT NULL
            GROUP BY theme ORDER BY n DESC LIMIT 6
        """)).all()
        themes = [{"theme": r[0], "count": int(r[1])} for r in theme_rows]
        total = sum(t["count"] for t in themes)
        for t in themes:
            t["pct"] = round(100 * t["count"] / total) if total > 0 else 0
    except Exception:
        themes = []
    try:
        catalog = db.execute(sqlt("SELECT COUNT(*) FROM publications")).scalar() or 0
        trials = db.execute(sqlt("SELECT COUNT(*) FROM clinical_trials")).scalar() or 0
    except Exception:
        catalog = 0
        trials = 0
    try:
        source_rows = db.execute(sqlt("""
            SELECT source, COUNT(*) as n FROM publications
            WHERE source IS NOT NULL
            GROUP BY source ORDER BY n DESC LIMIT 10
        """)).all()
        sources = [{"source": r[0], "count": int(r[1])} for r in source_rows]
        total_src = sum(s["count"] for s in sources)
        for sd in sources:
            sd["pct"] = round(100 * sd["count"] / total_src) if total_src > 0 else 0
    except Exception:
        sources = []
    try:
        theme_total = sum(t["count"] for t in themes) if themes else 0
    except Exception:
        theme_total = 0
    return {
        "recent": recent,
        "themes": themes,
        "themes_total": theme_total,
        "sources": sources,
        "catalog_size": catalog,
        "trials_size": trials,
        "total_size": catalog + trials,
    }

@router.get("/kpt/{kpt_id}")
def demo_kpt_detail(kpt_id: str, db: Session = Depends(get_db)):
    from sqlalchemy import text as sqlt
    row = db.execute(sqlt("""
        SELECT
            k.kpt_id, k.content_hash, k.version, k.status, k.issued_at,
            p.id, p.title, p.abstract, p.authors_raw, p.doi,
            p.institution_raw, p.submitted_at, p.kpt_status, p.source_origin,
            p.integrity_status, p.last_verified_at,
            p.fp_identity, p.fp_metadata, p.fp_content, p.fp_references,
            p.fp_canonical, p.fp_content_length, p.fp_word_count,
            p.fp_computed_at, p.fp_spec_version,
            ts.score, ts.is_indexation_score
        FROM kpts k
        JOIN publications p ON p.id = k.publication_id
        LEFT JOIN trust_scores ts ON ts.publication_id = p.id
        WHERE k.kpt_id = :kid
        LIMIT 1
    """), {"kid": kpt_id}).first()

    if not row:
        raise HTTPException(status_code=404, detail="KPT introuvable dans le catalog Oparence.")

    authors_raw = row[8] or ""
    try:
        import json as _json
        parsed = _json.loads(authors_raw) if isinstance(authors_raw, str) and authors_raw.strip().startswith("[") else None
        authors = parsed if isinstance(parsed, list) else [a.strip() for a in str(authors_raw).split(",") if a.strip()]
    except Exception:
        authors = [a.strip() for a in str(authors_raw).split(",") if a.strip()]

    score_val = row[25]
    is_idx = row[26]
    trust_score = int(round(score_val * 100)) if score_val is not None and not is_idx else None
    indexation_score = int(round(score_val * 100)) if score_val is not None and is_idx else None

    has_fp = row[20] is not None

    return {
        "kpt_id": row[0],
        "content_hash": row[1],
        "version": row[2],
        "status": row[3],
        "issued_at": row[4].isoformat() if row[4] else None,
        "publication_id": str(row[5]),
        "title": row[6],
        "abstract": (row[7] or "")[:1200] if row[7] else None,
        "authors": authors[:12],
        "doi": row[9],
        "publisher": row[10],
        "publication_date": row[11].strftime("%Y-%m-%d") if row[11] else None,
        "kpt_status": row[12],
        "source_origin": row[13],
        "trust_score": trust_score,
        "indexation_score": indexation_score,
        "integrity_status": row[14],
        "last_verified_at": row[15].isoformat() if row[15] else None,
        "fingerprint": {
            "available": has_fp,
            "spec_version": row[24],
            "computed_at": row[23].isoformat() if row[23] else None,
            "zones": {
                "identity": row[16],
                "metadata": row[17],
                "content": row[18],
                "references": row[19],
            },
            "canonical": row[20],
            "content_length": row[21],
            "word_count": row[22],
        },
    }


@router.get("/integrity/verify/{kpt_id}")
def integrity_verify(kpt_id: str, db: Session = Depends(get_db)):
    from app.services.integrity_checker import verify_kpt
    return verify_kpt(db, kpt_id, triggered_by="api_manual")


@router.post("/integrity/recrawl")
def integrity_recrawl(batch_size: int = 50, db: Session = Depends(get_db)):
    from app.services.integrity_checker import recrawl_batch
    return recrawl_batch(db, batch_size=batch_size, max_age_hours=24)


@router.get("/integrity/summary")
def integrity_summary(db: Session = Depends(get_db)):
    from app.services.integrity_checker import get_integrity_summary
    return get_integrity_summary(db)
