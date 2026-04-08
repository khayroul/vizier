"""Tests for Hermes gateway overhead metering hook.

The hook uses importlib.util.spec_from_file_location to import vizier's
spans module (avoiding the hermes utils/ shadow). Tests must therefore
mock _import_spans on the hook module rather than patching utils.spans
directly — the hook never touches sys.modules["utils.spans"].
"""
from __future__ import annotations

import asyncio
import importlib.util
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_HOOK_PATH = "/Users/Executor/.hermes/hooks/vizier_token_tracker/handler.py"


def _load_hook():
    """Load a fresh copy of the hook module."""
    spec = importlib.util.spec_from_file_location("vizier_token_tracker", _HOOK_PATH)
    assert spec is not None and spec.loader is not None
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    return hook


def _run_async(coro):  # type: ignore[type-arg]
    """Helper to run async handler in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_mock_spans() -> SimpleNamespace:
    """Return a fake spans module with mock functions."""
    return SimpleNamespace(
        init_db=MagicMock(),
        record_span=MagicMock(),
        record_gateway_turn=MagicMock(),
    )


def test_hook_records_span_on_agent_end() -> None:
    """agent:end with token data records a gateway_overhead span."""
    hook = _load_hook()
    mock_spans = _make_mock_spans()

    context = {
        "platform": "telegram",
        "user_id": "666780441",
        "session_id": "test-session",
        "message": "hello",
        "response": "hi there",
        "input_tokens": 1500,
        "output_tokens": 300,
        "model": "gpt-5.4-mini",
        "api_calls": 2,
    }

    with patch.object(hook, "_import_spans", return_value=mock_spans):
        _run_async(hook.handle("agent:end", context))

    mock_spans.record_span.assert_called_once()
    kwargs = mock_spans.record_span.call_args[1]
    assert kwargs["model"] == "gpt-5.4-mini"
    assert kwargs["input_tokens"] == 1500
    assert kwargs["output_tokens"] == 300
    assert kwargs["step_type"] == "gateway_overhead"
    assert kwargs["job_id"] is None
    # Cost = (1500/1M * 0.15) + (300/1M * 0.60)
    expected_cost = (1500 / 1_000_000) * 0.15 + (300 / 1_000_000) * 0.60
    assert abs(kwargs["cost_usd"] - expected_cost) < 1e-12


def test_hook_records_gateway_turn() -> None:
    """agent:end also records a per-turn row in gateway_turns."""
    hook = _load_hook()
    mock_spans = _make_mock_spans()

    context = {
        "session_id": "sess-abc",
        "message": "what is vizier?",
        "input_tokens": 6000,
        "output_tokens": 200,
        "model": "gpt-5.4-mini",
        "api_calls": 1,
    }

    with patch.object(hook, "_import_spans", return_value=mock_spans):
        _run_async(hook.handle("agent:end", context))

    mock_spans.record_gateway_turn.assert_called_once()
    kwargs = mock_spans.record_gateway_turn.call_args[1]
    assert kwargs["session_id"] == "sess-abc"
    assert kwargs["turn_number"] == 1
    assert kwargs["input_tokens"] == 6000
    assert kwargs["delta_input"] == 6000  # first turn — delta == cumulative


def test_hook_skips_zero_token_events() -> None:
    """agent:end with 0 tokens (command-only) doesn't record a span."""
    hook = _load_hook()
    mock_spans = _make_mock_spans()

    context = {
        "input_tokens": 0,
        "output_tokens": 0,
        "model": "gpt-5.4-mini",
    }

    with patch.object(hook, "_import_spans", return_value=mock_spans):
        _run_async(hook.handle("agent:end", context))

    mock_spans.record_span.assert_not_called()


def test_hook_ignores_wrong_event_type() -> None:
    """Non agent:end events are ignored."""
    hook = _load_hook()
    mock_spans = _make_mock_spans()

    with patch.object(hook, "_import_spans", return_value=mock_spans):
        _run_async(hook.handle("agent:start", {"input_tokens": 100, "output_tokens": 50}))

    mock_spans.record_span.assert_not_called()


def test_hook_survives_span_failure() -> None:
    """If _import_spans raises, the hook logs but doesn't crash."""
    hook = _load_hook()

    context = {
        "input_tokens": 500,
        "output_tokens": 100,
        "model": "gpt-5.4-mini",
    }

    with patch.object(hook, "_import_spans", side_effect=RuntimeError("db locked")):
        # Should not raise
        _run_async(hook.handle("agent:end", context))
