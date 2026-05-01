import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.schemas.demo import DemoResult, CitedKPT
from datetime import datetime, timezone

client = TestClient(app)

MOCK_RESULT = DemoResult(
    question="Test question",
    mode="kakapo",
    answer_text="Réponse test avec KPT-11111111-v1.",
    cited_kpts=[],
    tool_calls_count=1,
    latency_ms=1200,
    estimated_cost_usd=0.002,
    input_tokens=100,
    output_tokens=50,
    request_id="test-request-id-123",
    timestamp=datetime.now(timezone.utc),
)


def test_demo_health():
    resp = client.get("/demo/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "anthropic_ok" in data
    assert "ready_for_demo" in data


def test_demo_query_kakapo():
    with patch("app.services.demo_orchestrator.run_demo_query", return_value=MOCK_RESULT):
        resp = client.post("/demo/query", json={"question": "Qu\'est-ce que le deep learning ?", "with_kakapo": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "kakapo"


def test_demo_query_raw():
    mock_raw = MOCK_RESULT.model_copy(update={"mode": "raw", "cited_kpts": [], "tool_calls_count": 0})
    with patch("app.services.demo_orchestrator.run_demo_query", return_value=mock_raw):
        resp = client.post("/demo/query", json={"question": "Qu\'est-ce que le deep learning ?", "with_kakapo": False})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "raw"


def test_demo_export_not_found():
    resp = client.post("/demo/export", json={"request_id": "inexistant-id"})
    assert resp.status_code == 404


def test_demo_query_too_short():
    resp = client.post("/demo/query", json={"question": "Hi", "with_kakapo": True})
    assert resp.status_code == 422
