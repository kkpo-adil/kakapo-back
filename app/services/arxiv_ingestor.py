import uuid
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.publication import Publication
from app.models.kpt import KPT
from app.models.trust_score import TrustScore
from app.services import arxiv_client

logger = logging.getLogger(__name__)

BATCH_SIZE = 10


@dataclass
class ArxivIngestReport:
    total_fetched: int = 0
    total_created: int = 0
    total_skipped_existing: int = 0
    total_failed: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


def ingest_batch(
    db: Session,
    query: str,
    max_results: int = 100,
    categories: list[str] = None,
    start: int = 0,
    download_pdf: bool = True,
) -> ArxivIngestReport:
    report = ArxivIngestReport()
    t0 = time.time()

    results = arxiv_client.search(
        query=query,
        max_results=min(max_results, 100),
        start=start,
        categories=categories,
    )
    report.total_fetched = len(results)

    for i in range(0, len(results), BATCH_SIZE):
        batch = results[i:i + BATCH_SIZE]
        try:
            for result in batch:
                try:
                    existing = db.query(Publication).filter(
                        Publication.hal_id == f"arxiv:{result.arxiv_id}"
                    ).first()
                    if existing:
                        report.total_skipped_existing += 1
                        continue

                    pdf_text = None
                    pdf_hash = None
                    kpt_status = "indexed"

                    if download_pdf:
                        pdf_text, pdf_hash = arxiv_client.download_and_hash_pdf(result.arxiv_id)
                        if pdf_hash:
                            kpt_status = "certified"

                    pub_id = uuid.uuid4()
                    pub = Publication(
                        id=pub_id,
                        title=result.title[:512],
                        abstract=result.abstract[:5000] if result.abstract else None,
                        source="arxiv",
                        doi=result.doi,
                        authors_raw=str(result.authors[:10]),
                        institution_raw=result.journal_ref,
                        submitted_at=datetime.fromisoformat(result.published).replace(tzinfo=timezone.utc) if result.published else None,
                        kpt_status=kpt_status,
                        source_origin="arxiv",
                        hal_id=f"arxiv:{result.arxiv_id}",
                        file_hash=pdf_hash,
                    )
                    db.add(pub)

                    import hashlib
                    kpt_hash = pdf_hash if pdf_hash else hashlib.sha256(f"{result.arxiv_id}{result.title}".encode()).hexdigest()
                    kpt_id = f"KPT-{kpt_hash[:8].upper()}-arXiv-{result.arxiv_id.replace('/', '-')}"

                    kpt = KPT(
                        id=uuid.uuid4(),
                        publication_id=pub_id,
                        kpt_id=kpt_id,
                        content_hash=kpt_hash,
                        is_indexed=(kpt_status == "indexed"),
                        issued_at=datetime.now(timezone.utc),
                        version=1,
                    )
                    db.add(kpt)

                    score = _compute_score(result, pdf_text)
                    ts = TrustScore(
                        id=uuid.uuid4(),
                        publication_id=pub_id,
                        score=round(score / 100.0, 2),
                        source_score=0.0,
                        completeness_score=0.0,
                        freshness_score=0.0,
                        citation_score=0.0,
                        dataset_score=0.0,
                        is_indexation_score=(kpt_status == "indexed"),
                    )
                    db.add(ts)
                    report.total_created += 1

                except Exception as e:
                    report.total_failed += 1
                    msg = f"Failed {result.arxiv_id}: {e}"
                    logger.warning(msg)
                    if len(report.errors) < 100:
                        report.errors.append(msg)

            db.commit()

        except Exception as e:
            db.rollback()
            msg = f"Batch rollback: {e}"
            logger.error(msg)
            if len(report.errors) < 100:
                report.errors.append(msg)

    report.duration_seconds = round(time.time() - t0, 2)
    return report


def _compute_score(result: arxiv_client.ArxivResult, pdf_text: str = None) -> int:
    score = 0
    if result.doi:
        score += 10
    if result.abstract and len(result.abstract) > 100:
        score += 5
    if result.authors:
        score += 5
    if result.published:
        score += 3
    if result.categories:
        score += 2
    if result.journal_ref:
        score += 10
    else:
        score += 5
    try:
        year = int(result.published[:4]) if result.published else 2000
        age = 2026 - year
        if age < 5:
            score += 10
        elif age < 10:
            score += 6
        else:
            score += 3
    except Exception:
        score += 3
    if pdf_text and len(pdf_text) > 1000:
        score += 10
    return min(score, 100)
