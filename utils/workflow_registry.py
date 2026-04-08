"""Workflow registry — single source of truth for workflow metadata.

Reads config/workflow_registry.yaml. All workflow lookups (routing,
orchestration, validation) go through this module instead of hardcoded
dicts in Ring 1 structural code.

Cached via @lru_cache — YAML is read once per process lifetime.
Call reload_workflow_registry() to force re-read (parallel to
PolicyEvaluator.reload_config()).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from contracts.artifact_spec import ArtifactFamily

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "workflow_registry.yaml"
_WORKFLOWS_DIR = _REPO_ROOT / "manifests" / "workflows"
_PHASE_CONFIG_PATH = _REPO_ROOT / "config" / "phase.yaml"


class ConfigValidationError(Exception):
    """Raised when workflow registry validation fails."""


@lru_cache(maxsize=1)
def load_workflow_registry() -> dict[str, Any]:
    """Read and parse config/workflow_registry.yaml (cached).

    Runs validate_workflow_registry() on first load for fail-fast.
    """
    with _REGISTRY_PATH.open() as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
    validate_workflow_registry(data)
    return data


def reload_workflow_registry() -> None:
    """Clear lru_cache and force re-read on next access."""
    load_workflow_registry.cache_clear()
    _load_phase_config.cache_clear()


def get_workflow_description(name: str) -> str:
    """Return the description for a workflow name."""
    workflows = load_workflow_registry()["workflows"]
    entry = workflows.get(name)
    if entry is None:
        raise KeyError(f"Unknown workflow: {name}")
    return entry["description"]  # type: ignore[no-any-return]


def get_workflow_family(name: str) -> str:
    """Return the artifact_family string for a workflow name.

    Callers needing the enum wrap with ArtifactFamily(get_workflow_family(name)).
    """
    workflows = load_workflow_registry()["workflows"]
    entry = workflows.get(name)
    if entry is None:
        raise KeyError(f"Unknown workflow: {name}")
    return entry["artifact_family"]  # type: ignore[no-any-return]


def get_density_for_family(family: str) -> str:
    """Return the density string for an artifact family.

    Used by select_design_systems() which receives a family, not a workflow.
    Falls back to 'moderate' for unknown families.
    """
    densities = load_workflow_registry().get("artifact_family_density", {})
    return densities.get(family, "moderate")  # type: ignore[no-any-return]


@lru_cache(maxsize=1)
def _load_phase_config() -> dict[str, Any]:
    """Read and parse config/phase.yaml (cached)."""
    with _PHASE_CONFIG_PATH.open() as fh:
        return yaml.safe_load(fh)  # type: ignore[no-any-return]


def get_active_workflow_descriptions() -> list[tuple[str, str]]:
    """Return (name, description) tuples for workflows in active phases.

    Reads config/phase.yaml (cached) to determine which phases are active,
    then filters workflows by their phase_gate.
    """
    registry = load_workflow_registry()
    workflows = registry["workflows"]
    phase_config = _load_phase_config()

    active_phases: set[str] = set()
    for phase_name, phase_cfg in phase_config.get("phases", {}).items():
        if phase_cfg.get("active", False):
            active_phases.add(phase_name)

    result: list[tuple[str, str]] = []
    for wf_name, wf_cfg in workflows.items():
        if wf_cfg["phase_gate"] in active_phases:
            result.append((wf_name, wf_cfg["description"]))
    return result


def validate_workflow_registry(data: dict[str, Any] | None = None) -> None:
    """Validate registry against filesystem and enum constraints.

    Checks:
      1. Every registry workflow has a manifests/workflows/{name}.yaml
      2. Every YAML in manifests/workflows/ has a registry entry
      3. Every artifact_family is a valid ArtifactFamily enum member
      4. Every phase_gate matches a phase key in config/phase.yaml
      5. Every workflow in phase.yaml includes lists exists in the registry
      6. Every family in artifact_family_density is a valid ArtifactFamily

    Raises ConfigValidationError with ALL violations (not fail-on-first).
    """
    if data is None:
        with _REGISTRY_PATH.open() as fh:
            loaded = yaml.safe_load(fh)
        data = loaded if isinstance(loaded, dict) else {}

    workflows: dict[str, Any] = data.get("workflows", {})
    density: dict[str, str] = data.get("artifact_family_density", {})
    errors: list[str] = []

    # Load phase config
    with _PHASE_CONFIG_PATH.open() as fh:
        phase_config: dict[str, Any] = yaml.safe_load(fh)
    phase_names = set(phase_config.get("phases", {}).keys())

    # Valid ArtifactFamily values
    valid_families = {member.value for member in ArtifactFamily}

    # 1. Every registry workflow has a manifest YAML
    for wf_name in workflows:
        yaml_path = _WORKFLOWS_DIR / f"{wf_name}.yaml"
        if not yaml_path.exists():
            errors.append(f"Registry workflow '{wf_name}' has no manifest at {yaml_path}")

    # 2. Every manifest YAML has a registry entry
    if _WORKFLOWS_DIR.exists():
        for yaml_file in sorted(_WORKFLOWS_DIR.glob("*.yaml")):
            wf_name = yaml_file.stem
            if wf_name not in workflows:
                errors.append(f"Manifest '{yaml_file.name}' has no registry entry")

    # 3. Every artifact_family is a valid ArtifactFamily enum member
    for wf_name, wf_cfg in workflows.items():
        family = wf_cfg.get("artifact_family", "")
        if family not in valid_families:
            errors.append(f"Workflow '{wf_name}' has invalid artifact_family '{family}'")

    # 4. Every phase_gate matches a phase key in phase.yaml
    for wf_name, wf_cfg in workflows.items():
        gate = wf_cfg.get("phase_gate", "")
        if gate not in phase_names:
            errors.append(f"Workflow '{wf_name}' has phase_gate '{gate}' not in phase.yaml")

    # 5. Every workflow in phase.yaml includes lists exists in the registry
    # Non-workflow capabilities (e.g. calibration tools) are allowed in
    # phase includes without registry entries — maintain an explicit allowlist.
    non_workflow_capabilities = {"calibration", "drift_detection", "experiment_runner"}
    for phase_name, phase_cfg in phase_config.get("phases", {}).items():
        for included_wf in phase_cfg.get("includes", []):
            if included_wf not in workflows and included_wf not in non_workflow_capabilities:
                errors.append(
                    f"Phase '{phase_name}' includes '{included_wf}' which is "
                    "not in the workflow registry or the non-workflow allowlist"
                )

    # 6. Every family in artifact_family_density is a valid ArtifactFamily
    for family_name in density:
        if family_name not in valid_families:
            errors.append(f"artifact_family_density key '{family_name}' is not a valid ArtifactFamily")

    if errors:
        raise ConfigValidationError(
            f"Workflow registry validation failed ({len(errors)} errors):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
