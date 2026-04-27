"""
Trust Engine V2 — Multi-signal scoring.

Scoring breakdown V1 (total = 1.0):
  source_score    0.35  — Source credibility tier A/B/C/D
  data_score      0.25  — Data integrity (DOI, dataset, reproducibility)
  citation_score  0.20  — Citation network depth
  freshness_score 0.20  — Publication recency

V2 hooks (when reviews reach critical mass):
  source_score    0.30
  data_score      0.20
  citation_score  0.15
  freshness_score 0.15
  consistency     0.10
  review_score    0.10  — Peer review median, ORCID-traced

Principle: A good score does not say "this is true".
           It says "here is how much you can trust it today".
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.publication import Publication
from app.models.trust_score import TrustScore


SCORING_VERSION = "2.0"

SOURCE_TIERS = {
    "tier_a": {
        "sources": ["nature", "science", "cell", "lancet", "nejm"],
        "score": 0.95,
    },
    "tier_b": {
        "sources": ["arxiv", "hal", "pubmed", "biorxiv", "medrxiv", "plos", "ieee"],
        "score": 0.75,
    },
    "tier_c": {
        "sources": ["direct", "institutional"],
        "score": 0.50,
    },
    "tier_d": {
        "sources": ["other"],
        "score": 0.30,
    },
}

CITATION_TIERS = [
    (0, 0, 0.20),
    (1, 5, 0.50),
    (6, 20, 0.70),
    (21, 100, 0.85),
    (101, None, 0.95),
]

FRESHNESS_TIERS = [
    (0, 2, 0.95),
    (2, 5, 0.75),
    (5, 10, 0.55),
    (10, None, 0.30),
]

WEIGHTS_V1 = {
    "source": 0.35,
    "data": 0.25,
    "citation": 0.20,
    "freshness": 0.20,
}


def _score_source(publication: Publication) -> float:
    source = (publication.source or "").lower().strip()
    for tier in SOURCE_TIERS.values():
        if source in tier["sources"]:
            return tier["score"]
    doi = publication.doi or ""
    if "10.1038" in doi or "10.1126" in doi or "10.1016" in doi:
        return SOURCE_TIERS["tier_a"]["score"]
    if doi:
        return SOURCE_TIERS["tier_c"]["score"]
    return SOURCE_TIERS["tier_d"]["score"]


def _score_data(publication: Publication, dataset_hashes: list[str] | None) -> float:
    score = 0.0
    if publication.doi:
        score += 0.40
    if publication.abstract and len(publication.abstract.strip()) > 100:
        score += 0.20
    if publication.authors_raw and publication.authors_raw.strip():
        score += 0.20
    if dataset_hashes:
        score += 0.20
    return round(min(score, 1.0), 4)


def _score_citation(citation_count: int | None) -> float:
    count = citation_count or 0
    for low, high, score in CITATION_TIERS:
        if high is None:
            return score
        if low <= count <= high:
            return score
    return 0.20


def _score_freshness(publication: Publication) -> float:
    reference_date = publication.submitted_at or publication.created_at
    if reference_date is None:
        return 0.50
    now = datetime.now(timezone.utc)
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)
    age_years = (now - reference_date).days / 365.25
    for low, high, score in FRESHNESS_TIERS:
        if high is None or age_years < high:
            if age_years >= low:
                return score
    return FRESHNESS_TIERS[-1][2]


def _score_reviews(review_scores: list[float] | None) -> float | None:
    if not review_scores or len(review_scores) < 3:
        return None
    sorted_scores = sorted(review_scores)
    n = len(sorted_scores)
    if n % 2 == 0:
        median = (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
    else:
        median = sorted_scores[n // 2]
    return round(median / 5.0, 4)


def compute_trust_score(
    db: Session,
    publication: Publication,
    dataset_hashes: list[str] | None = None,
    citation_count: int | None = None,
    review_scores: list[float] | None = None,
) -> TrustScore:
    source_score = _score_source(publication)
    data_score = _score_data(publication, dataset_hashes)
    citation_score = _score_citation(citation_count)
    freshness_score = _score_freshness(publication)
    review_score = _score_reviews(review_scores)

    weights = WEIGHTS_V1.copy()
    if review_score is not None:
        weights = {
            "source": 0.30,
            "data": 0.20,
            "citation": 0.15,
            "freshness": 0.15,
            "review": 0.10,
            "consistency": 0.10,
        }

    global_score = round(
        source_score * weights["source"]
        + data_score * weights["data"]
        + citation_score * weights["citation"]
        + freshness_score * weights["freshness"]
        + (review_score * weights.get("review", 0) if review_score else 0),
        4,
    )

    trust_score = TrustScore(
        publication_id=publication.id,
        score=global_score,
        source_score=source_score,
        completeness_score=data_score,
        freshness_score=freshness_score,
        citation_score=citation_score,
        dataset_score=data_score,
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


def get_score_breakdown(trust_score: TrustScore) -> dict:
    return {
        "score": trust_score.score,
        "version": trust_score.scoring_version,
        "breakdown": {
            "source": {
                "score": trust_score.source_score,
                "weight": WEIGHTS_V1["source"],
                "label": "Crédibilité de la source",
            },
            "data": {
                "score": trust_score.completeness_score,
                "weight": WEIGHTS_V1["data"],
                "label": "Intégrité des données",
            },
            "citation": {
                "score": trust_score.citation_score,
                "weight": WEIGHTS_V1["citation"],
                "label": "Réseau de citations",
            },
            "freshness": {
                "score": trust_score.freshness_score,
                "weight": WEIGHTS_V1["freshness"],
                "label": "Fraîcheur",
            },
        },
        "interpretation": _interpret_score(trust_score.score),
    }


def _interpret_score(score: float) -> str:
    if score >= 0.90:
        return "Validé — fiabilité confirmée par l'usage"
    elif score >= 0.70:
        return "Solide — à confirmer dans le temps"
    elif score >= 0.50:
        return "Incertain — signaux mixtes"
    else:
        return "Faible crédibilité — prudence recommandée"
