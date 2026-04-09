"""Repo-owned Hermes bridge for the live ``vizier_tools`` plugin.

This module is the version-controlled source of truth for the Hermes↔Vizier
adapter. The live plugin in ``~/.hermes/plugins/vizier_tools/`` should stay a
thin loader that imports this file via ``importlib.util.spec_from_file_location``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_VIZIER_ROOT = Path(__file__).resolve().parents[1]
_HERMES_ENV_PATH = Path.home() / ".hermes" / ".env"
_PYTHON_BIN = "/opt/homebrew/bin/python3.11"

_REFERENCE_IMAGE_PATTERNS = (
    re.compile(r"image_url:\s*(/\S+\.(?:png|jpe?g|webp|gif))", re.IGNORECASE),
    re.compile(r"(/\S+\.(?:png|jpe?g|webp|gif))", re.IGNORECASE),
)
_REFERENCE_URL_PATTERNS = (
    re.compile(
        r"image_url:\s*(https?://\S+\.(?:png|jpe?g|webp|gif))",
        re.IGNORECASE,
    ),
    re.compile(r"(https?://\S+\.(?:png|jpe?g|webp|gif))", re.IGNORECASE),
)

_ARTIFACT_KEYWORDS = {
    "poster",
    "brochure",
    "book",
    "ebook",
    "invoice",
    "proposal",
    "document",
    "profile",
    "caption",
    "calendar",
    "flyer",
    "visual",
    "artwork",
    "illustration",
    "deck",
    "slideshow",
    "children",
    "branding",
}
_ACTION_KEYWORDS = {
    "create",
    "make",
    "generate",
    "design",
    "build",
    "produce",
    "draft",
    "prepare",
    "write",
    "rework",
    "adapt",
    "buat",
    "hasilkan",
    "reka",
    "tulis",
    "sediakan",
}

_SESSION_STATE: dict[str, "BridgeSessionState"] = {}


@dataclass(frozen=True)
class BridgeMediaContext:
    """Normalized per-turn media context for bridge-side tool enrichment."""

    media_paths: tuple[str, ...] = ()
    media_urls: tuple[str, ...] = ()
    primary_image_path: str = ""
    primary_image_url: str = ""
    source: str = ""

    def has_reference(self) -> bool:
        return bool(self.primary_image_path or self.primary_image_url)


@dataclass
class BridgeSessionState:
    """Lightweight per-session bridge state for hook coordination."""

    session_id: str
    platform: str = ""
    model: str = ""
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    llm_turns: int = 0
    production_turns: int = 0
    guidance_injections: int = 0
    tool_enrichments: int = 0
    last_user_preview: str = ""
    last_assistant_preview: str = ""
    media_context: BridgeMediaContext = field(default_factory=BridgeMediaContext)


def register(ctx: object) -> None:
    """Register tools and Hermes lifecycle hooks."""

    try:
        ctx.register_tool(  # type: ignore[attr-defined]
            name="run_pipeline",
            toolset="vizier-core",
            schema=_RUN_PIPELINE_SCHEMA,
            handler=_run_pipeline_handler,
            check_fn=lambda: True,
            description=(
                "Execute Vizier governed production pipeline. Routes requests "
                "to the correct workflow (poster, brochure, document, "
                "children's book, ebook, invoice, etc.) with readiness + "
                "policy gates. Use action='list' to see available workflows."
            ),
        )
        logger.info("Vizier bridge: registered run_pipeline")

        ctx.register_tool(  # type: ignore[attr-defined]
            name="query_logs",
            toolset="vizier-core",
            schema=_QUERY_LOGS_SCHEMA,
            handler=_query_logs_handler,
            check_fn=lambda: True,
            description="Inspect Vizier span traces: LLM call chains, token usage, costs",
        )
        logger.info("Vizier bridge: registered query_logs")

        ctx.register_hook("pre_llm_call", _pre_llm_call)  # type: ignore[attr-defined]
        ctx.register_hook("post_llm_call", _post_llm_call)  # type: ignore[attr-defined]
        ctx.register_hook("pre_tool_call", _pre_tool_call)  # type: ignore[attr-defined]
        ctx.register_hook("on_session_start", _on_session_start)  # type: ignore[attr-defined]
        ctx.register_hook("on_session_end", _on_session_end)  # type: ignore[attr-defined]
        logger.info("Vizier bridge: registered lifecycle hooks")
    except Exception as exc:
        logger.error("Vizier bridge registration failed: %s", exc, exc_info=True)


_RUN_PIPELINE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": (
                "Set to 'list' to see available workflows, or omit to run a workflow"
            ),
            "enum": ["list"],
        },
        "request": {
            "type": "string",
            "description": (
                "The production request (e.g. 'Create a Raya poster for DMB halal "
                "catering')"
            ),
        },
        "client_id": {
            "type": "string",
            "description": (
                "Client identifier (e.g. 'dmb', 'autohub'). Defaults to 'default'."
            ),
        },
        "job_id": {
            "type": "string",
            "description": "Job identifier. Auto-generated if not provided.",
        },
        "platform": {
            "type": "string",
            "description": (
                "Origin platform hint (for example 'telegram') so Vizier can pick "
                "platform-appropriate output sizing."
            ),
        },
        "reference_image_path": {
            "type": "string",
            "description": (
                "Absolute local path to a cached reference image to adapt from when "
                "producing a poster."
            ),
        },
        "reference_image_url": {
            "type": "string",
            "description": (
                "Hosted reference image URL to adapt from when producing a poster."
            ),
        },
        "reference_notes": {
            "type": "string",
            "description": (
                "Optional guidance about which elements from the reference image to "
                "borrow or adapt."
            ),
        },
    },
    "required": [],
}

_QUERY_LOGS_SCHEMA = {
    "type": "object",
    "properties": {
        "last_n": {
            "type": "integer",
            "description": "Return the last N span entries (default 10)",
        },
        "step_type": {
            "type": "string",
            "description": "Filter by step type (e.g. 'embedding', 'gateway_overhead')",
        },
        "summary": {
            "type": "boolean",
            "description": "Return token totals instead of individual entries",
        },
    },
    "required": [],
}


def _get_session_state(
    session_id: str,
    *,
    platform: str = "",
    model: str = "",
) -> BridgeSessionState:
    state = _SESSION_STATE.get(session_id)
    if state is None:
        state = BridgeSessionState(session_id=session_id)
        _SESSION_STATE[session_id] = state
    if platform:
        state.platform = platform
    if model:
        state.model = model
    return state


def _looks_like_production_request(text: str) -> bool:
    """Heuristic: identify turns where a governed Vizier tool hint is useful."""

    lowered = (text or "").lower()
    if not lowered.strip():
        return False
    artifact_hit = any(keyword in lowered for keyword in _ARTIFACT_KEYWORDS)
    action_hit = any(keyword in lowered for keyword in _ACTION_KEYWORDS)
    return artifact_hit and action_hit


def _has_reference_marker(text: str) -> bool:
    return bool(
        _extract_reference_image_path(text) or _extract_reference_image_url(text)
    )


def _extract_reference_image_paths(text: str) -> tuple[str, ...]:
    """Recover all local image paths from gateway-enriched text."""

    if not text:
        return ()
    found: list[str] = []
    seen: set[str] = set()
    for pattern in _REFERENCE_IMAGE_PATTERNS:
        for match in pattern.finditer(text):
            candidate = match.group(1)
            if not candidate or candidate in seen:
                continue
            if Path(candidate).is_file():
                seen.add(candidate)
                found.append(candidate)
    return tuple(found)


def _extract_reference_image_urls(text: str) -> tuple[str, ...]:
    """Recover all hosted image URLs from gateway-enriched text."""

    if not text:
        return ()
    found: list[str] = []
    seen: set[str] = set()
    for pattern in _REFERENCE_URL_PATTERNS:
        for match in pattern.finditer(text):
            candidate = match.group(1)
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            found.append(candidate)
    return tuple(found)


def _load_json_list_env(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return ()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _extract_env_media_context() -> BridgeMediaContext:
    """Read structured gateway media metadata when Hermes exposes it."""

    primary_path = os.getenv("HERMES_SESSION_PRIMARY_IMAGE_PATH", "").strip()
    primary_url = os.getenv("HERMES_SESSION_PRIMARY_IMAGE_URL", "").strip()
    media_urls = _load_json_list_env("HERMES_SESSION_MEDIA_URLS")
    media_types = _load_json_list_env("HERMES_SESSION_MEDIA_TYPES")

    image_paths: list[str] = []
    image_urls: list[str] = []
    for index, candidate in enumerate(media_urls):
        media_type = media_types[index] if index < len(media_types) else ""
        is_image = media_type.startswith("image/")
        if Path(candidate).is_file():
            if is_image or candidate.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                image_paths.append(candidate)
        elif candidate.startswith(("http://", "https://")):
            if is_image or candidate.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                image_urls.append(candidate)

    if primary_path and not Path(primary_path).is_file():
        primary_path = ""
    if primary_url and not primary_url.startswith(("http://", "https://")):
        primary_url = ""

    if not primary_path and image_paths:
        primary_path = image_paths[0]
    if not primary_url and image_urls:
        primary_url = image_urls[0]

    if not (primary_path or primary_url or image_paths or image_urls):
        return BridgeMediaContext()

    return BridgeMediaContext(
        media_paths=tuple(image_paths),
        media_urls=tuple(image_urls),
        primary_image_path=primary_path,
        primary_image_url=primary_url,
        source="gateway_env",
    )


def _extract_message_media_context(text: str) -> BridgeMediaContext:
    """Fallback media envelope derived from gateway-enriched message text."""

    image_paths = _extract_reference_image_paths(text)
    image_urls = _extract_reference_image_urls(text)
    if not image_paths and not image_urls:
        return BridgeMediaContext()
    return BridgeMediaContext(
        media_paths=image_paths,
        media_urls=image_urls,
        primary_image_path=image_paths[0] if image_paths else "",
        primary_image_url=image_urls[0] if image_urls else "",
        source="gateway_text",
    )


def _resolve_media_context(text: str) -> BridgeMediaContext:
    """Prefer structured gateway metadata, then fall back to text recovery."""

    env_media = _extract_env_media_context()
    if env_media.has_reference():
        return env_media
    return _extract_message_media_context(text)


def _preview(text: str, *, limit: int = 160) -> str:
    compact = re.sub(r"\s+", " ", (text or "")).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _build_guidance(platform: str, *, has_reference: bool) -> str:
    parts = [
        "For governed artifact requests, prefer the `run_pipeline` tool instead of handling production manually.",
    ]
    if has_reference:
        parts.append(
            "If the message includes a cached image path or `image_url`, pass it via `reference_image_path` or `reference_image_url`."
        )
    if platform:
        parts.append(
            f"Pass `platform=\"{platform}\"` when channel-specific sizing or delivery matters."
        )
    return " ".join(parts)


def _on_session_start(
    session_id: str,
    model: str = "",
    platform: str = "",
    **kwargs: Any,
) -> None:
    del kwargs
    state = _get_session_state(session_id, platform=platform, model=model)
    logger.info(
        "Vizier bridge session start: %s",
        json.dumps(
            {
                "session_id": session_id,
                "platform": state.platform,
                "model": state.model,
                "started_at": state.started_at,
            },
            sort_keys=True,
        ),
    )


def _pre_llm_call(
    session_id: str,
    user_message: str = "",
    is_first_turn: bool = False,
    model: str = "",
    platform: str = "",
    **kwargs: Any,
) -> dict[str, str] | None:
    del kwargs
    state = _get_session_state(session_id, platform=platform, model=model)
    state.llm_turns += 1
    state.last_user_preview = _preview(user_message)
    state.media_context = _resolve_media_context(user_message)

    is_production = _looks_like_production_request(user_message)
    has_reference = state.media_context.has_reference()
    if is_production:
        state.production_turns += 1

    if not is_production:
        return None
    if not is_first_turn and not has_reference:
        return None

    state.guidance_injections += 1
    guidance = _build_guidance(state.platform or platform, has_reference=has_reference)
    logger.info(
        "Vizier bridge guidance injected: %s",
        json.dumps(
            {
                "session_id": session_id,
                "platform": state.platform or platform,
                "is_first_turn": bool(is_first_turn),
                "has_reference": has_reference,
                "media_source": state.media_context.source,
            },
            sort_keys=True,
        ),
    )
    return {"context": guidance}


def _post_llm_call(
    session_id: str,
    user_message: str = "",
    assistant_response: str = "",
    model: str = "",
    platform: str = "",
    **kwargs: Any,
) -> None:
    del kwargs
    state = _get_session_state(session_id, platform=platform, model=model)
    state.last_user_preview = _preview(user_message)
    state.last_assistant_preview = _preview(assistant_response)

    if not _looks_like_production_request(user_message):
        return

    logger.info(
        "Vizier bridge turn summary: %s",
        json.dumps(
            {
                "session_id": session_id,
                "platform": state.platform or platform,
                "llm_turns": state.llm_turns,
                "production_turns": state.production_turns,
                "guidance_injections": state.guidance_injections,
                "tool_enrichments": state.tool_enrichments,
                "media_source": state.media_context.source,
                "assistant_mentions_pipeline": (
                    "pipeline complete:" in assistant_response.lower()
                ),
                "user_preview": state.last_user_preview,
                "assistant_preview": state.last_assistant_preview,
            },
            sort_keys=True,
        ),
    )


def _pre_tool_call(
    tool_name: str,
    args: dict[str, Any] | None = None,
    task_id: str = "",
    **kwargs: Any,
) -> None:
    del kwargs
    if tool_name != "run_pipeline" or not isinstance(args, dict):
        return

    state = _SESSION_STATE.get(task_id)
    media_context = state.media_context if state else BridgeMediaContext()
    enriched_fields: list[str] = []

    platform_hint = ""
    if state and state.platform:
        platform_hint = state.platform
    else:
        platform_hint = os.getenv("HERMES_SESSION_PLATFORM", "").strip()

    if platform_hint and not args.get("platform"):
        args["platform"] = platform_hint
        enriched_fields.append("platform")

    if media_context.primary_image_path and not args.get("reference_image_path"):
        args["reference_image_path"] = media_context.primary_image_path
        enriched_fields.append("reference_image_path")
    if media_context.primary_image_url and not args.get("reference_image_url"):
        args["reference_image_url"] = media_context.primary_image_url
        enriched_fields.append("reference_image_url")

    if not enriched_fields:
        return

    if state:
        state.tool_enrichments += 1

    logger.info(
        "Vizier bridge tool enrichment: %s",
        json.dumps(
            {
                "session_id": task_id,
                "tool_name": tool_name,
                "media_source": media_context.source,
                "enriched_fields": enriched_fields,
            },
            sort_keys=True,
        ),
    )


def _on_session_end(
    session_id: str,
    completed: bool = False,
    interrupted: bool = False,
    model: str = "",
    platform: str = "",
    **kwargs: Any,
) -> None:
    del kwargs
    state = _SESSION_STATE.pop(
        session_id,
        BridgeSessionState(session_id=session_id, platform=platform, model=model),
    )
    if platform and not state.platform:
        state.platform = platform
    if model and not state.model:
        state.model = model

    logger.info(
        "Vizier bridge session end: %s",
        json.dumps(
            {
                "session_id": session_id,
                "completed": bool(completed),
                "interrupted": bool(interrupted),
                "platform": state.platform,
                "model": state.model,
                "llm_turns": state.llm_turns,
                "production_turns": state.production_turns,
                "guidance_injections": state.guidance_injections,
                "tool_enrichments": state.tool_enrichments,
                "media_source": state.media_context.source,
                "last_user_preview": state.last_user_preview,
                "last_assistant_preview": state.last_assistant_preview,
            },
            sort_keys=True,
        ),
    )


def _list_workflows() -> str:
    """List available workflow YAMLs from manifests/workflows/."""

    workflows_dir = _VIZIER_ROOT / "manifests" / "workflows"
    if not workflows_dir.exists():
        return "No workflows directory found at manifests/workflows/"
    yamls = sorted(workflows_dir.glob("*.yaml"))
    lines = ["Available workflows:"]
    for path in yamls:
        lines.append(f"  - {path.stem}")
    return "\n".join(lines)


def _extract_nested(data: dict[str, Any], key: str) -> Any:
    """Walk a nested dict (including lists) to find a key."""

    if key in data:
        return data[key]
    for value in data.values():
        if isinstance(value, dict):
            found = _extract_nested(value, key)
            if found is not None:
                return found
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found = _extract_nested(item, key)
                    if found is not None:
                        return found
    return None


def _extract_reference_image_path(text: str) -> str | None:
    """Best-effort extraction of a cached image path from gateway-enriched text."""

    paths = _extract_reference_image_paths(text)
    return paths[0] if paths else None


def _extract_reference_image_url(text: str) -> str | None:
    """Best-effort extraction of a hosted image URL from gateway-enriched text."""

    urls = _extract_reference_image_urls(text)
    return urls[0] if urls else None


def _run_pipeline_handler(args: dict[str, Any], **kwargs: Any) -> str:
    """Handle ``run_pipeline`` tool calls via subprocess isolation."""

    del kwargs

    if args.get("action") == "list":
        return _list_workflows()

    request = args.get("request", "")
    if not request:
        return "Error: 'request' is required. Describe what you want to produce."

    client_id = args.get("client_id", "default")
    job_id = args.get("job_id") or _generate_job_id()
    platform = args.get("platform")
    reference_image_path = args.get("reference_image_path") or _extract_reference_image_path(
        request
    )
    reference_image_url = args.get("reference_image_url") or _extract_reference_image_url(
        request
    )
    reference_notes = args.get("reference_notes")

    # Thread Hermes session_id into governed execution (hardening 1.6)
    hermes_session_id: str | None = None
    if _SESSION_STATE:
        # Use the most recent session (there's typically only one active)
        latest_state = next(iter(_SESSION_STATE.values()))
        hermes_session_id = latest_state.session_id

    run_kwargs: dict[str, Any] = {
        "raw_input": request,
        "client_id": client_id,
        "job_id": job_id,
    }
    if hermes_session_id:
        run_kwargs["hermes_session_id"] = hermes_session_id
    if platform:
        run_kwargs["platform"] = platform
    if reference_image_path:
        run_kwargs["reference_image_path"] = reference_image_path
    if reference_image_url:
        run_kwargs["reference_image_url"] = reference_image_url
    if reference_notes:
        run_kwargs["reference_notes"] = reference_notes

    script = f"""
import json
import sys
sys.path.insert(0, {str(_VIZIER_ROOT)!r})
from tools.orchestrate import PolicyDenied, ReadinessError, run_governed
try:
    result = run_governed(**json.loads({json.dumps(json.dumps(run_kwargs))!r}))
    print(json.dumps({{"ok": True, "result": result}}, default=str))
except ReadinessError as exc:
    print(json.dumps({{"ok": False, "error_type": "readiness", "error": str(exc)}}))
except PolicyDenied as exc:
    print(json.dumps({{"ok": False, "error_type": "policy", "error": str(exc)}}))
except Exception as exc:
    print(json.dumps({{"ok": False, "error_type": "runtime", "error": str(exc)}}))
"""

    try:
        env = _load_subprocess_env()
        proc = subprocess.run(
            [_PYTHON_BIN, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(_VIZIER_ROOT),
            env=env,
            timeout=300,
        )
        output_lines = proc.stdout.strip().splitlines()
        json_line = ""
        for line in reversed(output_lines):
            line = line.strip()
            if line.startswith("{"):
                json_line = line
                break

        if not json_line:
            stderr_tail = (proc.stderr or "")[-500:]
            logger.error(
                "Pipeline subprocess produced no JSON. stderr: %s", stderr_tail
            )
            return f"Pipeline error: no output. stderr: {stderr_tail}"

        data = json.loads(json_line)
        if not data.get("ok"):
            error_type = data.get("error_type", "unknown")
            error_msg = _sanitize_error_message(data.get("error", "unknown error"))
            if error_type == "readiness":
                return f"Readiness gate blocked: {error_msg}"
            if error_type == "policy":
                return f"Policy denied: {error_msg}"
            return f"Pipeline error: {error_msg}"

        result = data["result"]
        pdf_path = _extract_nested(result, "pdf_path")
        png_path = _extract_nested(result, "png_path")
        image_path = _extract_nested(result, "image_path")
        qa_score = _extract_nested(result, "score")
        workflow = result.get("routing", {}).get("workflow", "unknown")
        preview_path = png_path or image_path

        lines = [f"Pipeline complete: {workflow}"]
        if pdf_path:
            lines.append(f"PDF: {pdf_path}")
        if preview_path:
            lines.append(f"Preview image: {preview_path}")
        if qa_score is not None:
            try:
                lines.append(f"QA score: {float(qa_score):.1f}/5")
            except (TypeError, ValueError):
                pass
        lines.append("")
        lines.append("Send the PDF file to the operator. Also send the preview image.")
        return "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "Pipeline error: execution timed out after 300 seconds"
    except Exception as exc:
        logger.error("run_governed subprocess failed: %s", exc, exc_info=True)
        return f"Pipeline error: {exc}"


def _query_logs_handler(args: dict[str, Any], **kwargs: Any) -> str:
    """Query span traces via subprocess isolation."""

    del kwargs
    summary = args.get("summary", False)
    last_n = args.get("last_n", 10)
    step_type = args.get("step_type")

    script = f"""
import json
import sqlite3
from pathlib import Path

db = Path({str(_VIZIER_ROOT)!r}) / "data" / "spans.db"
if not db.exists():
    print(json.dumps({{"ok": True, "result": "No spans database found."}}))
    raise SystemExit(0)

conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row

if {summary!r}:
    row = conn.execute(
        "SELECT COUNT(*) as calls, "
        "COALESCE(SUM(input_tokens),0) as input_tokens, "
        "COALESCE(SUM(output_tokens),0) as output_tokens, "
        "COALESCE(SUM(cost_usd),0) as cost_usd "
        "FROM spans"
    ).fetchone()
    conn.close()
    result = (
        f"Total spans: {{row['calls']}}\\n"
        f"Input tokens: {{row['input_tokens']:,}}\\n"
        f"Output tokens: {{row['output_tokens']:,}}\\n"
        f"Total cost: ${{row['cost_usd']:.4f}}"
    )
    print(json.dumps({{"ok": True, "result": result}}))
    raise SystemExit(0)

step_type = {step_type!r}
last_n = {last_n!r}
if step_type:
    rows = conn.execute(
        "SELECT * FROM spans WHERE step_type = ? ORDER BY timestamp DESC LIMIT ?",
        (step_type, last_n),
    ).fetchall()
else:
    rows = conn.execute(
        "SELECT * FROM spans ORDER BY timestamp DESC LIMIT ?",
        (last_n,),
    ).fetchall()
conn.close()

if not rows:
    print(json.dumps({{"ok": True, "result": "No spans found."}}))
    raise SystemExit(0)

lines = []
for row in rows:
    cost = float(row["cost_usd"] or 0)
    lines.append(
        f"[{{row['timestamp']}}] model={{row['model']}} "
        f"in={{row['input_tokens'] or 0}} out={{row['output_tokens'] or 0}} "
        f"cost=${{cost:.6f}} type={{row['step_type']}}"
    )
print(json.dumps({{"ok": True, "result": chr(10).join(lines)}}))
"""

    try:
        proc = subprocess.run(
            [_PYTHON_BIN, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(_VIZIER_ROOT),
            timeout=15,
        )
        for line in reversed(proc.stdout.strip().splitlines()):
            if line.strip().startswith("{"):
                data = json.loads(line.strip())
                return data.get("result", "No result")
        return f"Query error: {(proc.stderr or 'no output')[-300:]}"
    except Exception as exc:
        return f"Query error: {exc}"


def _load_subprocess_env() -> dict[str, str]:
    env = {**os.environ}
    if not _HERMES_ENV_PATH.exists():
        return env
    for line in _HERMES_ENV_PATH.read_text().splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and value:
            env[key] = value
    return env


def _sanitize_error_message(error_msg: str) -> str:
    if "<html" not in error_msg.lower():
        return error_msg
    status = re.search(r"(\d{3}\s+\w[\w\s]+)", error_msg)
    if status:
        return status.group(1).strip()
    return "Service temporarily unavailable"


def _generate_job_id() -> str:
    """Generate a unique job ID."""

    import uuid

    return f"job-{uuid.uuid4().hex[:8]}"


__all__ = [
    "BridgeMediaContext",
    "BridgeSessionState",
    "register",
    "_SESSION_STATE",
    "_extract_env_media_context",
    "_extract_nested",
    "_extract_message_media_context",
    "_extract_reference_image_path",
    "_extract_reference_image_paths",
    "_extract_reference_image_url",
    "_extract_reference_image_urls",
    "_generate_job_id",
    "_looks_like_production_request",
    "_on_session_end",
    "_on_session_start",
    "_post_llm_call",
    "_pre_llm_call",
    "_pre_tool_call",
    "_query_logs_handler",
    "_resolve_media_context",
    "_run_pipeline_handler",
]
