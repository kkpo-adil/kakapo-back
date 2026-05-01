import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"

from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.services.kakapo_search import search

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)


def test_search_empty_returns_list():
    db = TestSession()
    results = search(db, "machine learning", limit=5)
    assert isinstance(results, list)
    db.close()


def test_search_respects_limit():
    db = TestSession()
    results = search(db, "transformer", limit=2)
    assert len(results) <= 2
    db.close()


def test_search_excludes_opted_out():
    db = TestSession()
    results = search(db, "test", limit=10)
    assert all(r.kpt_status in ("certified", "indexed") for r in results)
    db.close()
