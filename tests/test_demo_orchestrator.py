import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.services.demo_orchestrator import run_demo_query, _extract_cited_kpts
from app.services.kakapo_search import SearchResult

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)

MOCK_SEARCH_RESULT = SearchResult(
    publication_id="11111111-0001-0001-0001-000000000001",
    kpt_id="KPT-11111111-v1",
    kpt_status="certified",
    source_origin="direct_deposit",
    title="Attention Is All You Need",
    abstract="Transformer paper",
    authors=["Vaswani, A."],
    doi="10.48550/arXiv.1706.03762",
    publisher="Google Brain",
    publication_date="2017-06-12",
    hash_kpt="abc123",
    trust_score=87,
    indexation_score=None,
    hal_id=None,
    source_label="KAKAPO certified",
    url_kakapo="https://kakapo-front.vercel.app/publications/11111111-0001",
)


def make_mock_tool_response():
    from app.services.anthropic_client import AnthropicResponse, ToolCall
    return AnthropicResponse(
        content=[{"type": "tool_use", "id": "toolu_001", "name": "search_kakapo", "input": {"query": "transformer"}}],
        stop_reason="tool_use",
        tool_calls=[ToolCall(id="toolu_001", name="search_kakapo", input={"query": "transformer"})],
        input_tokens=100,
        output_tokens=50,
        estimated_cost_usd=0.001,
        latency_ms=500,
    )


def make_mock_final_response():
    from app.services.anthropic_client import AnthropicResponse
    return AnthropicResponse(
        content=[{"type": "text", "text": "Le Transformer (KPT-11111111-v1) est fondamental."}],
        stop_reason="end_turn",
        tool_calls=[],
        input_tokens=200,
        output_tokens=100,
        estimated_cost_usd=0.002,
        latency_ms=800,
    )


def test_raw_mode_returns_no_kpts():
    from app.services.anthropic_client import AnthropicResponse
    mock_resp = AnthropicResponse(
        content=[{"type": "text", "text": "Réponse sans source."}],
        stop_reason="end_turn",
        tool_calls=[],
        input_tokens=50,
        output_tokens=30,
        estimated_cost_usd=0.0005,
        latency_ms=300,
    )
    db = TestSession()
    with patch("app.services.demo_orchestrator.ac.chat_simple", return_value=mock_resp):
        result = run_demo_query(db, "Qu'est-ce qu'un transformer ?", with_kakapo=False)
    assert result.mode == "raw"
    assert result.cited_kpts == []
    assert result.tool_calls_count == 0
    db.close()


def test_kakapo_mode_calls_tool():
    db = TestSession()
    with patch("app.services.demo_orchestrator.ac.chat_with_tools") as mock_chat, \
         patch("app.services.demo_orchestrator.kakapo_search.search", return_value=[MOCK_SEARCH_RESULT]):
        mock_chat.side_effect = [make_mock_tool_response(), make_mock_final_response()]
        result = run_demo_query(db, "transformer attention", with_kakapo=True)
    assert result.mode == "kakapo"
    assert result.tool_calls_count >= 1
    db.close()


def test_extract_cited_kpts_with_mention():
    answer = "Le papier KPT-11111111-v1 est important."
    cited = _extract_cited_kpts(answer, [MOCK_SEARCH_RESULT])
    assert len(cited) == 1
    assert cited[0].kpt_id == "KPT-11111111-v1"


def test_extract_cited_kpts_no_mention():
    answer = "Réponse générique sans citation."
    cited = _extract_cited_kpts(answer, [MOCK_SEARCH_RESULT])
    assert isinstance(cited, list)
