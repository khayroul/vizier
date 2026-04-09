"""Root conftest — shared markers and skip logic for the Vizier test suite."""

from __future__ import annotations

import os

import psycopg2
import pytest

# ---------------------------------------------------------------------------
# Database availability check (runs once per session)
# ---------------------------------------------------------------------------

_db_available: bool | None = None


def _check_db() -> bool:
    """Return True if Postgres is reachable, False otherwise."""
    global _db_available  # noqa: PLW0603
    if _db_available is not None:
        return _db_available
    url = os.environ.get("DATABASE_URL", "postgres://localhost:5432/vizier")
    try:
        conn = psycopg2.connect(url, connect_timeout=2)
        conn.close()
        _db_available = True
    except Exception:
        _db_available = False
    return _db_available


# ---------------------------------------------------------------------------
# Auto-skip for requires_db marker
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_db: skip test when Postgres is not reachable",
    )
    config.addinivalue_line(
        "markers",
        "acceptance: user-POV acceptance tests for final deliverables",
    )
    config.addinivalue_line(
        "markers",
        (
            "requires_api: skip test unless real external APIs are available "
            "(run with --run-api)"
        ),
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-api",
        action="store_true",
        default=False,
        help="Run tests that hit real external APIs (OpenAI, fal.ai)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    # Auto-skip DB tests when Postgres is unreachable
    if not _check_db():
        skip_db = pytest.mark.skip(reason="Postgres not reachable (DATABASE_URL)")
        for item in items:
            if item.get_closest_marker("requires_db"):
                item.add_marker(skip_db)

    # Auto-skip API tests unless --run-api is passed
    if not config.getoption("--run-api"):
        skip_api = pytest.mark.skip(
            reason="Real API tests skipped (pass --run-api to run)"
        )
        for item in items:
            if item.get_closest_marker("requires_api"):
                item.add_marker(skip_api)


# ---------------------------------------------------------------------------
# Runtime readiness bypass — tests don't have OPENAI_API_KEY / FAL_KEY
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _bypass_runtime_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass runtime readiness hard-blocks in all tests.

    The readiness gate checks for OPENAI_API_KEY and FAL_KEY which
    are not present in the test environment.  Tests that explicitly
    need to verify readiness behaviour should override this fixture
    or call ``_check_runtime_readiness`` directly with controlled env.
    """
    monkeypatch.setattr(
        "tools.orchestrate._check_runtime_readiness",
        lambda workflow_name, contract_strictness="warn": ([], []),
    )
