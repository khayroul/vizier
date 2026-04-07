"""Quality posture handler (§4.1).

Reads quality posture from config/phase.yaml and returns a read-only
PostureConfig that controls:
  - Which quality techniques are active
  - Contract strictness level (warn | reject)
  - Number of critique rounds

Quality posture is informational — it doesn't make decisions, it informs them.
Each client starts at canva_baseline and upgrades based on data thresholds:
  - canva_baseline → enhanced: 10+ exemplars per client AND per artifact type
  - enhanced → full: fine-tuned models >80% correlation AND golden dataset v1.0 locked
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "phase.yaml"


@dataclass(frozen=True)
class PostureConfig:
    """Read-only quality posture configuration.

    Attributes:
        name: Posture identifier (canva_baseline, enhanced, full).
        techniques: Active quality techniques for this posture.
        contract_strictness: 'warn' or 'reject' for missing contract fields.
        critique_rounds: Number of critique passes (1-3).
    """

    name: str
    techniques: list[str]
    contract_strictness: str
    critique_rounds: int


def _load_config(config_path: Path) -> dict[str, Any]:
    """Read and parse phase.yaml."""
    with open(config_path) as fh:
        return yaml.safe_load(fh)  # type: ignore[no-any-return]


def get_quality_posture(
    posture_name: str,
    *,
    config_path: Path = _DEFAULT_CONFIG,
) -> PostureConfig:
    """Return the PostureConfig for the given posture name.

    Args:
        posture_name: One of 'canva_baseline', 'enhanced', 'full'.
        config_path: Override for testing. Defaults to config/phase.yaml.

    Returns:
        PostureConfig with techniques, strictness, and critique rounds.

    Raises:
        ValueError: If posture_name is not defined in config.
    """
    config = _load_config(config_path)
    postures: dict[str, Any] = config.get("quality_posture", {})

    if posture_name not in postures:
        available = ", ".join(sorted(postures.keys()))
        raise ValueError(
            f"Unknown quality posture '{posture_name}'. "
            f"Available: {available}"
        )

    posture_cfg = postures[posture_name]

    return PostureConfig(
        name=posture_name,
        techniques=list(posture_cfg.get("techniques", [])),
        contract_strictness=str(posture_cfg.get("contract_strictness", "warn")),
        critique_rounds=int(posture_cfg.get("critique_rounds", 1)),
    )


def get_all_postures(
    *,
    config_path: Path = _DEFAULT_CONFIG,
) -> dict[str, PostureConfig]:
    """Return all configured quality postures as a dict.

    Useful for dashboard display and configuration validation.
    """
    config = _load_config(config_path)
    postures: dict[str, Any] = config.get("quality_posture", {})

    return {
        name: PostureConfig(
            name=name,
            techniques=list(cfg.get("techniques", [])),
            contract_strictness=str(cfg.get("contract_strictness", "warn")),
            critique_rounds=int(cfg.get("critique_rounds", 1)),
        )
        for name, cfg in postures.items()
    }
