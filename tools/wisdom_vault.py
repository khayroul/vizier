"""Wisdom Vault — Obsidian markdown import to knowledge cards.

Reads markdown files, splits by headings into cards, contextualises
each card via S12's contextualise_card, and stores with embeddings.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from tools.knowledge import ingest_card
from utils.database import get_cursor

logger = logging.getLogger(__name__)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown. Returns (metadata, body)."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            return meta, body
    return {}, text


def _chunk_by_headings(body: str) -> list[str]:
    """Split markdown body by ## headings.

    Each chunk includes the heading and content up to the next heading.
    ### sub-headings are kept within their parent ## section.
    Falls back to ~100-word paragraph splits if no headings found.
    """
    # Split on ## (but not ### within sections)
    sections = re.split(r"(?=^## )", body, flags=re.MULTILINE)
    chunks = [s.strip() for s in sections if s.strip()]

    if len(chunks) <= 1 and len(body.split()) > 150:
        # Fallback: split into ~100-word paragraph chunks
        paragraphs = body.split("\n\n")
        chunks = []
        current: list[str] = []
        word_count = 0
        for para in paragraphs:
            words = len(para.split())
            if word_count + words > 150 and current:
                chunks.append("\n\n".join(current))
                current = [para]
                word_count = words
            else:
                current.append(para)
                word_count += words
        if current:
            chunks.append("\n\n".join(current))

    return chunks


def import_book(
    vault_path: str,
    title: str,
    domain: str | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    """Import an Obsidian markdown file as knowledge cards.

    Splits by ## headings, contextualises each chunk, embeds, and stores.

    Returns: {"source_id": str, "card_count": int, "title": str}
    """
    path = Path(vault_path)
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)

    resolved_domain = domain or meta.get("domain", "general")
    resolved_title = title or meta.get("title", path.stem)

    # Create knowledge_source for the book
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_sources
                (client_id, source_type, title, domain, status)
            VALUES (%s, 'book', %s, %s, 'active')
            RETURNING id
            """,
            (client_id, resolved_title, resolved_domain),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

    # Chunk and ingest
    chunks = _chunk_by_headings(body)
    card_count = 0

    for idx, chunk in enumerate(chunks):
        if not chunk.strip():
            continue

        # Extract heading as card title if present
        lines = chunk.strip().split("\n")
        if lines[0].startswith("#"):
            card_title = lines[0].lstrip("#").strip()
            card_content = "\n".join(lines[1:]).strip()
        else:
            card_title = f"{resolved_title} — Part {idx + 1}"
            card_content = chunk

        if len(card_content.split()) < 10:
            continue  # Skip very short chunks

        ingest_card(
            source_id=source_id,
            content=card_content,
            card_type="book",
            title=card_title,
            tags=meta.get("tags", []),
            domain=resolved_domain,
            client_id=client_id,
        )
        card_count += 1

    logger.info("Imported book '%s': %d cards from %s", resolved_title, card_count, path.name)
    return {"source_id": source_id, "card_count": card_count, "title": resolved_title}


def import_vault_directory(
    vault_dir: str,
    domain_map: dict[str, str] | None = None,
    client_id: str | None = None,
) -> list[dict[str, Any]]:
    """Batch import markdown files from an Obsidian vault directory.

    Args:
        vault_dir: Path to directory containing .md files.
        domain_map: Optional {filename_pattern: domain} for auto-tagging.
        client_id: Optional client to associate cards with.

    Returns list of import results from import_book().
    """
    vault_path = Path(vault_dir)
    results: list[dict[str, Any]] = []

    for md_file in sorted(vault_path.glob("*.md")):
        domain = None
        if domain_map:
            for pattern, dom in domain_map.items():
                if pattern in md_file.name:
                    domain = dom
                    break

        result = import_book(
            vault_path=str(md_file),
            title=md_file.stem.replace("_", " ").title(),
            domain=domain,
            client_id=client_id,
        )
        results.append(result)

    logger.info("Vault import: %d files processed from %s", len(results), vault_dir)
    return results
