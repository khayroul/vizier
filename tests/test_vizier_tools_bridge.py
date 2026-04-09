"""Tests for the repo-owned Hermes Vizier bridge."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Iterator

import pytest

from plugins import vizier_tools_bridge as bridge


@pytest.fixture(autouse=True)
def _clear_session_state() -> Iterator[None]:
    """Ensure bridge session state never leaks between tests."""

    bridge._SESSION_STATE.clear()
    bridge._TASK_TO_SESSION.clear()
    bridge._ACTIVE_SESSION_ID = ""
    yield
    bridge._SESSION_STATE.clear()
    bridge._TASK_TO_SESSION.clear()
    bridge._ACTIVE_SESSION_ID = ""


class _FakePluginContext:
    def __init__(self) -> None:
        self.tools: list[dict[str, object]] = []
        self.hooks: list[tuple[str, object]] = []

    def register_tool(self, **kwargs: object) -> None:
        self.tools.append(kwargs)

    def register_hook(self, hook_name: str, callback: object) -> None:
        self.hooks.append((hook_name, callback))


def test_register_adds_tools_and_chunk1_hooks() -> None:
    ctx = _FakePluginContext()

    bridge.register(ctx)

    tool_names = {tool["name"] for tool in ctx.tools}
    hook_names = {name for name, _ in ctx.hooks}

    assert tool_names == {"run_pipeline", "query_logs"}
    assert hook_names == {
        "pre_tool_call",
        "pre_llm_call",
        "post_llm_call",
        "on_session_start",
        "on_session_end",
    }


def test_pre_llm_call_injects_guidance_on_first_production_turn() -> None:
    result = bridge._pre_llm_call(
        session_id="sess-1",
        user_message="Create a Raya poster for DMB halal catering",
        is_first_turn=True,
        model="gpt-5.4-mini",
        platform="telegram",
    )

    assert result is not None
    assert "run_pipeline" in result["context"]
    state = bridge._SESSION_STATE["sess-1"]
    assert state.llm_turns == 1
    assert state.production_turns == 1
    assert state.guidance_injections == 1


def test_pre_llm_call_skips_non_production_chat() -> None:
    result = bridge._pre_llm_call(
        session_id="sess-2",
        user_message="How are token counts tracked in Hermes?",
        is_first_turn=True,
        model="gpt-5.4-mini",
        platform="cli",
    )

    assert result is None
    state = bridge._SESSION_STATE["sess-2"]
    assert state.llm_turns == 1
    assert state.production_turns == 0
    assert state.guidance_injections == 0


def test_pre_llm_call_reinforces_reference_turns_after_first_turn(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "reference.png"
    image_path.write_bytes(b"fake")

    result = bridge._pre_llm_call(
        session_id="sess-3",
        user_message=(
            "Please adapt this poster reference with image_url: "
            f"{image_path} and make a new poster"
        ),
        is_first_turn=False,
        model="gpt-5.4-mini",
        platform="telegram",
    )

    assert result is not None
    assert "reference_image_path" in result["context"]
    assert bridge._SESSION_STATE["sess-3"].media_context.primary_image_path == str(
        image_path
    )


def test_pre_llm_call_injects_guidance_on_iterative_production_turn() -> None:
    """Follow-up production edits (no reference, not first turn) get guidance."""
    # First turn sets up the session
    bridge._pre_llm_call(
        session_id="sess-iter",
        user_message="Create a Raya poster for DMB",
        is_first_turn=True,
        model="gpt-5.4-mini",
        platform="telegram",
    )
    # Follow-up: iterative edit, no reference image, not first turn.
    # Must contain artifact + action keywords to pass production heuristic.
    result = bridge._pre_llm_call(
        session_id="sess-iter",
        user_message="Create the same poster design but change the date",
        is_first_turn=False,
        model="gpt-5.4-mini",
        platform="telegram",
    )

    assert result is not None
    assert "run_pipeline" in result["context"]
    state = bridge._SESSION_STATE["sess-iter"]
    assert state.guidance_injections == 2
    assert state.production_turns == 2


def test_pre_llm_call_prefers_structured_gateway_media_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = tmp_path / "gateway-reference.png"
    image_path.write_bytes(b"fake")
    monkeypatch.setenv("HERMES_SESSION_MEDIA_URLS", f'["{image_path}"]')
    monkeypatch.setenv("HERMES_SESSION_MEDIA_TYPES", '["image/png"]')
    monkeypatch.setenv("HERMES_SESSION_PRIMARY_IMAGE_PATH", str(image_path))

    result = bridge._pre_llm_call(
        session_id="sess-env",
        user_message="Create a launch poster using the uploaded reference",
        is_first_turn=True,
        model="gpt-5.4-mini",
        platform="telegram",
    )

    assert result is not None
    state = bridge._SESSION_STATE["sess-env"]
    assert state.media_context.source == "gateway_env"
    assert state.media_context.primary_image_path == str(image_path)


def test_gateway_env_builds_media_manifest_for_all_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manifest includes non-image media (e.g. PDF, audio) that were previously filtered out."""
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"fake-jpg")
    pdf_path = tmp_path / "brief.pdf"
    pdf_path.write_bytes(b"fake-pdf")

    monkeypatch.setenv(
        "HERMES_SESSION_MEDIA_URLS", f'["{image_path}", "{pdf_path}"]'
    )
    monkeypatch.setenv(
        "HERMES_SESSION_MEDIA_TYPES", '["image/jpeg", "application/pdf"]'
    )

    result = bridge._pre_llm_call(
        session_id="sess-manifest",
        user_message="Create a poster using the uploaded files",
        is_first_turn=True,
        model="gpt-5.4-mini",
        platform="telegram",
    )

    assert result is not None
    state = bridge._SESSION_STATE["sess-manifest"]
    manifest = state.media_context.media_manifest

    # Both entries should be in the manifest
    assert len(manifest) == 2
    mime_types = {entry.mime_type for entry in manifest}
    assert "image/jpeg" in mime_types
    assert "application/pdf" in mime_types

    # Image should still appear in backward-compat image_paths
    assert len(state.media_context.media_paths) == 1
    assert str(image_path) in state.media_context.media_paths[0]

    # Primary image should be marked in manifest
    primary_entries = [e for e in manifest if e.role == "primary_image"]
    assert len(primary_entries) == 1
    assert primary_entries[0].mime_type == "image/jpeg"


def test_pre_tool_call_enriches_run_pipeline_args_from_session_media_context(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "tool-reference.png"
    image_path.write_bytes(b"fake")

    bridge._pre_llm_call(
        session_id="sess-tool",
        user_message=f"Make a poster from image_url: {image_path}",
        is_first_turn=True,
        model="gpt-5.4-mini",
        platform="telegram",
    )

    args = {"request": "Create a poster for DMB"}
    # Use a different task_id to match real Hermes behaviour (task_id != session_id).
    bridge._pre_tool_call("run_pipeline", args=args, task_id="task-uuid-1")

    assert args["platform"] == "telegram"
    assert args["reference_image_path"] == str(image_path)
    assert bridge._SESSION_STATE["sess-tool"].tool_enrichments == 1


def test_pre_tool_call_keeps_explicit_reference_args() -> None:
    bridge._on_session_start(
        session_id="sess-explicit",
        model="gpt-5.4-mini",
        platform="telegram",
    )

    args = {
        "request": "Create a poster",
        "reference_image_path": "/tmp/already-set.png",
        "platform": "cli",
    }
    # Use a different task_id to match real Hermes behaviour (task_id != session_id).
    bridge._pre_tool_call("run_pipeline", args=args, task_id="task-uuid-2")

    assert args["reference_image_path"] == "/tmp/already-set.png"
    assert args["platform"] == "cli"
    assert bridge._SESSION_STATE["sess-explicit"].tool_enrichments == 0


def test_session_lifecycle_clears_state_on_end() -> None:
    bridge._on_session_start(
        session_id="sess-4",
        model="gpt-5.4-mini",
        platform="telegram",
    )
    bridge._pre_llm_call(
        session_id="sess-4",
        user_message="Generate a brochure for a launch",
        is_first_turn=True,
        model="gpt-5.4-mini",
        platform="telegram",
    )
    bridge._post_llm_call(
        session_id="sess-4",
        user_message="Generate a brochure for a launch",
        assistant_response="I created the draft.",
        model="gpt-5.4-mini",
        platform="telegram",
    )

    assert "sess-4" in bridge._SESSION_STATE
    bridge._on_session_end(
        session_id="sess-4",
        completed=True,
        interrupted=False,
        model="gpt-5.4-mini",
        platform="telegram",
    )
    assert "sess-4" not in bridge._SESSION_STATE


def test_extract_reference_image_path_requires_real_file(tmp_path: Path) -> None:
    image_path = tmp_path / "cached-reference.webp"
    image_path.write_bytes(b"reference")

    text = f"vision_analyze with image_url: {image_path}"
    assert bridge._extract_reference_image_path(text) == str(image_path)
    assert bridge._extract_reference_image_paths(text) == (str(image_path),)


def test_extract_reference_image_url_recovers_hosted_reference() -> None:
    text = "Please adapt this layout from image_url: https://example.com/ref.jpg"
    assert bridge._extract_reference_image_url(text) == "https://example.com/ref.jpg"


def test_pre_tool_call_resolves_session_when_task_id_differs(
    tmp_path: Path,
) -> None:
    """Regression: Hermes passes a per-turn UUID as task_id, not session_id.

    pre_tool_call must still find the session state created by pre_llm_call
    even when the two identifiers are completely different.
    """
    image_path = tmp_path / "distinct-ids.png"
    image_path.write_bytes(b"fake")

    session_id = "session-abc-123"
    task_id = "task-uuid-999-differs"

    bridge._on_session_start(
        session_id=session_id,
        model="gpt-5.4-mini",
        platform="whatsapp",
    )
    bridge._pre_llm_call(
        session_id=session_id,
        user_message=f"Create a poster from image_url: {image_path}",
        is_first_turn=True,
        model="gpt-5.4-mini",
        platform="whatsapp",
    )

    args: dict[str, object] = {"request": "Make a poster"}
    bridge._pre_tool_call("run_pipeline", args=args, task_id=task_id)

    # Enrichment must have found the session state despite different task_id.
    assert args["platform"] == "whatsapp"
    assert args["reference_image_path"] == str(image_path)
    assert args.get("_hermes_session_id") == session_id
    assert bridge._SESSION_STATE[session_id].tool_enrichments == 1

    # The mapping should be cached for subsequent tool calls in the same turn.
    assert bridge._TASK_TO_SESSION[task_id] == session_id

    # Second tool call in same turn should still resolve via cached mapping.
    args2: dict[str, object] = {"request": "Make another poster"}
    bridge._pre_tool_call("run_pipeline", args=args2, task_id=task_id)
    assert args2["platform"] == "whatsapp"
    assert bridge._SESSION_STATE[session_id].tool_enrichments == 2


def test_session_end_cleans_task_to_session_mapping() -> None:
    """_on_session_end must evict stale task→session entries."""
    session_id = "sess-cleanup"
    task_id = "task-cleanup-uuid"

    bridge._on_session_start(session_id=session_id, model="gpt-5.4-mini")
    bridge._pre_llm_call(
        session_id=session_id,
        user_message="Create a poster for DMB",
        is_first_turn=True,
        model="gpt-5.4-mini",
    )
    bridge._pre_tool_call("run_pipeline", args={"request": "poster"}, task_id=task_id)

    assert task_id in bridge._TASK_TO_SESSION

    bridge._on_session_end(session_id=session_id, completed=True)

    assert task_id not in bridge._TASK_TO_SESSION
    assert bridge._ACTIVE_SESSION_ID == ""


def test_live_plugin_loader_still_exposes_bridge_helpers() -> None:
    import importlib.util

    plugin_path = Path.home() / ".hermes" / "plugins" / "vizier_tools" / "__init__.py"
    spec = importlib.util.spec_from_file_location("vizier_tools_live", plugin_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod._extract_nested({"pdf_path": "/tmp/out.pdf"}, "pdf_path") == "/tmp/out.pdf"
    ctx = _FakePluginContext()
    mod.register(ctx)
    assert {tool["name"] for tool in ctx.tools} == {"run_pipeline", "query_logs"}
