# Nano Banana Draft Tier Decision

**Session:** S4 — Endpoint Testing
**Date:** 2026-04-07
**Status:** GO

## Decision

Nano Banana (non-Pro, `fal-ai/nano-banana`) is approved as `draft_preview` tier for iteration/preview purposes.

## Evidence

- BM text rendering quality comparable to Pro variant
- "PROMOSI RAYA", "RM29.90 SAHAJA" rendered correctly
- Nasi Lemak poster text accurate
- Katering poster with BM pricing and phone number correct
- Cost: ~$0.10/image (vs $0.134 for Pro)

## For S9

Add to image_model_preference in workflow YAMLs:
```yaml
draft_preview: nano-banana
```

This enables a two-pass workflow:
1. Draft with Nano Banana (~$0.10) for operator preview
2. Final with Nano Banana Pro ($0.134) or Kontext ($0.04) for production

## Limitation

Not tested for character consistency (multi-reference). Use only for text-heavy posters and marketing graphics in draft stage.
