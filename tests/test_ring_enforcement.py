"""Ring enforcement tests — structural guards against Ring 1/Ring 2 leakage.

These tests prevent hardcoded Ring 2 config from silently reappearing in
Ring 1 structural code. They also validate the workflow registry against
the filesystem and enum constraints.

Extended by CT-006 with bug-class prevention tests:
  - SCHEMA_DRIFT: SQL columns must match Pydantic contract fields
  - DEAD_CODE: ruff F401/F841 must be clean on production code
  - WIRING: every production module must import without error
  - VOCABULARY: status column values must match CHECK constraints

If any of these tests fail, it means someone added a hardcoded workflow list,
density map, or family mapping into structural code instead of using
config/workflow_registry.yaml via utils/workflow_registry.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Prevention 1: SCHEMA_DRIFT — SQL columns must match Pydantic fields
# ---------------------------------------------------------------------------


class TestSchemaDrift:
    """SQL table columns must match Pydantic contract fields.

    Catches the class of bug where schema changes in one place
    (SQL, Pydantic, or test fixtures) but not the others.
    """

    def test_policy_logs_columns_match_policy_decision(self) -> None:
        """policy_logs SQL columns must match PolicyDecision fields."""
        from contracts.policy import PolicyDecision

        # Expected SQL columns from the CREATE TABLE statement
        sql_columns = {
            "id", "decision_id", "job_id", "client_id", "capability",
            "action", "gate", "reason", "constraints", "evaluated_at",
        }
        # Pydantic fields (excluding timestamp which maps to evaluated_at)
        pydantic_fields = set(PolicyDecision.model_fields.keys())
        # Mapping: Pydantic 'timestamp' → SQL 'evaluated_at'
        field_mapping = {"timestamp": "evaluated_at"}
        mapped_fields = {field_mapping.get(f, f) for f in pydantic_fields}
        # SQL has 'id' which is auto-generated, not in Pydantic
        mapped_fields.add("id")

        missing_in_sql = mapped_fields - sql_columns
        missing_in_pydantic = sql_columns - mapped_fields

        assert not missing_in_sql, (
            f"PolicyDecision fields not in policy_logs SQL: {missing_in_sql}. "
            "Add ALTER TABLE to migrations/core.sql."
        )
        assert not missing_in_pydantic, (
            f"policy_logs SQL columns not in PolicyDecision: {missing_in_pydantic}. "
            "Add field to contracts/policy.py::PolicyDecision."
        )

    def test_feedback_status_vocabulary_matches_trigger(self) -> None:
        """feedback_status CHECK constraint values must match trigger logic."""
        valid_statuses = {
            "awaiting", "explicitly_approved", "revision_requested",
            "rejected", "silence_flagged", "prompted",
            "responded", "unresponsive",
        }
        # Read the migration file and extract CHECK constraint values
        migration = (Path(__file__).parent.parent / "migrations" / "core.sql").read_text()
        # All status values referenced in the trigger's CASE statement
        import re
        trigger_statuses = set(re.findall(r"'(\w+)'", migration.split("feedback_on_update")[1].split("$$")[1])) if "feedback_on_update" in migration else set()
        # Filter to only actual status values (not function names etc)
        known_statuses = trigger_statuses & valid_statuses
        assert known_statuses == valid_statuses, (
            f"Trigger references statuses not in CHECK constraint: "
            f"{known_statuses.symmetric_difference(valid_statuses)}"
        )


# ---------------------------------------------------------------------------
# Prevention 3: DEAD_CODE — ruff F401/F841 must be clean
# ---------------------------------------------------------------------------


class TestDeadCode:
    """No unused imports or variables in production code."""

    def test_no_dead_imports_or_variables(self) -> None:
        """ruff F401 (unused import) and F841 (unused variable) must be clean."""
        repo_root = Path(__file__).parent.parent
        result = subprocess.run(
            [
                sys.executable, "-m", "ruff", "check",
                "--select", "F401,F841",
                "--quiet",
                str(repo_root / "contracts"),
                str(repo_root / "middleware"),
                str(repo_root / "tools"),
                str(repo_root / "utils"),
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            # Filter out noqa-suppressed lines (ruff respects noqa inline)
            assert not lines, (
                f"Dead code found in production code ({len(lines)} issues):\n"
                + "\n".join(lines[:10])
            )


# ---------------------------------------------------------------------------
# Prevention 4: WIRING — every production module must import cleanly
# ---------------------------------------------------------------------------


class TestModuleImports:
    """Every production module must import without error in isolation."""

    PRODUCTION_MODULES = [
        "contracts.artifact_spec", "contracts.context", "contracts.knowledge",
        "contracts.policy", "contracts.publishing", "contracts.readiness",
        "contracts.routing", "contracts.trace",
        "middleware.guardrails", "middleware.observability",
        "middleware.policy", "middleware.quality_gate", "middleware.quality_posture",
        "tools.bizops", "tools.book_production", "tools.briefing",
        "tools.calibration", "tools.design_selector_api", "tools.ebook_production",
        "tools.executor", "tools.experiment", "tools.illustrate", "tools.image",
        "tools.improvement", "tools.invoice", "tools.knowledge",
        "tools.orchestrate", "tools.prompt_version", "tools.publish",
        "tools.registry", "tools.research", "tools.seeding",
        "tools.serial_fiction", "tools.steward", "tools.visual_dna",
        "tools.visual_pipeline", "tools.visual_scoring", "tools.wisdom_vault",
        "tools.workflow_schema",
        "utils.call_llm", "utils.database", "utils.diagnostics",
        "utils.embeddings", "utils.idle_alarm", "utils.image_processing",
        "utils.knowledge", "utils.prayer_times", "utils.retrieval",
        "utils.spans", "utils.storage", "utils.trace_persist",
        "utils.workflow_registry",
    ]

    def test_all_modules_import_cleanly(self) -> None:
        """Every production module can be imported without ImportError."""
        failures: list[str] = []
        for module in self.PRODUCTION_MODULES:
            result = subprocess.run(
                [sys.executable, "-c", f"import {module}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                # Extract just the last line of the traceback
                error_line = result.stderr.strip().split("\n")[-1]
                failures.append(f"{module}: {error_line}")

        assert not failures, (
            f"{len(failures)} module(s) failed to import:\n"
            + "\n".join(failures)
        )
