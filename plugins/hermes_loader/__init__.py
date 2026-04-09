"""Thin loader for the repo-owned Vizier Hermes bridge."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)

_BRIDGE_PATH = Path.home() / "vizier" / "plugins" / "vizier_tools_bridge.py"
_BRIDGE_MODULE: ModuleType | None = None


def _load_bridge_module() -> ModuleType:
    """Load the repo-owned bridge module via file path to avoid import drift."""

    global _BRIDGE_MODULE
    if _BRIDGE_MODULE is not None:
        return _BRIDGE_MODULE

    spec = importlib.util.spec_from_file_location(
        "vizier_repo_bridge",
        _BRIDGE_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load Vizier bridge from {_BRIDGE_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _BRIDGE_MODULE = module
    return module


def register(ctx: object) -> None:
    """Delegate plugin registration to the repo-owned bridge module."""

    try:
        bridge = _load_bridge_module()
        bridge.register(ctx)
    except Exception as exc:
        logger.error("Vizier bridge loader failed: %s", exc, exc_info=True)
        raise


def __getattr__(name: str) -> Any:
    """Expose bridge helpers for runtime compatibility and test access."""

    bridge = _load_bridge_module()
    return getattr(bridge, name)
