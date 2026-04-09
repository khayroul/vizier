"""Listening-engine domain exceptions.

Ported from pro-max's top-level ``exceptions`` module.  Only the two
exception classes actually used by this package are kept here.
"""
from __future__ import annotations


class InputCheckError(Exception):
    """Raised when user-supplied input fails validation."""

    def __init__(self, field: str, errors: list[str]) -> None:
        self.field = field
        self.errors = errors
        super().__init__(f"Input check failed on '{field}': {'; '.join(errors)}")


class WatchlistNotFoundError(Exception):
    """Raised when a watchlist ID does not exist in the store."""

    def __init__(self, watchlist_id: str) -> None:
        self.watchlist_id = watchlist_id
        super().__init__(f"Watchlist not found: {watchlist_id}")
