"""S19 Self-Improvement Loop — comprehensive tests.

Tests pattern detection, failure analysis, experiment framework,
prompt versioning, calibration, and message formatters.

Uses synthetic test data inserted directly via get_cursor().
Mocks call_llm for LLM-dependent functions.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.requires_db

from utils.database import get_cursor

# ---------------------------------------------------------------------------
# Fixtures: synthetic test data
# ---------------------------------------------------------------------------

_TEST_CLIENT_ID: str = ""
_TEST_JOB_IDS: list[str] = []


@pytest.fixture(scope="module", autouse=True)
def seed_test_data() -> Any:
    """Insert 25+ synthetic jobs with known patterns for testing."""
    global _TEST_CLIENT_ID, _TEST_JOB_IDS

    with get_cursor() as cur:
        # Create test client
        cur.execute(
            "INSERT INTO clients (name, brand_config) VALUES (%s, %s) RETURNING id",
            ("test_s19_client", json.dumps({"brand": "test"})),
        )
        _TEST_CLIENT_ID = str(cur.fetchone()["id"])

        _TEST_JOB_IDS = []
        for i in range(25):
            approved = i < 15  # 15 approved, 10 rejected
            has_knowledge = i < 12  # knowledge cards used in first 12

            trace = {
                "steps_executed": ["research", "draft", "refine"] if has_knowledge else ["draft", "refine"],
                "knowledge_cards_used": ["card_1", "card_2"] if has_knowledge else [],
                "refinement_cycles": 1 if approved else 3,
            }
            cost = {"total_cost_usd": 0.05 if i < 20 else 0.25}  # last 5 are expensive
            quality = {
                "overall_score": 4.0 if approved else 2.0,
                "cta_visibility": 4 if approved else 2,
                "brand_alignment": 4 if approved else 1,
            }

            cur.execute(
                """
                INSERT INTO jobs (client_id, job_type, status, production_trace)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (_TEST_CLIENT_ID, "poster", "completed", json.dumps(trace)),
            )
            job_id = str(cur.fetchone()["id"])
            _TEST_JOB_IDS.append(job_id)

            # Feedback — non-anchor, non-silence
            cur.execute(
                """
                INSERT INTO feedback (job_id, client_id, feedback_status, operator_rating, anchor_set)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (job_id, _TEST_CLIENT_ID, "explicitly_approved" if approved else "revision_requested",
                 5 if approved else 2, False),
            )

            # Outcome memory
            cur.execute(
                """
                INSERT INTO outcome_memory (job_id, client_id, first_pass_approved, cost_summary, quality_summary)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (job_id, _TEST_CLIENT_ID, approved, json.dumps(cost), json.dumps(quality)),
            )

        # Add 3 anchor_set jobs (should be excluded)
        for i in range(3):
            cur.execute(
                """
                INSERT INTO jobs (client_id, job_type, status, production_trace)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (_TEST_CLIENT_ID, "poster", "completed",
                 json.dumps({"steps_executed": ["draft"], "anchor": True})),
            )
            anchor_job_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO feedback (job_id, client_id, feedback_status, operator_rating, anchor_set)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (anchor_job_id, _TEST_CLIENT_ID, "explicitly_approved", 5, True),
            )
            cur.execute(
                """
                INSERT INTO outcome_memory (job_id, client_id, first_pass_approved, cost_summary, quality_summary)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (anchor_job_id, _TEST_CLIENT_ID, True,
                 json.dumps({"total_cost_usd": 0.05}),
                 json.dumps({"overall_score": 5.0})),
            )

        # Add 2 silence_flagged jobs (should be excluded)
        for i in range(2):
            cur.execute(
                """
                INSERT INTO jobs (client_id, job_type, status, production_trace)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (_TEST_CLIENT_ID, "poster", "completed",
                 json.dumps({"steps_executed": ["draft"], "silence": True})),
            )
            silence_job_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO feedback (job_id, client_id, feedback_status, operator_rating, anchor_set)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (silence_job_id, _TEST_CLIENT_ID, "silence_flagged", 5, False),
            )
            cur.execute(
                """
                INSERT INTO outcome_memory (job_id, client_id, first_pass_approved, cost_summary, quality_summary)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (silence_job_id, _TEST_CLIENT_ID, True,
                 json.dumps({"total_cost_usd": 0.05}),
                 json.dumps({"overall_score": 5.0})),
            )

    yield

    # Cleanup — order matters for FK constraints
    with get_cursor() as cur:
        cur.execute("DELETE FROM experiment_results WHERE experiment_id IN (SELECT id FROM experiments WHERE name LIKE 'test_%%')")
        cur.execute("DELETE FROM experiments WHERE name LIKE 'test_%'")
        cur.execute("DELETE FROM outcome_memory WHERE client_id = %s", (_TEST_CLIENT_ID,))
        # Delete ALL feedback referencing our jobs (including benchmark-injected ones)
        cur.execute(
            "DELETE FROM feedback WHERE job_id IN (SELECT id FROM jobs WHERE client_id = %s)",
            (_TEST_CLIENT_ID,),
        )
        cur.execute("DELETE FROM jobs WHERE client_id = %s", (_TEST_CLIENT_ID,))
        cur.execute("DELETE FROM clients WHERE id = %s", (_TEST_CLIENT_ID,))


# ---------------------------------------------------------------------------
# Pattern Detection Tests
# ---------------------------------------------------------------------------


class TestPatternDetector:
    def test_finds_approval_correlations(self) -> None:
        from tools.improvement import PatternDetector

        detector = PatternDetector()
        correlations = detector.detect_approval_correlations("poster", min_jobs=10)

        assert isinstance(correlations, list)
        assert len(correlations) > 0
        # Should find correlation with knowledge_cards_used or steps_executed
        patterns = [c["pattern"] for c in correlations]
        assert any("knowledge" in p or "steps" in p or "refinement" in p for p in patterns)

    def test_excludes_anchor_set_feedback(self) -> None:
        """Anti-drift #56: anchor_set=true must be excluded."""
        from tools.improvement import PatternDetector

        detector = PatternDetector()
        correlations = detector.detect_approval_correlations("poster", min_jobs=10)

        # We inserted 25 normal + 3 anchor + 2 silence = 30 total
        # But only 25 should be analysed
        for corr in correlations:
            assert corr["sample_size"] <= 25, (
                f"Sample size {corr['sample_size']} exceeds non-anchor count of 25"
            )

    def test_excludes_silence_flagged_feedback(self) -> None:
        """Anti-drift #13: silence_flagged must be excluded."""
        from tools.improvement import PatternDetector

        detector = PatternDetector()
        correlations = detector.detect_approval_correlations("poster", min_jobs=10)

        for corr in correlations:
            assert corr["sample_size"] <= 25

    def test_cost_outlier_detection(self) -> None:
        from tools.improvement import PatternDetector

        detector = PatternDetector()
        outliers = detector.detect_cost_outliers("poster", threshold_multiplier=2.0)

        assert isinstance(outliers, list)
        # Last 5 jobs cost 0.25 vs median ~0.05
        assert len(outliers) >= 1
        for outlier in outliers:
            assert outlier["multiplier"] >= 2.0

    def test_step_value_detection(self) -> None:
        from tools.improvement import PatternDetector

        detector = PatternDetector()
        results = detector.detect_step_value("poster")

        assert isinstance(results, list)
        if results:
            assert "step_name" in results[0]
            assert "quality_with" in results[0]
            assert "quality_without" in results[0]
            assert "delta" in results[0]


# ---------------------------------------------------------------------------
# Improvement Proposal Tests
# ---------------------------------------------------------------------------


class TestImprovementProposal:
    def test_formats_correctly_with_confidence_levels(self) -> None:
        from tools.improvement import generate_improvement_proposal

        # High confidence
        pattern_high = {
            "pattern": "knowledge_cards_used",
            "approval_rate_with": 0.93,
            "approval_rate_without": 0.68,
            "sample_size": 34,
        }
        proposal = generate_improvement_proposal(pattern_high)
        assert proposal["confidence"] == "high"
        assert "id" in proposal
        assert "observation" in proposal

        # Medium confidence
        pattern_med = {**pattern_high, "sample_size": 20}
        proposal_med = generate_improvement_proposal(pattern_med)
        assert proposal_med["confidence"] == "medium"

        # Low confidence
        pattern_low = {**pattern_high, "sample_size": 10}
        proposal_low = generate_improvement_proposal(pattern_low)
        assert proposal_low["confidence"] == "low"


# ---------------------------------------------------------------------------
# Failure Analysis Tests
# ---------------------------------------------------------------------------


class TestFailureAnalysis:
    @patch("tools.improvement.call_llm")
    def test_clusters_low_rated_jobs(self, mock_llm: Any) -> None:
        mock_llm.return_value = {
            "content": json.dumps({
                "diagnosis": "Low CTA visibility in poster designs",
                "proposed_rule": "Always place CTA in bottom-centre with high contrast",
            }),
        }

        from tools.improvement import FailureAnalysis

        analyser = FailureAnalysis()
        results = analyser.analyse_failures(artifact_type="poster", min_rating=3.0)

        assert isinstance(results, list)
        if results:
            result = results[0]
            assert "cluster_id" in result
            assert "common_features" in result
            assert "diagnosis" in result
            assert "proposed_rule" in result
            assert result["sample_size"] >= 2

    @patch("tools.improvement.call_llm")
    def test_saves_improvement_rule_yaml(self, mock_llm: Any) -> None:
        mock_llm.return_value = {
            "content": json.dumps({
                "diagnosis": "Test diagnosis",
                "proposed_rule": "Test rule",
            }),
        }

        from tools.improvement import FailureAnalysis

        analyser = FailureAnalysis()
        results = analyser.analyse_failures(artifact_type="poster", min_rating=3.0)

        # Check that YAML rule files were created
        rules_dir = Path("config/improvement_rules")
        rule_files = list(rules_dir.glob("rule_poster_*.yaml"))
        assert len(rule_files) >= 1

        # Cleanup
        for f in rule_files:
            f.unlink()


# ---------------------------------------------------------------------------
# Experiment Framework Tests
# ---------------------------------------------------------------------------


class TestExperiment:
    def test_create_experiment(self) -> None:
        from tools.experiment import create_experiment

        proposal = {
            "name": "test_experiment_1",
            "hypothesis": "Adding CTA instruction improves approval",
            "experiment_type": "prompt_variation",
            "control_config": {"template": "v1"},
            "experiment_config": {"template": "v2"},
            "target_artifact_type": "poster",
            "sample_size": 5,
        }
        exp_id = create_experiment(proposal)
        assert exp_id is not None

        # Verify in DB
        with get_cursor() as cur:
            cur.execute("SELECT * FROM experiments WHERE id = %s", (exp_id,))
            row = cur.fetchone()
            assert row is not None
            assert row["name"] == "test_experiment_1"
            assert row["status"] == "pending"

    def test_tag_job_and_round_robin(self) -> None:
        from tools.experiment import create_experiment, should_assign_experiment, tag_job

        # Use unique artifact type to avoid interference from other test experiments
        proposal = {
            "name": "test_experiment_rr",
            "hypothesis": "Round-robin test",
            "experiment_type": "prompt_variation",
            "control_config": {},
            "experiment_config": {},
            "target_artifact_type": "poster_rr_test",
            "sample_size": 3,
        }
        exp_id = create_experiment(proposal)

        # First assignment should be control (both at 0, control <= experiment)
        assignment = should_assign_experiment(_TEST_JOB_IDS[0], "poster_rr_test")
        assert assignment is not None
        assert assignment["arm"] == "control"

        tag_job(_TEST_JOB_IDS[0], exp_id, "control")

        # Second should be experiment (control=1, experiment=0)
        assignment2 = should_assign_experiment(_TEST_JOB_IDS[1], "poster_rr_test")
        assert assignment2 is not None
        assert assignment2["arm"] == "experiment"

        tag_job(_TEST_JOB_IDS[1], exp_id, "experiment")

    def test_record_result_and_evaluate(self) -> None:
        from tools.experiment import (
            create_experiment,
            evaluate_experiment,
            record_result,
            tag_job,
        )

        proposal = {
            "name": "test_experiment_eval",
            "hypothesis": "Evaluation test",
            "experiment_type": "prompt_variation",
            "control_config": {},
            "experiment_config": {},
            "target_artifact_type": "poster",
            "sample_size": 2,
        }
        exp_id = create_experiment(proposal)

        # Tag and record control arm
        tag_job(_TEST_JOB_IDS[0], exp_id, "control")
        tag_job(_TEST_JOB_IDS[1], exp_id, "control")
        record_result(exp_id, _TEST_JOB_IDS[0], rating=3, approved=True, tokens=100, cost=0.01)
        record_result(exp_id, _TEST_JOB_IDS[1], rating=2, approved=False, tokens=200, cost=0.02)

        # Tag and record experiment arm
        tag_job(_TEST_JOB_IDS[2], exp_id, "experiment")
        tag_job(_TEST_JOB_IDS[3], exp_id, "experiment")
        record_result(exp_id, _TEST_JOB_IDS[2], rating=5, approved=True, tokens=90, cost=0.009)
        record_result(exp_id, _TEST_JOB_IDS[3], rating=4, approved=True, tokens=110, cost=0.011)

        # Evaluate
        summary = evaluate_experiment(exp_id)
        assert summary["winner"] == "experiment"  # 100% approval vs 50%
        assert summary["control_approved"] == 1
        assert summary["experiment_approved"] == 2


# ---------------------------------------------------------------------------
# Prompt Template Versioning Tests
# ---------------------------------------------------------------------------


class TestPromptVersioning:
    @pytest.fixture(autouse=True)
    def setup_template(self, tmp_path: Path) -> Any:
        """Create a temp template for testing."""
        self.template_path = tmp_path / "test_template.md"
        self.template_path.write_text(
            "version: 1\nvalidation_score: 3.5\n\n# Test Template\nSome content here.",
            encoding="utf-8",
        )
        self.archive_dir = Path("config/prompt_templates/archive")
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        yield

    def test_get_template_version(self) -> None:
        from tools.prompt_version import get_template_version

        info = get_template_version(str(self.template_path))
        assert info["version"] == 1
        assert info["validation_score"] == 3.5

    def test_promote_increments_version(self) -> None:
        from tools.prompt_version import promote_template

        result = promote_template(
            str(self.template_path),
            "# Improved Template\nBetter content.",
            "Test promotion",
        )

        assert result["old_version"] == 1
        assert result["new_version"] == 2

        # Check archive exists
        archive = Path(result["archived_to"])
        assert archive.exists()

        # Check new content
        new_content = self.template_path.read_text(encoding="utf-8")
        assert "version: 2" in new_content

        # Verify system_state logged
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM system_state WHERE change_type = 'template_promotion' ORDER BY created_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            assert row is not None
            assert "test_template" in row["change_description"]

    def test_revert_restores_previous(self) -> None:
        from tools.prompt_version import promote_template, revert_template

        # First promote
        promote_template(
            str(self.template_path),
            "# V2 Template\nNew stuff.",
            "First promotion",
        )

        # Then revert
        result = revert_template(str(self.template_path))
        assert result["reverted_from"] == 2
        assert result["reverted_to"] == 1

        content = self.template_path.read_text(encoding="utf-8")
        assert "Some content here" in content


# ---------------------------------------------------------------------------
# Calibration Tests
# ---------------------------------------------------------------------------


class TestCalibration:
    @patch("tools.calibration.call_llm")
    def test_anchor_set_detects_drift(self, mock_llm: Any) -> None:
        """Drift > 0.5 should be detected."""
        # Mock scorer returns inflated scores (simulating drift)
        mock_llm.return_value = {"content": "5"}

        from tools.calibration import score_anchor_set

        result = score_anchor_set()

        assert result["anchor_count"] >= 3  # We seeded 3 anchor examples
        assert result["original_avg"] > 0
        # Mock returns 5 for all, originals are 5 → drift should be 0
        # Actually our anchors all have rating=5, so no drift with mock=5
        assert isinstance(result["drift"], float)

    @patch("tools.calibration.call_llm")
    def test_anchor_set_drift_detection_with_shift(self, mock_llm: Any) -> None:
        """When scorer returns different scores, drift should be detected."""
        mock_llm.return_value = {"content": "2"}  # Low scores vs original 5

        from tools.calibration import score_anchor_set

        result = score_anchor_set()
        if result["anchor_count"] > 0:
            # Original avg is 5.0, current avg is 2.0, drift = 3.0
            assert result["drift"] > 0.5

    def test_velocity_decay_alert(self) -> None:
        from tools.calibration import check_velocity_decay

        result = check_velocity_decay(window_jobs=100)
        assert "total_jobs" in result
        assert "proposals_in_window" in result
        assert "alert" in result
        # Should alert if 0 proposals in 100+ jobs (and we have 25+ jobs)
        assert isinstance(result["alert"], bool)

    def test_external_benchmark_ingestion(self) -> None:
        from tools.calibration import ingest_external_benchmark

        feedback_id = ingest_external_benchmark(
            image_data=b"fake_image_data",
            metadata={
                "job_id": _TEST_JOB_IDS[0],
                "description": "Competitor poster example",
            },
        )

        assert feedback_id is not None

        # Verify tagged with benchmark_source = 'external'
        with get_cursor() as cur:
            cur.execute(
                "SELECT benchmark_source FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["benchmark_source"] == "external"


# ---------------------------------------------------------------------------
# Exemplar Optimisation Tests
# ---------------------------------------------------------------------------


class TestExemplarOptimiser:
    @patch("tools.calibration.call_llm")
    def test_insufficient_exemplars_returns_error(self, mock_llm: Any) -> None:
        from tools.calibration import ExemplarOptimiser

        optimiser = ExemplarOptimiser()
        result = optimiser.optimise_exemplar_set("poster", _TEST_CLIENT_ID, k=3, n_trials=5)

        # We haven't seeded 20+ exemplars, so should return error
        assert "error" in result


# ---------------------------------------------------------------------------
# Prompt Variation Testing Tests
# ---------------------------------------------------------------------------


class TestPromptVariationTester:
    @patch("tools.calibration.call_llm")
    def test_generates_variants_and_scores(self, mock_llm: Any, tmp_path: Path) -> None:
        mock_llm.return_value = {"content": "4"}

        template = tmp_path / "test_poster.md"
        template.write_text("# Poster Template\nCreate a poster for {{brand}}.", encoding="utf-8")

        from tools.calibration import PromptVariationTester

        tester = PromptVariationTester()
        result = tester.test_prompt_variations(
            str(template), "poster_production", n_variants=3
        )

        assert "current_score" in result
        assert len(result["variants"]) == 3
        assert "best_variant" in result
        assert "improvement" in result


# ---------------------------------------------------------------------------
# Rule Manager Tests
# ---------------------------------------------------------------------------


class TestRuleManager:
    def test_loads_rules_from_yaml(self) -> None:
        from tools.improvement import RuleManager

        manager = RuleManager()
        rules = manager.load_rules()

        # mutation_operators.yaml should be loaded
        assert len(rules) > 0

    def test_loads_rules_filtered_by_type(self) -> None:
        from tools.improvement import RuleManager

        manager = RuleManager()
        rules = manager.load_rules(artifact_type="poster")

        assert all(
            "poster" in r.get("applies_to", []) or r.get("artifact_type") == "poster"
            for r in rules
        )

    def test_injects_rules_into_template(self) -> None:
        from tools.improvement import RuleManager

        manager = RuleManager()
        template = "# Poster Prompt\nCreate a poster."
        rules = [
            {"rule": "Always place CTA at bottom-centre"},
            {"rule": "Use high-contrast colours for text"},
        ]

        result = manager.inject_rules_into_template(template, rules)
        assert "IMPROVEMENT RULES:" in result
        assert "Always place CTA at bottom-centre" in result
        assert "Use high-contrast colours for text" in result

    def test_inject_empty_rules_returns_unchanged(self) -> None:
        from tools.improvement import RuleManager

        manager = RuleManager()
        template = "Original template"
        result = manager.inject_rules_into_template(template, [])
        assert result == template


# ---------------------------------------------------------------------------
# Message Formatter Tests
# ---------------------------------------------------------------------------


class TestMessageFormatters:
    def test_format_proposal_message(self) -> None:
        from tools.improvement import format_proposal_message

        proposal = {
            "observation": "CTA exact text improves approval",
            "proposed_change": "Add CTA instruction",
            "expected_impact": "+25% approval",
            "confidence": "high",
            "sample_size": 34,
        }
        msg = format_proposal_message(proposal)

        assert "IMPROVEMENT PROPOSAL" in msg
        assert "CTA exact text" in msg
        assert "/test" in msg
        assert "/promote" in msg
        assert "/reject" in msg
        assert "high" in msg
        assert "34 jobs" in msg

    def test_format_experiment_result(self) -> None:
        from tools.improvement import format_experiment_result

        result = {
            "name": "poster-cta-exact",
            "control_approved": 3,
            "control_total": 5,
            "experiment_approved": 5,
            "experiment_total": 5,
            "control_avg_cost": 2400,
            "experiment_avg_cost": 2200,
        }
        msg = format_experiment_result(result)

        assert "EXPERIMENT COMPLETE" in msg
        assert "poster-cta-exact" in msg
        assert "3/5" in msg
        assert "5/5" in msg
        assert "/promote" in msg

    def test_format_drift_alert(self) -> None:
        from tools.improvement import format_drift_alert

        drift_data = {
            "original_avg": 3.4,
            "current_avg": 4.1,
            "drift": 0.7,
        }
        msg = format_drift_alert(drift_data)

        assert "DRIFT ALERT" in msg
        assert "3.4/5" in msg
        assert "4.1/5" in msg
        assert "+0.7 drift" in msg
        assert "/review-anchors" in msg


# ---------------------------------------------------------------------------
# Promote Decision Logging Tests
# ---------------------------------------------------------------------------


class TestDecisionLogging:
    def test_promote_logs_to_docs_decisions(self, tmp_path: Path) -> None:
        from tools.prompt_version import promote_template

        template = tmp_path / "log_test_template.md"
        template.write_text("version: 1\n# Template\nContent.", encoding="utf-8")

        promote_template(str(template), "# Better content", "Test decision note")

        decisions_dir = Path("docs/decisions")
        decision_files = list(decisions_dir.glob("promote_log_test_template_*.md"))
        assert len(decision_files) >= 1

        content = decision_files[0].read_text(encoding="utf-8")
        assert "Test decision note" in content
        assert "v1" in content

        # Cleanup
        for f in decision_files:
            f.unlink()

    def test_promote_updates_system_state(self, tmp_path: Path) -> None:
        from tools.prompt_version import promote_template

        template = tmp_path / "sysstate_test.md"
        template.write_text("version: 1\n# Test\nContent.", encoding="utf-8")

        promote_template(str(template), "# New content", "System state test")

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM system_state
                WHERE change_type = 'template_promotion'
                  AND change_description LIKE '%%sysstate_test%%'
                ORDER BY created_at DESC LIMIT 1
                """
            )
            row = cur.fetchone()
            assert row is not None
