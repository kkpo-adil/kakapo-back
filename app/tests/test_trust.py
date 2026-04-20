import io


def test_trust_score_created_on_upload(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    response = client.get(f"/trust/score/{pub_id}")
    assert response.status_code == 200
    score = response.json()
    assert score["publication_id"] == pub_id
    assert 0.0 <= score["score"] <= 1.0
    assert score["scoring_version"] == "1.0"


def test_trust_score_components_present(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    score = client.get(f"/trust/score/{pub_id}").json()

    for field in [
        "source_score",
        "completeness_score",
        "freshness_score",
        "citation_score",
        "dataset_score",
    ]:
        assert field in score
        assert 0.0 <= score[field] <= 1.0


def test_arxiv_source_gets_full_source_score(client, sample_pdf_bytes):
    response = client.post(
        "/publications/upload",
        data={"title": "Arxiv Paper", "source": "arxiv"},
        files={"file": ("p.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    pub_id = response.json()["id"]
    score = client.get(f"/trust/score/{pub_id}").json()
    assert score["source_score"] == 1.0


def test_direct_source_gets_partial_source_score(client, sample_pdf_bytes):
    response = client.post(
        "/publications/upload",
        data={"title": "Direct Upload", "source": "direct"},
        files={"file": ("p.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    pub_id = response.json()["id"]
    score = client.get(f"/trust/score/{pub_id}").json()
    assert score["source_score"] == 0.5


def test_doi_present_gives_full_citation_score(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    score = client.get(f"/trust/score/{pub_id}").json()
    assert score["citation_score"] == 1.0


def test_no_doi_gives_zero_citation_score(client, sample_pdf_bytes):
    response = client.post(
        "/publications/upload",
        data={"title": "No DOI Paper", "source": "arxiv"},
        files={"file": ("p.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    pub_id = response.json()["id"]
    score = client.get(f"/trust/score/{pub_id}").json()
    assert score["citation_score"] == 0.0


def test_rescore_creates_new_entry(client, uploaded_publication):
    pub_id = uploaded_publication["id"]

    response = client.post(f"/trust/score/{pub_id}")
    assert response.status_code == 201

    history = client.get(f"/trust/history/{pub_id}").json()
    assert len(history) == 2


def test_score_history_ordered_desc(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    client.post(f"/trust/score/{pub_id}")
    client.post(f"/trust/score/{pub_id}")

    history = client.get(f"/trust/history/{pub_id}").json()
    assert len(history) == 3
    dates = [h["scored_at"] for h in history]
    assert dates == sorted(dates, reverse=True)


def test_trust_score_not_found(client):
    response = client.get("/trust/score/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_complete_publication_scores_higher_than_minimal(client, sample_pdf_bytes):
    complete = client.post(
        "/publications/upload",
        data={
            "title": "Complete Paper",
            "abstract": "Full abstract here.",
            "source": "hal",
            "doi": "10.1234/complete.001",
            "authors_raw": '[{"name": "Alice"}]',
            "institution_raw": "CNRS",
            "submitted_at": "2024-01-01T00:00:00",
        },
        files={"file": ("c.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    minimal = client.post(
        "/publications/upload",
        data={"title": "Minimal Paper"},
        files={"file": ("m.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )

    complete_score = client.get(f"/trust/score/{complete.json()['id']}").json()["score"]
    minimal_score = client.get(f"/trust/score/{minimal.json()['id']}").json()["score"]

    assert complete_score > minimal_score
