import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"

from app.services.trust_engine import (
    _score_source,
    _score_data,
    _score_citation,
    _score_freshness,
    _interpret_score,
)
from app.models.publication import Publication
from datetime import datetime, timezone, timedelta


def make_pub(**kwargs):
    p = Publication()
    p.source = kwargs.get("source", "arxiv")
    p.doi = kwargs.get("doi", "10.1234/test")
    p.abstract = kwargs.get("abstract", "A" * 200)
    p.authors_raw = kwargs.get("authors_raw", "[{name: Test}]")
    p.institution_raw = kwargs.get("institution_raw", "MIT")
    p.submitted_at = kwargs.get("submitted_at", datetime.now(timezone.utc) - timedelta(days=365))
    p.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
    return p


def test_source_tier_a():
    p = make_pub(source="nature")
    assert _score_source(p) >= 0.90


def test_source_tier_b():
    p = make_pub(source="arxiv")
    assert _score_source(p) == 0.75


def test_source_tier_c():
    p = make_pub(source="direct")
    assert _score_source(p) == 0.50


def test_source_unknown():
    p = make_pub(source="random_journal")
    assert _score_source(p) > 0


def test_data_score_full():
    p = make_pub()
    score = _score_data(p, ["hash1"])
    assert score == 1.0


def test_data_score_no_doi():
    p = make_pub(doi=None)
    score = _score_data(p, None)
    assert score < 1.0


def test_citation_zero():
    assert _score_citation(0) == 0.20


def test_citation_low():
    assert _score_citation(3) == 0.50


def test_citation_medium():
    assert _score_citation(10) == 0.70


def test_citation_high():
    assert _score_citation(50) == 0.85


def test_citation_very_high():
    assert _score_citation(200) == 0.95


def test_freshness_recent():
    p = make_pub(submitted_at=datetime.now(timezone.utc) - timedelta(days=180))
    assert _score_freshness(p) == 0.95


def test_freshness_old():
    p = make_pub(submitted_at=datetime.now(timezone.utc) - timedelta(days=365 * 12))
    assert _score_freshness(p) == 0.30


def test_interpret_validated():
    assert "Validé" in _interpret_score(0.92)


def test_interpret_solid():
    assert "Solide" in _interpret_score(0.75)


def test_interpret_uncertain():
    assert "Incertain" in _interpret_score(0.55)


def test_interpret_low():
    assert "Faible" in _interpret_score(0.30)
