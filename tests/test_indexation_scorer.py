import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"

from app.services.indexation_scorer import compute


BASE_META = {
    "doiId_s": "10.1234/test",
    "abstract_s": ["A" * 100],
    "authFullName_s": ["Alice Martin"],
    "authORCIDIdExt_s": ["0000-0001-2345-6789"],
    "producedDate_s": "2023-01-01",
    "keyword_s": ["AI", "ML"],
    "journalTitle_s": "Nature",
    "domain_s": ["info.info-ai"],
    "openAccess_bool": True,
}


def test_max_score():
    score = compute(BASE_META, citation_count=200)
    assert score == 100


def test_min_score():
    score = compute({}, citation_count=0)
    assert score == 0


def test_no_doi():
    meta = {**BASE_META, "doiId_s": ""}
    score = compute(meta, 200)
    assert score < 100


def test_no_orcid():
    meta = {**BASE_META, "authORCIDIdExt_s": []}
    score = compute(meta, 200)
    assert score < 100


def test_citation_tiers():
    s0 = compute({}, 0)
    s1 = compute({}, 3)
    s2 = compute({}, 10)
    s3 = compute({}, 50)
    s4 = compute({}, 200)
    assert s0 < s1 < s2 < s3 < s4


def test_freshness_recent():
    from datetime import datetime, timezone
    year = datetime.now(timezone.utc).year
    meta = {**BASE_META, "producedDate_s": f"{year}-01-01"}
    score = compute(meta, 0)
    old_meta = {**BASE_META, "producedDate_s": "2000-01-01"}
    old_score = compute(old_meta, 0)
    assert score > old_score


def test_open_access_adds_points():
    meta_oa = {**BASE_META, "openAccess_bool": True}
    meta_no = {**BASE_META, "openAccess_bool": False}
    assert compute(meta_oa, 0) > compute(meta_no, 0)
