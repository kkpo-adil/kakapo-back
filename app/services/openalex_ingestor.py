import uuid
import time
import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.publication import Publication
from app.models.kpt import KPT
from app.models.trust_score import TrustScore
from app.services import openalex_client
from app.services.full_text_extractor import extract_full_text

logger = logging.getLogger(__name__)


@dataclass
class OpenAlexIngestReport:
    total_fetched: int = 0
    total_created: int = 0
    total_skipped_existing: int = 0
    total_failed: int = 0
    total_with_fulltext: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


def ingest_batch(
    db: Session,
    query: str,
    max_results: int = 100,
    year_from: int = 2015,
    year_to: int = 2026,
    cursor: str = "*",
    fetch_full_text: bool = True,
) -> OpenAlexIngestReport:
    report = OpenAlexIngestReport()
    t0 = time.time()

    results, _ = openalex_client.search(
        query=query,
        max_results=min(max_results, 200),
        cursor=cursor,
        year_from=year_from,
        year_to=year_to,
        filter_open_access=True,
    )
    report.total_fetched = len(results)

    for result in results:
        try:
            uid = f"openalex:{result.openalex_id}"
            existing = db.query(Publication).filter(
                Publication.hal_id == uid
            ).first()
            if existing:
                report.total_skipped_existing += 1
                continue

            full_text = None
            content_hash = None
            kpt_status = "indexed"

            if fetch_full_text and (result.pdf_url or result.oa_url or result.doi):
                full_text, content_hash = extract_full_text(
                    doi=result.doi,
                    article_url=result.pdf_url or result.oa_url,
                )
                if content_hash:
                    kpt_status = "certified"
                    report.total_with_fulltext += 1

            if not content_hash:
                raw = f"{result.openalex_id}{result.title}"
                content_hash = hashlib.sha256(raw.encode()).hexdigest()

            try:
                pub_str = result.published or ""
                if len(pub_str) == 4:
                    pub_str = pub_str + "-01-01"
                submitted_at = datetime.fromisoformat(pub_str).replace(tzinfo=timezone.utc) if pub_str else None
            except Exception:
                submitted_at = None

            all_keywords = list(set(result.keywords + result.concepts + result.mesh_terms))
            stored_abstract = (full_text[:10000] if full_text and len(full_text) > len(result.abstract or "") else (result.abstract or "")[:5000])

            pub_id = uuid.uuid4()
            pub = Publication(
                id=pub_id,
                title=result.title[:512],
                abstract=stored_abstract or None,
                source="openalex",
                doi=result.doi,
                authors_raw=json.dumps(result.authors[:10]),
                institution_raw=result.journal or result.publisher,
                submitted_at=submitted_at,
                kpt_status=kpt_status,
                source_origin="openalex",
                hal_id=uid,
                file_hash=content_hash if kpt_status == "certified" else None,
                keywords_json=json.dumps(all_keywords) if all_keywords else None,
            )
            db.add(pub)

            kpt_id = f"KPT-{content_hash[:8].upper()}-OA-{result.openalex_id}"
            kpt = KPT(
                id=uuid.uuid4(),
                publication_id=pub_id,
                kpt_id=kpt_id,
                content_hash=content_hash,
                is_indexed=(kpt_status == "indexed"),
                issued_at=datetime.now(timezone.utc),
                version=1,
            )
            db.add(kpt)

            score = _compute_score(result, full_text)
            ts = TrustScore(
                id=uuid.uuid4(),
                publication_id=pub_id,
                score=round(score / 100.0, 2),
                source_score=0.0,
                completeness_score=0.0,
                freshness_score=0.0,
                citation_score=min(result.citations_count / 1000.0, 1.0),
                dataset_score=0.0,
                is_indexation_score=(kpt_status == "indexed"),
            )
            db.add(ts)
            report.total_created += 1

        except Exception as e:
            report.total_failed += 1
            msg = f"Failed {result.openalex_id}: {e}"
            logger.warning(msg)
            if len(report.errors) < 20:
                report.errors.append(msg)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Commit failed: {e}")

    report.duration_seconds = round(time.time() - t0, 2)
    return report


def _compute_score(result: openalex_client.OpenAlexResult, full_text: str = None) -> int:
    score = 0
    if result.doi:
        score += 10
    if result.abstract and len(result.abstract) > 100:
        score += 5
    if result.authors:
        score += min(len(result.authors) * 2, 8)
    if result.published:
        score += 3
    if result.keywords:
        score += min(len(result.keywords), 5)
    if result.concepts:
        score += min(len(result.concepts), 5)
    if result.mesh_terms:
        score += min(len(result.mesh_terms), 5)
    if result.journal:
        score += 7
    if result.citations_count > 1000:
        score += 15
    elif result.citations_count > 100:
        score += 10
    elif result.citations_count > 10:
        score += 5
    elif result.citations_count > 0:
        score += 2
    try:
        year = int(str(result.published)[:4]) if result.published else 2000
        age = 2026 - year
        if age < 2:
            score += 10
        elif age < 5:
            score += 7
        elif age < 10:
            score += 4
        else:
            score += 2
    except Exception:
        score += 2
    if result.is_open_access:
        score += 5
    if full_text and len(full_text) > 5000:
        score += 15
    elif full_text and len(full_text) > 1000:
        score += 8
    return min(score, 100)
