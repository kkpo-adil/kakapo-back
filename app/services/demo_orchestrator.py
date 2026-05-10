import re
import time
import json
import logging
from sqlalchemy.orm import Session
from app.services import anthropic_client as ac
from app.services import kakapo_search
from app.schemas.demo import DemoResult, CitedKPT

logger = logging.getLogger(__name__)

TOOL_EXPAND_QUERY = {
    "name": "expand_search_query",
    "description": (
        "Before searching KAKAPO, expand and translate the user query "
        "into optimal search terms. Convert French to English, fix typos, "
        "add medical synonyms, abbreviations, and related terms. "
        "Return a JSON object with: "
        "{'expanded_query': 'main search terms in English', "
        "'synonyms': ['term1', 'term2', ...], "
        "'language': 'fr|en'}"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "original_query": {
                "type": "string",
                "description": "The original user question"
            },
            "expanded_query": {
                "type": "string",
                "description": "Optimized search terms in English"
            },
            "synonyms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Medical synonyms and related terms"
            }
        },
        "required": ["original_query", "expanded_query", "synonyms"]
    }
}

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
    "You are a scientific reasoning assistant integrated with KAKAPO, "
    "a cryptographic provenance infrastructure for scientific publications.\n\n"
    "STEP 1 — QUERY EXPANSION (before searching):\n"
    "Translate and expand the user query into English medical terms.\n"
    "Examples:\n"
    "- 'cancer du sein triple négatif' → 'triple negative breast cancer TNBC'\n"
    "- 'insuffisance cardiaque' → 'heart failure cardiac dysfunction HF'\n"
    "- 'cœur artificiel' → 'artificial heart LVAD ventricular assist device'\n"
    "- 'pembrolizumab cancer sein' → 'pembrolizumab breast cancer KEYNOTE immunotherapy'\n"
    "Always search in ENGLISH. Include trial names, acronyms, brand names.\n\n"
    "STEP 2 — SEARCH (call search_kakapo once or twice maximum):\n"
    "Call search_kakapo with your expanded English terms.\n"
    "If first search returns few results, try one more search with different terms.\n"
    "NEVER search more than 2 times. After 2 searches, proceed to answer.\n\n"
    "STEP 3 — ANSWER (mandatory after searching):\n"
    "ALWAYS provide a complete answer after searching, even if results are imperfect.\n"
    "If you found relevant sources: cite them with kpt_id and reason deeply.\n"
    "If sources are partially relevant: use what you found and supplement with "
    "your knowledge, clearly distinguishing certified sources from inference.\n"
    "If no relevant sources found: say so explicitly and answer from your knowledge "
    "without fabricating KPT identifiers.\n\n"
    "STRICT RULES:\n"
    "1. NEVER fabricate KPT IDs, DOIs, hashes or any metadata.\n"
    "2. NEVER search more than 2 times.\n"
    "3. ALWAYS provide a final answer — never end with 'let me search again'.\n"
    "4. Cite ONLY publications returned by search_kakapo.\n"
    "5. Respond in the language of the user.\n"
    "6. Structure: context → findings → implications → synthesis.\n"
    "7. For certified KPTs: reason deeply on full content.\n"
    "8. For indexed i-KPTs: reason on abstract, flag as indexed source.\n"
    "9. You are NOT a substitute for medical judgment."
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
            answer_text = " ".join(
                b["text"] if isinstance(b, dict) else (b.text if hasattr(b, "text") else "")
                for b in resp.content
                if (isinstance(b, dict) and b.get("type") == "text") or
                   (hasattr(b, "type") and b.type == "text")
            )
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
                        limit=tc.input.get("limit", 10),
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

    if not answer_text:
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content_blocks = msg.get("content", [])
                if isinstance(content_blocks, list):
                    answer_text = " ".join(
                        (b["text"] if isinstance(b, dict) else (b.text if hasattr(b, "text") else ""))
                        for b in content_blocks
                        if (isinstance(b, dict) and b.get("type") == "text") or
                           (hasattr(b, "type") and b.type == "text")
                    )
                elif isinstance(content_blocks, str):
                    answer_text = content_blocks
                if answer_text:
                    break

    cited = _extract_cited_kpts(answer_text, all_search_results)


    if cited and db:
        try:
            from app.models.vo_transaction import VOTransaction, VOPartyType
            import uuid as _uuid
            for kpt_item in cited:
                try:
                    pub_id = _uuid.UUID(kpt_item.url_kakapo.split("/")[-1])
                except Exception:
                    pub_id = _uuid.uuid4()
                db.add(VOTransaction(
                    id=_uuid.uuid4(),
                    publication_id=pub_id,
                    kpt_id=kpt_item.kpt_id,
                    question=question[:500],
                    consumer_segment="demo",
                    total_amount_usd=0.40,
                    kakapo_amount_usd=0.16,
                    party_amount_usd=0.24,
                    party_type=VOPartyType.scientist,
                    party_id=None,
                ))
            db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"VO transaction failed: {e}")

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
