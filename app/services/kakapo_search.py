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
    q = db.query(Publication, KPT, TrustScore).join(
        KPT, KPT.publication_id == Publication.id
    ).outerjoin(
        TrustScore, TrustScore.publication_id == Publication.id
    ).filter(
        Publication.opted_out_at.is_(None)
    )

    if kpt_status_filter != "all":
        q = q.filter(Publication.kpt_status == kpt_status_filter)

    terms = query.strip().split()
    for term in terms[:5]:
        q = q.filter(or_(
            Publication.title.ilike(f"%{term}%"),
            Publication.abstract.ilike(f"%{term}%"),
            Publication.authors_raw.ilike(f"%{term}%"),
        ))

    from sqlalchemy import case as _case
    title_relevance = sum(
        _case((Publication.title.ilike(f"%{t}%"), 1), else_=0)
        for t in terms[:5]
    ) if terms else 0

    q = q.order_by(
        (Publication.kpt_status == "certified").desc(),
        title_relevance.desc(),
        Publication.submitted_at.desc().nulls_last(),
    ).limit(limit)

    rows = q.all()
    results = []
    for pub, kpt, ts in rows:
        authors_raw = pub.authors_raw or ""
        if isinstance(authors_raw, list):
            authors = [a.get("name", "") if isinstance(a, dict) else str(a) for a in authors_raw]
        else:
            authors = [a.strip() for a in str(authors_raw).split(",") if a.strip()][:5]

        date_str = pub.submitted_at.strftime("%Y-%m-%d") if pub.submitted_at else "—"
        score_val = ts.score if ts else None
        trust_int = int(round(score_val * 100)) if score_val and not (ts and ts.is_indexation_score) else None
        index_int = int(round(score_val * 100)) if score_val and ts and ts.is_indexation_score else None

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
            trust_score=trust_int,
            indexation_score=index_int,
            hal_id=pub.hal_id,
            source_label="KAKAPO certified" if pub.kpt_status == "certified" else "HAL indexed",
            url_kakapo=f"{API_BASE_URL}/publications/{pub.id}",
        ))

    logger.info(f"KakapoSearch query={query!r} filter={kpt_status_filter} results={len(results)}")
    return results
