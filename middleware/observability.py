"""Observability middleware — Langfuse integration + dual tracing (§29.7).

Token tracking handled by Langfuse — no custom token ledger table.
Every LLM call instrumented via Langfuse @observe with custom metadata:
  {client_id, tier, job_id, artifact_type}

Dual tracing: local spans (utils/spans.py) AND Langfuse fire on every call.
Langfuse is additive — if it fails, local spans still work.
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Any

import yaml

from contracts.policy import PolicyAction, PolicyDecision
from contracts.trace import ProductionTrace

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "phase.yaml"

# Lazy-initialised Langfuse client — None until first use
_langfuse_client: Any = None


def _get_langfuse_client() -> Any:
    """Return the global Langfuse client, creating it on first call.

    Returns None if Langfuse is unavailable (import or config error).
    Local spans still work when Langfuse is down.
    """
    global _langfuse_client  # noqa: PLW0603
    if _langfuse_client is not None:
        return _langfuse_client

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse()
        logger.info("langfuse_initialised")
    except Exception:
        logger.warning("langfuse_unavailable", exc_info=True)
        _langfuse_client = None

    return _langfuse_client


# ---------------------------------------------------------------------------
# Langfuse @observe wrapper with custom metadata
# ---------------------------------------------------------------------------


def observe_with_metadata(
    *,
    client_id: str,
    tier: str,
    job_id: str,
    artifact_type: str,
) -> Any:
    """Decorator that wraps a function with Langfuse observation + metadata.

    Metadata is attached to the Langfuse trace for filtering/grouping.
    If Langfuse is unavailable, the function runs normally without tracing.
    """

    def _decorator(fn: Any) -> Any:
        @functools.wraps(fn)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            client = _get_langfuse_client()

            if client is not None:
                try:
                    _trace = client.trace(  # noqa: F841 — Langfuse auto-flushes on creation
                        name=fn.__name__,
                        metadata={
                            "client_id": client_id,
                            "tier": tier,
                            "job_id": job_id,
                            "artifact_type": artifact_type,
                        },
                    )
                except Exception:
                    logger.warning("langfuse_observe_failed", exc_info=True)

            result = fn(*args, **kwargs)

            return result

        return _wrapper

    return _decorator


# ---------------------------------------------------------------------------
# Push completed ProductionTrace to Langfuse
# ---------------------------------------------------------------------------


def trace_to_langfuse(
    production_trace: ProductionTrace,
    metadata: dict[str, Any],
    *,
    langfuse_client: Any = None,
) -> None:
    """Push a completed ProductionTrace to Langfuse as a structured trace.

    Args:
        production_trace: Finalised trace from TraceCollector.
        metadata: Must include client_id, tier, job_id, artifact_type.
        langfuse_client: Override for testing. Falls back to global client.
    """
    client = langfuse_client or _get_langfuse_client()
    if client is None:
        logger.warning("langfuse_unavailable — skipping trace push")
        return

    try:
        trace = client.trace(
            name=production_trace.job_id or "unknown_job",
            metadata=metadata,
            input={"steps": len(production_trace.steps)},
            output={
                "total_cost_usd": production_trace.total_cost_usd,
                "total_input_tokens": production_trace.total_input_tokens,
                "total_output_tokens": production_trace.total_output_tokens,
                "total_duration_ms": production_trace.total_duration_ms,
            },
        )

        # Create a generation span for each step
        for step in production_trace.steps:
            trace.generation(
                name=step.step_name,
                model=step.model,
                usage={
                    "input": step.input_tokens,
                    "output": step.output_tokens,
                    "total": step.input_tokens + step.output_tokens,
                },
                metadata={
                    "cost_usd": step.cost_usd,
                    "duration_ms": step.duration_ms,
                    "proof": step.proof,
                    "error": step.error,
                },
            )

        logger.info(
            "langfuse_trace_pushed",
            extra={
                "job_id": production_trace.job_id,
                "steps": len(production_trace.steps),
                "total_cost_usd": production_trace.total_cost_usd,
            },
        )
    except Exception:
        logger.warning("langfuse_trace_push_failed", exc_info=True)


# ---------------------------------------------------------------------------
# Dual tracing helper
# ---------------------------------------------------------------------------


def dual_trace(
    production_trace: ProductionTrace,
    metadata: dict[str, Any],
    *,
    langfuse_client: Any = None,
) -> None:
    """Record a ProductionTrace to both local spans and Langfuse.

    Local spans always succeed. Langfuse is best-effort.
    """
    from utils.spans import record_span

    # Local spans — always fire
    for step in production_trace.steps:
        record_span(
            step_id=str(step.trace_id),
            model=step.model,
            input_tokens=step.input_tokens,
            output_tokens=step.output_tokens,
            cost_usd=step.cost_usd,
            duration_ms=step.duration_ms,
            job_id=production_trace.job_id,
            step_type=step.step_name,
        )

    # Langfuse — additive, best-effort
    trace_to_langfuse(production_trace, metadata, langfuse_client=langfuse_client)


# ---------------------------------------------------------------------------
# Context size cap
# ---------------------------------------------------------------------------


def _load_config(config_path: Path) -> dict[str, Any]:
    """Read and parse phase.yaml."""
    with open(config_path) as fh:
        return yaml.safe_load(fh)  # type: ignore[no-any-return]


def check_context_size(
    *,
    prompt_tokens: int,
    config_path: Path = _DEFAULT_CONFIG,
) -> PolicyDecision:
    """Check prompt token count against configured limit.

    Returns a PolicyDecision: allow if within limit, block if over.
    """
    config = _load_config(config_path)
    cap_cfg: dict[str, Any] = config.get("context_size_cap", {})
    max_tokens: int = cap_cfg.get("max_tokens", 128_000)

    if prompt_tokens > max_tokens:
        return PolicyDecision(
            action=PolicyAction.block,
            reason=(
                f"Prompt token count {prompt_tokens:,} exceeds "
                f"context size cap of {max_tokens:,}"
            ),
            gate="context_size",
            constraints={"max_tokens": max_tokens, "prompt_tokens": prompt_tokens},
        )

    return PolicyDecision(
        action=PolicyAction.allow,
        reason=f"Context size OK: {prompt_tokens:,} of {max_tokens:,}",
        gate="context_size",
    )
