"""Postgres connection helper for Vizier.

Provides a thin wrapper around psycopg2 for connection management.
All connections use the DATABASE_URL environment variable.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# Register UUID adapter so psycopg2 returns uuid columns as Python uuid objects
psycopg2.extras.register_uuid()


def get_connection_string() -> str:
    """Return the DATABASE_URL from environment, raising if unset."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


def get_connection() -> psycopg2.extensions.connection:
    """Open a new Postgres connection using DATABASE_URL."""
    return psycopg2.connect(get_connection_string())


@contextmanager
def get_cursor(
    autocommit: bool = False,
) -> Generator[psycopg2.extras.RealDictCursor, None, None]:
    """Context manager yielding a RealDictCursor.

    Commits on clean exit, rolls back on exception.
    If autocommit=True, sets connection to autocommit mode (useful for DDL).
    """
    conn = get_connection()
    if autocommit:
        conn.autocommit = True
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
            if not autocommit:
                conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()


def run_migration(sql_path: Path) -> None:
    """Execute a SQL migration file against the database.

    Runs the entire file as a single transaction.
    """
    sql = sql_path.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        logger.info("Migration applied: %s", sql_path.name)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
