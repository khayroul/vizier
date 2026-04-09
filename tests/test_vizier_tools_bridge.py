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
    yield
    bridge._SESSION_STATE.clear()


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
    bridge._pre_tool_call("run_pipeline", args=args, task_id="sess-tool")

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
    bridge._pre_tool_call("run_pipeline", args=args, task_id="sess-explicit")

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
