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
from app.services import pubmed_client

logger = logging.getLogger(__name__)

BATCH_SIZE = 10


@dataclass
class PubMedIngestReport:
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
    year_from: int = 2015,
    year_to: int = 2026,
    start: int = 0,
) -> PubMedIngestReport:
    report = PubMedIngestReport()
    t0 = time.time()

    pmc_ids = pubmed_client.search_ids(
        query=query,
        max_results=min(max_results, 100),
        start=start,
        year_from=year_from,
        year_to=year_to,
    )
    report.total_fetched = len(pmc_ids)

    if not pmc_ids:
        report.duration_seconds = round(time.time() - t0, 2)
        return report

    for i in range(0, len(pmc_ids), BATCH_SIZE):
        batch_ids = pmc_ids[i:i + BATCH_SIZE]
        try:
            results = pubmed_client.fetch_articles(batch_ids)
            for result in results:
                try:
                    uid = f"pmc:{result.pmc_id}"
                    existing = db.query(Publication).filter(
                        Publication.hal_id == uid
                    ).first()
                    if existing:
                        if existing.keywords_json is None and (result.keywords or result.mesh_terms):
                            all_kw = list(set(result.keywords + result.mesh_terms))
                            existing.keywords_json = json.dumps(all_kw)
                            db.add(existing)
                        report.total_skipped_existing += 1
                        continue

                    content_hash = result.full_text_hash
                    kpt_status = "certified" if content_hash else "indexed"

                    if not content_hash:
                        raw = f"{result.pmc_id}{result.title}"
                        content_hash = hashlib.sha256(raw.encode()).hexdigest()

                    try:
                        if result.published and len(result.published) >= 4:
                            year = result.published[:4]
                            month = result.published[5:7] if len(result.published) >= 7 else "01"
                            submitted_at = datetime.fromisoformat(
                                f"{year}-{month}-01"
                            ).replace(tzinfo=timezone.utc)
                        else:
                            submitted_at = None
                    except Exception:
                        submitted_at = None

                    all_keywords = list(set(result.keywords + result.mesh_terms))

                    pub_id = uuid.uuid4()
                    pub = Publication(
                        id=pub_id,
                        title=result.title[:512],
                        abstract=result.abstract[:5000] if result.abstract else None,
                        source="pubmed",
                        doi=result.doi,
                        authors_raw=json.dumps(result.authors[:10]),
                        institution_raw=result.journal,
                        submitted_at=submitted_at,
                        kpt_status=kpt_status,
                        source_origin="pubmed",
                        hal_id=uid,
                        file_hash=content_hash if kpt_status == "certified" else None,
                        keywords_json=json.dumps(all_keywords) if all_keywords else None,
                    )
                    db.add(pub)

                    kpt_id = f"KPT-{content_hash[:8].upper()}-PMC-{result.pmc_id}"
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

                    score = _compute_score(result)
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
                    msg = f"Failed {result.pmc_id}: {e}"
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


def _compute_score(result: pubmed_client.PMCResult) -> int:
    score = 0
    if result.doi:
        score += 10
    if result.abstract and len(result.abstract) > 100:
        score += 5
    if result.authors:
        score += 5
    if result.published:
        score += 3
    if result.keywords:
        score += 5
    if result.mesh_terms:
        score += 5
    if result.journal:
        score += 10
    try:
        year = int(str(result.published)[:4]) if result.published else 2000
        age = 2026 - year
        if age < 5:
            score += 10
        elif age < 10:
            score += 6
        else:
            score += 3
    except Exception:
        score += 3
    if result.full_text and len(result.full_text) > 1000:
        score += 15
    return min(score, 100)
