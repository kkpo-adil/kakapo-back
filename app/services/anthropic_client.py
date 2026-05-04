import os
import time
import logging
from dataclasses import dataclass, field
from anthropic import Anthropic, RateLimitError, APIStatusError, APIConnectionError

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5"
INPUT_COST_PER_TOKEN = 3.0 / 1_000_000
OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class AnthropicResponse:
    content: list
    stop_reason: str
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: int


def _extract_tool_calls(content: list) -> list[ToolCall]:
    return [
        ToolCall(id=b.id, name=b.name, input=b.input)
        for b in content
        if hasattr(b, "type") and b.type == "tool_use"
    ]


def _call_with_retry(fn, max_retries: int = 3):
    last_exc = None
    for attempt in range(max_retries):
        try:
            return fn()
        except RateLimitError as e:
            raise e
        except (APIStatusError, APIConnectionError) as e:
            last_exc = e
            wait = 0.5 * (2 ** attempt)
            logger.warning(f"Anthropic error attempt {attempt+1}/{max_retries}: {e} — retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Anthropic API unreachable after {max_retries} attempts") from last_exc


def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    system: str = "",
    tool_choice: dict | None = None,
    max_tokens: int = 1024,
) -> AnthropicResponse:
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    t0 = time.time()

    def _call():
        kwargs = dict(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        return client.messages.create(**kwargs)

    resp = _call_with_retry(_call)
    latency_ms = int((time.time() - t0) * 1000)
    cost = resp.usage.input_tokens * INPUT_COST_PER_TOKEN + resp.usage.output_tokens * OUTPUT_COST_PER_TOKEN
    tool_calls = _extract_tool_calls(resp.content)
    logger.info(f"Anthropic tool call: in={resp.usage.input_tokens} out={resp.usage.output_tokens} cost=${cost:.5f} latency={latency_ms}ms stop={resp.stop_reason}")
    return AnthropicResponse(
        content=[b.model_dump() if hasattr(b, "model_dump") else b for b in resp.content],
        stop_reason=resp.stop_reason,
        tool_calls=tool_calls,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        estimated_cost_usd=round(cost, 6),
        latency_ms=latency_ms,
    )


def chat_simple(
    messages: list[dict],
    system: str = "",
    max_tokens: int = 1024,
) -> AnthropicResponse:
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    t0 = time.time()

    def _call():
        return client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )

    resp = _call_with_retry(_call)
    latency_ms = int((time.time() - t0) * 1000)
    cost = resp.usage.input_tokens * INPUT_COST_PER_TOKEN + resp.usage.output_tokens * OUTPUT_COST_PER_TOKEN
    logger.info(f"Anthropic simple: in={resp.usage.input_tokens} out={resp.usage.output_tokens} cost=${cost:.5f} latency={latency_ms}ms")
    return AnthropicResponse(
        content=[b.model_dump() if hasattr(b, "model_dump") else b for b in resp.content],
        stop_reason=resp.stop_reason,
        tool_calls=[],
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        estimated_cost_usd=round(cost, 6),
        latency_ms=latency_ms,
    )
