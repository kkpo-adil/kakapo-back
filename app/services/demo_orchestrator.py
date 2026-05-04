import re
import time
import json
import logging
from sqlalchemy.orm import Session
from app.services import anthropic_client as ac
from app.services import kakapo_search
from app.schemas.demo import DemoResult, CitedKPT

logger = logging.getLogger(__name__)

TOOL_SEARCH_KAKAPO = {
    "name": "search_kakapo",
    "description": (
        "Search the KAKAPO scientific provenance catalog for verified publications "
        "relevant to the user query. Returns certified KPT or indexed i-KPT with full "
        "metadata including cryptographic hash, publisher, date, and trust score. "
        "ALWAYS use this tool before answering any scientific or medical question. "
        "Cite ONLY publications returned by this tool. NEVER fabricate or invent "
        "KPT identifiers, DOIs, or sources."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query in natural language."},
            "kpt_status_filter": {
                "type": "string",
                "enum": ["certified", "indexed", "all"],
                "default": "all",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
        },
        "required": ["query"],
    },
}

SYSTEM_KAKAPO = (
    "You are an AI assistant integrated with the KAKAPO scientific provenance infrastructure. "
    "Your role is to answer scientific and medical questions.\n\n"
    "Strict rules:\n"
    "1. ALWAYS call search_kakapo FIRST. No exceptions.\n"
    "2. After receiving results, evaluate relevance to the user question.\n"
    "3. If certified sources (kpt_status=certified) are directly relevant: "
    "cite them using [kpt_id] inline. These are cryptographically certified.\n"
    "4. If only indexed sources (kpt_status=indexed) are directly relevant: "
    "cite them using [kpt_id] inline but add a note that they are indexed i-KPT, "
    "not yet cryptographically certified.\n"
    "5. If NO source (certified or indexed) is directly relevant to the question: "
    "Start with exactly: "
    "\'\u26a0 Aucune source KAKAPO disponible sur ce sujet. "
    "Reponse basee sur la connaissance generale de Claude - non opposable.\' "
    "Then provide a complete answer with zero citations.\n"
    "6. NEVER cite a source not directly relevant to the question asked.\n"
    "7. NEVER fabricate KPT identifiers, DOIs, hashes, or metadata.\n"
    "8. Respond in the language of the user (French or English).\n"
    "9. Remind that clinical decisions belong to licensed professionals.\n"
    "10. Your answer MUST be at least 150 words."
)

SYSTEM_RAW = (
    "You are a general-purpose AI assistant. Answer the user question to the best of "
    "your knowledge. Do not pretend to have external sources. "
    "Respond in the language of the user."
)


def _extract_cited_kpts(answer_text: str, search_results: list) -> list[CitedKPT]:
    if "Aucune source certifi" in answer_text or "non opposable" in answer_text:
        return []
    pattern = r"(?:KPT|IKPT)-[A-Z0-9]{8,12}-v\d+"
    mentioned = set(re.findall(pattern, answer_text, re.IGNORECASE))
    if not mentioned:
        return []
    cited = []
    for r in search_results:
        if r.kpt_id.upper() in {m.upper() for m in mentioned}:
            cited.append(CitedKPT(
                kpt_id=r.kpt_id,
                kpt_status=r.kpt_status,
                title=r.title,
                publisher=r.publisher,
                publication_date=r.publication_date,
                doi=r.doi,
                hash_kpt=r.hash_kpt,
                trust_score=r.trust_score,
                indexation_score=r.indexation_score,
                source_label=r.source_label,
                url_kakapo=r.url_kakapo,
            ))
    return cited[:5]


def run_demo_query(
    db: Session,
    question: str,
    with_kakapo: bool = True,
    max_loops: int = 3,
) -> DemoResult:
    t0 = time.time()
    total_input = total_output = total_cost = 0.0
    tool_calls_count = 0
    all_search_results = []

    if not with_kakapo:
        resp = ac.chat_simple(
            messages=[{"role": "user", "content": question}],
            system=SYSTEM_RAW,
        )
        answer_text = " ".join(
            b["text"] for b in resp.content if isinstance(b, dict) and b.get("type") == "text"
        )
        return DemoResult(
            question=question,
            mode="raw",
            answer_text=answer_text,
            cited_kpts=[],
            tool_calls_count=0,
            latency_ms=int((time.time() - t0) * 1000),
            estimated_cost_usd=resp.estimated_cost_usd,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )

    messages = [{"role": "user", "content": question}]
    force_tool = {"type": "tool", "name": "search_kakapo"}

    for loop in range(max_loops):
        resp = ac.chat_with_tools(
            messages=messages,
            tools=[TOOL_SEARCH_KAKAPO],
            system=SYSTEM_KAKAPO,
            tool_choice=force_tool if loop == 0 else None,
        )
        total_input += resp.input_tokens
        total_output += resp.output_tokens
        total_cost += resp.estimated_cost_usd

        if resp.stop_reason == "end_turn":
            messages.append({"role": "assistant", "content": resp.content})
            break

        if resp.stop_reason == "tool_use":
            tool_calls_count += len(resp.tool_calls)
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for tc in resp.tool_calls:
                if tc.name == "search_kakapo":
                    results = kakapo_search.search(
                        db=db,
                        query=tc.input.get("query", question),
                        limit=tc.input.get("limit", 5),
                        kpt_status_filter=tc.input.get("kpt_status_filter", "all"),
                    )
                    all_search_results.extend(results)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": json.dumps([r.model_dump() for r in results], default=str),
                    })
            messages.append({"role": "user", "content": tool_results})
            force_tool = None

    answer_text = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                answer_text = " ".join(
                    b["text"] for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            elif isinstance(content, str):
                answer_text = content
            if answer_text:
                break

    cited = _extract_cited_kpts(answer_text, all_search_results)

    return DemoResult(
        question=question,
        mode="kakapo",
        answer_text=answer_text,
        cited_kpts=cited,
        tool_calls_count=tool_calls_count,
        latency_ms=int((time.time() - t0) * 1000),
        estimated_cost_usd=round(total_cost, 6),
        input_tokens=int(total_input),
        output_tokens=int(total_output),
    )
