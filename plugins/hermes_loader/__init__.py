"""Thin loader for the repo-owned Vizier Hermes bridge."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)

# Resolve bridge path for two contexts:
# 1. In-repo:  plugins/hermes_loader/__init__.py → parent.parent = plugins/
# 2. Installed: ~/.hermes/plugins/vizier_tools/__init__.py → parent.parent = ~/.hermes/plugins/
# Only case 1 has vizier_tools_bridge.py next to the loader.
# Fall back to VIZIER_ROOT env var, then ~/vizier as last resort.
def _resolve_bridge_path() -> Path:
    """Find vizier_tools_bridge.py with deterministic resolution.

    Resolution order:
    1. Repo-relative — works when running from source tree.
    2. Stamped .vizier_root — written by install_plugin.sh alongside the
       installed copy.  Deterministic: no env vars, no guessing.
    3. VIZIER_ROOT env var — explicit override for non-standard installs.
    4. ~/vizier fallback — last resort (default clone location).
    """
    # 1. Repo-relative (source tree)
    repo_relative = Path(__file__).resolve().parent.parent / "vizier_tools_bridge.py"
    if repo_relative.exists():
        return repo_relative

    # 2. Stamped root — install_plugin.sh writes .vizier_root next to __init__.py
    stamp_file = Path(__file__).resolve().parent / ".vizier_root"
    if stamp_file.exists():
        stamped_root = stamp_file.read_text().strip()
        if stamped_root:
            stamped_path = Path(stamped_root) / "plugins" / "vizier_tools_bridge.py"
            if stamped_path.exists():
                return stamped_path

    # 3. VIZIER_ROOT env var (explicit config)
    import os
    env_root = os.environ.get("VIZIER_ROOT", "").strip()
    if env_root:
        env_path = Path(env_root) / "plugins" / "vizier_tools_bridge.py"
        if env_path.exists():
            return env_path

    # 4. ~/vizier fallback (default clone location)
    return Path.home() / "vizier" / "plugins" / "vizier_tools_bridge.py"


_BRIDGE_PATH = _resolve_bridge_path()
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
