import uuid
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.publication import Publication
from app.models.kpt import KPT
from app.models.trust_score import TrustScore
from app.services import hal_client, citation_reach, indexation_scorer

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


@dataclass
class IngestReport:
    total_fetched: int = 0
    total_created: int = 0
    total_skipped_existing: int = 0
    total_failed: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


def _str(val) -> str:
    if isinstance(val, list):
        return val[0] if val else ""
    return str(val) if val else ""


def _map_hal_to_publication(doc: dict) -> dict:
    title = _str(doc.get("title_s", "")) or "Sans titre"
    abstract = _str(doc.get("abstract_s", ""))
    authors = doc.get("authFullName_s", [])
    authors_raw = ", ".join(authors) if isinstance(authors, list) else str(authors or "")
    doi = _str(doc.get("doiId_s", ""))
    hal_id = _str(doc.get("halId_s", ""))
    publisher = _str(doc.get("publisher_s", ""))
    date_str = _str(doc.get("producedDate_s") or doc.get("submittedDate_s") or "")

    submitted_at = None
    if date_str:
        try:
            submitted_at = datetime.fromisoformat(date_str[:10]).replace(tzinfo=timezone.utc)
        except ValueError:
            submitted_at = None

    return {
        "title": title[:500],
        "abstract": abstract[:5000],
        "doi": doi,
        "authors_raw": authors_raw,
        "institution_raw": publisher,
        "source": "hal",
        "submitted_at": submitted_at,
        "kpt_status": "indexed",
        "source_origin": "hal",
        "hal_id": hal_id,
    }


def ingest_batch(
    db: Session,
    query: str,
    max_results: int = 1000,
    domains: list[str] | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> IngestReport:
    report = IngestReport()
    start_time = time.time()

    all_docs: list[dict] = []
    batch_size = 100
    offset = 0

    while len(all_docs) < max_results:
        rows = min(batch_size, max_results - len(all_docs))
        if domains:
            for domain in domains:
                yf = year_from or 2000
                yt = year_to or datetime.now(timezone.utc).year
                docs = hal_client.search_by_domain(domain, yf, yt, rows=rows, start=offset)
                all_docs.extend(docs)
        else:
            docs = hal_client.search(query=query, rows=rows, start=offset)
            all_docs.extend(docs)
            if len(docs) < rows:
                break
        offset += rows
        if not docs:
            break

    all_docs = all_docs[:max_results]
    report.total_fetched = len(all_docs)

    pending: list[tuple[Publication, dict]] = []

    for doc in all_docs:
        try:
            hal_id = doc.get("halId_s", "")
            if hal_id:
                existing = db.query(Publication).filter(Publication.hal_id == hal_id).first()
                if existing:
                    report.total_skipped_existing += 1
                    continue

            mapped = _map_hal_to_publication(doc)
            pub = Publication(**{k: v for k, v in mapped.items() if v is not None and v != ""})
            pub.id = uuid.uuid4()
            pending.append((pub, doc))

            if len(pending) >= BATCH_SIZE:
                _commit_batch(db, pending, report)
                pending = []

        except Exception as exc:
            report.total_failed += 1
            report.errors.append(f"doc {doc.get('halId_s', '?')}: {exc}")
            logger.error(f"Ingest error for {doc.get('halId_s', '?')}: {exc}")

    if pending:
        _commit_batch(db, pending, report)

    report.duration_seconds = round(time.time() - start_time, 2)
    logger.info(f"Ingest complete: {report}")
    return report


def _commit_batch(db: Session, pending: list[tuple[Publication, dict]], report: IngestReport) -> None:
    try:
        for pub, doc in pending:
            doi = pub.doi or ""
            citation_count = citation_reach.fetch_citation_count(doi) if doi else 0
            idx_score = indexation_scorer.compute(doc, citation_count)

            db.add(pub)
            db.flush()

            kpt = KPT(
                id=uuid.uuid4(),
                publication_id=pub.id,
                kpt_id=f"IKPT-{str(pub.id).upper()[:8]}-v1",
                content_hash=f"hal-{pub.hal_id or str(pub.id)[:8]}",
                status="active",
                version=1,
                is_indexed=True,
            )
            db.add(kpt)

            ts = TrustScore(
                publication_id=pub.id,
                score=round(idx_score / 100, 4),
                source_score=0.0,
                completeness_score=0.0,
                freshness_score=0.0,
                citation_score=0.0,
                dataset_score=0.0,
                scoring_version="indexation-1.0",
                is_indexation_score=True,
            )
            db.add(ts)

        db.commit()
        report.total_created += len(pending)
        logger.info(f"Committed batch of {len(pending)}")
    except Exception as exc:
        db.rollback()
        report.total_failed += len(pending)
        report.errors.append(f"Batch rollback: {exc}")
        logger.error(f"Batch commit failed, rolled back: {exc}")
