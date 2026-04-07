# Decision: Position-Aware Center Crop for CLIP Verification

**Date:** 2026-04-08
**Session:** S15b
**Status:** Accepted

## Context

The illustration pipeline verifies character consistency via CLIP cosine
similarity on cropped character regions (§42.4 specifies threshold 0.75
on "cropped character region"). Full-page CLIP scores are noisier due to
background variation.

## Decision

Use a position-aware crop heuristic based on `composition_guide.character_position`:
- `centre` -> crop center 60% of image
- `left_third` -> crop left 60%
- `right_third` -> crop right 60%

This avoids adding an object detection dependency (MediaPipe, YOLO) while
leveraging the composition data already available in every PageScaffold.

## Consequences

- **Pro:** Zero additional dependencies; uses existing scaffold data.
- **Pro:** More accurate than a fixed center crop for non-centered compositions.
- **Con:** Assumes characters are where the scaffold says; no verification.
- **Con:** Multi-character pages still use a single crop region.

## Future Enhancement

If crop accuracy proves insufficient, MediaPipe (already in the architecture
at §30.3 for face detection) can provide precise bounding boxes. This would
be a drop-in replacement for `crop_character_region()` in `utils/image_processing.py`.
