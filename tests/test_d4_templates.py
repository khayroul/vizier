"""Tests for D4 CGL layout clustering → HTML poster template archetypes.

TDD tests for scripts/cluster_d4_templates.py (Task 8) and
industry_fit tagging from D5 (Task 9).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates" / "html"
D4_DIR = REPO_ROOT / "datasets" / "D4_CGL_Dataset_v2" / "data"
D5_DIR = REPO_ROOT / "datasets" / "D5_Magazine_Layout" / "data"

# Existing (hand-crafted) templates — must never be overwritten
EXISTING_TEMPLATES = {
    p.stem.replace("_meta", "")
    for p in TEMPLATE_DIR.glob("*_meta.yaml")
    if not p.stem.startswith("poster_d4_")
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _d4_templates() -> list[Path]:
    """Return all poster_d4_* HTML files in the template directory."""
    return sorted(TEMPLATE_DIR.glob("poster_d4_*.html"))


def _d4_metas() -> dict[str, dict[str, Any]]:
    """Return {template_name: meta_dict} for all poster_d4_* metas."""
    result: dict[str, dict[str, Any]] = {}
    for meta_path in sorted(TEMPLATE_DIR.glob("poster_d4_*_meta.yaml")):
        name = meta_path.stem.replace("_meta", "")
        with meta_path.open() as fh:
            result[name] = yaml.safe_load(fh)
    return result


# ---------------------------------------------------------------------------
# Dataset availability guard
# ---------------------------------------------------------------------------

_has_d4 = D4_DIR.is_dir() and any(D4_DIR.glob("*.parquet"))
_has_d5 = D5_DIR.is_dir() and any(D5_DIR.glob("*.parquet"))

skip_no_d4 = pytest.mark.skipif(not _has_d4, reason="D4 dataset not available")
skip_no_d5 = pytest.mark.skipif(not _has_d5, reason="D5 dataset not available")


# ===========================================================================
# Task 8 — cluster_d4_templates.py
# ===========================================================================


class TestD4TemplateClustering:
    """Clustering D4 layouts produces >= 20 new HTML template archetypes."""

    def test_template_from_d4_cluster_count(self) -> None:
        """At least 20 new template HTML files generated from D4 clusters."""
        generated = _d4_templates()
        assert len(generated) >= 20, (
            f"Expected >= 20 D4-derived templates, found {len(generated)}"
        )

    def test_template_meta_yaml_valid(self) -> None:
        """Every new template has a valid _meta.yaml companion."""
        html_files = _d4_templates()
        assert len(html_files) > 0, "No D4-derived templates found"

        for html_path in html_files:
            name = html_path.stem
            meta_path = TEMPLATE_DIR / f"{name}_meta.yaml"
            assert meta_path.exists(), f"Missing meta for {name}"

            with meta_path.open() as fh:
                meta = yaml.safe_load(fh)

            assert isinstance(meta, dict), f"Meta for {name} is not a dict"

            # Required fields per existing schema
            for field in (
                "density",
                "tone_fit",
                "occasion_fit",
                "cta_prominence",
                "supported_slots",
            ):
                assert field in meta, f"Meta for {name} missing '{field}'"

            # Type checks
            assert meta["density"] in (
                "minimal",
                "moderate",
                "dense",
            ), f"Invalid density for {name}: {meta['density']}"
            assert isinstance(
                meta["tone_fit"], list
            ), f"tone_fit for {name} must be list"
            assert isinstance(
                meta["occasion_fit"], list
            ), f"occasion_fit for {name} must be list"
            assert meta["cta_prominence"] in (
                "none",
                "low",
                "medium",
                "high",
            ), f"Invalid cta_prominence for {name}: {meta['cta_prominence']}"
            assert isinstance(
                meta["supported_slots"], list
            ), f"supported_slots for {name} must be list"
            assert len(meta["supported_slots"]) >= 1, (
                f"supported_slots for {name} must have at least one slot"
            )

    def test_no_existing_templates_overwritten(self) -> None:
        """D4-derived templates must not overwrite hand-crafted ones."""
        d4_names = {p.stem for p in _d4_templates()}
        overlap = d4_names & EXISTING_TEMPLATES
        assert not overlap, f"D4 templates overwrite existing: {overlap}"

    def test_templates_are_valid_html(self) -> None:
        """Each D4 template is syntactically valid HTML with a <body>."""
        for html_path in _d4_templates():
            content = html_path.read_text()
            assert "<!DOCTYPE html>" in content, (
                f"{html_path.name} missing DOCTYPE"
            )
            assert "<body>" in content, f"{html_path.name} missing <body>"
            assert "</body>" in content, f"{html_path.name} missing </body>"
            assert "</html>" in content, f"{html_path.name} missing </html>"

    def test_templates_have_css_grid(self) -> None:
        """Each D4 template uses CSS grid for layout (not JS)."""
        for html_path in _d4_templates():
            content = html_path.read_text()
            assert "grid" in content.lower(), (
                f"{html_path.name} should use CSS grid"
            )
            assert "<script>" not in content, (
                f"{html_path.name} must not contain JavaScript"
            )

    def test_templates_have_zone_divs(self) -> None:
        """Each D4 template has at least 2 positioned zone divs."""
        for html_path in _d4_templates():
            content = html_path.read_text()
            zone_count = content.count('class="zone-')
            assert zone_count >= 2, (
                f"{html_path.name} has only {zone_count} zone divs, need >= 2"
            )

    def test_templates_use_jinja_placeholders(self) -> None:
        """D4 templates use Jinja2 {{ placeholder }} for content slots."""
        for html_path in _d4_templates():
            content = html_path.read_text()
            assert "{{" in content and "}}" in content, (
                f"{html_path.name} must use Jinja2 placeholders"
            )

    def test_unique_archetype_names(self) -> None:
        """All D4-derived templates have unique, descriptive names."""
        names = [p.stem for p in _d4_templates()]
        assert len(names) == len(set(names)), "Duplicate template names found"
        for name in names:
            assert name.startswith("poster_d4_"), (
                f"Template {name} must start with poster_d4_"
            )
            # At least 3 chars after prefix
            suffix = name.replace("poster_d4_", "")
            assert len(suffix) >= 3, (
                f"Template name suffix too short: {suffix}"
            )

    def test_supported_slots_are_standard(self) -> None:
        """Supported slots must be from the known set."""
        valid_slots = {
            "hero_image",
            "headline",
            "subheadline",
            "body_text",
            "cta",
            "logo",
            "price",
            "tagline",
            "badge",
            "kicker",
            "offer_block",
            "event_meta",
            "footer",
            "disclaimer",
        }
        for name, meta in _d4_metas().items():
            slots = set(meta["supported_slots"])
            invalid = slots - valid_slots
            assert not invalid, (
                f"{name} has invalid slots: {invalid}"
            )


# ===========================================================================
# Task 9 — industry_fit tagging
# ===========================================================================


class TestIndustryFitTagging:
    """D5-derived industry_fit tags on D4-generated and existing templates."""

    def test_d4_templates_have_industry_fit(self) -> None:
        """Every D4-derived template meta has an industry_fit field."""
        metas = _d4_metas()
        assert len(metas) > 0, "No D4-derived template metas found"

        for name, meta in metas.items():
            assert "industry_fit" in meta, (
                f"{name} missing industry_fit field"
            )
            assert isinstance(meta["industry_fit"], list), (
                f"{name} industry_fit must be list"
            )
            assert len(meta["industry_fit"]) >= 1, (
                f"{name} industry_fit must have at least one entry"
            )

    def test_industry_fit_values_are_valid(self) -> None:
        """industry_fit values must come from the 6 canonical industries."""
        valid_industries = {"food", "fashion", "education", "tech", "retail", "general"}
        metas = _d4_metas()
        for name, meta in metas.items():
            if "industry_fit" not in meta:
                continue
            industries = set(meta["industry_fit"])
            invalid = industries - valid_industries
            assert not invalid, (
                f"{name} has invalid industry_fit values: {invalid}"
            )

    def test_existing_templates_tagged(self) -> None:
        """All 10 existing (hand-crafted) templates now have industry_fit."""
        for template_name in EXISTING_TEMPLATES:
            meta_path = TEMPLATE_DIR / f"{template_name}_meta.yaml"
            if not meta_path.exists():
                continue
            with meta_path.open() as fh:
                meta = yaml.safe_load(fh)
            assert "industry_fit" in meta, (
                f"Existing template {template_name} missing industry_fit"
            )
            assert isinstance(meta["industry_fit"], list)
            assert len(meta["industry_fit"]) >= 1

    def test_industry_distribution_not_all_general(self) -> None:
        """At least 50% of D4 templates have a non-general industry tag."""
        metas = _d4_metas()
        non_general = 0
        for meta in metas.values():
            industries = set(meta.get("industry_fit", []))
            if industries - {"general"}:
                non_general += 1
        ratio = non_general / len(metas) if metas else 0
        assert ratio >= 0.5, (
            f"Only {ratio:.0%} of templates have non-general industry_fit"
        )


# ===========================================================================
# Module-level import smoke test
# ===========================================================================


class TestClusterModuleImport:
    """The clustering script is importable as a module."""

    def test_import_cluster_module(self) -> None:
        """scripts.cluster_d4_templates can be imported."""
        from scripts.cluster_d4_templates import (
            cluster_layouts,
            extract_layout_features,
            generate_template_html,
        )
        assert callable(extract_layout_features)
        assert callable(cluster_layouts)
        assert callable(generate_template_html)
