from fastapi.testclient import TestClient


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_publications_empty(client):
    r = client.get("/publications/")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "items" in data


def test_get_publication_not_found(client):
    r = client.get("/publications/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
