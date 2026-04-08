"""Tests for S9 — WorkflowPack schema, executor, tripwire, quality techniques.

Covers all exit criteria:
- Schema validates all 16 YAMLs
- Executor runs poster_production and childrens_book_production end-to-end
- Tripwire critique-then-revise
- Rolling context post_step_update
- Quality techniques activation
- Client override (DMB)
- Rework workflow
- Stub workflow error
- Reminder prompt resolution
- Model lock enforcement
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.executor import (
    StubWorkflowError,
    WorkflowExecutor,
    apply_quality_techniques,
    resolve_reminder,
    run_tripwire,
)
from tools.workflow_schema import (
    QualityTechniquesConfig,
    StageDefinition,
    WorkflowPack,
    load_workflow,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WORKFLOWS_DIR = Path("manifests/workflows")

ALL_YAML_FILES = sorted(WORKFLOWS_DIR.glob("*.yaml"))

CORE_YAMLS = [
    "poster_production.yaml",
    "document_production.yaml",
    "brochure_production.yaml",
    "research.yaml",
    "refinement.yaml",
    "onboarding.yaml",
    "childrens_book_production.yaml",
    "ebook_production.yaml",
    "rework.yaml",
]

EXTENDED_YAMLS = [
    "invoice.yaml",
    "proposal.yaml",
    "company_profile.yaml",
    "social_batch.yaml",
    "social_caption.yaml",
    "content_calendar.yaml",
    "serial_fiction_production.yaml",
]


def _stub_tool(context: dict[str, Any]) -> dict[str, Any]:
    """Stub tool that returns success with basic output."""
    return {
        "status": "ok",
        "output": f"stub output for stage={context.get('stage', '?')}",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.001,
    }


def _make_scorer(score: float, critique: dict[str, Any] | None = None):
    """Factory for scorer functions with configurable score."""

    def scorer(context: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"score": score}
        if critique is not None:
            result["critique"] = critique
        return result

    return scorer


def _make_reviser():
    """Factory for reviser function that marks output as revised."""

    def reviser(context: dict[str, Any]) -> dict[str, Any]:
        original = context.get("original_output", {})
        critique = context.get("critique", {})
        return {
            **original,
            "output": f"revised (attempt {context.get('attempt', 0)})",
            "_revised": True,
            "_revision_critique": critique,
        }

    return reviser


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestWorkflowPackSchema:
    """WorkflowPack schema validates all 16 YAML files."""

    def test_all_16_yamls_exist(self) -> None:
        """All 16 workflow YAMLs are present."""
        expected = set(CORE_YAMLS + EXTENDED_YAMLS)
        actual = {f.name for f in ALL_YAML_FILES}
        assert expected == actual, f"Missing: {expected - actual}, Extra: {actual - expected}"

    @pytest.mark.parametrize(
        "yaml_file",
        ALL_YAML_FILES,
        ids=[f.stem for f in ALL_YAML_FILES],
    )
    def test_yaml_validates_against_schema(self, yaml_file: Path) -> None:
        """Each YAML loads and validates against WorkflowPack schema."""
        pack = load_workflow(yaml_file)
        assert pack.name
        assert len(pack.stages) >= 1

    @pytest.mark.parametrize(
        "yaml_file",
        ALL_YAML_FILES,
        ids=[f.stem for f in ALL_YAML_FILES],
    )
    def test_model_preference_all_gpt_5_4_mini(self, yaml_file: Path) -> None:
        """Anti-drift #54: every model_preference entry = gpt-5.4-mini."""
        pack = load_workflow(yaml_file)
        for key, value in pack.model_preference.items():
            assert value == "gpt-5.4-mini", (
                f"{yaml_file.name}: model_preference['{key}'] = '{value}'"
            )
        assert pack.scorer_model == "gpt-5.4-mini"
        assert pack.scorer_fallback == "gpt-5.4-mini"
        for guardrail in pack.parallel_guardrails:
            assert guardrail.model == "gpt-5.4-mini", (
                f"{yaml_file.name}: guardrail '{guardrail.name}' model = '{guardrail.model}'"
            )

    def test_model_lock_rejects_wrong_model(self) -> None:
        """Schema rejects non-gpt-5.4-mini model_preference."""
        with pytest.raises(ValueError, match="anti-drift #54"):
            WorkflowPack(
                name="bad_workflow",
                stages=[StageDefinition(name="test", role="production", action="test")],
                model_preference={"en_creative": "claude-opus-4-6"},
            )

    def test_scorer_model_rejects_wrong_model(self) -> None:
        """Schema rejects non-gpt-5.4-mini scorer_model."""
        with pytest.raises(ValueError, match="scorer_model"):
            WorkflowPack(
                name="bad_workflow",
                stages=[StageDefinition(name="test", role="production", action="test")],
                scorer_model="claude-sonnet-4-6",
            )

    def test_context_strategy_values(self) -> None:
        """context_strategy accepts simple/rolling_summary/aggressive."""
        for strategy in ("simple", "rolling_summary", "aggressive"):
            pack = WorkflowPack(
                name="test",
                stages=[StageDefinition(name="s1", role="production", action="test")],
                context_strategy=strategy,
            )
            assert pack.context_strategy == strategy

    def test_scorer_fallback_and_latency_validated(self) -> None:
        """scorer_fallback and latency_threshold_ms fields are validated."""
        pack = load_workflow(WORKFLOWS_DIR / "poster_production.yaml")
        assert pack.scorer_fallback == "gpt-5.4-mini"
        assert pack.latency_threshold_ms > 0

    def test_creative_workshop_derivative_requires_source(self) -> None:
        """creative_workshop='derivative' requires derivative_source."""
        with pytest.raises(ValueError, match="derivative_source"):
            WorkflowPack(
                name="test",
                stages=[StageDefinition(name="s1", role="production", action="test")],
                creative_workshop="derivative",
            )

    def test_creative_workshop_derivative_with_source(self) -> None:
        """creative_workshop='derivative' works with derivative_source."""
        pack = WorkflowPack(
            name="test",
            stages=[StageDefinition(name="s1", role="production", action="test")],
            creative_workshop="derivative",
            derivative_source="project-123",
        )
        assert pack.creative_workshop == "derivative"
        assert pack.derivative_source == "project-123"


# ---------------------------------------------------------------------------
# Children's book YAML specifics
# ---------------------------------------------------------------------------


class TestChildrensBookYAML:
    """childrens_book_production.yaml has required complex features."""

    @pytest.fixture()
    def pack(self) -> WorkflowPack:
        return load_workflow(WORKFLOWS_DIR / "childrens_book_production.yaml")

    def test_creative_workshop_enabled(self, pack: WorkflowPack) -> None:
        assert pack.creative_workshop is True

    def test_rolling_summary_context(self, pack: WorkflowPack) -> None:
        assert pack.context_strategy == "rolling_summary"

    def test_rolling_context_config(self, pack: WorkflowPack) -> None:
        assert pack.rolling_context is not None
        assert pack.rolling_context.recent_window == 8
        assert pack.rolling_context.medium_scope == "not_needed"

    def test_section_tripwire(self, pack: WorkflowPack) -> None:
        assert pack.section_tripwire is True

    def test_quality_techniques(self, pack: WorkflowPack) -> None:
        qt = pack.quality_techniques
        assert qt.self_refine == "per_section"
        assert qt.exemplar_injection is True
        assert qt.contrastive_examples is True
        assert len(qt.critique_chain) >= 3
        assert qt.persona is not None

    def test_has_reminder_prompt(self, pack: WorkflowPack) -> None:
        assert pack.reminder_prompt is not None
        assert "text-free" in pack.reminder_prompt.lower()
        assert "{client_name}" in pack.reminder_prompt


# ---------------------------------------------------------------------------
# Rework YAML
# ---------------------------------------------------------------------------


class TestReworkYAML:
    """rework.yaml validates and has required stages."""

    @pytest.fixture()
    def pack(self) -> WorkflowPack:
        return load_workflow(WORKFLOWS_DIR / "rework.yaml")

    def test_validates(self, pack: WorkflowPack) -> None:
        assert pack.name == "rework"

    def test_has_diagnose_stage(self, pack: WorkflowPack) -> None:
        stage_names = [s.name for s in pack.stages]
        assert "diagnose" in stage_names

    def test_diagnose_uses_trace_insight(self, pack: WorkflowPack) -> None:
        diagnose = next(s for s in pack.stages if s.name == "diagnose")
        assert "trace_insight" in diagnose.tools

    def test_rerun_inherits_tools(self, pack: WorkflowPack) -> None:
        """Rerun stage tools list is empty — inherits from original workflow."""
        rerun = next(s for s in pack.stages if s.name == "rerun")
        assert rerun.tools == []

    def test_has_qa_and_delivery(self, pack: WorkflowPack) -> None:
        stage_names = [s.name for s in pack.stages]
        assert "qa" in stage_names
        assert "delivery" in stage_names


# ---------------------------------------------------------------------------
# Executor tests — poster_production (simple)
# ---------------------------------------------------------------------------


class TestExecutorPosterProduction:
    """Executor runs poster_production end-to-end with stub tools."""

    def test_end_to_end(self) -> None:
        """Full run with stub tools produces trace and stage results."""
        tool_reg = {
            "classify_artifact": _stub_tool,
            "generate_poster": _stub_tool,
            "image_generate": _stub_tool,
            "visual_qa": _stub_tool,
            "deliver": _stub_tool,
        }
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "poster_production.yaml",
            tool_registry=tool_reg,
        )
        result = executor.run(job_context={
            "job_id": "job-001",
            "client_name": "TestCo",
            "copy_register": "casual",
            "platform": "Instagram",
        })
        assert result["workflow"] == "poster_production"
        assert len(result["stages"]) == 4
        assert "trace" in result
        assert result["trace"]["job_id"] == "job-001"

    def test_reminder_prompt_appended(self) -> None:
        """reminder_prompt resolves variables and is present in flow."""
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "poster_production.yaml",
            tool_registry={"classify_artifact": _stub_tool},
        )
        assert executor.pack.reminder_prompt is not None
        resolved = resolve_reminder(
            executor.pack.reminder_prompt,
            {"client_name": "DMB", "copy_register": "formal", "platform": "Facebook"},
        )
        assert "DMB" in resolved
        assert "formal" in resolved
        assert "Facebook" in resolved


# ---------------------------------------------------------------------------
# Executor tests — childrens_book_production (complex)
# ---------------------------------------------------------------------------


class TestExecutorChildrensBook:
    """Executor runs childrens_book_production with rolling context."""

    def test_end_to_end_with_rolling_context(self) -> None:
        """Full run produces rolling_context in result."""
        tool_reg = {
            "classify_artifact": _stub_tool,
            "character_workshop": _stub_tool,
            "story_workshop": _stub_tool,
            "scaffold_build": _stub_tool,
            "generate_page_text": _stub_tool,
            "image_generate": _stub_tool,
            "character_verify": _stub_tool,
            "typst_render": _stub_tool,
            "visual_qa": _stub_tool,
            "narrative_qa": _stub_tool,
            "deliver": _stub_tool,
        }
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "childrens_book_production.yaml",
            tool_registry=tool_reg,
        )
        result = executor.run(job_context={
            "job_id": "job-002",
            "client_name": "KidPublisher",
            "copy_register": "casual",
        })
        assert result["workflow"] == "childrens_book_production"
        assert "rolling_context" in result
        # Rolling context should have entries from stage updates
        rc = result["rolling_context"]
        assert "recent" in rc

    def test_post_step_update_fires(self) -> None:
        """Rolling context is updated after each stage."""
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "childrens_book_production.yaml",
            tool_registry={
                "classify_artifact": _stub_tool,
                "character_workshop": _stub_tool,
                "story_workshop": _stub_tool,
                "scaffold_build": _stub_tool,
                "generate_page_text": _stub_tool,
                "image_generate": _stub_tool,
                "character_verify": _stub_tool,
                "typst_render": _stub_tool,
                "visual_qa": _stub_tool,
                "narrative_qa": _stub_tool,
                "deliver": _stub_tool,
            },
        )
        assert executor.rolling_context is not None
        initial_step = executor.rolling_context.current_step

        executor.run(job_context={"job_id": "job-003"})

        # After running all stages, current_step should have advanced
        assert executor.rolling_context.current_step > initial_step


# ---------------------------------------------------------------------------
# Executor tests — rework
# ---------------------------------------------------------------------------


class TestExecutorRework:
    """Executor can iterate rework stages."""

    def test_rework_runs(self) -> None:
        """Rework workflow executes all 4 stages."""
        tool_reg = {
            "trace_insight": _stub_tool,
            "quality_gate": _stub_tool,
            "deliver": _stub_tool,
        }
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "rework.yaml",
            tool_registry=tool_reg,
        )
        result = executor.run(job_context={
            "job_id": "rework-001",
            "original_trace": {"steps": []},
            "feedback": "The CTA is too small",
        })
        assert result["workflow"] == "rework"
        assert len(result["stages"]) == 4

    def test_diagnose_accepts_trace_and_feedback(self) -> None:
        """Diagnose stage receives trace and feedback via job_context."""
        captured: list[dict[str, Any]] = []

        def capture_tool(context: dict[str, Any]) -> dict[str, Any]:
            captured.append(context)
            return {"status": "ok", "output": "diagnosed: CTA too small"}

        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "rework.yaml",
            tool_registry={
                "trace_insight": capture_tool,
                "quality_gate": _stub_tool,
                "deliver": _stub_tool,
            },
        )
        executor.run(job_context={
            "original_trace": {"steps": [{"name": "production"}]},
            "feedback": "CTA is not visible",
        })
        # The tool should have received job_context
        assert len(captured) >= 1
        assert "original_trace" in captured[0]["job_context"]
        assert "feedback" in captured[0]["job_context"]


# ---------------------------------------------------------------------------
# Tripwire tests
# ---------------------------------------------------------------------------


class TestTripwire:
    """Tripwire generates structured critique and produces revised output."""

    @pytest.fixture()
    def pack(self) -> WorkflowPack:
        return load_workflow(WORKFLOWS_DIR / "poster_production.yaml")

    def test_pass_through_above_threshold(self, pack: WorkflowPack) -> None:
        """Output passes through when score >= threshold."""
        scorer = _make_scorer(4.0)
        output = {"output": "original"}
        result = run_tripwire(output, pack, "production", scorer_fn=scorer)
        assert result["output"] == "original"

    def test_critique_then_revise(self, pack: WorkflowPack) -> None:
        """Below threshold triggers critique-then-revise."""
        critique = {
            "dimension": "cta_visibility",
            "score": 2.0,
            "issues": ["CTA is buried below fold"],
            "revision_instruction": "Move CTA to top-right with high contrast",
        }
        scorer = _make_scorer(2.0, critique)
        reviser = _make_reviser()
        output = {"output": "original bad poster"}
        result = run_tripwire(
            output, pack, "production",
            scorer_fn=scorer,
            reviser_fn=reviser,
        )
        assert result.get("_revised") is True
        assert "revised" in result["output"]

    def test_max_retries_escalates(self, pack: WorkflowPack) -> None:
        """After max retries, escalates to operator."""
        critique = {"dimension": "cta_visibility", "issues": ["still bad"]}
        # Score always below threshold — reviser never fixes it
        scorer = _make_scorer(1.0, critique)

        def bad_reviser(context: dict[str, Any]) -> dict[str, Any]:
            return {"output": "still bad", "stage": "production"}

        output = {"output": "original"}
        result = run_tripwire(
            output, pack, "production",
            scorer_fn=scorer,
            reviser_fn=bad_reviser,
        )
        assert result.get("_tripwire_escalated") is True
        assert "_tripwire_critique" in result

    def test_structured_critique_json(self, pack: WorkflowPack) -> None:
        """Critique must return structured JSON with specific dimensions."""
        critique = {
            "dimension": "text_readability",
            "score": 2.5,
            "issues": ["Text overlaps image", "Font too small at 8pt"],
            "revision_instruction": "Use 12pt minimum, add text backing",
        }
        scorer = _make_scorer(2.5, critique)
        reviser = _make_reviser()
        output = {"output": "bad text"}
        result = run_tripwire(
            output, pack, "production",
            scorer_fn=scorer,
            reviser_fn=reviser,
        )
        assert result.get("_revision_critique") == critique


# ---------------------------------------------------------------------------
# Quality techniques tests
# ---------------------------------------------------------------------------


class TestQualityTechniques:
    """quality_techniques activates persona and self_refine from YAML."""

    def test_persona_injected(self, tmp_path: Path) -> None:
        """Persona file content is prepended to prompt."""
        persona_file = tmp_path / "persona.md"
        persona_file.write_text("You are a senior marketing director.")
        techniques = QualityTechniquesConfig(persona=str(persona_file))
        result = apply_quality_techniques("Generate a poster", techniques, "production")
        assert "senior marketing director" in result
        assert "Generate a poster" in result

    def test_self_refine_injected(self) -> None:
        """Self-refine instruction is added for production stages."""
        techniques = QualityTechniquesConfig(self_refine="on_prompt")
        result = apply_quality_techniques("Generate", techniques, "production")
        assert "Self-refine" in result

    def test_critique_chain_in_qa(self) -> None:
        """Critique chain dimensions are injected for QA stages."""
        techniques = QualityTechniquesConfig(
            critique_chain=["cta_visibility", "text_readability"]
        )
        result = apply_quality_techniques("Evaluate", techniques, "qa")
        assert "cta_visibility" in result
        assert "text_readability" in result

    def test_no_injection_for_intake(self) -> None:
        """No quality technique injection for intake stages."""
        techniques = QualityTechniquesConfig(
            self_refine="on_prompt",
            persona="config/personas/marketing_director_my.md",
        )
        result = apply_quality_techniques("Classify", techniques, "intake")
        assert result == "Classify"

    def test_contrastive_examples(self) -> None:
        """Contrastive examples instruction is injected."""
        techniques = QualityTechniquesConfig(contrastive_examples=True)
        result = apply_quality_techniques("Generate", techniques, "production")
        assert "Contrastive" in result

    def test_domain_vocab_injected(self, tmp_path: Path) -> None:
        """Domain vocabulary is injected for production stages."""
        vocab_file = tmp_path / "vocab.yaml"
        vocab_file.write_text("terms:\n  - raya\n  - hari raya")
        techniques = QualityTechniquesConfig(domain_vocab=str(vocab_file))
        result = apply_quality_techniques("Generate", techniques, "production")
        assert "Domain vocabulary" in result


# ---------------------------------------------------------------------------
# Client override tests
# ---------------------------------------------------------------------------


class TestClientOverride:
    """Executor merges workflow_overrides from client config."""

    def test_dmb_override_raises_tripwire_threshold(self) -> None:
        """DMB override raises tripwire threshold from 3.0 to 3.5."""
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "poster_production.yaml",
            client_id="dmb",
        )
        assert executor.pack.tripwire.threshold == 3.5

    def test_dmb_override_preserves_other_fields(self) -> None:
        """Client override preserves non-overridden fields."""
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "poster_production.yaml",
            client_id="dmb",
        )
        # scorer_model should still be gpt-5.4-mini
        assert executor.pack.scorer_model == "gpt-5.4-mini"
        # Stages should be unchanged
        assert len(executor.pack.stages) == 4

    def test_missing_client_uses_defaults(self) -> None:
        """Non-existent client config uses workflow defaults."""
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "poster_production.yaml",
            client_id="nonexistent_client",
        )
        assert executor.pack.tripwire.threshold == 3.0


# ---------------------------------------------------------------------------
# Stub workflow error tests
# ---------------------------------------------------------------------------


class TestStubWorkflowError:
    """Extended YAMLs validate but executor reports friendly error."""

    @pytest.mark.parametrize(
        "yaml_name",
        EXTENDED_YAMLS,
        ids=[Path(y).stem for y in EXTENDED_YAMLS],
    )
    def test_extended_yaml_validates_structurally(self, yaml_name: str) -> None:
        """Extended YAMLs validate against schema."""
        pack = load_workflow(WORKFLOWS_DIR / yaml_name)
        assert pack.name
        assert pack.requires_session is not None

    def test_stub_workflow_error_is_human_readable(self) -> None:
        """Executor gives human-readable error for unbuilt tools."""
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "social_batch.yaml",
        )
        with pytest.raises(StubWorkflowError) as exc_info:
            executor.run()
        msg = str(exc_info.value)
        assert "social_batch" in msg
        assert "S24" in msg
        assert "config/phase.yaml" in msg
        assert "hasn't shipped yet" in msg


# ---------------------------------------------------------------------------
# Reminder prompt tests
# ---------------------------------------------------------------------------


class TestReminderPrompt:
    """reminder_prompt field supported and resolves variables."""

    def test_poster_has_reminder_prompt(self) -> None:
        pack = load_workflow(WORKFLOWS_DIR / "poster_production.yaml")
        assert pack.reminder_prompt is not None

    def test_childrens_book_has_reminder_prompt(self) -> None:
        pack = load_workflow(WORKFLOWS_DIR / "childrens_book_production.yaml")
        assert pack.reminder_prompt is not None

    def test_resolve_variables(self) -> None:
        """Variables like {client_name} resolve from job context."""
        template = "Client: {client_name}. Register: {copy_register}."
        result = resolve_reminder(template, {
            "client_name": "Acme Corp",
            "copy_register": "formal",
        })
        assert result == "Client: Acme Corp. Register: formal."

    def test_unresolved_variables_kept(self) -> None:
        """Unresolved variables are kept as-is."""
        template = "Client: {client_name}. Unknown: {missing_var}."
        result = resolve_reminder(template, {"client_name": "Test"})
        assert result == "Client: Test. Unknown: {missing_var}."

    def test_reminder_appended_to_production_stage(self) -> None:
        """Reminder prompt is appended during production stages."""
        captured_prompts: list[str] = []

        def capture_tool(context: dict[str, Any]) -> dict[str, Any]:
            captured_prompts.append(context.get("prompt", ""))
            return {"status": "ok", "output": "done"}

        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "poster_production.yaml",
            tool_registry={
                "classify_artifact": _stub_tool,
                "generate_poster": capture_tool,
                "image_generate": capture_tool,
                "visual_qa": _stub_tool,
                "deliver": _stub_tool,
            },
        )
        executor.run(job_context={
            "client_name": "DMB",
            "copy_register": "formal",
            "platform": "Instagram",
        })
        # At least one production tool should have received the reminder
        assert any("DMB" in p for p in captured_prompts)


# ---------------------------------------------------------------------------
# Rolling context tests
# ---------------------------------------------------------------------------


class TestRollingContext:
    """Rolling summary fires post_step_update correctly."""

    def test_rolling_context_initialised(self) -> None:
        """Executor initialises RollingContext for rolling_summary strategy."""
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "childrens_book_production.yaml",
        )
        assert executor.rolling_context is not None
        assert executor.rolling_context.recent_window == 8

    def test_context_not_initialised_for_simple(self) -> None:
        """No RollingContext for simple context_strategy."""
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "poster_production.yaml",
        )
        assert executor.rolling_context is None

    def test_ebook_uses_rolling_summary(self) -> None:
        """eBook workflow uses rolling_summary context."""
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "ebook_production.yaml",
        )
        assert executor.rolling_context is not None
        assert executor.rolling_context.recent_window == 2
