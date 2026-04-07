"""S12 — Research tools for Vizier.

Provides:
  - ``fetch_trends``: pytrends wrapper for Malaysian market trends.
  - ``ingest_swipe``: Screenshot/image → visual DNA → knowledge card(s).
  - ``check_calendar_events``: Calendar cron — surfaces upcoming events.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pytrends.request import TrendReq  # type: ignore[import-untyped]

from tools.visual_dna import extract_visual_dna
from utils.call_llm import call_llm
from utils.database import get_cursor
from utils.retrieval import contextualise_card
from utils.spans import track_span
from utils.storage import upload_bytes

logger = logging.getLogger(__name__)

CALENDAR_PATH = Path(__file__).resolve().parent.parent / "config" / "calendar"

# ---------------------------------------------------------------------------
# 1. Trends (pytrends)
# ---------------------------------------------------------------------------

_TRENDS_PREFIX: list[dict[str, str]] = [
    {
        "role": "system",
        "content": (
            "You are a market research analyst for the Malaysian market. "
            "Summarise Google Trends data into 2-3 actionable insights for "
            "content creation. Be specific about numbers and timing."
        ),
    },
]


@track_span(step_type="research")
def fetch_trends(
    keywords: list[str],
    *,
    timeframe: str = "today 3-m",
    geo: str = "MY",
    job_id: str | None = None,
) -> dict[str, Any]:
    """Fetch Google Trends data for keywords in Malaysia.

    Args:
        keywords: Up to 5 search terms.
        timeframe: pytrends timeframe string.
        geo: Country code (default Malaysia).
        job_id: Optional job for tracing.

    Returns:
        Dict with ``interest_over_time`` (list of dicts per date),
        ``related_queries`` (dict per keyword), and ``summary`` (LLM insight).
    """
    pt = TrendReq(hl="ms", tz=480)  # Malaysia UTC+8
    pt.build_payload(keywords[:5], timeframe=timeframe, geo=geo)

    interest = pt.interest_over_time()
    interest_records: list[dict[str, Any]] = []
    if not interest.empty:
        interest = interest.reset_index()
        interest_records = interest.to_dict(orient="records")
        # Convert Timestamps to ISO strings for serialisation
        for rec in interest_records:
            for key, val in rec.items():
                if hasattr(val, "isoformat"):
                    rec[key] = val.isoformat()

    related: dict[str, Any] = {}
    for kw in keywords[:5]:
        try:
            related[kw] = pt.related_queries().get(kw, {})
        except Exception:  # noqa: BLE001 — pytrends can be flaky
            related[kw] = {}

    # Summarise with LLM
    summary_prompt = (
        f"Keywords: {keywords}\nGeo: {geo}\n"
        f"Interest data points: {len(interest_records)}\n"
        f"Top data: {interest_records[:5]}\n"
        f"Related queries: {related}"
    )
    llm_result = call_llm(
        stable_prefix=_TRENDS_PREFIX,
        variable_suffix=[{"role": "user", "content": summary_prompt}],
        model="gpt-5.4-mini",
        temperature=0.5,
        max_tokens=300,
        job_id=job_id,
        operation_type="extract",
    )

    return {
        "keywords": keywords,
        "geo": geo,
        "interest_over_time": interest_records,
        "related_queries": related,
        "summary": llm_result["content"],
    }


# ---------------------------------------------------------------------------
# 2. Swipe Ingest
# ---------------------------------------------------------------------------

_SWIPE_PREFIX: list[dict[str, str]] = [
    {
        "role": "system",
        "content": (
            "You are a design analyst. Given a description of a design's visual "
            "properties, extract: layout pattern, typography notes, tone, CTA "
            "pattern, and notable design choices. Output as structured text "
            "with labeled fields. Keep each field to 1-2 sentences."
        ),
    },
]


@track_span(step_type="research")
def ingest_swipe(
    image_data: bytes,
    *,
    client_id: str | None = None,
    filename: str = "swipe.png",
    mime_type: str = "image/png",
    notes: str = "",
    job_id: str | None = None,
) -> list[dict[str, Any]]:
    """Ingest a swipe file screenshot → extract visual DNA → create knowledge cards.

    Args:
        image_data: Raw image bytes.
        client_id: Optional client association.
        filename: Original filename.
        mime_type: MIME type.
        notes: Operator notes about the design.
        job_id: Optional job for tracing.

    Returns:
        List of created knowledge card dicts.
    """
    # 1. Upload to MinIO
    import uuid

    object_name = f"swipes/{uuid.uuid4()}/{filename}"
    storage_path = upload_bytes(object_name, image_data, content_type=mime_type)

    # 2. Extract visual DNA (CLIP embedding, dominant colours, layout)
    visual = extract_visual_dna(image_data)

    # 3. Store as asset with visual metadata
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO assets
                (storage_path, filename, mime_type, size_bytes, asset_class,
                 dominant_colours, layout_type, visual_embedding, source, client_id)
            VALUES (%s, %s, %s, %s, 'swipe', %s, %s, %s, 'swipe_ingest', %s)
            RETURNING id
            """,
            (
                storage_path,
                filename,
                mime_type,
                len(image_data),
                visual["dominant_colours_json"],
                visual["layout_type"],
                visual["visual_embedding_str"],
                client_id,
            ),
        )
        asset_row = cur.fetchone()
        assert asset_row is not None
        asset_id = str(asset_row["id"])

    # 4. Build design analysis via LLM
    analysis_prompt = (
        f"Design filename: {filename}\n"
        f"Dominant colours: {visual['dominant_colours']}\n"
        f"Layout type: {visual['layout_type']}\n"
        f"Operator notes: {notes or 'none'}"
    )
    analysis = call_llm(
        stable_prefix=_SWIPE_PREFIX,
        variable_suffix=[{"role": "user", "content": analysis_prompt}],
        model="gpt-5.4-mini",
        temperature=0.4,
        max_tokens=400,
        job_id=job_id,
        operation_type="extract",
    )

    # 5. Create knowledge card(s)
    source_info = {
        "source_type": "swipe",
        "client_name": client_id or "general",
        "title": f"Swipe: {filename}",
        "domain": "design",
    }

    cards_created: list[dict[str, Any]] = []

    # Card 1: Design analysis
    card_data = {
        "card_type": "swipe",
        "title": f"Swipe analysis: {filename}",
        "content": analysis["content"],
        "domain": "design",
    }
    prefix = contextualise_card(card_data, source_info)
    cards_created.append(
        _store_knowledge_card(
            card_data=card_data,
            prefix=prefix,
            client_id=client_id,
            source_type="swipe",
            source_title=f"Swipe: {filename}",
            asset_id=asset_id,
        )
    )

    # Card 2: Colour palette card
    palette_content = (
        f"Colour palette from {filename}: "
        f"dominant colours {visual['dominant_colours']}, "
        f"layout {visual['layout_type']}."
    )
    palette_card = {
        "card_type": "brand_pattern",
        "title": f"Palette: {filename}",
        "content": palette_content,
        "domain": "design",
    }
    palette_prefix = contextualise_card(palette_card, source_info)
    cards_created.append(
        _store_knowledge_card(
            card_data=palette_card,
            prefix=palette_prefix,
            client_id=client_id,
            source_type="swipe",
            source_title=f"Swipe palette: {filename}",
            asset_id=asset_id,
        )
    )

    logger.info("Swipe ingest created %d cards from %s", len(cards_created), filename)
    return cards_created


# ---------------------------------------------------------------------------
# 3. Calendar Cron
# ---------------------------------------------------------------------------


def load_calendar(calendar_file: str = "malaysia_2026.yaml") -> list[dict[str, Any]]:
    """Load calendar events from YAML."""
    path = CALENDAR_PATH / calendar_file
    if not path.exists():
        logger.warning("Calendar file not found: %s", path)
        return []
    with path.open() as fh:
        data = yaml.safe_load(fh)
    return data.get("events", [])


def check_calendar_events(
    *,
    reference_date: date | None = None,
    calendar_file: str = "malaysia_2026.yaml",
) -> list[dict[str, Any]]:
    """Return events whose prep window includes the reference date.

    An event is returned if:
        event.date - prep_window_days <= reference_date <= event.date

    Args:
        reference_date: Date to check against (default: today).
        calendar_file: Calendar YAML filename.

    Returns:
        List of event dicts that are within their prep window.
    """
    ref = reference_date or date.today()
    events = load_calendar(calendar_file)
    upcoming: list[dict[str, Any]] = []

    for event in events:
        event_date_raw = event.get("date")
        if event_date_raw is None:
            continue

        if isinstance(event_date_raw, str):
            event_date = datetime.strptime(event_date_raw, "%Y-%m-%d").date()
        elif isinstance(event_date_raw, date):
            event_date = event_date_raw
        else:
            continue

        prep_days = event.get("prep_window_days", 7)
        window_start = event_date - timedelta(days=prep_days)

        if window_start <= ref <= event_date:
            upcoming.append(
                {
                    **event,
                    "days_until": (event_date - ref).days,
                    "prep_started": True,
                }
            )

    upcoming.sort(key=lambda e: e.get("days_until", 999))
    logger.info("Calendar check (%s): %d events in prep window", ref, len(upcoming))
    return upcoming


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store_knowledge_card(
    *,
    card_data: dict[str, str],
    prefix: str,
    client_id: str | None,
    source_type: str,
    source_title: str,
    asset_id: str | None = None,
) -> dict[str, Any]:
    """Create a knowledge source + card with contextualised embedding.

    Delegates card insertion to tools.knowledge.ingest_card (canonical).
    """
    from tools.knowledge import ingest_card

    # Create knowledge source (stays here — source creation is context-specific)
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_sources
                (source_type, title, domain, asset_id, status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING id
            """,
            (source_type, source_title, card_data.get("domain", "general"), asset_id),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

    # Delegate card insertion — pass prefix to skip double contextualisation
    tags = card_data.get("tags", [])
    if isinstance(tags, str):
        tags = tags.split(",")

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
        "content": card_data["content"],
        "prefix": prefix,
        "client_id": client_id,
    }
