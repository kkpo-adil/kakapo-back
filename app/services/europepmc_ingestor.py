import uuid
import time
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.publication import Publication
from app.models.kpt import KPT
from app.models.trust_score import TrustScore
from app.services import europepmc_client
from app.services.full_text_extractor import extract_full_text

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


@dataclass
class EPMCIngestReport:
    total_fetched: int = 0
    total_created: int = 0
    total_skipped_existing: int = 0
    total_failed: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


def ingest_batch(
    db: Session,
    query: str,
    max_results: int = 500,
    fetch_full_text: bool = False,
    year_from: int = 2015,
    year_to: int = 2026,
    cursor_mark: str = "*",
) -> EPMCIngestReport:
    report = EPMCIngestReport()
    t0 = time.time()
    fetched = 0

    while fetched < max_results:
        batch_size = min(1000, max_results - fetched)
        results, next_cursor = europepmc_client.search(
            query=query,
            max_results=batch_size,
            cursor_mark=cursor_mark,
            filter_open_access=True,
            year_from=year_from,
            year_to=year_to,
        )

        if not results:
            break

        report.total_fetched += len(results)
        fetched += len(results)

        for i in range(0, len(results), BATCH_SIZE):
            batch = results[i:i + BATCH_SIZE]
            try:
                for result in batch:
                    try:
                        uid_raw = result.pmcid or result.pmid or result.doi or result.title[:50]
                        uid = f"epmc:{uid_raw}"
                        existing = db.query(Publication).filter(
                            Publication.hal_id == uid
                        ).first()
                        if existing:
                            report.total_skipped_existing += 1
                            continue

                        full_text = None
                        content_hash = None
                        kpt_status = "indexed"

                        if fetch_full_text and result.pmcid:
                            full_text, content_hash = europepmc_client.get_full_text_hash(result.pmcid)
                            if content_hash:
                                kpt_status = "certified"

                        if not content_hash:
                            raw = f"{result.pmid or ''}{result.title}"
                            content_hash = hashlib.sha256(raw.encode()).hexdigest()

                        pub_id = uuid.uuid4()

                        try:
                            submitted_at = datetime.fromisoformat(
                                result.published + "-01-01" if len(result.published) == 4 else result.published
                            ).replace(tzinfo=timezone.utc) if result.published else None
                        except Exception:
                            submitted_at = None

                        import json as _json

                        if not full_text and fetch_full_text:
                            if hasattr(result, 'full_text_urls') and result.full_text_urls:
                                for ft_url in result.full_text_urls[:3]:
                                    full_text, content_hash = extract_full_text(article_url=ft_url, doi=result.doi)
                                    if full_text:
                                        kpt_status = "certified"
                                        break
                            if not full_text and result.doi:
                                full_text, content_hash = extract_full_text(doi=result.doi, pmcid=result.pmcid)
                                if full_text:
                                    kpt_status = "certified"

                        if not content_hash:
                            raw = f"{result.pmid or ''}{result.title}"
                            content_hash = hashlib.sha256(raw.encode()).hexdigest()

                        pub = Publication(
                            id=pub_id,
                            title=result.title[:512],
                            abstract=result.abstract[:5000] if result.abstract else None,
                            full_text=full_text[:10000000] if full_text else None,
                            source="europepmc",
                            doi=result.doi,
                            authors_raw=str(result.authors[:10]),
                            institution_raw=result.journal,
                            submitted_at=submitted_at,
                            kpt_status=kpt_status,
                            source_origin="europepmc",
                            hal_id=uid,
                            file_hash=content_hash if kpt_status == "certified" else None,
                            keywords_json=_json.dumps(result.keywords) if result.keywords else None,
                            mesh_terms_json=_json.dumps(result.mesh_terms) if getattr(result, 'mesh_terms', None) else None,
                            citations_count=getattr(result, 'citations_count', 0) or 0,
                            language=getattr(result, 'language', None),
                            article_type=getattr(result, 'article_type', None),
                            license=getattr(result, 'license', None),
                            funding_json=_json.dumps(result.grants) if getattr(result, 'grants', None) else None,
                            orcid_authors_json=_json.dumps(result.orcid_authors) if getattr(result, 'orcid_authors', None) else None,
                        )
                        db.add(pub)

                        kpt_id_suffix = (result.pmcid or result.pmid or content_hash[:8]).replace("/", "-")
                        kpt_id = f"KPT-{content_hash[:8].upper()}-EPMC-{kpt_id_suffix}"

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
                            citation_score=0.0,
                            dataset_score=0.0,
                            is_indexation_score=(kpt_status == "indexed"),
                        )
                        db.add(ts)
                        report.total_created += 1

                    except Exception as e:
                        report.total_failed += 1
                        msg = f"Failed {result.title[:50]}: {e}"
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

        if next_cursor == cursor_mark or next_cursor == "*":
            break
        cursor_mark = next_cursor

    report.duration_seconds = round(time.time() - t0, 2)
    return report


def _compute_score(result: europepmc_client.EPMCResult, full_text: str = None) -> int:
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
        score += 2
    if result.journal:
        score += 10
    else:
        score += 5
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
    if result.is_open_access:
        score += 10
    if full_text and len(full_text) > 1000:
        score += 10
    return min(score, 100)
