"""IT-3: Fast-Path Routing Integration Test.

Validates: S11 routing → S9 workflow schema linkage.
The most basic "does the plumbing connect?" test.

Input: "poster DMB"
Expected: fast_path=True, workflow=poster_production, zero LLM tokens.
"""

from __future__ import annotations

import json

from contracts.routing import RoutingResult, fast_path_route, route
from tools.workflow_schema import load_workflow
from utils.database import get_cursor


class TestFastPathRouting:
    """IT-3: fast_path_route("poster DMB") resolves at zero tokens."""

    def test_fast_path_route_returns_result(self) -> None:
        """fast_path_route("poster DMB") returns a RoutingResult, not None."""
        result = fast_path_route("poster DMB")
        assert result is not None, (
            "fast_path_route('poster DMB') returned None — "
            "expected a match on the 'poster' pattern in config/fast_paths.yaml"
        )

    def test_fast_path_route_workflow(self) -> None:
        """Fast-path routes to poster_production workflow."""
        result = fast_path_route("poster DMB")
        assert result is not None
        assert result.workflow == "poster_production", (
            f"Expected workflow='poster_production', got '{result.workflow}'"
        )

    def test_fast_path_route_is_fast_path(self) -> None:
        """RoutingResult.fast_path is True (deterministic, no LLM)."""
        result = fast_path_route("poster DMB")
        assert result is not None
        assert result.fast_path is True

    def test_fast_path_route_zero_tokens(self) -> None:
        """Zero LLM tokens consumed — no call_llm invocation."""
        result = fast_path_route("poster DMB")
        assert result is not None
        assert result.token_cost == 0, (
            f"Fast-path should consume zero tokens, got {result.token_cost}"
        )

    def test_fast_path_confidence_is_one(self) -> None:
        """Deterministic match has confidence=1.0."""
        result = fast_path_route("poster DMB")
        assert result is not None
        assert result.confidence == 1.0

    def test_fast_path_model_preference(self) -> None:
        """Anti-drift #54: model_preference must be gpt-5.4-mini."""
        result = fast_path_route("poster DMB")
        assert result is not None
        assert result.model_preference == "gpt-5.4-mini"


class TestRouteEntryPoint:
    """IT-3: route("poster DMB") uses fast-path, never calls LLM."""

    def test_route_returns_fast_path(self) -> None:
        """route() resolves via fast-path for 'poster DMB'."""
        result = route("poster DMB")
        assert result.fast_path is True, (
            "route('poster DMB') should resolve via fast-path, but fast_path is False. "
            f"Reason: {result.reason}"
        )

    def test_route_workflow_is_poster_production(self) -> None:
        """route() selects poster_production workflow."""
        result = route("poster DMB")
        assert result.workflow == "poster_production"

    def test_route_zero_tokens(self) -> None:
        """route() consumes zero tokens when fast-path resolves."""
        result = route("poster DMB")
        assert result.token_cost == 0

    def test_route_has_routing_id(self) -> None:
        """RoutingResult always has a UUID routing_id."""
        result = route("poster DMB")
        assert result.routing_id is not None


class TestRoutingResultStorable:
    """Verify RoutingResult can be stored on a job record in Postgres."""

    def test_routing_result_serialises_to_json(self) -> None:
        """RoutingResult.model_dump(mode='json') produces valid JSON."""
        result = fast_path_route("poster DMB")
        assert result is not None
        dumped = result.model_dump(mode="json")
        # Round-trip through JSON
        serialised = json.dumps(dumped, default=str)
        parsed = json.loads(serialised)
        assert parsed["workflow"] == "poster_production"
        assert parsed["fast_path"] is True
        assert parsed["token_cost"] == 0

    def test_routing_result_stored_on_job(self, test_job) -> None:
        """RoutingResult JSONB can be written to jobs.routing_result."""
        result = fast_path_route("poster DMB")
        assert result is not None
        result_json = json.dumps(result.model_dump(mode="json"), default=str)

        with get_cursor() as cur:
            cur.execute(
                "UPDATE jobs SET routing_result = %s::jsonb WHERE id = %s",
                (result_json, test_job["id"]),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT routing_result FROM jobs WHERE id = %s",
                (test_job["id"],),
            )
            row = cur.fetchone()

        assert row is not None
        stored = row["routing_result"]
        assert stored["workflow"] == "poster_production"
        assert stored["fast_path"] is True
        assert stored["token_cost"] == 0


class TestWorkflowLinkage:
    """Verify the workflow selected by fast-path actually loads and validates."""

    def test_poster_production_yaml_loads(self) -> None:
        """poster_production.yaml loads via WorkflowPack schema without error."""
        pack = load_workflow("manifests/workflows/poster_production.yaml")
        assert pack.name == "poster_production"

    def test_poster_production_has_stages(self) -> None:
        """poster_production has at least 4 stages (intake, production, qa, delivery)."""
        pack = load_workflow("manifests/workflows/poster_production.yaml")
        assert len(pack.stages) >= 4
        stage_names = [s.name for s in pack.stages]
        assert "intake" in stage_names
        assert "production" in stage_names
        assert "qa" in stage_names
        assert "delivery" in stage_names

    def test_poster_production_model_lock(self) -> None:
        """Anti-drift #54: all model_preference values are gpt-5.4-mini."""
        pack = load_workflow("manifests/workflows/poster_production.yaml")
        for key, value in pack.model_preference.items():
            assert value == "gpt-5.4-mini", (
                f"model_preference['{key}'] = '{value}' violates anti-drift #54"
            )
        assert pack.scorer_model == "gpt-5.4-mini"
        assert pack.scorer_fallback == "gpt-5.4-mini"
