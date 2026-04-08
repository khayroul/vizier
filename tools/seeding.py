"""S12 — Client seeding pipeline for Vizier.

Seeds knowledge cards FRESH from:
  - S1 brand pattern configs (``config/brand_patterns/*.yaml``).
  - S1 copy pattern configs (``config/copy_patterns/*.yaml``).
  - Client YAML configs (``config/clients/*.yaml``).

Zero data from pro-max. All cards seeded fresh.
Each ingested item → contextualise_card() → embed → knowledge_cards table.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from utils.database import get_cursor
from utils.retrieval import contextualise_card

logger = logging.getLogger(__name__)

CONFIG_ROOT = Path(__file__).resolve().parent.parent / "config"
BRAND_PATTERNS_DIR = CONFIG_ROOT / "brand_patterns"
COPY_PATTERNS_DIR = CONFIG_ROOT / "copy_patterns"
CLIENTS_DIR = CONFIG_ROOT / "clients"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def seed_client(client_id: str) -> dict[str, Any]:
    """Seed all knowledge cards for a single client.

    Ingests from brand patterns, copy patterns, and client config.
    Returns summary of cards created.
    """
    cards: list[dict[str, Any]] = []

    # 1. Client config → business facts cards
    cards.extend(_seed_from_client_config(client_id))

    # 2. Brand patterns matching this client
    cards.extend(_seed_from_brand_patterns(client_id))

    # 3. Copy patterns matching this client
    cards.extend(_seed_from_copy_patterns(client_id))

    logger.info("Seeded %d cards for client %s", len(cards), client_id)
    return {
        "client_id": client_id,
        "cards_created": len(cards),
        "cards": cards,
    }


def seed_all_clients() -> dict[str, Any]:
    """Seed knowledge cards for all clients with config files.

    Skips ``_schema.yaml`` and other non-client files.
    """
    results: dict[str, Any] = {}
    for yaml_path in sorted(CLIENTS_DIR.glob("*.yaml")):
        if yaml_path.name.startswith("_"):
            continue
        client_id = yaml_path.stem
        results[client_id] = seed_client(client_id)

    total = sum(r["cards_created"] for r in results.values())
    logger.info("Seeded %d total cards across %d clients", total, len(results))
    return results


# ---------------------------------------------------------------------------
# Client config seeding
# ---------------------------------------------------------------------------


def _seed_from_client_config(client_id: str) -> list[dict[str, Any]]:
    """Create knowledge cards from client YAML config."""
    config_path = CLIENTS_DIR / f"{client_id}.yaml"
    if not config_path.exists():
        logger.warning("No client config for %s", client_id)
        return []

    with config_path.open() as fh:
        config = yaml.safe_load(fh)

    if not config:
        return []

    cards: list[dict[str, Any]] = []
    client_name = config.get("client_name", client_id)
    source_info = {
        "source_type": "client_config",
        "client_name": client_name,
        "title": f"{client_name} client configuration",
        "domain": config.get("defaults", {}).get("industry", "general"),
    }

    # Card: brand identity
    brand = config.get("brand", {})
    if brand:
        brand_content = (
            f"Brand identity for {client_name}: "
            f"Primary colour {brand.get('primary_color', 'N/A')}, "
            f"secondary {brand.get('secondary_color', 'N/A')}, "
            f"accent {brand.get('accent_color', 'N/A')}. "
            f"Headline font: {brand.get('headline_font', 'N/A')}, "
            f"body font: {brand.get('body_font', 'N/A')}."
        )
        card = {
            "card_type": "client",
            "title": f"{client_name} brand identity",
            "content": brand_content,
            "domain": "brand",
            "tags": ["brand", "identity", "colours", "typography"],
        }
        prefix = contextualise_card(card, source_info)
        cards.append(
            _store_card(card, prefix, client_id, "client_config", source_info["title"])
        )

    # Card: production defaults
    defaults = config.get("defaults", {})
    if defaults:
        defaults_content = (
            f"Production defaults for {client_name}: "
            f"template={defaults.get('template_name', 'N/A')}, "
            f"image_mode={defaults.get('image_mode', 'N/A')}, "
            f"style_hint={defaults.get('style_hint', 'N/A')}, "
            f"language={defaults.get('language', 'N/A')}, "
            f"tone={defaults.get('tone', 'N/A')}, "
            f"copy_register={defaults.get('copy_register', 'N/A')}."
        )
        card = {
            "card_type": "client",
            "title": f"{client_name} production defaults",
            "content": defaults_content,
            "domain": "production",
            "tags": ["defaults", "production", "style"],
        }
        prefix = contextualise_card(card, source_info)
        cards.append(
            _store_card(card, prefix, client_id, "client_config", source_info["title"])
        )

    return cards


# ---------------------------------------------------------------------------
# Brand pattern seeding
# ---------------------------------------------------------------------------


def _seed_from_brand_patterns(client_id: str) -> list[dict[str, Any]]:
    """Create knowledge cards from brand pattern YAML files."""
    cards: list[dict[str, Any]] = []

    for yaml_path in sorted(BRAND_PATTERNS_DIR.glob("*.yaml")):
        with yaml_path.open() as fh:
            data = yaml.safe_load(fh)
        if not data:
            continue

        patterns = data.get("patterns", [data]) if isinstance(data, dict) else [data]
        for pattern in patterns:
            # Check if pattern applies to this client
            applies_to = pattern.get("applies_to", [])
            if applies_to and client_id not in applies_to:
                continue

            source_info = {
                "source_type": "brand_pattern",
                "client_name": client_id,
                "title": f"Brand pattern: {yaml_path.stem}",
                "domain": pattern.get("domain", "brand"),
            }
            content = pattern.get("content", "") or pattern.get("description", "")
            if not content:
                content = yaml.dump(pattern, default_flow_style=False)

            card = {
                "card_type": "brand_pattern",
                "title": pattern.get("name", yaml_path.stem),
                "content": content,
                "domain": pattern.get("domain", "brand"),
                "tags": pattern.get("tags", ["brand_pattern"]),
            }
            prefix = contextualise_card(card, source_info)
            cards.append(_store_card(
                card, prefix, client_id,
                "brand_pattern", source_info["title"],
            ))

    return cards


# ---------------------------------------------------------------------------
# Copy pattern seeding
# ---------------------------------------------------------------------------


def _seed_from_copy_patterns(client_id: str) -> list[dict[str, Any]]:
    """Create knowledge cards from copy pattern YAML files."""
    cards: list[dict[str, Any]] = []

    for yaml_path in sorted(COPY_PATTERNS_DIR.glob("*.yaml")):
        with yaml_path.open() as fh:
            data = yaml.safe_load(fh)
        if not data:
            continue

        patterns = data.get("patterns", [data]) if isinstance(data, dict) else [data]
        for pattern in patterns:
            applies_to = pattern.get("applies_to", [])
            if applies_to and client_id not in applies_to:
                continue

            source_info = {
                "source_type": "copy_pattern",
                "client_name": client_id,
                "title": f"Copy pattern: {yaml_path.stem}",
                "domain": pattern.get("domain", "copywriting"),
            }
            content = pattern.get("content", "") or pattern.get("description", "")
            if not content:
                content = yaml.dump(pattern, default_flow_style=False)

            card = {
                "card_type": "copy_pattern",
                "title": pattern.get("name", yaml_path.stem),
                "content": content,
                "domain": pattern.get("domain", "copywriting"),
                "tags": pattern.get("tags", ["copy_pattern"]),
            }
            prefix = contextualise_card(card, source_info)
            cards.append(_store_card(
                card, prefix, client_id,
                "copy_pattern", source_info["title"],
            ))

    return cards


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store_card(
    card_data: dict[str, Any],
    prefix: str,
    client_id: str,
    source_type: str,
    source_title: str,
) -> dict[str, Any]:
    """Store a contextualised knowledge card. Delegates to ingest_card."""
    from tools.knowledge import ingest_card

    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_sources
                (client_id, source_type, title, domain, status)
            VALUES (
                (SELECT id FROM clients WHERE id::text = %s OR name = %s LIMIT 1),
                %s, %s, %s, 'active')
            RETURNING id
            """,
            (
                client_id, client_id, source_type,
                source_title,
                card_data.get("domain", "general"),
            ),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

    tags = card_data.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    card_id = ingest_card(
        source_id=source_id,
        content=card_data["content"],
        card_type=card_data.get("card_type", "general"),
        title=card_data.get("title", ""),
        tags=tags,
        domain=card_data.get("domain", "general"),
        client_id=client_id,
        prefix=prefix,  # caller already contextualised — skip re-contextualisation
    )

    return {
        "card_id": card_id,
        "source_id": source_id,
        "card_type": card_data.get("card_type", "general"),
        "title": card_data.get("title", ""),
        "prefix": prefix,
        "client_id": client_id,
    }
