import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"


def test_create_publisher_without_key(client):
    r = client.post("/publishers", json={"name": "Test", "slug": "test-pub", "contract_type": "prepaid"})
    assert r.status_code == 401


def test_create_publisher_with_key(client, api_key):
    r = client.post(
        "/publishers",
        json={"name": "Test Publisher", "slug": "test-publisher", "contract_type": "prepaid"},
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "test-publisher"
    assert data["status"] == "active"


def test_list_publishers(client):
    r = client.get("/publishers")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_duplicate_publisher(client, api_key):
    client.post(
        "/publishers",
        json={"name": "Dup", "slug": "dup-slug", "contract_type": "prepaid"},
        headers={"X-API-Key": api_key},
    )
    r = client.post(
        "/publishers",
        json={"name": "Dup2", "slug": "dup-slug", "contract_type": "prepaid"},
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 409
