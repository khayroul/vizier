"""Prompt template versioning: promote, archive, revert.

Built by S19. Every template in config/prompt_templates/ and
config/critique_templates/ has version tracking. On /promote the old version
is archived and the new version takes its place. On /revert the most recent
archive is restored. All changes logged to system_state table.

Anti-drift #53: versions are archived, never deleted.
Anti-drift #52: validate before promote (caller responsibility).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.database import get_cursor

logger = logging.getLogger(__name__)

_ARCHIVE_DIR = Path("config/prompt_templates/archive")


def get_template_version(template_path: str) -> dict[str, Any]:
    """Read a template file and extract its version metadata.

    Looks for a YAML-like front-matter block with ``version:`` and
    ``validation_score:`` fields, or defaults to version 1.
    """
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    content = path.read_text(encoding="utf-8")
    version = 1
    validation_score: float | None = None
    last_promoted_at: str | None = None

    version_match = re.search(r"^version:\s*(\d+)", content, re.MULTILINE)
    if version_match:
        version = int(version_match.group(1))

    score_match = re.search(r"^validation_score:\s*([\d.]+)", content, re.MULTILINE)
    if score_match:
        validation_score = float(score_match.group(1))

    promoted_match = re.search(r"^last_promoted_at:\s*(.+)", content, re.MULTILINE)
    if promoted_match:
        last_promoted_at = promoted_match.group(1).strip()

    return {
        "path": str(path),
        "version": version,
        "validation_score": validation_score,
        "last_promoted_at": last_promoted_at,
    }


def promote_template(
    template_path: str,
    new_content: str,
    decision_note: str,
) -> dict[str, Any]:
    """Promote a new template version: archive current, write new, log decision.

    Returns {path, old_version, new_version, archived_to}.
    """
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    current = path.read_text(encoding="utf-8")
    info = get_template_version(template_path)
    old_version = info["version"]
    new_version = old_version + 1

    # Archive current version (anti-drift #53: never deleted)
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    archive_path = _ARCHIVE_DIR / f"{stem}_v{old_version}.md"
    archive_path.write_text(current, encoding="utf-8")

    # Inject version header into new content
    now_str = datetime.now(timezone.utc).isoformat()
    header = (
        f"version: {new_version}\n"
        f"validation_score: 0.0\n"
        f"last_promoted_at: {now_str}\n"
    )

    # Replace existing header or prepend
    if re.search(r"^version:\s*\d+", new_content, re.MULTILINE):
        new_content = re.sub(
            r"^version:\s*\d+",
            f"version: {new_version}",
            new_content,
            count=1,
            flags=re.MULTILINE,
        )
        new_content = re.sub(
            r"^last_promoted_at:\s*.+",
            f"last_promoted_at: {now_str}",
            new_content,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        new_content = header + "\n" + new_content

    path.write_text(new_content, encoding="utf-8")

    # Log to system_state table
    _log_system_state(
        version=new_version,
        change_type="template_promotion",
        description=(
            f"Promoted {path.name} "
            f"v{old_version}\u2192v{new_version}: "
            f"{decision_note}"
        ),
        changed_by="operator",
        previous_state={
            "version": old_version,
            "content_hash": hash(current),
        },
    )

    # Log decision to docs/decisions/
    _log_decision(path.name, old_version, new_version, decision_note)

    logger.info("Promoted %s v%d → v%d", path.name, old_version, new_version)
    return {
        "path": str(path),
        "old_version": old_version,
        "new_version": new_version,
        "archived_to": str(archive_path),
    }


def revert_template(template_path: str) -> dict[str, Any]:
    """Restore the most recent archived version of a template.

    Returns {path, reverted_from, reverted_to}.
    """
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    info = get_template_version(template_path)
    current_version = info["version"]

    # Find the most recent archive
    stem = path.stem
    archives = sorted(
        _ARCHIVE_DIR.glob(f"{stem}_v*.md"),
        key=lambda p: _extract_version_number(p),
        reverse=True,
    )

    if not archives:
        raise FileNotFoundError(f"No archived versions found for {path.name}")

    latest_archive = archives[0]
    restored_version = _extract_version_number(latest_archive)
    restored_content = latest_archive.read_text(encoding="utf-8")

    path.write_text(restored_content, encoding="utf-8")

    _log_system_state(
        version=restored_version,
        change_type="template_revert",
        description=f"Reverted {path.name} v{current_version}→v{restored_version}",
        changed_by="operator",
        previous_state={"version": current_version},
    )

    logger.info("Reverted %s v%d → v%d", path.name, current_version, restored_version)
    return {
        "path": str(path),
        "reverted_from": current_version,
        "reverted_to": restored_version,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_version_number(path: Path) -> int:
    """Extract version number from archive filename like 'template_v3.md'."""
    match = re.search(r"_v(\d+)\.md$", path.name)
    return int(match.group(1)) if match else 0


def _log_system_state(
    version: int,
    change_type: str,
    description: str,
    changed_by: str,
    previous_state: dict[str, Any],
) -> None:
    """Insert a record into the system_state table."""
    import json

    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO system_state
                (version, change_type, change_description,
                 changed_by, previous_state)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                str(version), change_type, description,
                changed_by, json.dumps(previous_state),
            ),
        )


def _log_decision(
    template_name: str,
    old_version: int,
    new_version: int,
    decision_note: str,
) -> None:
    """Write a decision record to docs/decisions/."""
    decisions_dir = Path("docs/decisions")
    decisions_dir.mkdir(parents=True, exist_ok=True)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"promote_{template_name.replace('.md', '')}_{now_str}.md"
    content = (
        f"# Template Promotion: {template_name}\n\n"
        f"**Date:** {now_str}\n"
        f"**Version:** v{old_version} → v{new_version}\n"
        f"**Decision:** {decision_note}\n"
        f"**Rationale:** Operator-approved improvement based on production data.\n"
    )
    (decisions_dir / filename).write_text(content, encoding="utf-8")
