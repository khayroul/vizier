"""Ring enforcement tests — structural guards against Ring 1/Ring 2 leakage.

These tests prevent hardcoded Ring 2 config from silently reappearing in
Ring 1 structural code. They also validate the workflow registry against
the filesystem and enum constraints.

If any of these tests fail, it means someone added a hardcoded workflow list,
density map, or family mapping into structural code instead of using
config/workflow_registry.yaml via utils/workflow_registry.py.
"""

from __future__ import annotations

import contracts.routing as routing_module
import tools.orchestrate as orchestrate_module
from utils.workflow_registry import (
    get_active_workflow_descriptions,
    get_density_for_family,
    get_workflow_family,
    load_workflow_registry,
    validate_workflow_registry,
)


# ---------------------------------------------------------------------------
# Ring 1 purity: no Ring 2 constants in structural code
# ---------------------------------------------------------------------------


class TestNoRing2InRouting:
    """contracts.routing must not contain hardcoded workflow/density dicts."""

    def test_no_active_workflows_constant(self) -> None:
        assert not hasattr(routing_module, "_ACTIVE_WORKFLOWS"), (
            "_ACTIVE_WORKFLOWS found in contracts.routing — "
            "workflow list must come from config/workflow_registry.yaml"
        )

    def test_no_artifact_density_constant(self) -> None:
        assert not hasattr(routing_module, "_ARTIFACT_DENSITY"), (
            "_ARTIFACT_DENSITY found in contracts.routing — "
            "density must come from config/workflow_registry.yaml"
        )

    def test_no_workflow_family_map_constant(self) -> None:
        assert not hasattr(routing_module, "_WORKFLOW_FAMILY_MAP"), (
            "_WORKFLOW_FAMILY_MAP found in contracts.routing — "
            "family mapping must come from config/workflow_registry.yaml"
        )

    def test_no_workflow_to_family_function(self) -> None:
        assert not hasattr(routing_module, "_workflow_to_family"), (
            "_workflow_to_family found in contracts.routing — "
            "family lookup must go through utils.workflow_registry"
        )


class TestNoRing2InOrchestrate:
    """tools.orchestrate must not contain hardcoded workflow maps."""

    def test_no_workflow_family_map(self) -> None:
        assert not hasattr(orchestrate_module, "_WORKFLOW_FAMILY_MAP"), (
            "_WORKFLOW_FAMILY_MAP found in tools.orchestrate — "
            "family mapping must come from config/workflow_registry.yaml"
        )

    def test_no_workflow_to_family_function(self) -> None:
        assert not hasattr(orchestrate_module, "_workflow_to_family"), (
            "_workflow_to_family found in tools.orchestrate — "
            "family lookup must go through utils.workflow_registry"
        )


# ---------------------------------------------------------------------------
# Workflow registry validation
# ---------------------------------------------------------------------------


class TestWorkflowRegistryValid:
    """Registry passes all structural validation checks."""

    def test_validate_workflow_registry(self) -> None:
        """Full validation: manifests, enums, phase gates, density keys."""
        validate_workflow_registry()

    def test_registry_matches_phase_yaml(self) -> None:
        """Every workflow in phase.yaml includes exists in registry or allowlist."""
        from pathlib import Path

        import yaml

        phase_path = Path(__file__).resolve().parent.parent / "config" / "phase.yaml"
        with phase_path.open() as fh:
            phase_config = yaml.safe_load(fh)

        registry = load_workflow_registry()
        workflow_names = set(registry["workflows"].keys())
        # Non-workflow capabilities allowed in phase includes
        non_workflow_capabilities = {"calibration", "drift_detection", "experiment_runner"}

        missing: list[str] = []
        for phase_name, phase_cfg in phase_config.get("phases", {}).items():
            for included_wf in phase_cfg.get("includes", []):
                if included_wf not in workflow_names and included_wf not in non_workflow_capabilities:
                    missing.append(f"{phase_name}:{included_wf}")

        assert not missing, (
            f"Phase includes reference unknown workflows: {missing}. "
            "Add to config/workflow_registry.yaml or the non-workflow allowlist."
        )

    def test_all_workflow_yamls_registered(self) -> None:
        """Every YAML in manifests/workflows/ has a registry entry."""
        from pathlib import Path

        workflows_dir = Path(__file__).resolve().parent.parent / "manifests" / "workflows"
        registry = load_workflow_registry()
        workflow_names = set(registry["workflows"].keys())

        for yaml_file in sorted(workflows_dir.glob("*.yaml")):
            wf_name = yaml_file.stem
            assert wf_name in workflow_names, (
                f"Manifest '{yaml_file.name}' has no entry in "
                "config/workflow_registry.yaml"
            )


# ---------------------------------------------------------------------------
# Registry lookup correctness
# ---------------------------------------------------------------------------


class TestWorkflowFamilyLookup:
    """Registry returns correct artifact families."""

    def test_poster_maps_to_poster(self) -> None:
        assert get_workflow_family("poster_production") == "poster"

    def test_document_production_maps_to_document(self) -> None:
        assert get_workflow_family("document_production") == "document"

    def test_research_maps_to_document(self) -> None:
        assert get_workflow_family("research") == "document"

    def test_childrens_book_maps_correctly(self) -> None:
        assert get_workflow_family("childrens_book_production") == "childrens_book"

    def test_serial_fiction_maps_correctly(self) -> None:
        assert get_workflow_family("serial_fiction_production") == "serial_fiction"

    def test_social_batch_maps_to_social_post(self) -> None:
        assert get_workflow_family("social_batch") == "social_post"

    def test_unknown_workflow_raises(self) -> None:
        import pytest

        with pytest.raises(KeyError, match="Unknown workflow"):
            get_workflow_family("nonexistent_workflow")


class TestDensityForFamily:
    """Registry returns correct density values."""

    def test_poster_moderate(self) -> None:
        assert get_density_for_family("poster") == "moderate"

    def test_document_minimal(self) -> None:
        assert get_density_for_family("document") == "minimal"

    def test_childrens_book_dense(self) -> None:
        assert get_density_for_family("childrens_book") == "dense"

    def test_serial_fiction_dense(self) -> None:
        assert get_density_for_family("serial_fiction") == "dense"

    def test_unknown_family_defaults_to_moderate(self) -> None:
        assert get_density_for_family("nonexistent") == "moderate"


class TestActiveWorkflowDescriptions:
    """get_active_workflow_descriptions returns correct filtered list."""

    def test_returns_only_active_phase_workflows(self) -> None:
        active = get_active_workflow_descriptions()
        names = [name for name, _ in active]
        # core and publishing are active
        assert "poster_production" in names
        assert "childrens_book_production" in names
        # social is inactive
        assert "social_batch" not in names
        assert "content_calendar" not in names
        # extended_ops is inactive
        assert "invoice" not in names

    def test_serial_fiction_included(self) -> None:
        """serial_fiction_production is in active publishing phase."""
        active = get_active_workflow_descriptions()
        names = [name for name, _ in active]
        assert "serial_fiction_production" in names
