"""Seed the exemplars table with synthetic development data.

Creates the full FK chain (client → job → spec → asset → artifact → exemplar)
and corresponding feedback rows. Three feedback rows are marked anchor_set=true
for drift detection (§15.10).

Idempotent: checks for existing seed data before inserting.

Usage:
    DATABASE_URL=postgres://... python scripts/seed_exemplars.py
"""

from __future__ import annotations

import json
import logging
import random
import sys
import uuid

from utils.database import get_cursor

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SEED_TAG = "vizier-seed-v1"

# 8 exemplar definitions — 5 posters, 3 brochures
EXEMPLARS: list[dict[str, str | list[str]]] = [
    {
        "family": "poster",
        "type": "promotional",
        "quality": "excellent",
        "summary": "Raya 2025 festive poster — warm gold palette, traditional motifs",
        "tags": ["festive", "raya", "traditional", "gold"],
        "mime": "image/png",
        "filename": "raya_2025_poster_01.png",
    },
    {
        "family": "poster",
        "type": "promotional",
        "quality": "excellent",
        "summary": "Corporate anniversary poster — green/gold brand colours, formal layout",
        "tags": ["corporate", "anniversary", "formal"],
        "mime": "image/png",
        "filename": "anniversary_poster_01.png",
    },
    {
        "family": "poster",
        "type": "product",
        "quality": "good",
        "summary": "Product launch poster — bold typography, textile showcase",
        "tags": ["product", "launch", "textile", "bold"],
        "mime": "image/png",
        "filename": "product_launch_01.png",
    },
    {
        "family": "poster",
        "type": "event",
        "quality": "excellent",
        "summary": "Charity gala invite poster — elegant dark background, accent gold",
        "tags": ["event", "charity", "elegant", "dark"],
        "mime": "image/png",
        "filename": "charity_gala_01.png",
    },
    {
        "family": "poster",
        "type": "promotional",
        "quality": "good",
        "summary": "Merdeka Day promotional poster — patriotic palette, community theme",
        "tags": ["merdeka", "patriotic", "community"],
        "mime": "image/png",
        "filename": "merdeka_poster_01.png",
    },
    {
        "family": "brochure",
        "type": "corporate",
        "quality": "excellent",
        "summary": "Company profile tri-fold — premium paper feel, brand consistency",
        "tags": ["corporate", "profile", "trifold", "premium"],
        "mime": "application/pdf",
        "filename": "company_profile_brochure_01.pdf",
    },
    {
        "family": "brochure",
        "type": "product",
        "quality": "good",
        "summary": "Product catalogue brochure — clean grid layout, textile swatches",
        "tags": ["product", "catalogue", "grid", "textile"],
        "mime": "application/pdf",
        "filename": "product_catalogue_01.pdf",
    },
    {
        "family": "brochure",
        "type": "event",
        "quality": "excellent",
        "summary": "CSR programme brochure — warm community imagery, bilingual text",
        "tags": ["csr", "community", "bilingual", "warm"],
        "mime": "application/pdf",
        "filename": "csr_programme_01.pdf",
    },
]

# Indices of exemplars whose feedback rows get anchor_set=true (3 of 8)
ANCHOR_INDICES = {0, 1, 5}


def _make_synthetic_embedding(seed: int) -> str:
    """Generate a deterministic 512-dim unit vector as pgvector literal."""
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(512)]
    norm = sum(v * v for v in raw) ** 0.5
    normalised = [v / norm for v in raw]
    return "[" + ",".join(f"{v:.6f}" for v in normalised) + "]"


def seed() -> None:
    """Insert seed exemplars if not already present."""
    with get_cursor() as cur:
        # Idempotency check — look for our seed tag in any existing exemplar
        cur.execute(
            "SELECT count(*) AS n FROM exemplars WHERE %s = ANY(style_tags)",
            (SEED_TAG,),
        )
        existing = cur.fetchone()["n"]  # type: ignore[index]
        if existing > 0:
            logger.info("Seed data already present (%d rows). Skipping.", existing)
            return

        # Ensure DMB client exists
        cur.execute("SELECT id FROM clients WHERE name = 'Darul Makmur Berhad'")
        row = cur.fetchone()
        if row:
            client_id = row["id"]
            logger.info("Using existing DMB client: %s", client_id)
        else:
            client_id = uuid.uuid4()
            cur.execute(
                """INSERT INTO clients (id, name, industry, brand_config, brand_mood, status)
                   VALUES (%s, %s, %s, %s, %s, 'active')""",
                (
                    str(client_id),
                    "Darul Makmur Berhad",
                    "textile",
                    json.dumps({
                        "primary_color": "#1B4332",
                        "secondary_color": "#2D6A4F",
                        "accent_color": "#D4A843",
                    }),
                    ["warm", "traditional"],
                ),
            )
            logger.info("Created DMB client: %s", client_id)

        for idx, ex in enumerate(EXEMPLARS):
            job_id = uuid.uuid4()
            spec_id = uuid.uuid4()
            asset_id = uuid.uuid4()
            artifact_id = uuid.uuid4()
            exemplar_id = uuid.uuid4()
            feedback_id = uuid.uuid4()
            is_anchor = idx in ANCHOR_INDICES

            storage_path = f"exemplars/dmb/{ex['filename']}"
            embedding = _make_synthetic_embedding(seed=1000 + idx)

            # Job
            cur.execute(
                """INSERT INTO jobs (id, client_id, raw_input, job_type, status)
                   VALUES (%s, %s, %s, %s, 'completed')""",
                (str(job_id), str(client_id), f"Seed exemplar: {ex['summary']}", ex["family"]),
            )

            # Artifact spec
            cur.execute(
                """INSERT INTO artifact_specs (id, job_id, spec_data, status, is_provisional)
                   VALUES (%s, %s, %s, 'promoted', false)""",
                (
                    str(spec_id),
                    str(job_id),
                    json.dumps({
                        "artifact_type": ex["type"],
                        "artifact_family": ex["family"],
                        "summary": ex["summary"],
                    }),
                ),
            )

            # Asset with synthetic CLIP embedding
            cur.execute(
                """INSERT INTO assets
                   (id, storage_path, filename, mime_type, asset_class, tags,
                    visual_embedding, quality_tier, client_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s, %s)""",
                (
                    str(asset_id),
                    storage_path,
                    ex["filename"],
                    ex["mime"],
                    ex["family"],
                    list(ex["tags"]),
                    embedding,
                    ex["quality"],
                    str(client_id),
                ),
            )

            # Artifact
            cur.execute(
                """INSERT INTO artifacts
                   (id, job_id, spec_id, artifact_type, role, asset_id, status)
                   VALUES (%s, %s, %s, %s, 'final', %s, 'delivered')""",
                (str(artifact_id), str(job_id), str(spec_id), ex["type"], str(asset_id)),
            )

            # Exemplar — include seed tag for idempotency
            tags_with_seed = list(ex["tags"]) + [SEED_TAG]
            cur.execute(
                """INSERT INTO exemplars
                   (id, artifact_id, client_id, artifact_family, artifact_type,
                    approval_quality, style_tags, summary, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')""",
                (
                    str(exemplar_id),
                    str(artifact_id),
                    str(client_id),
                    ex["family"],
                    ex["type"],
                    ex["quality"],
                    tags_with_seed,
                    ex["summary"],
                ),
            )

            # Feedback — explicitly_approved, with anchor_set for designated rows
            cur.execute(
                """INSERT INTO feedback
                   (id, job_id, artifact_id, client_id, feedback_status,
                    anchor_set, operator_rating)
                   VALUES (%s, %s, %s, %s, 'explicitly_approved', %s, %s)""",
                (
                    str(feedback_id),
                    str(job_id),
                    str(artifact_id),
                    str(client_id),
                    is_anchor,
                    5 if ex["quality"] == "excellent" else 4,
                ),
            )

            marker = " [ANCHOR]" if is_anchor else ""
            logger.info(
                "  [%d/%d] %s/%s — %s%s",
                idx + 1,
                len(EXEMPLARS),
                ex["family"],
                ex["type"],
                ex["filename"],
                marker,
            )

        logger.info(
            "Seeded %d exemplars (%d anchor set) for DMB.",
            len(EXEMPLARS),
            len(ANCHOR_INDICES),
        )


if __name__ == "__main__":
    try:
        seed()
    except Exception as exc:
        logger.error("Seeding failed: %s", exc)
        sys.exit(1)
