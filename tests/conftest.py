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


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if _check_db():
        return
    skip_marker = pytest.mark.skip(reason="Postgres not reachable (DATABASE_URL)")
    for item in items:
        if item.get_closest_marker("requires_db"):
            item.add_marker(skip_marker)
