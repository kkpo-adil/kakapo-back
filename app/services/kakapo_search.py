import logging
from typing import Literal
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text, or_
from app.models.publication import Publication
from app.models.kpt import KPT
from app.models.trust_score import TrustScore

logger = logging.getLogger(__name__)

API_BASE_URL = "https://kakapo-front.vercel.app"


class SearchResult(BaseModel):
    publication_id: str
    kpt_id: str
    kpt_status: str
    source_origin: str
    title: str
    abstract: str | None
    authors: list[str]
    doi: str | None
    publisher: str | None
    publication_date: str
    hash_kpt: str
    trust_score: int | None
    indexation_score: int | None
    hal_id: str | None
    source_label: str
    url_kakapo: str

    model_config = {"from_attributes": True}


def search(
    db: Session,
    query: str,
    limit: int = 5,
    kpt_status_filter: Literal["certified", "indexed", "all"] = "all",
    min_score: int = 0,
) -> list[SearchResult]:

    tsquery = " & ".join(query.strip().split()[:5])

    sql = text("""
        SELECT
            p.id, p.title, p.abstract, p.authors_raw, p.doi,
            p.institution_raw, p.submitted_at, p.kpt_status,
            p.source_origin, p.hal_id,
            k.kpt_id, k.content_hash,
            ts.score, ts.is_indexation_score,
            ts_rank(
                to_tsvector('english', coalesce(p.title,'') || ' ' || coalesce(p.abstract,'')),
                to_tsquery('english', :tsquery)
            ) as rank
        FROM publications p
        JOIN kpts k ON k.publication_id = p.id
        LEFT JOIN trust_scores ts ON ts.publication_id = p.id
        WHERE p.opted_out_at IS NULL
        AND (:status_filter = 'all' OR p.kpt_status = :status_filter)
        AND to_tsvector('english', coalesce(p.title,'') || ' ' || coalesce(p.abstract,''))
            @@ to_tsquery('english', :tsquery)
        ORDER BY
            (p.kpt_status = 'certified') DESC,
            rank DESC,
            ts.score DESC NULLS LAST
        LIMIT :limit
    """)

    try:
        rows = db.execute(sql, {
            "tsquery": tsquery,
            "status_filter": kpt_status_filter,
            "limit": limit,
        }).fetchall()
    except Exception as e:
        logger.error(f"Full text search failed: {e} - returning empty (no ilike fallback on 14M rows)")
        try:
            db.rollback()
        except Exception:
            pass
        return []
        orm_rows = []
        results = []
        for pub, kpt, ts in orm_rows:
            authors_raw = pub.authors_raw or ""
            authors = [a.strip() for a in str(authors_raw).split(",") if a.strip()][:5]
            date_str = pub.submitted_at.strftime("%Y-%m-%d") if pub.submitted_at else "—"
            results.append(SearchResult(
                publication_id=str(pub.id),
                kpt_id=kpt.kpt_id if kpt else f"IKPT-{str(pub.id)[:8]}",
                kpt_status=pub.kpt_status or "indexed",
                source_origin=pub.source_origin or "direct_deposit",
                title=pub.title or "",
                abstract=(pub.abstract or "")[:500],
                authors=authors,
                doi=pub.doi,
                publisher=pub.institution_raw,
                publication_date=date_str,
                hash_kpt=kpt.content_hash if kpt else "",
                trust_score=None,
                indexation_score=None,
                hal_id=pub.hal_id,
                source_label="KAKAPO certified" if pub.kpt_status == "certified" else "HAL indexed",
                url_kakapo=f"{API_BASE_URL}/publications/{pub.id}",
            ))
        return results

    results = []
    for row in rows:
        authors_raw = row.authors_raw or ""
        if isinstance(authors_raw, list):
            authors = [a.get("name", "") if isinstance(a, dict) else str(a) for a in authors_raw]
        else:
            authors = [a.strip() for a in str(authors_raw).split(",") if a.strip()][:5]

        date_str = row.submitted_at.strftime("%Y-%m-%d") if row.submitted_at else "—"
        score_val = row.score
        is_idx = row.is_indexation_score
        trust_int = int(round(score_val * 100)) if score_val and not is_idx else None
        index_int = int(round(score_val * 100)) if score_val and is_idx else None

        results.append(SearchResult(
            publication_id=str(row.id),
            kpt_id=row.kpt_id if row.kpt_id else f"IKPT-{str(row.id)[:8]}",
            kpt_status=row.kpt_status or "indexed",
            source_origin=row.source_origin or "direct_deposit",
            title=row.title or "",
            abstract=(row.abstract or "")[:500],
            authors=authors,
            doi=row.doi,
            publisher=row.institution_raw,
            publication_date=date_str,
            hash_kpt=row.content_hash if row.content_hash else "",
            trust_score=trust_int,
            indexation_score=index_int,
            hal_id=row.hal_id,
            source_label="KAKAPO certified" if row.kpt_status == "certified" else "HAL indexed",
            url_kakapo=f"{API_BASE_URL}/publications/{row.id}",
        ))

    logger.info(f"KakapoSearch query={query!r} filter={kpt_status_filter} results={len(results)}")
    return results
