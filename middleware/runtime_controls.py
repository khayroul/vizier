"""Runtime quality/budget controls for governed execution.

This layer turns configuration into explicit runtime controls that the
executor, registry tools, and reporting can all share.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PHASE_CONFIG = _REPO_ROOT / "config" / "phase.yaml"
_CLIENTS_DIR = _REPO_ROOT / "config" / "clients"


@dataclass(frozen=True)
class BudgetProfileConfig:
    """Token/context/retry controls for a job."""

    name: str
    default_max_tokens: int
    critique_max_tokens: int
    revision_max_tokens: int
    identity_context_cap: int
    essential_context_cap: int
    workflow_context_cap: int
    knowledge_card_cap: int
    allow_deep_search: bool
    max_tripwire_retries: int
    qa_threshold: float
    allow_parallel_guardrails: bool
    require_quality_pass: bool


def _load_phase_config(config_path: Path = _PHASE_CONFIG) -> dict[str, Any]:
    with config_path.open() as fh:
        return yaml.safe_load(fh) or {}


def _load_client_config(client_id: str) -> dict[str, Any]:
    path = _CLIENTS_DIR / f"{client_id}.yaml"
    if not path.exists():
        return {}
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def get_budget_profile(
    profile_name: str,
    *,
    config_path: Path = _PHASE_CONFIG,
) -> BudgetProfileConfig:
    """Return a configured runtime budget profile."""
    config = _load_phase_config(config_path)
    profiles: dict[str, Any] = config.get("budget_profiles", {})
    if profile_name not in profiles:
        available = ", ".join(sorted(profiles))
        raise ValueError(
            f"Unknown budget profile '{profile_name}'. Available: {available}"
        )

    raw = profiles[profile_name]
    return BudgetProfileConfig(
        name=profile_name,
        default_max_tokens=int(raw.get("default_max_tokens", 1024)),
        critique_max_tokens=int(raw.get("critique_max_tokens", 384)),
        revision_max_tokens=int(raw.get("revision_max_tokens", 1536)),
        identity_context_cap=int(raw.get("identity_context_cap", 6)),
        essential_context_cap=int(raw.get("essential_context_cap", 2)),
        workflow_context_cap=int(
            raw.get("workflow_context_cap", raw.get("knowledge_card_cap", 4)),
        ),
        knowledge_card_cap=int(
            raw.get("knowledge_card_cap", raw.get("workflow_context_cap", 4)),
        ),
        allow_deep_search=bool(raw.get("allow_deep_search", False)),
        max_tripwire_retries=int(raw.get("max_tripwire_retries", 1)),
        qa_threshold=float(raw.get("qa_threshold", 3.2)),
        allow_parallel_guardrails=bool(raw.get("allow_parallel_guardrails", True)),
        require_quality_pass=bool(raw.get("require_quality_pass", True)),
    )


def _normalise_language(value: str | None) -> str:
    if not value:
        return "en"
    lowered = value.strip().lower()
    if lowered in {"bm", "bahasa melayu", "malay"}:
        return "ms"
    return lowered


def resolve_runtime_controls(
    client_id: str,
    *,
    quality_posture: str | None = None,
    budget_profile: str | None = None,
    config_path: Path = _PHASE_CONFIG,
) -> dict[str, Any]:
    """Resolve explicit runtime controls for a governed job."""
    client_cfg = _load_client_config(client_id)
    defaults = client_cfg.get("defaults", {})

    resolved_quality_posture = (
        quality_posture
        or defaults.get("quality_posture")
        or "canva_baseline"
    )
    resolved_budget_profile = (
        budget_profile
        or defaults.get("budget_profile")
        or "standard"
    )

    budget = get_budget_profile(resolved_budget_profile, config_path=config_path)

    brand_config = dict(client_cfg.get("brand", {}))
    if client_cfg.get("brand_mood"):
        brand_config["brand_mood"] = client_cfg["brand_mood"]
    for key in ("tone", "copy_register", "language", "style_hint", "image_mode"):
        if key in defaults:
            brand_config[key] = defaults[key]

    return {
        "client_name": client_cfg.get("client_name", client_id),
        "brand_config": brand_config,
        "copy_register": defaults.get("copy_register", "neutral"),
        "template_name": defaults.get("template_name"),
        "platform": defaults.get("platform", "print"),
        "language": _normalise_language(defaults.get("language")),
        "quality_posture": resolved_quality_posture,
        "budget_profile": budget.name,
        "runtime_controls": {
            "quality_posture": resolved_quality_posture,
            "budget_profile": budget.name,
            "default_max_tokens": budget.default_max_tokens,
            "critique_max_tokens": budget.critique_max_tokens,
            "revision_max_tokens": budget.revision_max_tokens,
            "identity_context_cap": budget.identity_context_cap,
            "essential_context_cap": budget.essential_context_cap,
            "workflow_context_cap": budget.workflow_context_cap,
            "knowledge_card_cap": budget.knowledge_card_cap,
            "allow_deep_search": budget.allow_deep_search,
            "max_tripwire_retries": budget.max_tripwire_retries,
            "qa_threshold": budget.qa_threshold,
            "allow_parallel_guardrails": budget.allow_parallel_guardrails,
            "require_quality_pass": budget.require_quality_pass,
        },
    }
