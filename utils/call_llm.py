"""Single LLM call point for all of Vizier.

Implements prompt caching (§13.7):
  - Stable prefix (persona + templates + client config) is cacheable.
  - Variable suffix (job-specific content) is not cached.

For Anthropic calls: ``cache_control`` headers on stable blocks.
For OpenAI calls: structured so the provider can cache the prefix.
Token-Efficient Tool Use header enabled for Claude 4 models.

All memory operations routed to GPT-5.4-mini (Month 1-2).  Anti-drift #54.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from utils.spans import DB_PATH, record_memory_routing, track_span  # noqa: F401 — DB_PATH re-exported for test monkeypatching

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing (USD per 1M tokens) — Month 1-2 baseline
# ---------------------------------------------------------------------------

_PRICING: dict[str, dict[str, float]] = {
    "gpt-5.4-mini": {"input": 0.15, "output": 0.60, "cached_input": 0.075},
    # Embedding model — input-only, no output tokens
    "text-embedding-3-small": {"input": 0.02, "output": 0.0, "cached_input": 0.02},
    # Anthropic models inactive Month 1-2 but priced for future use
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cached_input": 0.30},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00, "cached_input": 0.08},
}

# Memory operation types that get logged to memory_routing_log
_MEMORY_OPS = frozenset({
    "summarise",
    "compress",
    "retrieve",
    "store",
    "extract",
    "classify",
})


def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return cost in USD for the given token counts."""
    pricing = _PRICING.get(model, _PRICING["gpt-5.4-mini"])
    cost = (input_tokens / 1_000_000) * pricing["input"] + (
        output_tokens / 1_000_000
    ) * pricing["output"]
    return cost


# ---------------------------------------------------------------------------
# Request builders (public — used by tests to inspect structure)
# ---------------------------------------------------------------------------


def build_openai_request(
    *,
    stable_prefix: list[dict[str, str]],
    variable_suffix: list[dict[str, str]],
    model: str = "gpt-5.4-mini",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an OpenAI-compatible chat completions request body.

    The stable prefix messages come first so the provider's automatic
    prompt caching can recognise and cache the shared prefix.
    """
    messages: list[dict[str, str]] = [*stable_prefix, *variable_suffix]

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }
    if response_format is not None:
        body["response_format"] = response_format
    return body


def build_anthropic_request(
    *,
    stable_prefix: list[dict[str, str]],
    variable_suffix: list[dict[str, str]],
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Build an Anthropic Messages API request body and headers.

    Returns ``(body, headers)``.

    - System messages from *stable_prefix* get ``cache_control``
      ``{"type": "ephemeral"}`` so Anthropic caches them.
    - Non-system messages in the variable suffix are sent as-is
      (no ``cache_control``).
    - The ``anthropic-beta`` header enables Token-Efficient Tool Use
      for Claude 4 models.
    """
    # Separate system messages (for caching) from user/assistant turns
    system_blocks: list[dict[str, Any]] = []
    prefix_turns: list[dict[str, Any]] = []

    for msg in stable_prefix:
        if msg.get("role") == "system":
            system_blocks.append(
                {
                    "type": "text",
                    "text": msg["content"],
                    "cache_control": {"type": "ephemeral"},
                }
            )
        else:
            prefix_turns.append({"role": msg["role"], "content": msg["content"]})

    # Variable suffix — no cache_control
    suffix_turns: list[dict[str, Any]] = [
        {"role": msg["role"], "content": msg["content"]} for msg in variable_suffix
    ]

    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_blocks,
        "messages": [*prefix_turns, *suffix_turns],
    }

    headers: dict[str, str] = {
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "anthropic-beta": "token-efficient-tools-2025-02-19",
    }

    return body, headers


# ---------------------------------------------------------------------------
# Unified call function
# ---------------------------------------------------------------------------


def _is_anthropic_model(model: str) -> bool:
    return model.startswith("claude")


@track_span
def call_llm(
    *,
    stable_prefix: list[dict[str, str]],
    variable_suffix: list[dict[str, str]],
    model: str = "gpt-5.4-mini",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
    job_id: str | None = None,
    operation_type: str | None = None,
) -> dict[str, Any]:
    """Single LLM call point for all of Vizier.

    Returns a standardised response dict::

        {
            "content": str,
            "model": str,
            "input_tokens": int,
            "output_tokens": int,
            "cost_usd": float,
        }
    """
    if _is_anthropic_model(model):
        body, headers = build_anthropic_request(
            stable_prefix=stable_prefix,
            variable_suffix=variable_suffix,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        headers["x-api-key"] = api_key

        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            json=body,
            headers=headers,
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        input_tokens = data.get("usage", {}).get("input_tokens", 0)
        output_tokens = data.get("usage", {}).get("output_tokens", 0)
    else:
        # OpenAI-compatible path (GPT-5.4-mini default)
        req_body = build_openai_request(
            stable_prefix=stable_prefix,
            variable_suffix=variable_suffix,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        api_key = os.environ.get("OPENAI_API_KEY", "")

        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            json=req_body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        input_tokens = data.get("usage", {}).get("prompt_tokens", 0)
        output_tokens = data.get("usage", {}).get("completion_tokens", 0)

    cost_usd = _calculate_cost(model, input_tokens, output_tokens)

    # Log memory routing operations
    if operation_type and operation_type in _MEMORY_OPS:
        record_memory_routing(
            operation=operation_type,
            model_used=model,
            tokens=input_tokens + output_tokens,
        )

    return {
        "content": content,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }
