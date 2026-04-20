import io


def test_upload_publication_success(client, sample_pdf_bytes):
    response = client.post(
        "/publications/upload",
        data={
            "title": "Deep Learning in Astrophysics",
            "abstract": "We explore neural networks applied to exoplanet detection.",
            "source": "arxiv",
            "doi": "10.1234/astro.2024.42",
            "authors_raw": '[{"name": "Jean Dupont"}]',
            "institution_raw": "Observatoire de Paris",
            "submitted_at": "2024-03-15T10:00:00",
        },
        files={"file": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Deep Learning in Astrophysics"
    assert data["source"] == "arxiv"
    assert data["file_hash"] is not None
    assert len(data["file_hash"]) == 64  # SHA-256 hex
    assert data["doi"] == "10.1234/astro.2024.42"


def test_upload_publication_missing_title(client, sample_pdf_bytes):
    response = client.post(
        "/publications/upload",
        data={"source": "arxiv"},
        files={"file": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 422


def test_upload_publication_invalid_source(client, sample_pdf_bytes):
    response = client.post(
        "/publications/upload",
        data={"title": "Test", "source": "unknown_source"},
        files={"file": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 422


def test_upload_non_pdf_rejected(client):
    response = client.post(
        "/publications/upload",
        data={"title": "Test"},
        files={"file": ("doc.txt", io.BytesIO(b"plain text"), "text/plain")},
    )
    assert response.status_code == 415


def test_get_publication_by_id(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    response = client.get(f"/publications/{pub_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == pub_id
    assert data["title"] == uploaded_publication["title"]


def test_get_publication_not_found(client):
    response = client.get("/publications/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_list_publications_empty(client):
    response = client.get("/publications/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_publications_with_results(client, uploaded_publication):
    response = client.get("/publications/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_list_publications_filter_by_source(client, uploaded_publication):
    response = client.get("/publications/?source=arxiv")
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = client.get("/publications/?source=hal")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_upload_creates_file_hash(client, sample_pdf_bytes):
    response = client.post(
        "/publications/upload",
        data={"title": "Hash Check"},
        files={"file": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 201
    assert response.json()["file_hash"] is not None


def test_pagination(client, sample_pdf_bytes):
    for i in range(5):
        client.post(
            "/publications/upload",
            data={"title": f"Publication {i}"},
            files={"file": (f"paper{i}.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
        )

    response = client.get("/publications/?limit=2&skip=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
