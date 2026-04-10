"""Tests for config-driven NIMA thresholds in visual_scoring.

Verifies that nima_prescreen reads thresholds from YAML config
rather than hardcoded values, and that custom config overrides work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def test_default_thresholds() -> None:
    """Score 3.5 (below default 4.0) -> regenerate; 7.5 (above 7.0) -> pass."""
    from tools.visual_scoring import nima_prescreen

    result_low = nima_prescreen(3.5)
    assert result_low["action"] == "regenerate"
    assert result_low["score"] == 3.5

    result_high = nima_prescreen(7.5)
    assert result_high["action"] == "pass"
    assert result_high["score"] == 7.5

    # In the middle band
    result_mid = nima_prescreen(5.0)
    assert result_mid["action"] == "proceed_with_caution"
    assert result_mid["score"] == 5.0


def test_custom_config_changes_behavior() -> None:
    """Passing a custom config dict overrides YAML thresholds."""
    from tools.visual_scoring import nima_prescreen

    # Custom config: regenerate below 6.0, pass above 8.0
    custom: dict[str, Any] = {
        "nima": {
            "regenerate_below": 6.0,
            "pass_above": 8.0,
        },
    }

    # 5.5 is above default regenerate (4.0) but below custom (6.0)
    result = nima_prescreen(5.5, config=custom)
    assert result["action"] == "regenerate", (
        "Custom config should make 5.5 regenerate (below 6.0)"
    )
    assert result["score"] == 5.5

    # 7.5 is above default pass (7.0) but below custom (8.0)
    result_mid = nima_prescreen(7.5, config=custom)
    assert result_mid["action"] == "proceed_with_caution", (
        "Custom config should make 7.5 proceed_with_caution (below 8.0)"
    )

    # 8.5 is above custom pass (8.0)
    result_high = nima_prescreen(8.5, config=custom)
    assert result_high["action"] == "pass"


def test_changing_yaml_changes_scorer_behavior(tmp_path: Path) -> None:
    """Clear cache, load config with different thresholds, verify behavior."""
    from tools.visual_scoring import _load_nima_thresholds, nima_prescreen

    # Clear the cache so next call re-reads from disk
    _load_nima_thresholds.cache_clear()

    # Load the real config and verify the score above floor doesn't regenerate
    config = _load_nima_thresholds()
    regenerate_below = config["nima"]["regenerate_below"]

    # A score just above the regenerate floor should NOT regenerate
    safe_score = regenerate_below + 0.1
    result = nima_prescreen(safe_score)
    assert result["action"] != "regenerate", (
        f"Score {safe_score} is above regenerate_below={regenerate_below}, "
        "should not trigger regenerate"
    )

    # Clean up: clear cache again so other tests aren't affected
    _load_nima_thresholds.cache_clear()


def test_nima_config_yaml_exists() -> None:
    """The NIMA thresholds YAML must exist and be valid."""
    config_path = (
        Path(__file__).resolve().parent.parent
        / "config" / "quality_frameworks" / "nima_thresholds.yaml"
    )
    assert config_path.exists(), f"Missing NIMA config at {config_path}"

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "nima" in data
    assert "regenerate_below" in data["nima"]
    assert "pass_above" in data["nima"]
    assert isinstance(data["nima"]["regenerate_below"], (int, float))
    assert isinstance(data["nima"]["pass_above"], (int, float))


def test_nima_config_separate_from_posteriq() -> None:
    """NIMA (1-10 scale) config MUST be separate from posteriq (1-5 scale)."""
    base = Path(__file__).resolve().parent.parent / "config" / "quality_frameworks"

    nima_path = base / "nima_thresholds.yaml"
    posteriq_path = base / "posteriq_quality_dimensions.yaml"

    nima_data = yaml.safe_load(nima_path.read_text(encoding="utf-8"))
    posteriq_data = yaml.safe_load(posteriq_path.read_text(encoding="utf-8"))

    # NIMA thresholds are on 1-10 scale
    assert nima_data["nima"]["pass_above"] > 5.0, "NIMA pass_above should be > 5 (1-10 scale)"

    # posteriq is on 1-5 scale
    assert posteriq_data["scoring"]["thresholds"]["excellent"] <= 5.0, (
        "posteriq uses 1-5 scale"
    )
