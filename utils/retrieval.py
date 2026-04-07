from __future__ import annotations


def contextualise_card(card: dict, source: dict) -> str:
    """
    Generate 50-100 token context prefix via GPT-5.4-mini.
    Prepended to card content before embedding.
    Raw card content (without prefix) is served to production models.

    Returns: str — the context prefix, e.g. "This card is from DMB's
    Raya 2025 promotional campaign targeting middle-class Malay women."
    """
    raise NotImplementedError("Populated by S12")


def retrieve_similar_exemplars(
    image: bytes,
    client_id: str,
    top_k: int = 3,
) -> list[dict]:
    """
    CLIP ViT-B/32 similarity search against exemplars table.
    Used by S11 for exemplar injection into production prompts.
    Used by S13 for exemplar-anchored quality scoring.

    Returns: list of dicts, each with:
        {
            "exemplar_id": str,       # UUID from exemplars table
            "artifact_id": str,       # linked artifact UUID
            "asset_path": str,        # MinIO storage path to the image
            "similarity": float,      # cosine similarity score (0-1)
            "artifact_family": str,   # e.g. "poster", "brochure"
            "style_tags": list[str],  # from exemplars table
        }
    Sorted by similarity descending.
    Only returns results with similarity >= 0.5.
    For character consistency verification, use threshold 0.75 on cropped regions.
    """
    raise NotImplementedError("Populated by S11")
