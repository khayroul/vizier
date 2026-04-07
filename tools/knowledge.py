"""Knowledge tools — card ingestion, exemplar promotion, outcome memory.

Hermes tool functions for the knowledge spine.
Imports contextualise_card from S12 (utils.retrieval) — do NOT rebuild.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from utils.database import get_cursor
from utils.embeddings import embed_text, format_embedding
from utils.retrieval import contextualise_card

logger = logging.getLogger(__name__)


def ingest_card(
    *,
    source_id: str,
    content: str,
    card_type: str,
    title: str,
    tags: list[str],
    domain: str,
    client_id: str | None = None,
    prefix: str | None = None,
) -> str:
    """Ingest a knowledge card with contextualised embedding.

    Canonical ingestion function — all card creation should go through here.

    1. Contextualise via GPT-5.4-mini (50-100 token prefix) — skipped if prefix provided
    2. Embed contextualised text via text-embedding-3-small
    3. Store card with embedding and context_prefix in knowledge_cards

    Args:
        source_id: UUID of the knowledge_sources record.
        content: Raw card content text.
        card_type: Card type (e.g. "marketing", "brand_pattern", "book").
        title: Card title.
        tags: List of tag strings.
        domain: Domain label (e.g. "marketing", "design").
        client_id: Optional client UUID.
        prefix: If provided, skip contextualise_card call (avoids double
            contextualisation when callers already have a prefix).

    Returns card_id (UUID string).
    """
    if prefix is None:
        card_dict: dict[str, str] = {
            "content": content,
            "card_type": card_type,
            "title": title,
            "domain": domain,
        }

        # Look up source info for contextualisation
        source_info: dict[str, str] = {
            "source_type": "knowledge",
            "title": title,
            "domain": domain,
        }
        with get_cursor() as cur:
            cur.execute(
                "SELECT source_type, title, domain FROM knowledge_sources WHERE id = %s",
                (source_id,),
            )
            row = cur.fetchone()
            if row:
                source_info = {
                    "source_type": row["source_type"] or "knowledge",
                    "title": row["title"] or title,
                    "domain": row["domain"] or domain,
                }

        prefix = contextualise_card(card_dict, source_info)

    # Step 2: Embed contextualised text
    contextualised_text = f"{prefix} {content}"
    embedding = format_embedding(embed_text(contextualised_text))

    # Step 3: Store
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_cards
                (source_id, client_id, card_type, title, content, tags,
                 domain, embedding, context_prefix, confidence, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0.8, 'active')
            RETURNING id
            """,
            (source_id, client_id, card_type, title, content, tags,
             domain, embedding, prefix),
        )
        card_row = cur.fetchone()
        assert card_row is not None

    card_id = str(card_row["id"])
    logger.info("Ingested card %s (type=%s, prefix=%d chars)", card_id, card_type, len(prefix))
    return card_id


def promote_exemplar(
    *,
    artifact_id: str,
    client_id: str,
    operator_rating: int,
    job_id: str,
) -> str | None:
    """Promote an artifact to the exemplar library.

    Only promotes if operator_rating == 5 (explicitly_approved).
    Checks anchor_set flag on feedback — anchor set records are excluded
    from exemplar libraries per anti-drift #56.

    Returns exemplar_id or None if not promoted.
    """
    if operator_rating != 5:
        return None

    # Check anchor_set on the most recent feedback for this artifact+job
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT anchor_set FROM feedback
            WHERE artifact_id = %s AND job_id = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (artifact_id, job_id),
        )
        fb_row = cur.fetchone()
        if fb_row and fb_row["anchor_set"]:
            logger.info("Skipping exemplar promotion — anchor_set feedback (anti-drift #56)")
            return None

    # Get artifact metadata (artifact_family derived from artifact_type —
    # the artifacts table does not have artifact_family, only exemplars does)
    with get_cursor() as cur:
        cur.execute(
            "SELECT artifact_type FROM artifacts WHERE id = %s",
            (artifact_id,),
        )
        art_row = cur.fetchone()
        if art_row is None:
            logger.warning("Artifact %s not found for exemplar promotion", artifact_id)
            return None

        artifact_type = art_row["artifact_type"]

        cur.execute(
            """
            INSERT INTO exemplars
                (artifact_id, client_id, artifact_family, artifact_type,
                 approval_quality, status)
            VALUES (%s, %s, %s, %s, 'operator_5', 'active')
            RETURNING id
            """,
            (artifact_id, client_id, artifact_type, artifact_type),
        )
        ex_row = cur.fetchone()
        assert ex_row is not None

    exemplar_id = str(ex_row["id"])
    logger.info("Promoted artifact %s to exemplar %s", artifact_id, exemplar_id)
    return exemplar_id


def record_outcome(
    *,
    job_id: str,
    outcome_data: dict[str, Any],
) -> str:
    """Record job outcome in outcome_memory table.

    Args:
        job_id: The completed job's UUID.
        outcome_data: Dict with keys matching outcome_memory columns:
            artifact_id, client_id, first_pass_approved, revision_count,
            accepted_as_on_brand, human_feedback_summary, cost_summary,
            quality_summary, promote_to_exemplar.

    Returns outcome_memory record id.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO outcome_memory
                (job_id, artifact_id, client_id, first_pass_approved,
                 revision_count, accepted_as_on_brand, human_feedback_summary,
                 cost_summary, quality_summary, promote_to_exemplar)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                job_id,
                outcome_data.get("artifact_id"),
                outcome_data.get("client_id"),
                outcome_data.get("first_pass_approved"),
                outcome_data.get("revision_count", 0),
                outcome_data.get("accepted_as_on_brand"),
                outcome_data.get("human_feedback_summary"),
                json.dumps(outcome_data.get("cost_summary")) if outcome_data.get("cost_summary") else None,
                json.dumps(outcome_data.get("quality_summary")) if outcome_data.get("quality_summary") else None,
                outcome_data.get("promote_to_exemplar", False),
            ),
        )
        row = cur.fetchone()
        assert row is not None

    outcome_id = str(row["id"])
    logger.info("Recorded outcome %s for job %s", outcome_id, job_id)
    return outcome_id
