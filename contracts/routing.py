"""Routing layer — fast-path, LLM classification, refinement, design system selector.

Three phases (§8):
  Phase 1 — Interpret: normalise input, classify artifact, form spec.
  Phase 2 — Evaluate: readiness gate, workflow selection, policy, phase check.
  Phase 3 — Execute: emit RoutingResult, hand off to workflow.

Fast-path handles 60-70 % of requests at zero tokens.
LLM classification activates only when fast-path can't resolve.
Design system selector is called by S17 dashboard — do NOT rebuild.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import yaml
from pydantic import BaseModel, Field

from contracts.artifact_spec import (
    ArtifactFamily,
    DeliveryFormat,
    ProvisionalArtifactSpec,
)
from contracts.readiness import RefinementLimits, evaluate_readiness
from utils.call_llm import call_llm
from utils.spans import track_span
from utils.workflow_registry import (
    get_active_workflow_descriptions,
    get_density_for_family,
    get_workflow_family,
)

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


# ---------------------------------------------------------------------------
# RoutingResult contract
# ---------------------------------------------------------------------------


class RoutingResult(BaseModel):
    """Inspectable routing output stored on the job record (§8)."""

    routing_id: UUID = Field(default_factory=uuid4)
    job_id: str | None = None
    workflow: str = Field(description="Selected workflow name, e.g. 'poster_production'")
    model_preference: str = Field(default="gpt-5.4-mini", description="Anti-drift #54")
    image_model: str | None = Field(default=None, description="Selected image model if applicable")
    design_system: str | None = None
    fast_path: bool = Field(default=False, description="True if matched a fast-path pattern")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = Field(default="", description="Why this route was chosen")
    token_cost: int = Field(default=0, description="Tokens consumed by routing")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Config loaders (cached)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_fast_paths() -> dict[str, Any]:
    path = _CONFIG_DIR / "fast_paths.yaml"
    with path.open() as fh:
        return yaml.safe_load(fh)  # type: ignore[no-any-return]


@lru_cache(maxsize=1)
def _load_phase_config() -> dict[str, Any]:
    path = _CONFIG_DIR / "phase.yaml"
    with path.open() as fh:
        return yaml.safe_load(fh)  # type: ignore[no-any-return]


@lru_cache(maxsize=1)
def _load_design_systems() -> dict[str, Any]:
    path = _CONFIG_DIR / "design_system_index.yaml"
    with path.open() as fh:
        return yaml.safe_load(fh)  # type: ignore[no-any-return]


def _load_client_config(client_id: str) -> dict[str, Any]:
    """Load client YAML config. Returns empty dict if not found."""
    path = _CONFIG_DIR / "clients" / f"{client_id}.yaml"
    if not path.exists():
        return {}
    with path.open() as fh:
        return yaml.safe_load(fh) or {}  # type: ignore[no-any-return]


def _is_phase_active(phase_gate: str) -> bool:
    """Check if a phase is active in config/phase.yaml."""
    phases = _load_phase_config().get("phases", {})
    phase = phases.get(phase_gate, {})
    return bool(phase.get("active", False))


# ---------------------------------------------------------------------------
# 1. Fast-Path Router (~50 lines)
# ---------------------------------------------------------------------------


def fast_path_route(raw_input: str, client_id: str | None = None) -> RoutingResult | None:
    """Deterministic pattern match against config/fast_paths.yaml.

    Returns RoutingResult with fast_path=True and token_cost=0, or None if
    no pattern matched.
    """
    config = _load_fast_paths()
    text = raw_input.lower().strip()

    # Check client-specific fast paths first (more specific)
    if client_id:
        for entry in config.get("client_fast_paths", []):
            client_pat = entry.get("client_pattern", "")
            artifact_pat = entry.get("artifact_pattern", "")
            if re.search(client_pat, text) and re.search(artifact_pat, text):
                phase_gate = entry.get("phase_gate", "core")
                if not _is_phase_active(phase_gate):
                    logger.info("Phase '%s' inactive, skipping client fast-path '%s'", phase_gate, entry["name"])
                    continue
                workflow = entry["workflow"].replace(".yaml", "")
                return RoutingResult(
                    workflow=workflow,
                    fast_path=True,
                    confidence=1.0,
                    token_cost=0,
                    reason=f"Client fast-path match: {entry['name']}",
                )

    # Check generic fast paths
    for entry in config.get("fast_paths", []):
        pattern = entry.get("pattern", "")
        if re.search(pattern, text):
            phase_gate = entry.get("phase_gate", "core")
            if not _is_phase_active(phase_gate):
                logger.info("Phase '%s' inactive, skipping fast-path '%s'", phase_gate, entry["name"])
                continue
            workflow = entry["workflow"].replace(".yaml", "")
            return RoutingResult(
                workflow=workflow,
                fast_path=True,
                confidence=1.0,
                token_cost=0,
                reason=f"Fast-path match: {entry['name']}",
            )

    return None


# ---------------------------------------------------------------------------
# 2. LLM Router (~80 lines)
# ---------------------------------------------------------------------------

_LLM_ROUTING_SYSTEM = """You are Vizier's routing classifier. Given a user request, determine which workflow to use.

Available workflows (only use active ones):
{workflows}

Respond with ONLY a JSON object:
{{"workflow": "<workflow_name>", "confidence": <0.0-1.0>, "artifact_family": "<family>", "reason": "<brief reason>"}}

Rules:
- Choose the most specific workflow that matches the request
- If the request is in Malay (BM), still route correctly
- confidence should reflect how certain you are about the match
- If you cannot determine a workflow, use "refinement" with low confidence
"""

@track_span(step_type="routing")
def llm_route(raw_input: str, client_id: str | None = None) -> RoutingResult:
    """LLM-based classification when fast-path misses.

    Calls GPT-5.4-mini to classify the request into a workflow.
    """
    active_workflows = get_active_workflow_descriptions()
    workflows_desc = "\n".join(f"- {name}: {desc}" for name, desc in active_workflows)
    system_msg = _LLM_ROUTING_SYSTEM.format(workflows=workflows_desc)

    user_msg = f"User request: {raw_input}"
    if client_id:
        user_msg += f"\nClient: {client_id}"

    response = call_llm(
        stable_prefix=[{"role": "system", "content": system_msg}],
        variable_suffix=[{"role": "user", "content": user_msg}],
        model="gpt-5.4-mini",
        temperature=0.0,
        max_tokens=256,
        operation_type="classify",
    )

    token_cost = response.get("input_tokens", 0) + response.get("output_tokens", 0)
    content = response.get("content", "").strip()

    # Parse JSON response
    try:
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        logger.warning("LLM routing returned non-JSON: %s", content)
        return RoutingResult(
            workflow="refinement",
            confidence=0.3,
            token_cost=token_cost,
            reason=f"LLM response unparseable, falling back to refinement: {content[:100]}",
        )

    workflow = parsed.get("workflow", "refinement")
    confidence = min(1.0, max(0.0, float(parsed.get("confidence", 0.5))))
    reason = parsed.get("reason", "LLM classification")

    return RoutingResult(
        workflow=workflow,
        confidence=confidence,
        token_cost=token_cost,
        reason=f"LLM classification: {reason}",
    )


# ---------------------------------------------------------------------------
# 3. Iterative Refinement (~100 lines)
# ---------------------------------------------------------------------------

_REFINEMENT_SYSTEM = """You are Vizier's refinement assistant. The user's request is vague and needs clarification.
Given what you know, ask 2-3 specific clarifying questions to shape the request into a production spec.

Current spec state:
{spec_state}

Client context:
{client_context}

Respond with ONLY a JSON object:
{{
  "questions": ["<question1>", "<question2>"],
  "inferred": {{
    "artifact_family": "<if determinable>",
    "language": "<if determinable>",
    "tone": "<if determinable>",
    "objective": "<partial objective if determinable>"
  }}
}}
"""

_REFINEMENT_APPLY_SYSTEM = """You are Vizier's spec builder. Given a partial spec and user answers to clarifying questions, update the spec fields.

Current spec: {spec_json}
Questions asked: {questions}
User answers: {answers}

Respond with ONLY a JSON object containing updated spec fields:
{{
  "artifact_family": "<family>",
  "language": "<lang code>",
  "objective": "<objective>",
  "tone": "<tone>",
  "format": "<delivery format>",
  "dimensions": "<if known>",
  "page_count": <if known or null>,
  "confidence": <0.0-1.0>,
  "completeness": <0.0-1.0>
}}
"""


@track_span(step_type="refinement")
def refine_request(
    raw_input: str,
    client_id: str,
    spec: ProvisionalArtifactSpec | None = None,
    user_answers: list[str] | None = None,
    limits: RefinementLimits | None = None,
) -> tuple[ProvisionalArtifactSpec, list[str]]:
    """Run one shaping cycle on a vague request.

    Returns (updated_spec, clarifying_questions).
    If spec is ready after this cycle, questions will be empty.

    Args:
        raw_input: Original user request.
        client_id: Client identifier.
        spec: Existing provisional spec (None for first cycle).
        user_answers: Answers to previous clarifying questions.
        limits: Refinement bounds.
    """
    limits = limits or RefinementLimits()
    client_config = _load_client_config(client_id)

    if spec is None:
        spec = ProvisionalArtifactSpec(
            client_id=client_id,
            artifact_family=ArtifactFamily.document,  # default, will be refined
            family_resolved=False,  # placeholder until routing classifies
            language=client_config.get("defaults", {}).get("language", "en"),
            raw_brief=raw_input,
        )

    # If we have user answers, apply them to the spec
    if user_answers and spec.cycle > 0:
        spec = _apply_answers(spec, user_answers, client_config)

    # Check readiness
    readiness = evaluate_readiness(spec, limits)
    spec = spec.model_copy(
        update={
            "readiness": readiness.status,
            "completeness": readiness.completeness,
            "missing_critical": readiness.missing_critical,
            "missing_nice_to_have": readiness.missing_nice_to_have,
        }
    )

    if readiness.status == "ready":
        return spec, []

    # Generate clarifying questions
    spec_state = spec.model_dump_json(indent=2)
    client_ctx = json.dumps(client_config.get("defaults", {}), indent=2)

    response = call_llm(
        stable_prefix=[
            {"role": "system", "content": _REFINEMENT_SYSTEM.format(
                spec_state=spec_state,
                client_context=client_ctx,
            )}
        ],
        variable_suffix=[{"role": "user", "content": f"Original request: {raw_input}"}],
        model="gpt-5.4-mini",
        temperature=0.3,
        max_tokens=512,
        operation_type="classify",
    )

    content = response.get("content", "").strip()
    try:
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Refinement LLM returned non-JSON: %s", content[:200])
        return spec, ["Could you describe what you need in more detail?"]

    questions = parsed.get("questions", [])
    inferred = parsed.get("inferred", {})

    # Apply any inferences
    updates: dict[str, Any] = {"cycle": spec.cycle + 1}
    if inferred.get("artifact_family"):
        try:
            updates["artifact_family"] = ArtifactFamily(inferred["artifact_family"])
            updates["family_resolved"] = True
        except ValueError:
            pass
    if inferred.get("language"):
        updates["language"] = inferred["language"]
    if inferred.get("tone"):
        updates["tone"] = inferred["tone"]
    if inferred.get("objective"):
        updates["objective"] = inferred["objective"]

    spec = spec.model_copy(update=updates)
    return spec, questions[:3]  # cap at 3 questions


def _apply_answers(
    spec: ProvisionalArtifactSpec,
    answers: list[str],
    client_config: dict[str, Any],
) -> ProvisionalArtifactSpec:
    """Apply user answers to refine the spec via LLM."""
    spec_json = spec.model_dump_json(indent=2)
    questions_str = json.dumps(spec.missing_critical + spec.missing_nice_to_have)

    response = call_llm(
        stable_prefix=[
            {"role": "system", "content": _REFINEMENT_APPLY_SYSTEM.format(
                spec_json=spec_json,
                questions=questions_str,
                answers=json.dumps(answers),
            )}
        ],
        variable_suffix=[{"role": "user", "content": "Update the spec based on these answers."}],
        model="gpt-5.4-mini",
        temperature=0.0,
        max_tokens=512,
        operation_type="classify",
    )

    content = response.get("content", "").strip()
    try:
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Apply-answers LLM returned non-JSON: %s", content[:200])
        return spec

    updates: dict[str, Any] = {}
    if parsed.get("artifact_family"):
        try:
            updates["artifact_family"] = ArtifactFamily(parsed["artifact_family"])
            updates["family_resolved"] = True
        except ValueError:
            pass
    if parsed.get("language"):
        updates["language"] = parsed["language"]
    if parsed.get("objective"):
        updates["objective"] = parsed["objective"]
    if parsed.get("tone"):
        updates["tone"] = parsed["tone"]
    if parsed.get("format"):
        try:
            updates["format"] = DeliveryFormat(parsed["format"])
        except ValueError:
            pass
    if parsed.get("dimensions"):
        updates["dimensions"] = parsed["dimensions"]
    if parsed.get("page_count") is not None:
        updates["page_count"] = parsed["page_count"]
    if parsed.get("confidence") is not None:
        updates["confidence"] = float(parsed["confidence"])
    if parsed.get("completeness") is not None:
        updates["completeness"] = float(parsed["completeness"])

    return spec.model_copy(update=updates)


# ---------------------------------------------------------------------------
# 6. Design System Selector (~20 lines)
# ---------------------------------------------------------------------------


def select_design_systems(
    client_id: str,
    artifact_family: str | None = None,
    top_k: int = 3,
    family_resolved: bool = True,
) -> list[str]:
    """Score all design systems and return top-k by relevance.

    Scoring via set intersection (§38.1.1):
      - Industry overlap: +2
      - Mood overlap:     +1
      - Density match:    +1  (skipped when family_resolved=False)
      - Colour temp match: +1

    When family_resolved=False, density scoring uses "moderate" default
    to prevent wrong-family density from distorting selection on
    unclassified specs.

    Returns list of design system names (e.g. ["petronas", "batik_air", "grab"]).
    """
    client_config = _load_client_config(client_id)
    systems = _load_design_systems().get("systems", {})

    # Client attributes
    client_industry = set(client_config.get("defaults", {}).get("industry", []))
    client_mood = set(client_config.get("brand_mood", client_config.get("defaults", {}).get("brand_mood", ["warm", "professional"])))
    client_colour = client_config.get("defaults", {}).get("colour_temperature", "warm")

    # Artifact density — use "moderate" default when family is unresolved
    if family_resolved:
        target_density = get_density_for_family(artifact_family or "")
    else:
        target_density = "moderate"

    scores: list[tuple[str, int]] = []
    for name, attrs in systems.items():
        score = 0
        sys_industry = set(attrs.get("industry", []))
        sys_mood = set(attrs.get("mood", []))
        sys_density = attrs.get("density", "moderate")
        sys_colour = attrs.get("colour_temperature", "neutral")

        if client_industry & sys_industry:
            score += 2
        if client_mood & sys_mood:
            score += 1
        if target_density == sys_density:
            score += 1
        if client_colour == sys_colour:
            score += 1

        scores.append((name, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in scores[:top_k]]


# ---------------------------------------------------------------------------
# Main route() entry point
# ---------------------------------------------------------------------------


@track_span(step_type="routing")
def route(
    raw_input: str,
    client_id: str | None = None,
    job_id: str | None = None,
) -> RoutingResult:
    """Main routing entry point (§8).

    Phase 1: Fast-path deterministic match.
    Phase 2: LLM classification fallback.
    Phase 3: Emit RoutingResult.
    """
    # Phase 1 — fast-path
    result = fast_path_route(raw_input, client_id)
    if result is not None:
        result.job_id = job_id

        # Attach design system if we have a client
        if client_id:
            try:
                family = get_workflow_family(result.workflow)
            except KeyError:
                family = None
            top_systems = select_design_systems(client_id, family)
            result.design_system = top_systems[0] if top_systems else None

        logger.info("Fast-path routed: %s → %s", raw_input[:50], result.workflow)
        return result

    # Phase 2 — LLM classification
    result = llm_route(raw_input, client_id)
    result.job_id = job_id

    # Attach design system
    if client_id:
        try:
            family = get_workflow_family(result.workflow)
        except KeyError:
            family = None
        top_systems = select_design_systems(client_id, family)
        result.design_system = top_systems[0] if top_systems else None

    logger.info("LLM routed: %s → %s (confidence=%.2f)", raw_input[:50], result.workflow, result.confidence)
    return result
