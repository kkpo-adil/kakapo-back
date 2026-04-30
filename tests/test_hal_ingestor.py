import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"

from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.services.hal_ingestor import ingest_batch, _map_hal_to_publication

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)

SAMPLE_DOC = {
    "halId_s": "hal-99999999",
    "title_s": ["Test Paper Title"],
    "abstract_s": ["Abstract content here"],
    "authFullName_s": ["Bob Smith"],
    "authORCIDIdExt_s": ["0000-0001-9999-0000"],
    "doiId_s": "10.1234/hal-test",
    "producedDate_s": "2022-06-01",
    "journalTitle_s": "Science",
    "openAccess_bool": True,
    "keyword_s": ["test"],
    "domain_s": ["info.info-ai"],
}


def test_map_hal_to_publication():
    mapped = _map_hal_to_publication(SAMPLE_DOC)
    assert mapped["hal_id"] == "hal-99999999"
    assert mapped["kpt_status"] == "indexed"
    assert mapped["source_origin"] == "hal"
    assert "Test Paper Title" in mapped["title"]


def test_ingest_batch_creates_publication():
    db = TestSession()
    with patch("app.services.hal_client.search", return_value=[SAMPLE_DOC]):
        with patch("app.services.citation_reach.fetch_citation_count", return_value=5):
            report = ingest_batch(db=db, query="test", max_results=1)
    assert report.total_created == 1
    assert report.total_failed == 0
    db.close()


def test_ingest_batch_idempotent():
    db = TestSession()
    doc = {**SAMPLE_DOC, "halId_s": "hal-idempotent-test", "doiId_s": "10.9999/idempotent-unique"}
    with patch("app.services.hal_client.search", return_value=[doc]):
        with patch("app.services.citation_reach.fetch_citation_count", return_value=0):
            report1 = ingest_batch(db=db, query="test", max_results=1)
            report2 = ingest_batch(db=db, query="test", max_results=1)
    assert report1.total_created == 1
    assert report2.total_skipped_existing == 1
    db.close()


def test_ingest_batch_empty():
    db = TestSession()
    with patch("app.services.hal_client.search", return_value=[]):
        report = ingest_batch(db=db, query="nothing", max_results=10)
    assert report.total_fetched == 0
    assert report.total_created == 0
    db.close()
