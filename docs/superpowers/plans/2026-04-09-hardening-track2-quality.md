# Hardening Track 2: Output Quality Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform poster output from "one layout, generic copy" to "intent-aware templates, enriched copy, adherence-scored quality."

**Architecture:** Brief interpreter extracts structured intent (Ring 1 contract, Ring 2 extraction behavior). Template selector scores templates against intent. Copy enrichment produces slot-rich content. Adherence gating catches brief-ignoring output.

**Tech Stack:** GPT-5.4-mini (all LLM calls), Pydantic (contracts), Jinja2 (templates), YAML (metadata)

**Ring discipline (per Codex review):**
- Ring 1 = `contracts/` — InterpretedIntent model, PosterContentSchema model
- Ring 2 = `config/`, `templates/html/`, selector logic, prompts — changeable without structural changes
- Ring 3 = `jobs.interpreted_intent` JSONB, filled poster content per run — governed input, never auto-mutates structure

---

## Chunk 1: Foundation Contracts + Benchmark Corpus

### Task 1: InterpretedIntent contract (Ring 1)

**Files:**
- Create: `contracts/interpreted_intent.py`
- Test: `tests/test_interpreted_intent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_interpreted_intent.py
from __future__ import annotations

import pytest
from contracts.interpreted_intent import InterpretedIntent


class TestInterpretedIntentValidation:
    def test_minimal_valid_intent(self) -> None:
        intent = InterpretedIntent(
            occasion="product_launch",
            audience="general_public",
            mood="professional",
        )
        assert intent.occasion == "product_launch"
        assert intent.must_include == []
        assert intent.must_avoid == []

    def test_full_intent(self) -> None:
        intent = InterpretedIntent(
            occasion="hari_raya",
            audience="malay_families",
            mood="festive",
            layout_hint="full_bleed_hero",
            text_density="moderate",
            cta_style="prominent",
            cultural_context="islamic_festive",
            must_include=["date", "venue"],
            must_avoid=["alcohol"],
        )
        assert intent.cultural_context == "islamic_festive"
        assert len(intent.must_include) == 2

    def test_to_prompt_context_returns_string(self) -> None:
        intent = InterpretedIntent(
            occasion="sale",
            audience="bargain_shoppers",
            mood="urgent",
        )
        ctx = intent.to_prompt_context()
        assert "sale" in ctx
        assert "urgent" in ctx
        assert isinstance(ctx, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_interpreted_intent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'contracts.interpreted_intent'`

- [ ] **Step 3: Write InterpretedIntent contract**

```python
# contracts/interpreted_intent.py
from __future__ import annotations

from pydantic import BaseModel, Field


class InterpretedIntent(BaseModel):
    """Canonical structured parse of a raw production brief.

    Ring 1 contract — the schema is stable.
    Ring 2 behavior — the extraction prompt/categories are changeable config.
    Ring 3 data — each job's stored row is runtime data.
    """

    occasion: str = ""
    audience: str = ""
    mood: str = ""
    layout_hint: str = ""
    text_density: str = "moderate"  # minimal | moderate | dense
    cta_style: str = "medium"  # high | medium | low | none
    cultural_context: str = ""
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Serialize intent into a human-readable prompt fragment."""
        parts: list[str] = []
        if self.occasion:
            parts.append(f"Occasion: {self.occasion}")
        if self.audience:
            parts.append(f"Audience: {self.audience}")
        if self.mood:
            parts.append(f"Mood/tone: {self.mood}")
        if self.layout_hint:
            parts.append(f"Layout preference: {self.layout_hint}")
        if self.text_density:
            parts.append(f"Text density: {self.text_density}")
        if self.cta_style:
            parts.append(f"CTA prominence: {self.cta_style}")
        if self.cultural_context:
            parts.append(f"Cultural context: {self.cultural_context}")
        if self.must_include:
            parts.append(f"Must include: {', '.join(self.must_include)}")
        if self.must_avoid:
            parts.append(f"Must avoid: {', '.join(self.must_avoid)}")
        return "\n".join(parts)

    def to_jsonb(self) -> dict[str, object]:
        """Serialize for jobs.interpreted_intent JSONB column."""
        return self.model_dump(mode="json")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_interpreted_intent.py -v`
Expected: PASS

- [ ] **Step 5: pyright check**

Run: `pyright contracts/interpreted_intent.py`

- [ ] **Step 6: Commit**

```bash
git add contracts/interpreted_intent.py tests/test_interpreted_intent.py
git commit -m "feat(contracts): add InterpretedIntent Ring 1 model"
```

---

### Task 2: PosterContentSchema contract (Ring 1)

**Files:**
- Create: `contracts/poster.py`
- Test: `tests/test_poster_contract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_poster_contract.py
from __future__ import annotations

import pytest
from contracts.poster import PosterContentSchema


class TestPosterContentSchema:
    def test_required_fields_only(self) -> None:
        schema = PosterContentSchema(
            headline="Grand Opening",
            body_text="Join us for an evening of celebration",
            cta="Register Now",
            background_image="/tmp/hero.jpg",
        )
        assert schema.headline == "Grand Opening"
        assert schema.kicker == ""
        assert schema.event_meta is None

    def test_full_schema_with_optional_slots(self) -> None:
        schema = PosterContentSchema(
            headline="Raya Sale",
            body_text="Up to 50% off",
            cta="Shop Now",
            background_image="/tmp/sale.jpg",
            subheadline="This weekend only",
            kicker="LIMITED TIME",
            offer_block={"discount": "50%", "validity": "April 10-12"},
            badge="SALE",
            footer="Terms apply. While stocks last.",
        )
        assert schema.badge == "SALE"
        assert schema.offer_block["discount"] == "50%"

    def test_backward_compat_to_legacy_dict(self) -> None:
        schema = PosterContentSchema(
            headline="Test",
            body_text="Body",
            cta="CTA",
            background_image="/tmp/img.jpg",
        )
        legacy = schema.to_legacy_dict()
        assert set(legacy.keys()) == {"headline", "subheadline", "cta", "body_text", "background_image"}

    def test_active_slots_returns_populated_only(self) -> None:
        schema = PosterContentSchema(
            headline="H",
            body_text="B",
            cta="C",
            background_image="/tmp/i.jpg",
            kicker="K",
        )
        active = schema.active_optional_slots()
        assert "kicker" in active
        assert "badge" not in active
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Write PosterContentSchema**

```python
# contracts/poster.py
from __future__ import annotations

from pydantic import BaseModel, Field


class PosterContentSchema(BaseModel):
    """Full poster content schema with required and optional slots.

    Ring 1 contract — slot names and types are stable.
    Ring 2 metadata — template _meta.yaml declares which optional slots it supports.
    Ring 3 data — filled content for a specific run.
    """

    # Required (every template must render these if provided)
    headline: str
    body_text: str
    cta: str
    background_image: str

    # Optional (templates declare support via _meta.yaml)
    subheadline: str = ""
    kicker: str = ""  # small text above headline
    event_meta: dict[str, str] | None = None  # date, time, venue, dress_code
    offer_block: dict[str, str] | None = None  # discount, original_price, sale_price, validity
    badge: str = ""  # corner badge: NEW, SALE, LIMITED
    price: str = ""
    footer: str = ""  # fine print, address, contact
    disclaimer: str = ""
    logo_treatment: str = ""  # top-right-circle | bottom-left-inline | watermark
    secondary_cta: str = ""

    def to_legacy_dict(self) -> dict[str, str]:
        """Backward compat: return the original 4+1 field dict for existing templates."""
        return {
            "headline": self.headline,
            "subheadline": self.subheadline,
            "cta": self.cta,
            "body_text": self.body_text,
            "background_image": self.background_image,
        }

    def active_optional_slots(self) -> set[str]:
        """Return names of optional slots that have non-empty values."""
        optional_fields = {
            "subheadline", "kicker", "event_meta", "offer_block", "badge",
            "price", "footer", "disclaimer", "logo_treatment", "secondary_cta",
        }
        active: set[str] = set()
        for name in optional_fields:
            val = getattr(self, name)
            if val:  # truthy: non-empty string, non-None dict
                active.add(name)
        return active
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: pyright check**
- [ ] **Step 6: Commit**

```bash
git add contracts/poster.py tests/test_poster_contract.py
git commit -m "feat(contracts): add PosterContentSchema with optional slots"
```

---

### Task 3: Adherence rubric config (Ring 2)

**Files:**
- Create: `config/quality_frameworks/adherence_rubric.yaml`

- [ ] **Step 1: Write adherence rubric**

```yaml
# adherence_rubric.yaml
# Brief-adherence scoring dimensions — supplements posteriq_quality_dimensions.yaml
# Used by quality harness and runtime adherence gating (2.8)

dimensions:
  occasion_match:
    description: "Does the output reflect the requested occasion/theme?"
    weight: 0.25
    criteria:
      - "Theme/occasion clearly present in visual and textual elements"
      - "Seasonal or cultural markers appropriate for the occasion"
      - "Tone matches the occasion (festive, formal, urgent, etc.)"

  audience_fit:
    description: "Is the output appropriate for the target audience?"
    weight: 0.20
    criteria:
      - "Language register matches audience (formal, casual, corporate)"
      - "Visual style appeals to target demographic"
      - "Vocabulary and references are audience-appropriate"

  content_completeness:
    description: "Are all must-include elements present and must-avoid respected?"
    weight: 0.25
    criteria:
      - "All must-include items from brief appear in output"
      - "No must-avoid items present in output"
      - "Required commercial info (date, venue, price) clearly visible"

  reference_fidelity:
    description: "If a reference was provided, is it reflected in the output?"
    weight: 0.15
    criteria:
      - "Composition echoes reference layout when provided"
      - "Color palette draws from reference when specified"
      - "Style elements (typography weight, image treatment) aligned"

  output_variety:
    description: "Is this output visually distinct from recent similar briefs?"
    weight: 0.15
    criteria:
      - "Layout differs from last 3 outputs for same client"
      - "Template choice varies across similar occasion types"
      - "Not a near-duplicate of recent production"

scoring:
  scale: "1-5"
  thresholds:
    fail: 2.0
    marginal: 3.0
    pass: 3.5
    good: 4.0
    excellent: 4.5
```

- [ ] **Step 2: Commit**

```bash
git add config/quality_frameworks/adherence_rubric.yaml
git commit -m "feat(quality): add brief-adherence rubric dimensions"
```

---

### Task 4: Benchmark corpus

**Files:**
- Create: `evaluations/benchmark/poster_briefs.yaml`

- [ ] **Step 1: Write benchmark corpus**

10-15 diverse poster briefs covering different occasions, audiences, tones, and slot requirements. Each brief has expected properties for scoring.

```yaml
# evaluations/benchmark/poster_briefs.yaml
# Frozen benchmark briefs for quality measurement.
# Each brief exercises different template families, content slots, and adherence patterns.

version: "1.0"
briefs:
  - id: bench_festive_raya
    raw_input: "Create a Hari Raya open house poster for DMB halal catering. Include date 10 April, venue Dewan Komuniti Shah Alam, dress code baju Melayu. Warm festive mood."
    client_id: dmb
    expected:
      occasion: hari_raya
      mood: festive
      text_density: moderate
      must_include: ["date", "venue", "dress code"]
      required_slots: [headline, body_text, cta, event_meta]

  - id: bench_corporate_launch
    raw_input: "Design a product launch poster for AutoHub's new SUV model X7. Professional look, premium feel. Include price from RM 189,000."
    client_id: autohub
    expected:
      occasion: product_launch
      mood: professional
      text_density: minimal
      required_slots: [headline, cta, price]

  - id: bench_sale_promo
    raw_input: "50% off Ramadan sale poster for DMB. Valid 1-30 March. All menu items. Urgent, bold design."
    client_id: dmb
    expected:
      occasion: sale
      mood: urgent
      text_density: moderate
      must_include: ["50%", "dates"]
      required_slots: [headline, cta, offer_block, badge]

  - id: bench_event_invitation
    raw_input: "Annual gala dinner invitation poster. Black tie event, 15 May 2026, Grand Hyatt KL. Elegant and formal."
    client_id: default
    expected:
      occasion: event
      mood: formal
      text_density: moderate
      must_include: ["date", "venue", "dress code"]
      required_slots: [headline, cta, event_meta, footer]

  - id: bench_road_safety
    raw_input: "Road safety awareness poster for Autohub. Buckle up campaign. Clear message, high contrast."
    client_id: autohub
    expected:
      occasion: awareness
      mood: serious
      text_density: minimal
      required_slots: [headline, body_text, cta]

  - id: bench_minimal_brief
    raw_input: "Poster for DMB"
    client_id: dmb
    expected:
      occasion: ""
      mood: ""
      text_density: moderate
      required_slots: [headline, cta]

  - id: bench_malay_festive
    raw_input: "Buat poster Maulidur Rasul untuk DMB. Tema hijau dan emas. Sertakan tarikh 27 September."
    client_id: dmb
    expected:
      occasion: maulidur_rasul
      mood: festive
      text_density: moderate
      must_include: ["tarikh"]
      required_slots: [headline, body_text, cta]

  - id: bench_playful_kids
    raw_input: "Fun children's day poster for a community event. Bright colors, playful fonts. Include games, face painting, balloon art. Free entry."
    client_id: default
    expected:
      occasion: community_event
      mood: playful
      text_density: dense
      must_include: ["games", "face painting", "free entry"]
      required_slots: [headline, body_text, cta, kicker]

  - id: bench_premium_announcement
    raw_input: "AutoHub is now an authorized BMW dealer. Premium announcement poster. Sophisticated, understated."
    client_id: autohub
    expected:
      occasion: announcement
      mood: premium
      text_density: minimal
      required_slots: [headline, subheadline, cta]

  - id: bench_health_awareness
    raw_input: "Health screening day poster. Free blood pressure and glucose checks. Saturday 20 April, 9am-1pm, Klinik Komuniti Subang. Bring IC."
    client_id: default
    expected:
      occasion: health
      mood: caring
      text_density: dense
      must_include: ["date", "time", "venue", "bring IC"]
      required_slots: [headline, body_text, cta, event_meta, footer]
```

- [ ] **Step 2: Commit**

```bash
git add evaluations/benchmark/poster_briefs.yaml
git commit -m "feat(quality): add 10-brief benchmark corpus for poster quality measurement"
```

---

## Chunk 2: Brief Interpreter + Copy Enrichment

### Task 5: Brief interpreter tool

**Files:**
- Create: `tools/brief_interpreter.py`
- Test: `tests/test_brief_interpreter.py`
- Modify: `tools/orchestrate.py` (call interpreter, write to DB, add to job_context)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_brief_interpreter.py
from __future__ import annotations

from unittest.mock import patch

import pytest
from contracts.interpreted_intent import InterpretedIntent


class TestBriefInterpreter:
    def test_interpret_returns_typed_intent(self) -> None:
        mock_response = {
            "content": '{"occasion":"hari_raya","audience":"malay_families","mood":"festive","layout_hint":"","text_density":"moderate","cta_style":"medium","cultural_context":"islamic_festive","must_include":["date","venue"],"must_avoid":[]}',
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            from tools.brief_interpreter import interpret_brief

            result = interpret_brief("Create a Hari Raya poster with date and venue")

        assert isinstance(result.intent, InterpretedIntent)
        assert result.intent.occasion == "hari_raya"
        assert "date" in result.intent.must_include
        assert result.input_tokens == 100

    def test_interpret_handles_malformed_json(self) -> None:
        mock_response = {
            "content": "not valid json {",
            "input_tokens": 50,
            "output_tokens": 20,
            "cost_usd": 0.0005,
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            from tools.brief_interpreter import interpret_brief

            result = interpret_brief("Some brief")

        # Should return a default intent, not crash
        assert isinstance(result.intent, InterpretedIntent)
        assert result.intent.occasion == ""

    def test_interpret_minimal_brief_returns_sparse_intent(self) -> None:
        mock_response = {
            "content": '{"occasion":"","audience":"","mood":"","layout_hint":"","text_density":"moderate","cta_style":"medium","cultural_context":"","must_include":[],"must_avoid":[]}',
            "input_tokens": 80,
            "output_tokens": 40,
            "cost_usd": 0.0008,
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            from tools.brief_interpreter import interpret_brief

            result = interpret_brief("Poster for DMB")

        assert result.intent.text_density == "moderate"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_brief_interpreter.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write brief_interpreter.py**

```python
# tools/brief_interpreter.py
"""One-shot brief interpretation via GPT-5.4-mini structured output.

Ring 2 behavior — the extraction prompt and category vocabulary live here
and can be changed without modifying the Ring 1 InterpretedIntent contract.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from contracts.interpreted_intent import InterpretedIntent
from utils.call_llm import call_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a brief interpreter for a design production engine.
Given a raw production request, extract structured intent.

Output ONLY a JSON object with these exact keys:
- occasion: string (e.g. "hari_raya", "product_launch", "sale", "event", "awareness", "announcement", "")
- audience: string (e.g. "malay_families", "corporate", "general_public", "bargain_shoppers", "")
- mood: string (e.g. "festive", "professional", "urgent", "playful", "formal", "premium", "caring", "")
- layout_hint: string (e.g. "full_bleed_hero", "split_layout", "minimal", "")
- text_density: "minimal" | "moderate" | "dense"
- cta_style: "high" | "medium" | "low" | "none"
- cultural_context: string (e.g. "islamic_festive", "chinese_new_year", "malaysian_corporate", "")
- must_include: list of strings the output MUST contain (dates, venues, prices, etc.)
- must_avoid: list of strings the output MUST NOT contain

If information is not in the brief, use empty string or empty list. Do not guess."""


@dataclass(frozen=True)
class InterpretationResult:
    """Result of brief interpretation with token metrics."""

    intent: InterpretedIntent
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


def interpret_brief(
    raw_input: str,
    *,
    model: str = "gpt-5.4-mini",
) -> InterpretationResult:
    """Extract structured intent from a raw brief via LLM.

    Returns InterpretationResult with typed intent and token metrics.
    Never raises — returns default intent on failure.
    """
    result = call_llm(
        stable_prefix=[{"role": "system", "content": _SYSTEM_PROMPT}],
        variable_suffix=[{"role": "user", "content": raw_input}],
        model=model,
        temperature=0.2,
        max_tokens=400,
        response_format={"type": "json_object"},
        operation_type="extract",
    )

    try:
        parsed = json.loads(result.get("content", "{}"))
        intent = InterpretedIntent.model_validate(parsed)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Brief interpretation failed to parse: %s", exc)
        intent = InterpretedIntent()

    return InterpretationResult(
        intent=intent,
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        cost_usd=result.get("cost_usd", 0.0),
    )
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: pyright check**

Run: `pyright tools/brief_interpreter.py`

- [ ] **Step 6: Commit**

```bash
git add tools/brief_interpreter.py tests/test_brief_interpreter.py
git commit -m "feat(tools): add brief interpreter — one-shot intent extraction"
```

---

### Task 6: Wire interpreter into orchestrate.py

**Files:**
- Modify: `tools/orchestrate.py` — call interpreter after routing, write to DB, add to job_context

- [ ] **Step 1: Write the failing test**

Add to `tests/test_orchestrate.py`:

```python
class TestInterpretedIntentWiring:
    """Verify that interpreted intent is extracted and added to job_context."""

    def test_job_context_contains_interpreted_intent(self) -> None:
        """run_governed adds interpreted_intent to job_context."""
        # Uses the stub workflow which captures job_context
        from unittest.mock import patch, MagicMock
        from contracts.interpreted_intent import InterpretedIntent
        from tools.brief_interpreter import InterpretationResult

        mock_intent = InterpretationResult(
            intent=InterpretedIntent(occasion="test", mood="professional"),
        )

        with patch("tools.orchestrate.interpret_brief", return_value=mock_intent):
            from tools.orchestrate import run_governed
            # Use the test fixture pattern from existing tests
            # ... (adapt to existing test patterns in the file)
```

- [ ] **Step 2: Add interpreter call to run_governed**

In `tools/orchestrate.py`, after routing (Step 1) and before readiness (Step 2):

```python
# Step 1.5: Interpret brief (hardening 2.3)
from tools.brief_interpreter import interpret_brief
interpretation = interpret_brief(raw_input)
interpreted_intent = interpretation.intent
```

After building `job_context` dict, add:

```python
job_context["interpreted_intent"] = interpreted_intent.to_jsonb()
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_orchestrate.py -v`

- [ ] **Step 4: pyright check**
- [ ] **Step 5: Commit**

```bash
git add tools/orchestrate.py tests/test_orchestrate.py
git commit -m "feat(orchestrate): wire brief interpreter into governed execution"
```

---

### Task 7: Enrich copy generation with interpreted intent

**Files:**
- Modify: `tools/registry.py:1324-1380` (`_generate_poster`)

- [ ] **Step 1: Update _generate_poster to inject intent**

In `_generate_poster()`, after building `system_content` and `brand_lines`, inject interpreted intent:

```python
# Inject interpreted intent for occasion-aware copy (hardening 2.7)
intent_data = job_ctx.get("interpreted_intent")
if intent_data:
    intent_lines: list[str] = []
    if intent_data.get("occasion"):
        intent_lines.append(f"Occasion: {intent_data['occasion']}")
    if intent_data.get("audience"):
        intent_lines.append(f"Target audience: {intent_data['audience']}")
    if intent_data.get("mood"):
        intent_lines.append(f"Mood/tone: {intent_data['mood']}")
    if intent_data.get("must_include"):
        intent_lines.append(f"MUST include: {', '.join(intent_data['must_include'])}")
    if intent_data.get("must_avoid"):
        intent_lines.append(f"MUST NOT include: {', '.join(intent_data['must_avoid'])}")
    if intent_data.get("cultural_context"):
        intent_lines.append(f"Cultural context: {intent_data['cultural_context']}")
    if intent_lines:
        system_content += "\n\nBrief intent:\n" + "\n".join(intent_lines)
```

- [ ] **Step 2: Extend copy output to produce optional slots**

Update the copy generation prompt to request additional slots when intent signals them:

```python
# Extend output schema based on intent (hardening 2.4)
slot_instruction = (
    "Generate poster copy. Output ONLY a JSON object with these keys: "
    "headline, subheadline, cta, body_text"
)
if intent_data:
    extra_slots: list[str] = []
    if intent_data.get("occasion") in ("sale", "promo"):
        extra_slots.extend(["offer_block", "badge"])
    if any(k in str(intent_data) for k in ("date", "venue", "time")):
        extra_slots.append("event_meta")
    if intent_data.get("text_density") == "dense":
        extra_slots.append("footer")
    # ... kicker for minimal density, etc.
    if extra_slots:
        slot_instruction += ", " + ", ".join(extra_slots)

slot_instruction += ". body_text is newline-separated bullet points. "
```

- [ ] **Step 3: Update _parse_poster_copy to handle new slots**

Extend `_parse_poster_copy()` at `registry.py:631` to extract all PosterContentSchema slots:

```python
def _parse_poster_copy(copy_text: str) -> dict[str, Any]:
    # ... existing JSON parse logic ...
    # Extended result with optional slots
    result: dict[str, Any] = {
        "headline": "", "subheadline": "", "cta": "", "body_text": "",
        "kicker": "", "badge": "", "price": "", "footer": "", "disclaimer": "",
        "secondary_cta": "",
        "event_meta": None, "offer_block": None,
    }
    # ... rest of parsing ...
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_orchestrate.py tests/test_registry_tools.py -v`

- [ ] **Step 5: pyright check**
- [ ] **Step 6: Commit**

```bash
git add tools/registry.py
git commit -m "feat(copy): enrich poster generation with interpreted intent and extended slots"
```

---

## Chunk 3: Template Library + Selector

### Task 8: Create poster template library (Ring 2)

**Files:**
- Create: `templates/html/poster_editorial_split.html` + `poster_editorial_split_meta.yaml`
- Create: `templates/html/poster_diagonal_cut.html` + `poster_diagonal_cut_meta.yaml`
- Create: `templates/html/poster_bold_knockout.html` + `poster_bold_knockout_meta.yaml`
- Create: `templates/html/poster_floating_card.html` + `poster_floating_card_meta.yaml`
- Create: `templates/html/poster_center_stage.html` + `poster_center_stage_meta.yaml`
- Create: `templates/html/poster_stacked_type.html` + `poster_stacked_type_meta.yaml`
- Create: `templates/html/poster_minimal_clean.html` + `poster_minimal_clean_meta.yaml`
- Create: `templates/html/poster_promo_grid.html` + `poster_promo_grid_meta.yaml`
- Create: `templates/html/poster_default_meta.yaml` (retroactive meta for existing template)
- Create: `templates/html/poster_road_safety_meta.yaml` (retroactive meta for existing template)

Each template follows the same 794×1123px viewport, Jinja2 slot convention, and CSS patterns from `poster_default.html`. Each `_meta.yaml` declares:

```yaml
density: moderate          # minimal | moderate | dense
tone_fit: [professional, corporate]
occasion_fit: [product_launch, announcement]
cta_prominence: medium     # high | medium | low
hero_style: split          # full_bleed | contained | split | minimal
supported_slots: [headline, subheadline, cta, body_text, kicker]
```

- [ ] **Step 1: Create meta files for existing templates**

`poster_default_meta.yaml`:
```yaml
density: moderate
tone_fit: [professional, versatile, corporate, festive]
occasion_fit: [product_launch, announcement, event, corporate, awareness]
cta_prominence: high
hero_style: full_bleed
supported_slots: [headline, subheadline, cta, body_text]
```

`poster_road_safety_meta.yaml`:
```yaml
density: moderate
tone_fit: [serious, urgent]
occasion_fit: [awareness, road_safety, public_service]
cta_prominence: high
hero_style: full_bleed
supported_slots: [headline, subheadline, cta, body_text]
```

- [ ] **Step 2: Create poster_editorial_split.html**

55/45 image|text grid with vertical divider. Image fills left panel, text content on right with colored background. Good for corporate and product launches.

- [ ] **Step 3: Create poster_floating_card.html**

Content card floating on image background with frosted glass effect. Good for premium announcements and formal events.

- [ ] **Step 4: Create poster_bold_knockout.html**

Large knockout typography with image showing through letter forms. Good for bold, high-impact briefs (sales, launches).

- [ ] **Step 5: Create poster_center_stage.html**

Radial vignette, centered content stack. Good for festive, celebratory, and community events.

- [ ] **Step 6: Create poster_stacked_type.html**

Typography-led minimal image. Good for text-heavy formal communications, announcements.

- [ ] **Step 7: Create poster_minimal_clean.html**

Generous whitespace, premium feel. Good for luxury, understated, premium brands.

- [ ] **Step 8: Create poster_promo_grid.html**

Price block, offer badge, sale-oriented grid layout. Supports offer_block and badge slots. Good for sales and promotions.

- [ ] **Step 9: Create poster_diagonal_cut.html**

Image clipped at diagonal with accent stripe. High-energy layout for events and launches.

- [ ] **Step 10: Commit**

```bash
git add templates/html/poster_*
git commit -m "feat(templates): add 8 poster layout families with metadata"
```

---

### Task 9: Template selector (Ring 2 logic)

**Files:**
- Create: `tools/template_selector.py`
- Test: `tests/test_template_selector.py`
- Modify: `tools/registry.py` — replace `_resolve_template_name` and `_TEMPLATE_ALIASES`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_template_selector.py
from __future__ import annotations

import pytest
from contracts.interpreted_intent import InterpretedIntent


class TestTemplateSelector:
    def test_festive_brief_selects_center_stage(self) -> None:
        from tools.template_selector import select_template

        intent = InterpretedIntent(occasion="hari_raya", mood="festive", text_density="moderate")
        result = select_template(intent)
        # Should NOT always be poster_default
        assert result.template_name != "" 
        assert result.score > 0

    def test_sale_brief_selects_promo_grid(self) -> None:
        from tools.template_selector import select_template

        intent = InterpretedIntent(
            occasion="sale", mood="urgent", text_density="moderate", cta_style="high",
        )
        result = select_template(intent, active_slots={"offer_block", "badge"})
        assert result.template_name == "poster_promo_grid"

    def test_minimal_brief_falls_back_to_default(self) -> None:
        from tools.template_selector import select_template

        intent = InterpretedIntent()
        result = select_template(intent)
        assert result.template_name == "poster_default"

    def test_different_moods_produce_different_templates(self) -> None:
        from tools.template_selector import select_template

        festive = select_template(InterpretedIntent(mood="festive", occasion="hari_raya"))
        premium = select_template(InterpretedIntent(mood="premium", occasion="announcement"))
        urgent = select_template(InterpretedIntent(mood="urgent", occasion="sale"), 
                                  active_slots={"offer_block"})
        templates = {festive.template_name, premium.template_name, urgent.template_name}
        assert len(templates) >= 2, f"Expected variety, got: {templates}"
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Write template_selector.py**

```python
# tools/template_selector.py
"""Intent-aware template selection — scores templates against interpreted intent.

Ring 2 logic — the scoring weights and metadata are config-driven.
Template _meta.yaml files are the source of truth for template capabilities.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from contracts.interpreted_intent import InterpretedIntent

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "html"


@dataclass(frozen=True)
class TemplateMatch:
    template_name: str
    score: float
    reasons: tuple[str, ...] = ()


def _load_template_meta() -> dict[str, dict[str, object]]:
    """Load all *_meta.yaml files from templates/html/."""
    meta: dict[str, dict[str, object]] = {}
    for meta_path in _TEMPLATES_DIR.glob("*_meta.yaml"):
        template_name = meta_path.stem.replace("_meta", "")
        try:
            data = yaml.safe_load(meta_path.read_text()) or {}
            meta[template_name] = data
        except Exception as exc:
            logger.warning("Failed to load %s: %s", meta_path, exc)
    return meta


def select_template(
    intent: InterpretedIntent,
    *,
    active_slots: set[str] | None = None,
    client_style_hint: str = "",
) -> TemplateMatch:
    """Score all templates against intent and return best match."""
    catalog = _load_template_meta()
    if not catalog:
        return TemplateMatch(template_name="poster_default", score=0.0)

    active_slots = active_slots or set()
    best = TemplateMatch(template_name="poster_default", score=0.0)

    for name, meta in catalog.items():
        score = 0.0
        reasons: list[str] = []

        # Mood ↔ tone_fit
        tone_fit = set(meta.get("tone_fit", []))
        if intent.mood and intent.mood in tone_fit:
            score += 3.0
            reasons.append(f"mood '{intent.mood}' matches tone_fit")
        elif "versatile" in tone_fit:
            score += 0.5

        # Occasion ↔ occasion_fit
        occasion_fit = set(meta.get("occasion_fit", []))
        if intent.occasion and intent.occasion in occasion_fit:
            score += 3.0
            reasons.append(f"occasion '{intent.occasion}' matches")

        # Text density ↔ density
        template_density = meta.get("density", "moderate")
        if intent.text_density == template_density:
            score += 1.5
            reasons.append("density matches")

        # CTA ↔ cta_prominence
        template_cta = meta.get("cta_prominence", "medium")
        if intent.cta_style == template_cta:
            score += 1.0

        # Slot compatibility
        supported = set(meta.get("supported_slots", []))
        if active_slots:
            overlap = active_slots & supported
            missing = active_slots - supported
            score += len(overlap) * 0.5
            score -= len(missing) * 1.0  # penalize missing required slots
            if missing:
                reasons.append(f"missing slots: {missing}")

        if score > best.score:
            best = TemplateMatch(
                template_name=name,
                score=score,
                reasons=tuple(reasons),
            )

    return best
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: pyright check**
- [ ] **Step 6: Commit**

```bash
git add tools/template_selector.py tests/test_template_selector.py
git commit -m "feat(tools): add intent-aware template selector"
```

---

### Task 10: Wire selector into registry.py

**Files:**
- Modify: `tools/registry.py:88-119` — replace `_TEMPLATE_ALIASES` and `_resolve_template_name`

- [ ] **Step 1: Replace _resolve_template_name**

```python
def _resolve_template_name(job_ctx: dict[str, Any], *, workflow: str) -> str:
    """Resolve a concrete render template from job context via intent-aware scoring."""
    if workflow != "poster_production":
        return "poster"

    # Backward compat: explicit template_name overrides selector
    explicit = job_ctx.get("template_name")
    if explicit and (_HTML_TEMPLATES_DIR / f"{explicit}.html").exists():
        return str(explicit)

    # Intent-aware selection (hardening 2.6)
    from contracts.interpreted_intent import InterpretedIntent
    from tools.template_selector import select_template

    intent_data = job_ctx.get("interpreted_intent", {})
    try:
        intent = InterpretedIntent.model_validate(intent_data) if intent_data else InterpretedIntent()
    except Exception:
        intent = InterpretedIntent()

    # Determine active optional slots from parsed copy
    active_slots: set[str] = set()
    # (populated by copy stage if available in job_ctx)

    match = select_template(
        intent,
        active_slots=active_slots,
        client_style_hint=job_ctx.get("design_system", ""),
    )

    if (_HTML_TEMPLATES_DIR / f"{match.template_name}.html").exists():
        return match.template_name
    return "poster_default"
```

- [ ] **Step 2: Remove _TEMPLATE_ALIASES**

Delete lines 88-93 (`_TEMPLATE_ALIASES` dict). It's fully replaced by the selector.

- [ ] **Step 3: Run tests**
- [ ] **Step 4: Commit**

```bash
git add tools/registry.py
git commit -m "feat(registry): replace template aliases with intent-aware selector"
```

---

## Chunk 4: Adherence Gating + Quality Harness

### Task 11: Runtime adherence scoring

**Files:**
- Modify: `tools/visual_scoring.py` — add adherence scoring
- Create: `config/quality_frameworks/adherence_dimensions.yaml`

- [ ] **Step 1: Create adherence dimensions config**

```yaml
# adherence_dimensions.yaml
# Loaded by visual_scoring.py for brief-adherence assessment

dimensions:
  occasion_match:
    prompt: "Does this poster clearly reflect the occasion '{occasion}'? Score 1-5."
    weight: 0.30
  content_completeness:
    prompt: "Are these required elements present and visible: {must_include}? Score 1-5."
    weight: 0.35
  tone_alignment:
    prompt: "Does the visual and textual tone match '{mood}'? Score 1-5."
    weight: 0.35
```

- [ ] **Step 2: Add adherence scoring function to visual_scoring.py**

```python
def score_adherence(
    image_bytes: bytes,
    interpreted_intent: dict[str, Any],
    *,
    model: str = "gpt-5.4-mini",
) -> dict[str, Any]:
    """Score poster adherence to interpreted intent (brief fidelity)."""
    # ... LLM critique with intent-specific prompts ...
```

- [ ] **Step 3: Wire into executor tripwire**

In `tools/executor.py`, add adherence score to production_trace alongside existing visual quality scores. Tripwire revision loop uses adherence failures as specific feedback.

- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

```bash
git add tools/visual_scoring.py config/quality_frameworks/adherence_dimensions.yaml
git commit -m "feat(quality): add runtime adherence scoring for brief fidelity"
```

---

### Task 12: Quality harness tool

**Files:**
- Create: `tools/quality_harness.py`
- Test: `tests/test_quality_harness.py`

- [ ] **Step 1: Write quality_harness.py**

```python
# tools/quality_harness.py
"""Offline quality measurement — runs benchmark briefs through scoring rubric.

Not a production tool. Used to measure and track quality floor.
"""
```

Takes benchmark briefs from `evaluations/benchmark/poster_briefs.yaml`, runs interpreted intent + adherence rubric scoring (without full pipeline execution), and reports per-dimension scores.

- [ ] **Step 2: Run tests**
- [ ] **Step 3: Commit**

```bash
git add tools/quality_harness.py tests/test_quality_harness.py
git commit -m "feat(quality): add offline quality harness for benchmark scoring"
```

---

## Update expand_brief() + exemplar curation

### Task 13: Update expand_brief() to consume interpreted intent

**Files:**
- Modify: `tools/image.py:122-167`

- [ ] **Step 1: Add interpreted_intent parameter to expand_brief**

```python
@track_span
def expand_brief(
    raw_brief: str,
    brand_config: dict[str, Any] | None = None,
    interpreted_intent: dict[str, Any] | None = None,
) -> dict[str, str]:
```

When `interpreted_intent` is provided, inject it into the expansion prompt so expand_brief does visual elaboration rather than redundant parsing.

- [ ] **Step 2: Run tests**
- [ ] **Step 3: Commit**

```bash
git add tools/image.py
git commit -m "feat(image): expand_brief consumes interpreted intent, avoids duplicate parse"
```

---

### Task 14: Exemplar curation (deferred to production)

This task requires running the full pipeline with the hardened templates and scoring real outputs. It cannot be completed until Tasks 5-11 are live and producing quality output.

**Defer to post-hardening:** Run 10-15 benchmark briefs, rate outputs, promote best to exemplars with real CLIP embeddings.

---

## Verification

After all tasks complete:
1. `pytest` — all tests pass
2. `pyright` — clean on all modified files  
3. `scripts/smoke.sh` — passes (when DB is up)
4. Benchmark corpus processed through quality harness — median adherence >= 3.5/5
5. 10 representative briefs select >= 5 distinct template families
