"""Prayer time calculation for Malaysian scheduling.

Uses static JAKIM-aligned monthly averages for Kuala Lumpur.
The adhan library is available as a dependency but its v0.1.1
calculations are unreliable — static times are authoritative.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time

logger = logging.getLogger(__name__)

# Kuala Lumpur coordinates (for future adhan library use)
_KL_LAT = 3.1390
_KL_LON = 101.6869

# Static JAKIM-aligned monthly averages for KL (24h format, MYT)
_STATIC_TIMES: dict[int, dict[str, tuple[int, int]]] = {
    1: {
        "subuh": (5, 58),
        "zohor": (13, 15),
        "asr": (16, 36),
        "maghrib": (19, 24),
        "isyak": (20, 35),
    },
    2: {
        "subuh": (6, 1),
        "zohor": (13, 16),
        "asr": (16, 38),
        "maghrib": (19, 25),
        "isyak": (20, 35),
    },
    3: {
        "subuh": (5, 57),
        "zohor": (13, 12),
        "asr": (16, 33),
        "maghrib": (19, 19),
        "isyak": (20, 29),
    },
    4: {
        "subuh": (5, 49),
        "zohor": (13, 6),
        "asr": (16, 25),
        "maghrib": (19, 12),
        "isyak": (20, 23),
    },
    5: {
        "subuh": (5, 44),
        "zohor": (13, 3),
        "asr": (16, 21),
        "maghrib": (19, 9),
        "isyak": (20, 21),
    },
    6: {
        "subuh": (5, 45),
        "zohor": (13, 4),
        "asr": (16, 23),
        "maghrib": (19, 11),
        "isyak": (20, 23),
    },
    7: {
        "subuh": (5, 49),
        "zohor": (13, 8),
        "asr": (16, 27),
        "maghrib": (19, 14),
        "isyak": (20, 26),
    },
    8: {
        "subuh": (5, 48),
        "zohor": (13, 7),
        "asr": (16, 26),
        "maghrib": (19, 13),
        "isyak": (20, 24),
    },
    9: {
        "subuh": (5, 42),
        "zohor": (13, 2),
        "asr": (16, 19),
        "maghrib": (19, 7),
        "isyak": (20, 18),
    },
    10: {
        "subuh": (5, 36),
        "zohor": (12, 57),
        "asr": (16, 12),
        "maghrib": (19, 1),
        "isyak": (20, 12),
    },
    11: {
        "subuh": (5, 36),
        "zohor": (12, 58),
        "asr": (16, 12),
        "maghrib": (19, 1),
        "isyak": (20, 13),
    },
    12: {
        "subuh": (5, 44),
        "zohor": (13, 5),
        "asr": (16, 20),
        "maghrib": (19, 10),
        "isyak": (20, 22),
    },
}


def get_prayer_times(target_date: date | None = None) -> dict[str, time]:
    """Return prayer times for Kuala Lumpur on the given date.

    Uses static JAKIM-aligned monthly averages. Accurate to ~5 minutes
    for any day in a given month.

    Returns:
        Dict with keys: subuh, zohor, asr, maghrib, isyak.
        Values are datetime.time objects in MYT (UTC+8).
    """
    if target_date is None:
        target_date = date.today()

    month_data = _STATIC_TIMES[target_date.month]
    return {name: time(hour, minute) for name, (hour, minute) in month_data.items()}


def is_after_prayer(prayer: str, target_date: date | None = None) -> bool:
    """Check if current time is after the given prayer time today."""
    times = get_prayer_times(target_date)
    if prayer not in times:
        raise ValueError(f"Unknown prayer: {prayer}. Use: {list(times.keys())}")
    now = datetime.now().time()
    return now >= times[prayer]
