# Worker Session: S15b — Illustration Pipeline (Kontext Iterative)

## Working Directory
cd ~/executor/vizier

## Context Files
Read these files in this order:
1. ~/executor/vizier/CLAUDE.md — read FIRST
2. ~/executor/vizier/docs/VIZIER_ARCHITECTURE_v5_4_1.md — read ONLY: §42.4 (illustration consistency pipeline tiers), §42.1 (CharacterBible), §42.6 (creative workshop), §6.3 (image routing), §4.2 (quality techniques)
3. ~/executor/vizier/docs/VIZIER_BUILD_v1_3_1.md — read ONLY §7 session S15 spec
4. ~/executor/vizier/docs/decisions/illustration_pipeline.md — the S4 tier decision
5. ~/executor/vizier/docs/decisions/nano_banana_draft_tier.md — draft tier decision

## What You Are Building
`tools/illustrate.py` — the stateful sequential illustration pipeline for publishing. Unlike `tools/image.py` (fire-and-forget for posters/marketing), this maintains page-to-page state: previous page image feeds into next generation, character references are tracked, consistency is verified via CLIP after each page, and anchor frame resets prevent cumulative drift.

Also: wire `check_visual_consistency()` in `tools/publish.py` (currently a stub), add `draft_preview: nano-banana` to S9's workflow YAMLs, and connect the full creative_workshop → specimen → production → assembly flow.

## Environment Setup
```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
set -a && source /Users/Executor/vizier/.env && set +a
```
Use `python3.11` explicitly. Use `pip3.11 install --break-system-packages` for any pip installs.

## Critical Rules
- GPT-5.4-mini for ALL text tasks. No exceptions. (Anti-drift #54)
- Text is NEVER rendered inside AI illustrations — Typst overlays text. (Anti-drift #49)
- Illustration prompts use `illustration_shows` field, NOT page text. (§42.3)
- Visual brief expansion ALWAYS runs before image generation. (Anti-drift #25)
- Do NOT skip creative workshop for publishing projects. (Anti-drift #45)
- Composition grammar rules are ADVISORY, not strict blockers. (Anti-drift #41)
- Conventional commits: `feat(s15b): ...`

## S4 Endpoint Testing Results — USE THESE EXACTLY
- **Selected tier:** Tier 2 — Kontext iterative
- **Endpoint:** `fal-ai/flux-pro/kontext` (NOT `fal-ai/flux-kontext/pro` — API quirk!)
- **API params:** `guidance_scale=3.5`, `output_format=jpeg`, feed previous page as `image_url`
- **Re-anchor every 8 pages** from original reference to prevent cumulative drift
- **CLIP threshold:** 0.75 on cropped character region, ~0.65 full-page expected
- **Cost:** ~$0.04/page
- **Fallback:** If consistency < 80% after 2 retries, flag for operator review every 4 pages

## S15a Assembly Pipeline (already built — DO NOT REBUILD)
- `from tools.publish import assemble_childrens_book_pdf, assemble_ebook, assemble_document_pdf`
- `assemble_childrens_book_pdf(images: list[Path], scaffold, style_lock, metadata, page_texts, output_dir)` — accepts list of image paths, returns PDF path
- `check_visual_consistency()` in `tools/publish.py` is a STUB — wire CLIP similarity into it
- `STRATEGY_TEMPLATE_MAP` maps `TextPlacementStrategy` → Typst template
- Images must exist on disk as absolute paths before calling assembly

## What To Build

### 1. tools/illustrate.py — Stateful Illustration Pipeline (~250-350 lines)

**Core class: `IllustrationPipeline`**

State per project:
- `character_references: dict[str, list[Path]]` — CharacterBible → curated reference images
- `style_lock: StyleLock` — locked art direction
- `previous_page_image: Path | None` — fed to Kontext as `image_url`
- `anchor_image: Path` — original reference, reset target every 8 pages
- `page_count: int` — track for anchor reset
- `consistency_scores: list[float]` — running CLIP scores

**Methods:**

`generate_character_references(character_bible: CharacterBible, count: int = 10) -> list[Path]`
- Generate 10+ candidate images from CharacterBible physical description
- Use fal.ai endpoint appropriate for character generation
- Operator selects best 2-3 as references (this method generates candidates)
- Store in MinIO via `upload_bytes()`

`illustrate_page(page: NarrativeScaffoldPage, page_number: int) -> Path`
- Build prompt from `page.illustration_shows` (NEVER from page text)
- Include style direction from StyleLock
- If page_number > 1: feed `previous_page_image` as `image_url` to Kontext
- If page_number % 8 == 0: re-anchor from `anchor_image` instead of previous page
- Call `fal-ai/flux-pro/kontext` with `guidance_scale=3.5, output_format=jpeg`
- After generation: verify consistency via CLIP
- If CLIP score < 0.75 on cropped character: retry up to 2 times
- If still failing: flag for operator checkpoint
- Update `previous_page_image` and `consistency_scores`
- Upload to MinIO, return local path

`verify_consistency(generated: Path, references: list[Path], threshold: float = 0.75) -> tuple[bool, float]`
- Crop character bounding box from generated image
- Compute CLIP cosine similarity against reference images
- Return (passed, similarity_score)
- CLIP: ViT-B/32, 512-dim, MPS device

`get_anchor_status() -> dict`
- Return current anchor page, pages since reset, average consistency

### 2. Wire check_visual_consistency() in tools/publish.py
- Replace the stub with actual CLIP similarity call
- Import from illustrate.py or implement inline
- Accept two images + threshold → return pass/fail + similarity

### 3. Creative Workshop → Production Flow (~100 lines)
Wire the full sequence that the workflow executor drives:
1. **creative_workshop stage:** Load CharacterBible + StoryBible + StyleLock → generate character references → specimen page
2. **specimen stage:** Generate 1 page through full pipeline → operator approval gate
3. **page_production stage:** Loop through NarrativeScaffold pages → `illustrate_page()` each
4. **post_page_update stage:** Update RollingContext + verify consistency + entity tracking
5. **assembly stage:** Pass all generated images to `assemble_childrens_book_pdf()` from S15a
6. **operator_review stage:** Present for approval

### 4. Derivative Workshop Support
- When `creative_workshop: derivative` + `derivative_source: project_id`:
  - Load source project's StyleLock, typography, illustration tier
  - Operator confirms inherited settings (1 screen, not 8 steps)
  - Proceed to: new premise → new characters → new scaffold → specimen
- Duration target: 45-60 min operator time (vs 2-4 hrs full workshop)

### 5. Update Workflow YAMLs — Draft Preview Tier
Add `draft_preview: nano-banana` to `image_model_preference` in all relevant workflow YAMLs:
```yaml
image_model_preference:
  text_heavy: nano-banana-pro
  draft_preview: nano-banana          # ← ADD THIS (S4 confirmed GO)
  photorealistic: flux-2-pro
  character_iterative: flux-kontext-pro
  draft: flux-2-dev
  element: flux-2-dev
```

### 6. Tests (~200 lines)
- `tools/illustrate.py` maintains page-to-page state (previous_page, references, scores)
- Illustration prompt uses `illustration_shows` not page text (parse generated prompt, verify)
- Anchor reset fires on page 8, 16, 24 (verify previous_page_image == anchor_image after reset)
- CLIP consistency check returns correct pass/fail against threshold
- Character reference generation produces 10+ candidates from CharacterBible
- Retry logic: 2 retries on low consistency, then escalate to operator
- check_visual_consistency() in publish.py is no longer a stub — returns real CLIP scores
- Derivative workshop: load source StyleLock → confirm → proceed to new content
- Full flow: creative_workshop → specimen → 2 test pages → post_page_update → assembly → operator_review
- RollingContext updates after each page
- Consistency check catches planted contradiction in test data (character wearing wrong clothes)
- Character-cropped CLIP scores more stable than full-page scores
- draft_preview tier present in workflow YAMLs

## Existing Code — Import, Don't Rebuild
- `from tools.publish import assemble_childrens_book_pdf, check_visual_consistency` — S15a
- `from contracts.publishing import NarrativeScaffold, CharacterBible, StoryBible, StyleLock, PlanningObject` — S6
- `from contracts.context import RollingContext` — S6
- `from contracts.trace import TraceCollector` — S6
- `from tools.executor import WorkflowExecutor` — S9
- `from tools.workflow_schema import load_workflow` — S9
- `from utils.call_llm import call_llm` — S7
- `from utils.spans import track_span` — S7
- `from utils.retrieval import retrieve_similar_exemplars, encode_image` — S11/S12
- `from utils.storage import upload_bytes, download_bytes` — S10a
- `from utils.database import get_cursor` — S10a
- `from middleware.observability import dual_trace` — S8
- `from tools.image import generate_image, select_image_model` — S13
- CLIP: ViT-B/32, 512d, MPS — installed and validated
- fal.ai API key in `.env` (FAL_KEY)

## Exit Criteria
- `tools/illustrate.py` exists with fal.ai wrapper supporting Kontext iterative tier
- `tools/illustrate.py` maintains page-to-page state (previous page image, character references, consistency scores)
- Illustration tool generates TEXT-FREE images (no words/letters in output)
- Illustration prompt uses `illustration_shows` field, not raw page text
- Character reference generation produces 10+ candidates from CharacterBible YAML
- check_visual_consistency() in publish.py wired with real CLIP (no longer stub)
- Visual consistency checker flags character mismatch between two test images
- Character-cropped CLIP scores more stable than full-page scores
- Anchor frame: Kontext resets to original reference on anchor pages (every 8)
- Derivative workshop: load source StyleLock → confirm → proceed to new content only
- Full workflow: creative_workshop → specimen → 2 test pages → post_page_update → assembly → operator_review
- RollingContext updates after each page
- Consistency check catches planted contradiction in test data
- draft_preview tier added to relevant workflow YAMLs
- Text gen respects page_turn_effect (continuation ends mid-sentence/tension)
- All tests pass, pyright clean

## When Done
Commit with conventional commit message: `feat(s15b): ...`
Report: Session ID, exit criteria pass/fail, decisions made, files created/modified, dependencies installed, NEXT SESSION NEEDS TO KNOW.
