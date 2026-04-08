# S13 Visual Intelligence + Guardrails Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the visual intelligence and quality pipeline: image generation via fal.ai, NIMA pre-screening, 4-dimension critique scoring, exemplar-anchored quality scoring, visual lineage tracking, brand voice guardrails, BM naturalness checks, and GuardrailMailbox dedup.

**Architecture:** Image generation routes through fal.ai with model selection by job characteristics. Generated images pass through a quality pipeline: NIMA aesthetic pre-screen (local, zero-cost) filters obvious failures, then GPT-5.4-mini 4-dimension critique scoring catches design issues with specific feedback. Guardrails run in parallel on GPT-5.4-mini for brand voice and BM naturalness. All steps traced via TraceCollector.

**Tech Stack:** fal.ai (image gen), PyTorch/MPS (NIMA MobileNetV2), CLIP ViT-B/32 (similarity), GPT-5.4-mini (scoring/guardrails), Postgres (visual_lineage), MinIO (asset storage)

---

## File Structure

| File | Responsibility | Lines |
|------|---------------|-------|
| `config/prompt_templates/visual_brief_expander.md` | Prompt template for brief expansion | ~30 |
| `config/quality_frameworks/posteriq_quality_dimensions.yaml` | 4-dimension scoring framework config | ~40 |
| `config/quality_frameworks/poster_quality.md` | Scoring rubric reference | ~50 |
| `tools/image.py` | fal.ai wrapper + visual brief expansion + model routing | ~120 |
| `tools/visual_scoring.py` | NIMA pre-screen + 4-dim critique + exemplar-anchored scoring + visual lineage | ~180 |
| `middleware/guardrails.py` | Brand voice guardrail + BM naturalness + GuardrailMailbox | ~100 |
| `tools/visual_pipeline.py` | Full pipeline: brief -> expand -> generate -> NIMA -> critique -> trace | ~80 |
| `tests/test_visual_intelligence.py` | All tests for S13 components | ~200 |

**Existing files imported (NOT rebuilt):**
- `utils/retrieval.py` — `retrieve_similar_exemplars()` (S11 stub, try/except fallback)
- `utils/call_llm.py` — `call_llm()` (auto-records spans)
- `utils/database.py` — `get_cursor()` (yields RealDictCursor)
- `utils/storage.py` — `upload_bytes()`, `download_bytes()` (MinIO)
- `utils/spans.py` — `@track_span` decorator
- `utils/trace_persist.py` — `persist_trace()`, `collect_and_persist()`
- `contracts/trace.py` — `TraceCollector`, `StepTrace`, `ProductionTrace`
- `middleware/quality_gate.py` — `ValidationResult`

---

## Chunk 1: Config Files + Image Generation

### Task 1: Create config files

**Files:**
- Create: `config/prompt_templates/visual_brief_expander.md`
- Create: `config/quality_frameworks/posteriq_quality_dimensions.yaml`
- Create: `config/quality_frameworks/poster_quality.md`

- [ ] **Step 1: Create visual brief expander prompt template**

```markdown
# Visual Brief Expander

You are a design brief expansion specialist. Given a raw visual brief, expand it into a structured JSON object with these fields:

## Output Format (JSON)
{
  "composition": "Detailed composition description — layout zones, visual hierarchy, focal points",
  "style": "Art style, mood, lighting, texture — specific, not generic",
  "brand": "Brand colours (hex), logo placement, brand personality expression",
  "technical": "Dimensions, resolution, format, bleed area, safe zones",
  "text_content": "ALL text that must appear in the design — headlines, subheads, body, CTA, legal"
}

## Rules
- Be SPECIFIC: "warm golden hour lighting from upper-left" not "nice lighting"
- Include exact hex colours from brand config when available
- Describe spatial relationships: "CTA button centred in bottom 20% zone"
- text_content lists EVERY text element — Typst renders text, NOT the image model
- If the brief mentions people, describe demographics, pose, expression in detail
- For BM (Bahasa Malaysia) content, note cultural context and visual metaphors
```

- [ ] **Step 2: Create 4-dimension quality scoring YAML**

```yaml
# posteriq_quality_dimensions.yaml
# Research-validated scoring for poster/graphic design (§30.6)

dimensions:
  text_visibility:
    description: "Is text legible, properly sized, good contrast against background?"
    weight: 0.25
    criteria:
      - "Font size readable at intended viewing distance"
      - "Sufficient contrast ratio (WCAG AA minimum)"
      - "Text not obscured by busy background"
      - "Hierarchy clear: headline > subhead > body > CTA"

  design_layout:
    description: "Is layout clean, balanced, consistent with clear visual hierarchy?"
    weight: 0.25
    criteria:
      - "Visual weight balanced across composition"
      - "Consistent margins and spacing"
      - "Clear focal point draws the eye"
      - "White space used intentionally, not accidentally"

  colour_harmony:
    description: "Are colours harmonious, images high quality, consistent with brand?"
    weight: 0.25
    criteria:
      - "Colour palette cohesive (analogous, complementary, or brand-driven)"
      - "No clashing colours that distract from message"
      - "Image resolution and quality appropriate"
      - "Brand colours used correctly per guidelines"

  overall_coherence:
    description: "Does everything work together as a unified design?"
    weight: 0.25
    criteria:
      - "Message, visuals, and layout tell a consistent story"
      - "No orphaned or disconnected elements"
      - "Design appropriate for target audience and medium"
      - "Professional finish — no amateur tells"

scoring:
  scale: "1-5"
  thresholds:
    regenerate: 2.0
    acceptable: 3.0
    good: 4.0
    excellent: 4.5
```

- [ ] **Step 3: Create poster quality rubric**

The `poster_quality.md` file provides the scoring rubric for GPT-5.4-mini critique passes.

- [ ] **Step 4: Commit config files**

```bash
git add config/prompt_templates/visual_brief_expander.md config/quality_frameworks/
git commit -m "feat(s13): add visual brief expander template and quality scoring frameworks"
```

### Task 2: Build tools/image.py — fal.ai wrapper + brief expansion

**Files:**
- Create: `tools/image.py`
- Test: `tests/test_visual_intelligence.py` (partial — image tests)

- [ ] **Step 1: Write failing tests for image model routing and brief expansion**

```python
# tests/test_visual_intelligence.py — image routing + brief expansion tests

def test_select_image_model_bm_text():
    """BM text-heavy content routes to nano-banana-pro."""
    result = select_image_model(language="ms", has_text=True, style="poster")
    assert result == "fal-ai/nano-banana-pro"

def test_select_image_model_photorealistic():
    result = select_image_model(language="en", has_text=False, style="photorealistic")
    assert result == "fal-ai/flux-2-pro"

def test_select_image_model_draft():
    result = select_image_model(language="en", has_text=False, style="draft")
    assert result == "fal-ai/nano-banana"

def test_select_image_model_generic():
    result = select_image_model(language="en", has_text=False, style="poster")
    assert result == "fal-ai/flux-2-dev"

def test_expand_brief_returns_structured_json(monkeypatch):
    """Brief expansion calls LLM and returns structured dict."""
    # Monkeypatch call_llm to return mock JSON response
    ...

def test_expand_brief_loads_template():
    """Template file exists and is loaded."""
    from tools.image import _load_brief_template
    template = _load_brief_template()
    assert "composition" in template
    assert "text_content" in template
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_visual_intelligence.py -v -x
```
Expected: ImportError or NameError (tools/image.py doesn't exist yet)

- [ ] **Step 3: Implement tools/image.py**

Key functions:
- `select_image_model(language, has_text, style, artifact_family) -> str` — routes by job characteristics
- `_load_brief_template() -> str` — loads from config/prompt_templates/visual_brief_expander.md
- `expand_brief(raw_brief, brand_config) -> dict` — calls GPT-5.4-mini, returns structured JSON
- `generate_image(prompt, model, width, height, guidance_scale) -> bytes` — fal.ai fire-and-forget
- `log_generation_cost(model, width, height, cost_usd)` — records cost to spans

- [ ] **Step 4: Run tests — verify they pass**
- [ ] **Step 5: Commit**

```bash
git add tools/image.py tests/test_visual_intelligence.py
git commit -m "feat(s13): add image generation wrapper with model routing and brief expansion"
```

---

## Chunk 2: Visual Scoring (NIMA + 4-dim critique + exemplar)

### Task 3: Build tools/visual_scoring.py — NIMA + critique + exemplar + lineage

**Files:**
- Create: `tools/visual_scoring.py`
- Modify: `tests/test_visual_intelligence.py` (add scoring tests)

- [ ] **Step 1: Write failing tests for NIMA pre-screen**

```python
def test_nima_score_returns_float():
    """NIMA returns a mean aesthetic score as float."""
    # Use a synthetic test image (random noise)
    image_bytes = create_test_image()
    score = nima_score(image_bytes)
    assert isinstance(score, float)
    assert 1.0 <= score <= 10.0

def test_nima_prescreen_low_triggers_regenerate():
    """Score < 4.0 returns action='regenerate'."""
    result = nima_prescreen(score=3.5)
    assert result["action"] == "regenerate"

def test_nima_prescreen_high_passes():
    """Score > 7.0 returns action='pass'."""
    result = nima_prescreen(score=7.5)
    assert result["action"] == "pass"

def test_nima_prescreen_mid_proceeds():
    """Score 4.0-7.0 returns action='proceed_with_caution'."""
    result = nima_prescreen(score=5.5)
    assert result["action"] == "proceed_with_caution"
```

- [ ] **Step 2: Run NIMA tests — verify fail**
- [ ] **Step 3: Implement NIMA pre-screen**

Key functions:
- `_load_nima_model() -> nn.Module` — MobileNetV2 + custom head, MPS device, cached
- `nima_score(image_bytes: bytes) -> float` — run inference, return mean aesthetic score
- `nima_prescreen(score: float) -> dict` — classify action based on thresholds

- [ ] **Step 4: Run NIMA tests — verify pass**

- [ ] **Step 5: Write failing tests for 4-dimension critique**

```python
def test_critique_4dim_returns_all_dimensions(monkeypatch):
    """Critique returns scores and issues for all 4 dimensions."""
    # Monkeypatch call_llm
    result = critique_4dim(image_bytes=b"...", brief={"composition": "..."})
    assert set(result.keys()) >= {"text_visibility", "design_layout", "colour_harmony", "overall_coherence"}
    for dim in result.values():
        assert "score" in dim
        assert "issues" in dim

def test_critique_4dim_uses_gpt54mini(monkeypatch):
    """All critique calls use gpt-5.4-mini (anti-drift #54)."""
    calls = []
    def mock_llm(**kwargs):
        calls.append(kwargs)
        return {"content": '{"score": 4.0, "issues": []}', ...}
    monkeypatch.setattr("tools.visual_scoring.call_llm", mock_llm)
    critique_4dim(image_bytes=b"...", brief={})
    assert all(c["model"] == "gpt-5.4-mini" for c in calls)
```

- [ ] **Step 6: Implement 4-dimension critique scoring**

Key function:
- `critique_4dim(image_bytes, brief, exemplars=None) -> dict[str, dict]` — 4 GPT-5.4-mini passes, returns per-dimension score + issues

- [ ] **Step 7: Write and implement exemplar-anchored scoring**

```python
def test_exemplar_scoring_with_stub_fallback():
    """When S11 not merged, falls back to empty exemplars gracefully."""
    result = score_with_exemplars(image_bytes=b"...", client_id="test", brief={})
    assert "exemplars_used" in result
    assert isinstance(result["exemplars_used"], int)
```

Key function:
- `score_with_exemplars(image_bytes, client_id, brief) -> dict` — try/except around `retrieve_similar_exemplars`, graceful fallback

- [ ] **Step 8: Write and implement visual lineage recording**

```python
def test_record_visual_lineage(mock_db):
    """Records lineage entry to visual_lineage table."""
    record_visual_lineage(job_id="...", artifact_id="...", asset_id="...", role="generated", reason="primary poster")
```

Key function:
- `record_visual_lineage(job_id, artifact_id, asset_id, role, reason) -> None` — INSERT into visual_lineage table

- [ ] **Step 9: Run all scoring tests — verify pass**
- [ ] **Step 10: Commit**

```bash
git add tools/visual_scoring.py tests/test_visual_intelligence.py
git commit -m "feat(s13): add NIMA pre-screen, 4-dim critique, exemplar scoring, visual lineage"
```

---

## Chunk 3: Guardrails + Pipeline

### Task 4: Build middleware/guardrails.py

**Files:**
- Create: `middleware/guardrails.py`
- Modify: `tests/test_visual_intelligence.py` (add guardrail tests)

- [ ] **Step 1: Write failing tests for guardrails**

```python
def test_brand_voice_flags_register_mismatch(monkeypatch):
    """Formal brand + casual copy flags mismatch."""
    result = check_brand_voice(copy="yo check this out lol", copy_register="formal", brand_config={})
    assert result["flagged"] is True
    assert "register" in result["issue"].lower()

def test_brand_voice_passes_matching_register(monkeypatch):
    result = check_brand_voice(copy="We are pleased to announce...", copy_register="formal", brand_config={})
    assert result["flagged"] is False

def test_bm_naturalness_flags_overly_formal():
    """Indonesian-sounding BM copy flagged."""
    result = check_bm_naturalness("Kami dengan ini memaklumkan bahawa perkara tersebut telah diputuskan.")
    assert result["flagged"] is True

def test_bm_naturalness_passes_natural():
    result = check_bm_naturalness("Jom cuba menu baru kami!")
    assert result["flagged"] is False

def test_guardrail_mailbox_deduplicates():
    """3 flags about same issue deduplicated to 1."""
    mailbox = GuardrailMailbox()
    mailbox.add_flag(issue_type="register_mismatch", detail="Paragraph 1: too casual")
    mailbox.add_flag(issue_type="register_mismatch", detail="Paragraph 3: too casual")
    mailbox.add_flag(issue_type="register_mismatch", detail="Paragraph 5: too casual")
    result = mailbox.collect()
    assert len(result) == 1
    assert result[0]["count"] == 3

def test_guardrail_mailbox_keeps_different_types():
    mailbox = GuardrailMailbox()
    mailbox.add_flag(issue_type="register_mismatch", detail="too casual")
    mailbox.add_flag(issue_type="bm_naturalness", detail="too formal")
    result = mailbox.collect()
    assert len(result) == 2
```

- [ ] **Step 2: Run tests — verify fail**
- [ ] **Step 3: Implement middleware/guardrails.py**

Key classes/functions:
- `check_brand_voice(copy, copy_register, brand_config) -> dict` — GPT-5.4-mini brand voice check
- `check_bm_naturalness(text) -> dict` — heuristic: sentence length, formal vocabulary density, passive voice
- `GuardrailMailbox` — collects flags, deduplicates by issue_type, returns actionable list
- `run_parallel_guardrails(copy, copy_register, brand_config, language) -> list[dict]` — runs all applicable guardrails

- [ ] **Step 4: Run tests — verify pass**
- [ ] **Step 5: Commit**

```bash
git add middleware/guardrails.py tests/test_visual_intelligence.py
git commit -m "feat(s13): add brand voice guardrail, BM naturalness check, GuardrailMailbox"
```

### Task 5: Build tools/visual_pipeline.py — full pipeline

**Files:**
- Create: `tools/visual_pipeline.py`
- Modify: `tests/test_visual_intelligence.py` (add pipeline tests)

- [ ] **Step 1: Write failing test for full pipeline**

```python
def test_visual_pipeline_full_flow(monkeypatch):
    """Pipeline: brief -> expand -> generate -> NIMA -> critique -> trace."""
    # Monkeypatch all external calls (fal.ai, call_llm, NIMA)
    result = run_visual_pipeline(
        raw_brief="Raya 2025 poster for DMB",
        job_id="test-job-1",
        client_id="test-client-1",
        artifact_family="poster",
        language="ms",
    )
    assert "image_bytes" in result or "image_path" in result
    assert "nima_score" in result
    assert "critique" in result
    assert "trace" in result
```

- [ ] **Step 2: Run test — verify fail**
- [ ] **Step 3: Implement tools/visual_pipeline.py**

Key function:
- `run_visual_pipeline(raw_brief, job_id, client_id, artifact_family, language, brand_config, copy_register, has_text) -> dict`
  - Steps: expand brief -> select model -> generate image -> NIMA prescreen -> 4-dim critique -> exemplar scoring -> record lineage -> run guardrails -> collect trace
  - Uses TraceCollector for all steps
  - Returns: image_bytes/path, nima_score, critique, guardrail_flags, trace

- [ ] **Step 4: Run tests — verify pass**
- [ ] **Step 5: Run pyright on all new files**

```bash
pyright tools/image.py tools/visual_scoring.py tools/visual_pipeline.py middleware/guardrails.py
```

- [ ] **Step 6: Final commit**

```bash
git add tools/visual_pipeline.py tests/test_visual_intelligence.py
git commit -m "feat(s13): add visual pipeline — brief to scored poster with guardrails"
```

---

## Exit Criteria Verification

- [ ] Poster generates via Nano Banana Pro with expanded brief
- [ ] NIMA pre-screen catches low-quality (< 4.0) -> regeneration
- [ ] NIMA passes high-quality (> 7.0) without regeneration
- [ ] 4-dim critique generates specific issues across all 4 dimensions
- [ ] Exemplar-anchored scoring retrieves exemplars (or graceful fallback)
- [ ] Visual lineage records template + stock assets + exemplar used
- [ ] Brand voice guardrail flags register mismatch
- [ ] GuardrailMailbox deduplicates 3 flags about same issue into 1
- [ ] BM naturalness heuristic flags overly formal copy
- [ ] Full pipeline: brief -> poster -> NIMA -> 4-dim critique -> trace -> feedback trigger
- [ ] `from utils.retrieval import retrieve_similar_exemplars` works
- [ ] All tests pass, pyright clean
