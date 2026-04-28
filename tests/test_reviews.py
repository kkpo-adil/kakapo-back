import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"


def test_get_reviews_empty(client):
    r = client.get("/reviews/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 200
    assert r.json() == []


def test_submit_review_unauthenticated(client):
    r = client.post("/reviews/00000000-0000-0000-0000-000000000000", json={
        "methodology_score": 4,
        "data_score": 3,
        "reproducibility_score": 4,
        "clarity_score": 5,
        "flag": "none",
    })
    assert r.status_code == 401


def test_submit_review_publication_not_found(client):
    r = client.post("/reviews/00000000-0000-0000-0000-000000000000",
        json={
            "methodology_score": 4,
            "data_score": 3,
            "reproducibility_score": 4,
            "clarity_score": 5,
            "flag": "none",
        },
        headers={"Authorization": "Bearer fake_token"}
    )
    assert r.status_code in [401, 404]
