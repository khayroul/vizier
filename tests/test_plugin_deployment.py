"""Deployment-boundary tests for the Hermes plugin install pipeline.

These tests verify that install_plugin.sh → installed loader → bridge resolution
works end-to-end, not just in the source tree.  They exercise the *actual*
installed boundary — temp dir, real file copies, real imports — not mocked proxies.

Finding 1 from Codex Round 3: "Add temp-dir install/import integration test
for plugin boundary."
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import textwrap
from pathlib import Path
from types import ModuleType

import pytest

# Repo root — two levels up from tests/
REPO_DIR = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_DIR / "scripts" / "install_plugin.sh"
SOURCE_LOADER = REPO_DIR / "plugins" / "hermes_loader" / "__init__.py"
SOURCE_YAML = REPO_DIR / "plugins" / "hermes_loader" / "plugin.yaml"
BRIDGE_MODULE = REPO_DIR / "plugins" / "vizier_tools_bridge.py"


def _load_module_from_path(name: str, path: Path) -> ModuleType:
    """Load a Python module from an arbitrary filesystem path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"Cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakePluginContext:
    """Minimal stand-in for Hermes plugin registration context."""

    def __init__(self) -> None:
        self.tools: list[dict[str, object]] = []
        self.hooks: list[tuple[str, object]] = []

    def register_tool(self, **kwargs: object) -> None:
        self.tools.append(kwargs)

    def register_hook(self, hook_name: str, callback: object) -> None:
        self.hooks.append((hook_name, callback))


# --------------------------------------------------------------------------- #
#  Parity tests — installed copy must match source of truth                    #
# --------------------------------------------------------------------------- #


class TestInstallParity:
    """Verify the install script produces files identical to the source."""

    def test_install_creates_stamp_file(self, tmp_path: Path) -> None:
        """install_plugin.sh must write .vizier_root with the repo path."""
        plugin_dir = tmp_path / ".hermes" / "plugins" / "vizier_tools"
        env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}

        subprocess.run(
            ["bash", str(INSTALL_SCRIPT)],
            env=env,
            check=True,
            capture_output=True,
        )

        stamp = plugin_dir / ".vizier_root"
        assert stamp.exists(), ".vizier_root not created by install script"
        assert stamp.read_text().strip() == str(REPO_DIR)

    def test_install_copies_match_source(self, tmp_path: Path) -> None:
        """Installed __init__.py and plugin.yaml must be byte-identical to source."""
        plugin_dir = tmp_path / ".hermes" / "plugins" / "vizier_tools"
        env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}

        subprocess.run(
            ["bash", str(INSTALL_SCRIPT)],
            env=env,
            check=True,
            capture_output=True,
        )

        installed_init = plugin_dir / "__init__.py"
        installed_yaml = plugin_dir / "plugin.yaml"

        assert installed_init.read_text() == SOURCE_LOADER.read_text(), (
            "Installed __init__.py diverged from source — run install_plugin.sh"
        )
        assert installed_yaml.read_text() == SOURCE_YAML.read_text(), (
            "Installed plugin.yaml diverged from source — run install_plugin.sh"
        )

    def test_install_is_idempotent(self, tmp_path: Path) -> None:
        """Running install twice must produce identical results."""
        env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}

        subprocess.run(["bash", str(INSTALL_SCRIPT)], env=env, check=True, capture_output=True)
        first_stamp = (tmp_path / ".hermes" / "plugins" / "vizier_tools" / ".vizier_root").read_text()

        subprocess.run(["bash", str(INSTALL_SCRIPT)], env=env, check=True, capture_output=True)
        second_stamp = (tmp_path / ".hermes" / "plugins" / "vizier_tools" / ".vizier_root").read_text()

        assert first_stamp == second_stamp


# --------------------------------------------------------------------------- #
#  Deployment boundary tests — loader works from installed location            #
# --------------------------------------------------------------------------- #


class TestDeploymentBoundary:
    """Verify the installed loader resolves the bridge via the stamp."""

    def test_installed_loader_resolves_bridge_via_stamp(
        self, tmp_path: Path,
    ) -> None:
        """Loader installed to tmp_path must find bridge via .vizier_root stamp."""
        plugin_dir = tmp_path / "plugins" / "vizier_tools"
        plugin_dir.mkdir(parents=True)

        # Copy loader
        shutil.copy2(SOURCE_LOADER, plugin_dir / "__init__.py")
        # Write stamp pointing to the real repo
        (plugin_dir / ".vizier_root").write_text(str(REPO_DIR))

        # Load the installed copy — NOT the source tree copy
        mod = _load_module_from_path(
            "vizier_installed_test", plugin_dir / "__init__.py",
        )

        # _BRIDGE_PATH should resolve to the real bridge, not a broken path
        assert mod._BRIDGE_PATH.exists(), (
            f"Installed loader resolved to non-existent bridge: {mod._BRIDGE_PATH}"
        )
        assert mod._BRIDGE_PATH == BRIDGE_MODULE

    def test_installed_loader_register_works(self, tmp_path: Path) -> None:
        """Full registration via installed loader must expose tools and hooks."""
        plugin_dir = tmp_path / "plugins" / "vizier_tools"
        plugin_dir.mkdir(parents=True)

        shutil.copy2(SOURCE_LOADER, plugin_dir / "__init__.py")
        (plugin_dir / ".vizier_root").write_text(str(REPO_DIR))

        mod = _load_module_from_path(
            "vizier_install_register_test", plugin_dir / "__init__.py",
        )

        ctx = _FakePluginContext()
        mod.register(ctx)

        tool_names = {tool["name"] for tool in ctx.tools}
        hook_names = {name for name, _ in ctx.hooks}

        assert "run_pipeline" in tool_names
        assert "query_logs" in tool_names
        assert "pre_tool_call" in hook_names

    def test_installed_loader_exposes_bridge_helpers(
        self, tmp_path: Path,
    ) -> None:
        """__getattr__ on installed loader must delegate to bridge."""
        plugin_dir = tmp_path / "plugins" / "vizier_tools"
        plugin_dir.mkdir(parents=True)

        shutil.copy2(SOURCE_LOADER, plugin_dir / "__init__.py")
        (plugin_dir / ".vizier_root").write_text(str(REPO_DIR))

        mod = _load_module_from_path(
            "vizier_install_getattr_test", plugin_dir / "__init__.py",
        )

        # _extract_nested is a helper defined in the bridge, not the loader
        result = mod._extract_nested({"pdf_path": "/tmp/out.pdf"}, "pdf_path")
        assert result == "/tmp/out.pdf"

    def test_loader_without_stamp_falls_back_to_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without .vizier_root stamp, VIZIER_ROOT env var is the next fallback."""
        plugin_dir = tmp_path / "plugins" / "vizier_tools"
        plugin_dir.mkdir(parents=True)

        shutil.copy2(SOURCE_LOADER, plugin_dir / "__init__.py")
        # No stamp file — simulate pre-stamp install
        monkeypatch.setenv("VIZIER_ROOT", str(REPO_DIR))

        mod = _load_module_from_path(
            "vizier_env_fallback_test", plugin_dir / "__init__.py",
        )

        assert mod._BRIDGE_PATH.exists()
        assert mod._BRIDGE_PATH == BRIDGE_MODULE

    def test_loader_without_stamp_or_env_falls_back_to_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without stamp or env, loader falls back to ~/vizier."""
        plugin_dir = tmp_path / "plugins" / "vizier_tools"
        plugin_dir.mkdir(parents=True)

        shutil.copy2(SOURCE_LOADER, plugin_dir / "__init__.py")
        # No stamp, no env var
        monkeypatch.delenv("VIZIER_ROOT", raising=False)

        mod = _load_module_from_path(
            "vizier_home_fallback_test", plugin_dir / "__init__.py",
        )

        # Should fall back to ~/vizier/plugins/vizier_tools_bridge.py
        expected_fallback = Path.home() / "vizier" / "plugins" / "vizier_tools_bridge.py"
        assert mod._BRIDGE_PATH == expected_fallback


# --------------------------------------------------------------------------- #
#  Drift detection — source loader must be in sync with repo bridge            #
# --------------------------------------------------------------------------- #


class TestDriftDetection:
    """Catch deployment drift before it reaches production.

    These tests import through the normal Python path (not spec_from_file_location)
    to avoid dataclass module-resolution issues when the bridge transitively
    imports Vizier domain modules.
    """

    def test_source_loader_resolves_bridge_in_repo(self) -> None:
        """Source tree loader must resolve to the bridge in the same repo."""
        mod = _load_module_from_path(
            "vizier_source_tree_test", SOURCE_LOADER,
        )
        assert mod._BRIDGE_PATH == BRIDGE_MODULE
        assert mod._BRIDGE_PATH.exists()

    def test_bridge_module_has_register_function(self) -> None:
        """Bridge must expose register() — loader delegates to it."""
        from plugins import vizier_tools_bridge as bridge_mod

        assert hasattr(bridge_mod, "register")
        assert callable(bridge_mod.register)

    def test_plugin_yaml_tools_match_bridge_registration(self) -> None:
        """Tools declared in plugin.yaml must match what register() exposes."""
        import yaml

        from plugins import vizier_tools_bridge as bridge_mod

        yaml_content = yaml.safe_load(SOURCE_YAML.read_text())
        declared_tools = set(yaml_content.get("provides_tools", []))

        ctx = _FakePluginContext()
        bridge_mod.register(ctx)
        registered_tools = {tool["name"] for tool in ctx.tools}

        assert declared_tools == registered_tools, (
            f"plugin.yaml declares {declared_tools} but bridge registers {registered_tools}"
        )

    def test_plugin_yaml_hooks_match_bridge_registration(self) -> None:
        """Hooks declared in plugin.yaml must match what register() exposes."""
        import yaml

        from plugins import vizier_tools_bridge as bridge_mod

        yaml_content = yaml.safe_load(SOURCE_YAML.read_text())
        declared_hooks = set(yaml_content.get("provides_hooks", []))

        ctx = _FakePluginContext()
        bridge_mod.register(ctx)
        registered_hooks = {name for name, _ in ctx.hooks}

        assert declared_hooks == registered_hooks, (
            f"plugin.yaml declares {declared_hooks} but bridge registers {registered_hooks}"
        )
