"""
Trust Engine V3 — Formules mathématiques continues.

T(p,t) = 0.30 S_source + 0.20 S_data + 0.20 S_citation + 0.15 S_freshness + 0.10 S_consistency + 0.05 S_reviews

Principe : T n'est pas une vérité. C'est une fonction de confiance stable sous incertitude.
"""

import math
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.publication import Publication
from app.models.trust_score import TrustScore


SCORING_VERSION = "3.0"

SOURCE_TIERS = {
    "tier_a": ["nature", "science", "cell", "lancet", "nejm", "bmj"],
    "tier_b": ["arxiv", "hal", "pubmed", "biorxiv", "medrxiv", "plos", "ieee", "acm"],
    "tier_c": ["direct", "institutional"],
    "tier_d": ["other"],
}

SOURCE_SCORES = {"tier_a": 0.90, "tier_b": 0.70, "tier_c": 0.50, "tier_d": 0.30}

WEIGHTS = {
    "source":      0.30,
    "data":        0.20,
    "citation":    0.20,
    "freshness":   0.15,
    "consistency": 0.10,
    "reviews":     0.05,
}

ALPHA = 0.05
LAMBDA = 0.10


def _score_source(publication: Publication) -> float:
    source = (publication.source or "").lower().strip()
    for tier, sources in SOURCE_TIERS.items():
        if source in sources:
            return SOURCE_SCORES[tier]
    doi = publication.doi or ""
    if any(prefix in doi for prefix in ["10.1038", "10.1126", "10.1016", "10.1056"]):
        return SOURCE_SCORES["tier_a"]
    if doi:
        return SOURCE_SCORES["tier_c"]
    return SOURCE_SCORES["tier_d"]


def _score_data(publication: Publication, dataset_hashes: list[str] | None) -> float:
    d1 = 1 if publication.doi else 0
    d2 = 1 if dataset_hashes else 0
    d3 = 0
    d4 = 1 if (publication.abstract and len(publication.abstract.strip()) > 100) else 0
    return round((d1 + 2 * d2 + 2 * d3 + d4) / 6, 4)


def _score_citation(citation_count: int | None) -> float:
    c = max(0, citation_count or 0)
    return round(1 - math.exp(-ALPHA * c), 4)


def _score_freshness(publication: Publication) -> float:
    ref = publication.submitted_at or publication.created_at
    if ref is None:
        return round(math.exp(-LAMBDA * 3), 4)
    now = datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    age_years = (now - ref).days / 365.25
    return round(math.exp(-LAMBDA * age_years), 4)


def _score_consistency(publication: Publication) -> float:
    c1 = 1 if (publication.doi and len(publication.doi) > 5) else 0
    c2 = 1 if (publication.authors_raw and publication.authors_raw.strip()) else 0
    c3 = 0
    c4 = 0
    return round((c1 + c2 + (1 - c3) + (1 - c4)) / 4, 4)


def _score_reviews(review_scores: list[float] | None) -> float:
    if not review_scores or len(review_scores) < 3:
        return 0.0
    sorted_scores = sorted(review_scores)
    n = len(sorted_scores)
    median = (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2 if n % 2 == 0 else sorted_scores[n // 2]
    return round(median / 5.0, 4)


def compute_trust_score(
    db: Session,
    publication: Publication,
    dataset_hashes: list[str] | None = None,
    citation_count: int | None = None,
    review_scores: list[float] | None = None,
) -> TrustScore:
    s_source      = _score_source(publication)
    s_data        = _score_data(publication, dataset_hashes)
    s_citation    = _score_citation(citation_count)
    s_freshness   = _score_freshness(publication)
    s_consistency = _score_consistency(publication)
    s_reviews     = _score_reviews(review_scores)

    global_score = round(
        WEIGHTS["source"]      * s_source
        + WEIGHTS["data"]      * s_data
        + WEIGHTS["citation"]  * s_citation
        + WEIGHTS["freshness"] * s_freshness
        + WEIGHTS["consistency"] * s_consistency
        + WEIGHTS["reviews"]   * s_reviews,
        4,
    )
    global_score = min(max(global_score, 0.0), 1.0)

    trust_score = TrustScore(
        publication_id=publication.id,
        score=global_score,
        source_score=s_source,
        completeness_score=s_data,
        freshness_score=s_freshness,
        citation_score=s_citation,
        dataset_score=s_data,
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
            "source":      {"score": trust_score.source_score,       "weight": WEIGHTS["source"],      "label": "Crédibilité source"},
            "data":        {"score": trust_score.completeness_score,  "weight": WEIGHTS["data"],        "label": "Intégrité données"},
            "citation":    {"score": trust_score.citation_score,      "weight": WEIGHTS["citation"],    "label": "Réseau citations"},
            "freshness":   {"score": trust_score.freshness_score,     "weight": WEIGHTS["freshness"],   "label": "Fraîcheur"},
            "consistency": {"score": 0.0,                             "weight": WEIGHTS["consistency"], "label": "Cohérence structurelle"},
            "reviews":     {"score": 0.0,                             "weight": WEIGHTS["reviews"],     "label": "Reviews pairs"},
        },
        "interpretation": _interpret_score(trust_score.score),
        "formula": "T = 0.30·S_source + 0.20·S_data + 0.20·S_citation + 0.15·S_freshness + 0.10·S_consistency + 0.05·S_reviews",
    }


def _interpret_score(score: float) -> str:
    if score >= 0.90:
        return "Validé — fiabilité confirmée"
    elif score >= 0.70:
        return "Solide — signaux convergents"
    elif score >= 0.50:
        return "Incertain — signaux mixtes"
    else:
        return "Faible — prudence recommandée"
