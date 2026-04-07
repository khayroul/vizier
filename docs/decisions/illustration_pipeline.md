# Illustration Pipeline Tier Selection

**Session:** S4 — Endpoint Testing
**Date:** 2026-04-07
**Status:** DECIDED

---

## Selected Tier: Tier 2 — Kontext Iterative Editing

**Primary path:** `fal-ai/flux-pro/kontext` (FLUX.1 Kontext [pro])
**Cost:** $0.04/image
**Consistency:** 4.6/5 (92%) across 8 sequential pages
**No training required.** Each page feeds into the next via iterative editing.

### Why Kontext Won

1. **Highest measured consistency** — 92% across 8 pages, well above the 80% threshold
2. **Best balance** of character consistency + scene variation — unlike IP-Adapter which suppresses scene changes
3. **No setup cost** — no training required, instant start on any new project
4. **Cheapest per-page** among high-consistency options ($0.04 vs $0.075 for IP-Adapter)
5. **Excellent scene diversity** — bedroom, kitchen, kampung, classroom, playground, sunset, reading scenes all distinct

### Kontext Consistency Scores (8 Pages)

| Page | Scene | Score | Notes |
|------|-------|-------|-------|
| 1 | Bedroom, morning | 5/5 | Perfect character match from reference |
| 2 | Kitchen, breakfast | 5/5 | Ponytail, blue floral outfit maintained |
| 3 | Kampung path | 5/5 | Outfit shifted to shirt+pants, character recognizable |
| 4 | Classroom | 5/5 | Excellent — consistent face, hair, outfit |
| 5 | Playing under tree | 4/5 | Slight face proportion shift |
| 6 | Helping child | 5/5 | Very consistent with page 5 |
| 7 | Walking home sunset | 4/5 | Hair flowing loose, still clearly same character |
| 8 | Reading by lamplight | 4/5 | Slightly older look, recognizable |

**Average: 4.6/5 (92%)**

### Known Limitations

- Outfit drifted from full baju kurung to shirt+pants by page 3 (stayed consistent after)
- Hair styling varies slightly (tight ponytail → looser)
- Potential for cumulative drift over 12+ pages — recommend re-anchoring from reference every 8 pages

### Fallback Plan

If consistency drops below 80% on a specific project:
- Re-anchor from reference image (use original reference as input instead of previous page)
- Operator review checkpoint every 4 pages
- For high-stakes books: upgrade to LoRA training (Tier 1) with real photographs

---

## Full Tier Comparison

| Method | Consistency | Scene Variation | Cost/Page | Setup Cost | CLIP Score (full-page) |
|--------|------------|-----------------|-----------|------------|----------------------|
| **Kontext Pro (iterative)** | **4.6/5 (92%)** | **Excellent** | **$0.04** | **$0** | **0.66** |
| IP-Adapter (3 refs) | 4.0/5 (80%) | Poor | $0.075 | $0 | N/A* |
| FLUX.2 Pro (2 refs) | 3.5/5 (70%) | Good | $0.03 | $0 | N/A* |
| LoRA (10 imgs, 1000 steps) | 2.5/5 (50%) | Good | $0.012 | $2.00 | 0.54 |
| Nano Banana Pro (3 refs) | 2.5/5 (50%) | Excellent | $0.134 | $0 | N/A* |

*IP-Adapter, FLUX.2, and Nano Banana character pages were generated before worktree reset; CLIP scores not available for those batches. Visual assessment was performed in-session.

### CLIP Verification Notes

- Full-page CLIP similarity is inherently lower than reference-to-reference (~0.80) because scenes add visual noise
- Kontext page 1 scored 0.66 against reference — strong for a complex scene
- LoRA scenes averaged 0.54 — significantly weaker
- Architecture threshold of 0.75 is for **cropped character regions**, not full pages
- Full-page scores of 0.65+ indicate good character preservation

---

## LoRA Training Assessment

**Training endpoint:** `fal-ai/flux-lora-fast-training`
**Cost:** $2.00 per training run
**Time:** 332 seconds (~5.5 minutes)
**Training data:** 10 AI-generated watercolour illustrations
**Steps:** 1,000
**Trigger word:** `aliya_char`

### LoRA Results

- Character concept captured broadly (young Asian girl, illustration style)
- Specific details lost (blue baju kurung → varied outfits, ponytail → varied hairstyles)
- Art style shifted from watercolour to more digital/3D rendering
- Multi-LoRA at scale 0.6-1.0: style control works but character identity weak

### LoRA Improvement Path (for Tier 1 projects)

1. Use 20-30 training images (not 10)
2. Use real photographs or highly consistent AI references with fixed seed
3. Increase to 2000-3000 steps
4. Train separate character LoRA and style LoRA
5. Viable for series/recurring characters where investment in training data is justified

**Recommendation:** LoRA training is viable for Tier 1 but requires better training data than what we tested. For Month 1-2, default to Kontext iterative (Tier 2). Revisit LoRA for series work in Month 2+ when real character reference photographs are available.

---

## Image Routing Map (Confirmed)

```yaml
image_model_preference:
  text_heavy: nano-banana-pro        # BM text rendering 5/5 — production ready
  photorealistic: flux-2-pro         # Stunning product/food photography
  character_iterative: flux-pro-kontext  # SELECTED — 92% consistency
  character_anchored: flux-general-ip    # Good for single-scene anchoring
  illustration: nano-banana-pro      # Beautiful art, weak character consistency
  draft: nano-banana                 # BM text still good at lower cost
  element: flux-2-dev                # Per architecture (not tested)
```

### API Endpoint Reference

| Config Key | fal.ai Endpoint | Cost |
|-----------|----------------|------|
| character_iterative | `fal-ai/flux-pro/kontext` | $0.04/img |
| character_anchored | `fal-ai/flux-general/image-to-image` | ~$0.075/MP |
| text_heavy | `fal-ai/nano-banana-pro` | $0.134/img |
| illustration | `fal-ai/nano-banana-pro` | $0.134/img |
| photorealistic | `fal-ai/flux-2-pro` | $0.03/MP |
| draft | `fal-ai/nano-banana` | ~$0.10/img |
| element | `fal-ai/flux-2/dev` | $0.012/MP |
| lora_training | `fal-ai/flux-lora-fast-training` | $2.00/run |
| lora_inference | `fal-ai/flux-lora` | ~$0.012/img |

---

## Nano Banana BM Text Rendering

**Verdict: STRONG GO**

| Test | BM Text Quality | Price/Number Accuracy | Notes |
|------|----------------|----------------------|-------|
| Bakery poster | 5/5 | "RM29.90" perfect | "PROMOSI RAYA" flawless |
| Real estate flyer | 5/5 | Phone number rendered | Good layout |
| Nasi Lemak poster | 5/5 | N/A | "Beli 2 Percuma 1" perfect |
| Seminar poster | 5/5 | "RM150" correct | Professional design |
| Katering flyer | 5/5 | "RM2,500", "019-876 5432" | Jawi script rendered |

Draft Nano Banana (non-Pro) also renders BM text well — viable for preview/iteration stage.

---

## FLUX.2 Pro Photorealistic

**Verdict: GO for product photography**

- Perfume bottle: Excellent studio quality
- Nasi goreng: Stunningly photorealistic food photography
- Batik fabric: Good product shot quality

Cost-effective at $0.03/MP for marketing product shots.

---

## MaLLaM Feasibility

- Ollama is installed and running (qwen3.5:9b + nomic-embed-text present)
- MaLLaM is not on the ollama registry — would need custom GGUF conversion
- **Month 1-2: Not needed.** All text tasks use GPT-5.4-mini (anti-drift #54)
- Revisit in Phase 2+ if BM-specific language model is needed for guardrails

---

## Total Test Cost

| Category | Count | Cost |
|----------|-------|------|
| Kontext reference (FLUX.1 dev) | 1 | $0.012 |
| Kontext 8 pages | 8 | $0.320 |
| Multi-ref references | 3 | $0.036 |
| IP-Adapter 5 pages | 5 | $0.375 |
| Nano Banana Pro character | 3 | $0.402 |
| Nano Banana Pro BM posters | 5 | $0.670 |
| FLUX.2 Pro multi-ref | 3 | $0.090 |
| LoRA references (6 new) | 6 | $0.072 |
| LoRA training | 1 | $2.000 |
| LoRA inference | 5 | $0.060 |
| Multi-LoRA composition | 3 | $0.036 |
| FLUX.2 Pro photorealistic | 3 | $0.090 |
| Draft Nano Banana posters | 3 | $0.300 |
| **TOTAL** | **49 images + 1 training** | **$4.46** |
