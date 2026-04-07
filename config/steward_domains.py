"""21 Wisdom Vault life domains for Steward task balance tracking.

Flat constant list — no logic. Used by steward.py for domain validation
and heatmap generation. Operator can adjust this list post-deploy.
"""

from __future__ import annotations

DOMAINS: list[str] = [
    "Deen",
    "Health",
    "Family",
    "Marriage",
    "Parenting",
    "Career",
    "Business",
    "Finance",
    "Learning",
    "Teaching",
    "Community",
    "Dawah",
    "Creativity",
    "Environment",
    "Legacy",
    "Social",
    "Self-Care",
    "Recreation",
    "Civic",
    "Travel",
    "Gratitude",
]

# Domain heatmap thresholds (tasks completed in last 7 days)
HEATMAP_GREEN = 3  # 3+ tasks = active
HEATMAP_AMBER = 1  # 1-2 tasks = slowing
# 0 tasks for 7+ days = red (neglected)
