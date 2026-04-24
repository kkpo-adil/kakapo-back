import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"


def test_register_client(client):
    r = client.post("/clients/register", json={
        "organization_name": "Test IA Lab",
        "contact_email": "ia@testlab.com",
        "plan_type": "compliance_starter",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["organization_name"] == "Test IA Lab"
    assert data["api_key"].startswith("kk_")
    assert data["monthly_quota"] == 100000
    assert data["price_per_query"] == 0.002


def test_register_duplicate_email(client):
    client.post("/clients/register", json={
        "organization_name": "Lab A",
        "contact_email": "dup@lab.com",
        "plan_type": "compliance_starter",
    })
    r = client.post("/clients/register", json={
        "organization_name": "Lab B",
        "contact_email": "dup@lab.com",
        "plan_type": "compliance_starter",
    })
    assert r.status_code == 409


def test_get_me_invalid_key(client):
    r = client.get("/clients/me", headers={"X-Client-API-Key": "invalid"})
    assert r.status_code == 401


def test_get_usage(client):
    reg = client.post("/clients/register", json={
        "organization_name": "Usage Lab",
        "contact_email": "usage@lab.com",
        "plan_type": "compliance_starter",
    })
    api_key = reg.json()["api_key"]
    r = client.get("/clients/me/usage", headers={"X-Client-API-Key": api_key})
    assert r.status_code == 200
    data = r.json()
    assert data["monthly_quota"] == 100000
    assert data["quota_used"] == 0
    assert data["quota_remaining"] == 100000


def test_plan_quotas(client):
    r = client.post("/clients/register", json={
        "organization_name": "LLM Lab",
        "contact_email": "llm@lab.com",
        "plan_type": "starter_llm",
    })
    assert r.status_code == 201
    assert r.json()["monthly_quota"] == 50_000_000
