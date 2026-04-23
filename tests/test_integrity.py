def test_integrity_verify_not_found(client):
    r = client.post("/integrity/verify", json={
        "doi": "10.9999/nonexistent",
        "content_hash": "a" * 64,
    })
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"


def test_integrity_verify_invalid_hash(client):
    r = client.post("/integrity/verify", json={
        "doi": "10.9999/test",
        "content_hash": "tooshort",
    })
    assert r.status_code == 422
