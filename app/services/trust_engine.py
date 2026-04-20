"""
Trust Engine V1 — Rule-based scoring.

Scoring breakdown (total = 1.0):
  source_score       0.20  — Known and reputable source (hal, arxiv > direct > other)
  completeness_score 0.30  — Mandatory fields presence (title, abstract, doi, authors, institution)
  freshness_score    0.20  — Publication recency (within 2 years = full score, decay after)
  citation_score     0.15  — Presence of DOI (proxy for citability in V1; citations graph in V2)
  dataset_score      0.15  — Associated dataset declared

V2 hooks:
  - Replace citation_score with a real citation graph query (Neo4j)
  - Add reproducibility_score from linked dataset verification
  - Add contradiction_score from cross-publication analysis
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.publication import Publication
from app.models.trust_score import TrustScore


SCORING_VERSION = "1.0"

SOURCE_WEIGHTS = {
    "hal": 1.0,
    "arxiv": 1.0,
    "direct": 0.5,
    "other": 0.3,
    None: 0.1,
}

COMPLETENESS_FIELDS = [
    ("title", 0.25),
    ("abstract", 0.25),
    ("doi", 0.20),
    ("authors_raw", 0.15),
    ("institution_raw", 0.15),
]

FRESHNESS_FULL_YEARS = 2
FRESHNESS_DECAY_YEARS = 5


def _score_source(publication: Publication) -> float:
    return SOURCE_WEIGHTS.get(publication.source, 0.1)


def _score_completeness(publication: Publication) -> float:
    total = 0.0
    for field, weight in COMPLETENESS_FIELDS:
        value = getattr(publication, field, None)
        if value is not None and str(value).strip():
            total += weight
    return round(total, 4)


def _score_freshness(publication: Publication) -> float:
    reference_date = publication.submitted_at or publication.created_at
    if reference_date is None:
        return 0.0

    now = datetime.now(timezone.utc)
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)

    age_days = (now - reference_date).days
    age_years = age_days / 365.25

    if age_years <= FRESHNESS_FULL_YEARS:
        return 1.0
    elif age_years >= FRESHNESS_DECAY_YEARS:
        return 0.0
    else:
        decay_range = FRESHNESS_DECAY_YEARS - FRESHNESS_FULL_YEARS
        elapsed = age_years - FRESHNESS_FULL_YEARS
        return round(1.0 - (elapsed / decay_range), 4)


def _score_citation(publication: Publication) -> float:
    """
    V1 proxy: having a DOI means the publication is formally citable.
    V2: replace with actual citation count from OpenAlex or Semantic Scholar.
    """
    return 1.0 if publication.doi else 0.0


def _score_dataset(publication: Publication, dataset_hashes: list[str] | None) -> float:
    """Score based on declared dataset hashes passed at KPT issue time."""
    return 1.0 if dataset_hashes else 0.0


def compute_trust_score(
    db: Session,
    publication: Publication,
    dataset_hashes: list[str] | None = None,
) -> TrustScore:
    """
    Compute and persist the Trust Score for a publication.
    Always creates a new score entry (score history is preserved).
    """
    weights = {
        "source": 0.20,
        "completeness": 0.30,
        "freshness": 0.20,
        "citation": 0.15,
        "dataset": 0.15,
    }

    source_score = _score_source(publication)
    completeness_score = _score_completeness(publication)
    freshness_score = _score_freshness(publication)
    citation_score = _score_citation(publication)
    dataset_score = _score_dataset(publication, dataset_hashes)

    global_score = round(
        source_score * weights["source"]
        + completeness_score * weights["completeness"]
        + freshness_score * weights["freshness"]
        + citation_score * weights["citation"]
        + dataset_score * weights["dataset"],
        4,
    )

    trust_score = TrustScore(
        publication_id=publication.id,
        score=global_score,
        source_score=source_score,
        completeness_score=completeness_score,
        freshness_score=freshness_score,
        citation_score=citation_score,
        dataset_score=dataset_score,
        scoring_version=SCORING_VERSION,
    )

    db.add(trust_score)
    db.commit()
    db.refresh(trust_score)
    return trust_score


def get_latest_trust_score(db: Session, publication_id) -> TrustScore | None:
    return (
        db.query(TrustScore)
        .filter(TrustScore.publication_id == publication_id)
        .order_by(TrustScore.scored_at.desc())
        .first()
    )
