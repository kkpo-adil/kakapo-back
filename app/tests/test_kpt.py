import io


def test_kpt_created_on_upload(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    response = client.get(f"/kpt/publication/{pub_id}")
    assert response.status_code == 200
    kpts = response.json()
    assert len(kpts) == 1
    kpt = kpts[0]
    assert kpt["status"] == "active"
    assert kpt["version"] == 1
    assert kpt["publication_id"] == pub_id
    assert kpt["kpt_id"].startswith("KPT-")
    assert len(kpt["content_hash"]) == 64


def test_get_kpt_by_kpt_id(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    kpts = client.get(f"/kpt/publication/{pub_id}").json()
    kpt_id = kpts[0]["kpt_id"]

    response = client.get(f"/kpt/{kpt_id}")
    assert response.status_code == 200
    assert response.json()["kpt_id"] == kpt_id


def test_get_kpt_not_found(client):
    response = client.get("/kpt/KPT-NOTEXIST-v1-DEADBEEF")
    assert response.status_code == 404


def test_issue_kpt_manually(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    response = client.post(
        "/kpt/issue",
        json={
            "publication_id": pub_id,
            "orcid_authors": ["https://orcid.org/0000-0001-2345-6789"],
            "ror_institution": "https://ror.org/02feahw73",
            "dataset_hashes": ["abc123def456abc123def456abc123def456abc123def456abc123def456abc1"],
        },
    )
    assert response.status_code == 201
    kpt = response.json()
    assert kpt["version"] == 2
    assert kpt["status"] == "active"
    assert kpt["metadata_json"]["orcid_authors"] == [
        "https://orcid.org/0000-0001-2345-6789"
    ]


def test_issue_kpt_supersedes_previous(client, uploaded_publication):
    pub_id = uploaded_publication["id"]

    client.post("/kpt/issue", json={"publication_id": pub_id})

    kpts = client.get(f"/kpt/publication/{pub_id}").json()
    assert len(kpts) == 2

    statuses = {k["version"]: k["status"] for k in kpts}
    assert statuses[2] == "active"
    assert statuses[1] == "superseded"


def test_issue_kpt_publication_not_found(client):
    response = client.post(
        "/kpt/issue",
        json={"publication_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 422


def test_verify_kpt_valid(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    kpts = client.get(f"/kpt/publication/{pub_id}").json()
    kpt_id = kpts[0]["kpt_id"]

    response = client.post(f"/kpt/{kpt_id}/verify")
    assert response.status_code == 200
    result = response.json()
    assert result["valid"] is True
    assert result["status"] == "active"
    assert result["message"] == "KPT is valid and active"


def test_verify_kpt_not_found(client):
    response = client.post("/kpt/KPT-GHOST-v1-00000000/verify")
    assert response.status_code == 200
    result = response.json()
    assert result["valid"] is False
    assert result["status"] == "not_found"


def test_update_kpt_status_revoke(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    kpts = client.get(f"/kpt/publication/{pub_id}").json()
    kpt_id = kpts[0]["kpt_id"]

    response = client.patch(f"/kpt/{kpt_id}/status", json={"status": "revoked"})
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"


def test_update_kpt_status_challenge(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    kpts = client.get(f"/kpt/publication/{pub_id}").json()
    kpt_id = kpts[0]["kpt_id"]

    response = client.patch(f"/kpt/{kpt_id}/status", json={"status": "challenged"})
    assert response.status_code == 200
    assert response.json()["status"] == "challenged"


def test_update_kpt_status_invalid(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    kpts = client.get(f"/kpt/publication/{pub_id}").json()
    kpt_id = kpts[0]["kpt_id"]

    response = client.patch(f"/kpt/{kpt_id}/status", json={"status": "approved"})
    assert response.status_code == 422


def test_verify_revoked_kpt_is_invalid(client, uploaded_publication):
    pub_id = uploaded_publication["id"]
    kpts = client.get(f"/kpt/publication/{pub_id}").json()
    kpt_id = kpts[0]["kpt_id"]

    client.patch(f"/kpt/{kpt_id}/status", json={"status": "revoked"})

    response = client.post(f"/kpt/{kpt_id}/verify")
    result = response.json()
    assert result["valid"] is False
    assert result["status"] == "revoked"
