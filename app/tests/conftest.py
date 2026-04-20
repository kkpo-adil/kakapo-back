"""
Test configuration.

Uses SQLite in-memory so tests require no running PostgreSQL.
The JSONB columns defined in models fall back to JSON in SQLite — acceptable
for logic testing. PostgreSQL-specific behaviour (indexing, JSONB operators)
is out of scope for unit tests.
"""

import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Minimal valid PDF binary for upload tests."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n190\n%%EOF"
    )


@pytest.fixture
def uploaded_publication(client, sample_pdf_bytes):
    """Helper: upload a publication and return the response JSON."""
    response = client.post(
        "/publications/upload",
        data={
            "title": "Test Publication",
            "abstract": "An abstract for testing purposes.",
            "source": "arxiv",
            "doi": "10.1234/test.2024.001",
            "authors_raw": '[{"name": "Alice Dupont", "orcid": "0000-0001-2345-6789"}]',
            "institution_raw": "Université Paris Cité",
            "submitted_at": "2024-06-01T12:00:00",
        },
        files={"file": ("test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()
