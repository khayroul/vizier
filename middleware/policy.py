"""PolicyEvaluator — centralised policy middleware (§7.2).

Four gates run in order: phase → tool → budget → cost.
Returns the first non-allow PolicyDecision, or allow if all pass.

Budget gate reads daily token usage from the local spans table.
All decisions are PolicyDecision instances for audit logging to policy_logs.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg2
import yaml

from contracts.policy import PolicyAction, PolicyDecision

logger = logging.getLogger(__name__)


def persist_policy_decision(decision: PolicyDecision) -> None:
    """Persist a policy decision to policy_logs. Non-fatal on DB failure.

    Uses lazy import of get_cursor to avoid import-time failure when
    DATABASE_URL is not configured (e.g. in tests, gateway-only mode).
    """
    try:
        from utils.database import get_cursor  # lazy: DB may not be configured

        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO policy_logs
                    (decision_id, job_id, client_id,
                     capability, action, gate,
                     reason, constraints)
                VALUES
                    (%(decision_id)s, %(job_id)s, %(client_id)s, %(capability)s,
                     %(action)s, %(gate)s, %(reason)s, %(constraints)s)
                """,
                {
                    "decision_id": str(decision.decision_id),
                    "job_id": decision.job_id,
                    "client_id": decision.client_id,
                    "capability": decision.capability,
                    "action": decision.action.value,
                    "gate": decision.gate,
                    "reason": decision.reason,
                    "constraints": (
                        json.dumps(decision.constraints)
                        if decision.constraints
                        else "{}"
                    ),
                },
            )
    except (psycopg2.Error, OSError, ImportError, RuntimeError):
        # RuntimeError: DATABASE_URL not set (get_connection_string)
        # psycopg2.Error: any database-level failure
        # OSError: connection refused / network error
        # ImportError: utils.database not available
        logger.warning("Failed to persist policy decision", exc_info=True)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "phase.yaml"
_DEFAULT_SPANS_DB = _REPO_ROOT / "data" / "spans.db"


@dataclass(frozen=True)
class PolicyRequest:
    """Input to PolicyEvaluator.evaluate().

    Attributes:
        capability: Workflow/capability name checked against phase gate.
        tool_name: Optional tool name checked against tool gate.
        job_id: Job identifier for cost tracking and audit.
        client_id: Client identifier for audit.
        running_cost_usd: Current job's accumulated cost for cost gate.
        prompt_tokens: Not used by PolicyEvaluator
            — see observability.check_context_size.
    """

    capability: str
    tool_name: str | None = None
    job_id: str | None = None
    client_id: str | None = None
    running_cost_usd: float = 0.0
    prompt_tokens: int = 0


def _load_config(config_path: Path) -> dict[str, Any]:
    """Read and parse phase.yaml."""
    with open(config_path) as fh:
        return yaml.safe_load(fh)  # type: ignore[no-any-return]


class PolicyEvaluator:
    """Runs four policy gates against a PolicyRequest.

    Gates (evaluated in order):
      1. Phase gate — is the capability in an active phase?
      2. Tool gate — is the tool approved for active phases?
      3. Budget gate — daily token usage within limit?
      4. Cost gate — per-job running cost within ceiling?
    """

    def __init__(
        self,
        config_path: Path = _DEFAULT_CONFIG,
        spans_db_path: Path = _DEFAULT_SPANS_DB,
    ) -> None:
        self._config_path = config_path
        self._spans_db_path = spans_db_path
        self._config = _load_config(config_path)

    def reload_config(self) -> None:
        """Re-read phase.yaml (useful after hot-reload)."""
        self._config = _load_config(self._config_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Run all gates in order. Return first non-allow or allow."""
        for gate in (
            self._phase_gate,
            self._tool_gate,
            self._budget_gate,
            self._cost_gate,
        ):
            decision = gate(request)
            if decision.action != PolicyAction.allow:
                logger.info(
                    "policy_gate_blocked",
                    extra={
                        "gate": decision.gate,
                        "action": decision.action,
                        "reason": decision.reason,
                        "capability": request.capability,
                        "job_id": request.job_id,
                    },
                )
                persist_policy_decision(decision)
                return decision

        decision = PolicyDecision(
            action=PolicyAction.allow,
            reason="All gates passed",
            gate="all",
            job_id=request.job_id,
            client_id=request.client_id,
            capability=request.capability,
        )
        persist_policy_decision(decision)
        return decision

    # ------------------------------------------------------------------
    # Gate 1: Phase gate
    # ------------------------------------------------------------------

    def _phase_gate(self, request: PolicyRequest) -> PolicyDecision:
        """Block if capability is not in any active phase."""
        phases: dict[str, Any] = self._config.get("phases", {})
        for phase_name, phase_cfg in phases.items():
            if not phase_cfg.get("active", False):
                continue
            includes: list[str] = phase_cfg.get("includes", [])
            if request.capability in includes:
                return PolicyDecision(
                    action=PolicyAction.allow,
                    reason=(
                        f"Capability '{request.capability}' "
                        f"active in phase '{phase_name}'"
                    ),
                    gate="phase",
                    job_id=request.job_id,
                    client_id=request.client_id,
                    capability=request.capability,
                )

        # Find which phase would contain it (for the error message)
        required_phase = "unknown"
        for phase_name, phase_cfg in phases.items():
            if request.capability in phase_cfg.get("includes", []):
                required_phase = phase_name
                break

        return PolicyDecision(
            action=PolicyAction.block,
            reason=(
                f"Capability '{request.capability}' requires phase "
                f"'{required_phase}' which is not yet active."
            ),
            gate="phase",
            job_id=request.job_id,
            client_id=request.client_id,
            capability=request.capability,
        )

    # ------------------------------------------------------------------
    # Gate 2: Tool gate
    # ------------------------------------------------------------------

    def _tool_gate(self, request: PolicyRequest) -> PolicyDecision:
        """Block if tool is not in the approved list for active phases."""
        if request.tool_name is None:
            return PolicyDecision(
                action=PolicyAction.allow,
                reason="No tool specified — tool gate skipped",
                gate="tool",
                job_id=request.job_id,
                client_id=request.client_id,
                capability=request.capability,
            )

        approved_tools: dict[str, list[str]] = self._config.get("approved_tools", {})
        phases: dict[str, Any] = self._config.get("phases", {})

        # Collect all approved tools from active phases
        active_tools: set[str] = set()
        for phase_name, phase_cfg in phases.items():
            if phase_cfg.get("active", False):
                phase_tools = approved_tools.get(phase_name, [])
                active_tools.update(phase_tools)

        if request.tool_name in active_tools:
            return PolicyDecision(
                action=PolicyAction.allow,
                reason=f"Tool '{request.tool_name}' is approved",
                gate="tool",
                job_id=request.job_id,
                client_id=request.client_id,
                capability=request.capability,
            )

        return PolicyDecision(
            action=PolicyAction.block,
            reason=f"Tool '{request.tool_name}' is not approved in any active phase",
            gate="tool",
            job_id=request.job_id,
            client_id=request.client_id,
            capability=request.capability,
        )

    # ------------------------------------------------------------------
    # Gate 3: Budget gate
    # ------------------------------------------------------------------

    def _budget_gate(self, request: PolicyRequest) -> PolicyDecision:
        """Block if daily token usage exceeds configured limit."""
        budget_cfg: dict[str, Any] = self._config.get("budget", {})
        daily_limit: int = budget_cfg.get("daily_token_limit", 5_000_000)

        total_tokens = self._get_daily_token_usage()

        if total_tokens > daily_limit:
            return PolicyDecision(
                action=PolicyAction.block,
                reason=(
                    f"Daily token budget exceeded: {total_tokens:,} used "
                    f"of {daily_limit:,} limit"
                ),
                gate="budget",
                job_id=request.job_id,
                client_id=request.client_id,
                capability=request.capability,
                constraints={"daily_limit": daily_limit, "used": total_tokens},
            )

        return PolicyDecision(
            action=PolicyAction.allow,
            reason=f"Budget OK: {total_tokens:,} of {daily_limit:,}",
            gate="budget",
            job_id=request.job_id,
            client_id=request.client_id,
            capability=request.capability,
        )

    def _get_daily_token_usage(self) -> int:
        """Sum input_tokens + output_tokens from spans in last 24 hours."""
        if not self._spans_db_path.exists():
            return 0

        conn = sqlite3.connect(str(self._spans_db_path))
        try:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(input_tokens + output_tokens), 0)
                FROM spans
                WHERE timestamp >= datetime('now', '-1 day')
                """
            ).fetchone()
            return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            logger.warning("spans table not found — assuming 0 usage")
            return 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Gate 4: Cost gate
    # ------------------------------------------------------------------

    def _cost_gate(self, request: PolicyRequest) -> PolicyDecision:
        """Degrade (not block) if per-job cost exceeds ceiling."""
        cost_cfg: dict[str, Any] = self._config.get("cost_ceiling", {})
        ceiling: float = cost_cfg.get("per_job_usd", 5.00)

        if request.running_cost_usd > ceiling:
            return PolicyDecision(
                action=PolicyAction.degrade,
                reason=(
                    f"Job cost ${request.running_cost_usd:.2f} exceeds "
                    f"ceiling ${ceiling:.2f} — degrading quality"
                ),
                gate="cost",
                job_id=request.job_id,
                client_id=request.client_id,
                capability=request.capability,
                constraints={
                    "ceiling_usd": ceiling,
                    "current_usd": request.running_cost_usd,
                },
            )

        return PolicyDecision(
            action=PolicyAction.allow,
            reason=f"Cost OK: ${request.running_cost_usd:.2f} of ${ceiling:.2f}",
            gate="cost",
            job_id=request.job_id,
            client_id=request.client_id,
            capability=request.capability,
        )
