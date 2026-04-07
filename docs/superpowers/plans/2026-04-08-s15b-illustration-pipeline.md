# S15b Illustration Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `tools/illustrate.py` — a stateful sequential illustration pipeline that maintains page-to-page consistency for children's book production via Kontext iterative image generation with CLIP verification.

**Architecture:** `IllustrationPipeline` class wraps fal.ai Kontext iterative generation with per-page CLIP verification, anchor frame resets every 8 pages, and position-aware character cropping. Uses existing `generate_image()` and `expand_brief()` from `tools/image.py`. Creative workshop flow implemented as standalone functions. All text generation on GPT-5.4-mini, all image gen via fal.ai.

**Tech Stack:** fal_client (image gen + URL upload), open_clip (CLIP ViT-B/32), PIL (cropping), Pydantic contracts (CharacterBible, StyleLock, NarrativeScaffold, RollingContext), MinIO (asset storage), TraceCollector (observability).

---

## Chunk 1: Foundation Utilities

### Task 1: fal.ai URL Upload Utility

Kontext needs a publicly accessible URL for `image_url`. Local paths and localhost MinIO presigned URLs won't work. fal_client provides `upload()` which returns a fal-hosted URL.

**Files:**
- Modify: `utils/storage.py`
- Test: `tests/test_storage_fal.py`

- [ ] **Step 1: Write failing test for `upload_to_fal()`**

```python
# tests/test_storage_fal.py
"""Tests for fal.ai URL upload utility."""
from __future__ import annotations

from unittest.mock import patch

from utils.storage import upload_to_fal


class TestUploadToFal:
    """upload_to_fal() returns a fal-hosted URL from raw bytes."""

    def test_returns_fal_url(self) -> None:
        with patch("utils.storage.fal_client") as mock_fal:
            mock_fal.upload.return_value = "https://fal.media/files/test/abc123.jpg"
            url = upload_to_fal(b"\xff\xd8\xff\xe0fake-jpeg", content_type="image/jpeg")
            assert url.startswith("https://")
            mock_fal.upload.assert_called_once()

    def test_passes_content_type(self) -> None:
        with patch("utils.storage.fal_client") as mock_fal:
            mock_fal.upload.return_value = "https://fal.media/files/test/abc123.png"
            upload_to_fal(b"\x89PNGfake", content_type="image/png")
            call_kwargs = mock_fal.upload.call_args
            # fal_client.upload accepts bytes directly
            assert call_kwargs[0][0] == b"\x89PNGfake"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_storage_fal.py -v`
Expected: FAIL — `ImportError: cannot import name 'upload_to_fal'`

- [ ] **Step 3: Implement `upload_to_fal()` in `utils/storage.py`**

Add at the end of `utils/storage.py` (after `object_exists()`):

```python
import fal_client  # type: ignore[import-untyped]


def upload_to_fal(
    data: bytes,
    content_type: str = "image/jpeg",
) -> str:
    """Upload image bytes to fal.ai storage and return a public URL.

    fal.ai's Kontext model requires a publicly accessible URL for
    ``image_url``. Local paths and localhost MinIO URLs are not
    reachable from fal.ai servers. This function uploads to fal.ai's
    own CDN and returns the hosted URL.

    Args:
        data: Raw image bytes.
        content_type: MIME type (default ``image/jpeg``).

    Returns:
        Publicly accessible fal.ai-hosted URL.
    """
    url: str = fal_client.upload(data, content_type=content_type)
    logger.info("Uploaded %d bytes to fal.ai: %s", len(data), url[:80])
    return url
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_storage_fal.py -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `cd /Users/Executor/vizier && python3.11 -m pyright utils/storage.py`
Expected: 0 errors

---

### Task 2: Position-Aware Character Cropping

Center-crop at 60% is naive — characters may be at `left_third` or `right_third` per `composition_guide.character_position`. Map position values to crop coordinates.

**Files:**
- Create: `utils/image_processing.py`
- Test: `tests/test_image_processing.py`

- [ ] **Step 1: Write failing tests for `crop_character_region()`**

```python
# tests/test_image_processing.py
"""Tests for position-aware character cropping."""
from __future__ import annotations

from io import BytesIO

from PIL import Image

from utils.image_processing import crop_character_region


def _make_test_image(width: int = 1024, height: int = 1024) -> bytes:
    """Create a solid-color test image."""
    img = Image.new("RGB", (width, height), color=(128, 128, 128))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestCropCharacterRegion:
    """crop_character_region() crops based on character_position."""

    def test_centre_crops_middle_60_percent(self) -> None:
        img_bytes = _make_test_image(1000, 1000)
        cropped = crop_character_region(img_bytes, character_position="centre")
        img = Image.open(BytesIO(cropped))
        # 60% of 1000 = 600
        assert img.width == 600
        assert img.height == 600

    def test_left_third_crops_left_region(self) -> None:
        img_bytes = _make_test_image(1000, 1000)
        cropped = crop_character_region(img_bytes, character_position="left_third")
        img = Image.open(BytesIO(cropped))
        # Left 60% = 600 wide, vertically centred 60% = 600 tall
        assert img.width == 600
        assert img.height == 600

    def test_right_third_crops_right_region(self) -> None:
        img_bytes = _make_test_image(1000, 1000)
        cropped = crop_character_region(img_bytes, character_position="right_third")
        img = Image.open(BytesIO(cropped))
        assert img.width == 600
        assert img.height == 600

    def test_unknown_position_falls_back_to_centre(self) -> None:
        img_bytes = _make_test_image(1000, 1000)
        cropped = crop_character_region(img_bytes, character_position="unknown")
        img = Image.open(BytesIO(cropped))
        assert img.width == 600

    def test_cropped_region_differs_by_position(self) -> None:
        """Left and right crops should produce different pixel data."""
        # Create gradient image so crops differ
        img = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (x * 2, y * 2, 0))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        left = crop_character_region(img_bytes, "left_third")
        right = crop_character_region(img_bytes, "right_third")
        assert left != right
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_image_processing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.image_processing'`

- [ ] **Step 3: Implement `crop_character_region()`**

```python
# utils/image_processing.py
"""Image processing utilities for the illustration pipeline.

Position-aware character cropping for CLIP consistency verification.
Uses composition_guide.character_position to determine crop region
rather than always center-cropping.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image

# Crop region = 60% of image dimensions.
# Position offsets map character_position to horizontal anchor.
_CROP_FRACTION = 0.6

_POSITION_X_ANCHOR: dict[str, float] = {
    "centre": 0.5,       # crop centred horizontally
    "left_third": 0.3,   # crop centred on left third
    "right_third": 0.7,  # crop centred on right third
}


def crop_character_region(
    image_bytes: bytes,
    character_position: str = "centre",
) -> bytes:
    """Crop the character region from an illustration.

    Uses ``character_position`` from ``CompositionGuide`` to determine
    where the character is likely placed, then crops a 60% region
    around that position.

    Args:
        image_bytes: Raw image bytes (JPEG/PNG).
        character_position: From ``CompositionGuide.character_position``
            — one of ``centre``, ``left_third``, ``right_third``.

    Returns:
        Cropped image as JPEG bytes.
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = img.size

    crop_w = int(width * _CROP_FRACTION)
    crop_h = int(height * _CROP_FRACTION)

    # Horizontal anchor — default to centre for unknown positions
    x_anchor = _POSITION_X_ANCHOR.get(character_position, 0.5)

    # Compute crop box, clamping to image bounds
    cx = int(width * x_anchor)
    x1 = max(0, cx - crop_w // 2)
    x2 = min(width, x1 + crop_w)
    x1 = max(0, x2 - crop_w)  # re-adjust if clamped on right

    # Vertical: always centre
    y1 = max(0, (height - crop_h) // 2)
    y2 = min(height, y1 + crop_h)

    cropped = img.crop((x1, y1, x2, y2))

    buf = BytesIO()
    cropped.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_image_processing.py -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `cd /Users/Executor/vizier && python3.11 -m pyright utils/image_processing.py`
Expected: 0 errors

---

### Task 3: Wire `check_visual_consistency()` in `tools/publish.py`

Replace the stub (lines 637-661) with real CLIP similarity using `encode_image()` from `utils/retrieval.py`.

**Files:**
- Modify: `tools/publish.py:637-661`
- Modify: `tests/test_publish.py` — update `TestConsistencyCheckerStub`

- [ ] **Step 1: Update test expectations — stub tests become real tests**

In `tests/test_publish.py`, replace `TestConsistencyCheckerStub` (lines 428-446) with tests that verify real CLIP scores:

```python
class TestVisualConsistency:
    """check_visual_consistency() returns real CLIP similarity scores."""

    def test_identical_images_pass(self) -> None:
        """Same image compared to itself should pass with high similarity."""
        img = FIXTURES / "page_1.png"
        result = check_visual_consistency(img, img, threshold=0.75)
        assert result["passed"] is True
        assert result["similarity"] > 0.99  # identical images

    def test_different_images_return_lower_score(self) -> None:
        """Different images should have lower similarity than identical."""
        img_a = FIXTURES / "page_1.png"
        img_b = FIXTURES / "page_2.png"
        result = check_visual_consistency(img_a, img_b, threshold=0.75)
        assert isinstance(result["passed"], bool)
        assert isinstance(result["similarity"], float)
        assert 0.0 <= result["similarity"] <= 1.0

    def test_returns_pass_fail_and_score_keys(self) -> None:
        img = FIXTURES / "page_1.png"
        result = check_visual_consistency(img, img)
        assert "passed" in result
        assert "similarity" in result

    def test_threshold_controls_pass_fail(self) -> None:
        """Impossibly high threshold should cause failure."""
        img = FIXTURES / "page_1.png"
        result = check_visual_consistency(img, img, threshold=1.01)
        assert result["passed"] is False
```

- [ ] **Step 2: Run tests to verify failure (old stub returns -1.0)**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_publish.py::TestVisualConsistency -v`
Expected: FAIL — `TestConsistencyCheckerStub` no longer exists / similarity is -1.0

- [ ] **Step 3: Replace stub with real CLIP implementation**

Replace `check_visual_consistency()` in `tools/publish.py` (lines 637-661):

```python
def check_visual_consistency(
    image_a: Path,
    image_b: Path,
    threshold: float = 0.75,
) -> dict[str, bool | float]:
    """Check visual consistency between two images using CLIP similarity.

    Encodes both images via CLIP ViT-B/32 and computes cosine similarity.

    Args:
        image_a: Path to the first image.
        image_b: Path to the second image.
        threshold: Minimum similarity score to pass (default 0.75).

    Returns:
        Dict with ``passed`` (bool) and ``similarity`` (float) keys.
    """
    from utils.retrieval import encode_image

    emb_a = encode_image(image_a.read_bytes())
    emb_b = encode_image(image_b.read_bytes())

    # Cosine similarity (embeddings are already L2-normalised)
    similarity = sum(a * b for a, b in zip(emb_a, emb_b))

    passed = similarity >= threshold
    logger.info(
        "Visual consistency: %s vs %s — %.4f (threshold=%.2f, %s)",
        image_a.name, image_b.name, similarity, threshold,
        "PASS" if passed else "FAIL",
    )
    return {"passed": passed, "similarity": similarity}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_publish.py::TestVisualConsistency -v`
Expected: PASS

- [ ] **Step 5: Run pyright on modified file**

Run: `cd /Users/Executor/vizier && python3.11 -m pyright tools/publish.py`
Expected: 0 errors

- [ ] **Step 6: Commit foundation utilities**

```bash
cd /Users/Executor/vizier
git add utils/storage.py utils/image_processing.py tools/publish.py \
    tests/test_storage_fal.py tests/test_image_processing.py tests/test_publish.py
git commit -m "feat(s15b): foundation utilities — fal upload, position-aware crop, CLIP consistency"
```

---

## Chunk 2: IllustrationPipeline Core

### Task 4: Pipeline Class Skeleton + State Management

**Files:**
- Create: `tools/illustrate.py`
- Create: `tests/test_illustrate.py`

- [ ] **Step 1: Write failing tests for pipeline initialisation and state**

```python
# tests/test_illustrate.py
"""Tests for the stateful illustration pipeline (S15b)."""
from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from contracts.publishing import (
    AgeGroup,
    CharacterBible,
    ClothingDescription,
    CompositionGuide,
    FaceDetails,
    HairDetails,
    NarrativeScaffold,
    PageScaffold,
    PageTurnEffect,
    PhysicalDescription,
    ReferenceImages,
    StyleLock,
    StyleNotes,
    TextImageRelationship,
    TextPlacementStrategy,
)
from tools.illustrate import IllustrationPipeline


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_test_image(width: int = 1024, height: int = 1024, color: tuple[int, int, int] = (128, 128, 128)) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _sample_character_bible() -> CharacterBible:
    return CharacterBible(
        character_id="aminah",
        name="Aminah",
        role="protagonist",
        physical=PhysicalDescription(
            age=7, ethnicity="Malay", skin_tone="#8D6E63",
            height="small", build="slender",
            face=FaceDetails(shape="round", eyes="large dark brown", nose="small", mouth="smiling"),
            hair=HairDetails(style="black straight, shoulder length", colour="#1A1A1A"),
        ),
        clothing=ClothingDescription(default="light blue baju kurung with white headscarf"),
        style_notes=StyleNotes(
            art_style="soft watercolour, warm tones",
            line_weight="thin, delicate",
            colour_palette="warm earth tones, soft pastels",
            never=["scary imagery", "violence"],
            always=["headscarf", "warm lighting"],
        ),
        reference_images=ReferenceImages(front_view="/tmp/test_ref_front.jpg"),
    )


def _sample_style_lock() -> StyleLock:
    return StyleLock(
        art_style="soft watercolour",
        palette=["#264653", "#FFF8F0", "#E76F51"],
        typography="Plus Jakarta Sans",
        text_placement_strategy=TextPlacementStrategy.text_always_below,
    )


def _sample_page(page_num: int = 1) -> PageScaffold:
    return PageScaffold(
        page=page_num,
        word_target=30,
        emotional_beat="curiosity",
        characters_present=["aminah"],
        checkpoint_progress=f"Page {page_num}",
        text_image_relationship=TextImageRelationship.complementary,
        illustration_shows="Aminah walking through a morning market, stalls with colourful fruit",
        page_turn_effect=PageTurnEffect.continuation,
        composition_guide=CompositionGuide(
            camera="medium_shot",
            character_position="centre",
            background_detail="detailed",
            colour_temperature="warm",
            text_zone="bottom_third",
        ),
    )


# ---------------------------------------------------------------------------
# Task 4: Pipeline init and state
# ---------------------------------------------------------------------------


class TestPipelineInit:
    """IllustrationPipeline initialises with correct state."""

    def test_init_sets_style_lock(self) -> None:
        sl = _sample_style_lock()
        pipeline = IllustrationPipeline(style_lock=sl, job_id="test-job")
        assert pipeline.style_lock == sl

    def test_init_empty_references(self) -> None:
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test-job")
        assert pipeline.character_references == {}

    def test_init_no_previous_page(self) -> None:
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test-job")
        assert pipeline.previous_page_image is None

    def test_init_empty_scores(self) -> None:
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test-job")
        assert pipeline.consistency_scores == []

    def test_get_anchor_status_initial(self) -> None:
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test-job")
        status = pipeline.get_anchor_status()
        assert status["pages_since_anchor"] == 0
        assert status["total_pages"] == 0
        assert status["avg_consistency"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestPipelineInit -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.illustrate'`

- [ ] **Step 3: Implement pipeline class skeleton**

```python
# tools/illustrate.py
"""Stateful sequential illustration pipeline for publishing (S15b).

Unlike tools/image.py (fire-and-forget for posters/marketing), this
maintains page-to-page state: previous page image feeds into next
generation, character references are tracked, consistency is verified
via CLIP after each page, and anchor frame resets prevent cumulative drift.

Illustrations are ALWAYS text-free (anti-drift #49).
Visual brief expansion ALWAYS runs before generation (anti-drift #25).
All text tasks on GPT-5.4-mini (anti-drift #54).
"""
from __future__ import annotations

import logging
from pathlib import Path

from contracts.publishing import (
    CharacterBible,
    PageScaffold,
    StyleLock,
)
from contracts.trace import TraceCollector

logger = logging.getLogger(__name__)

# Image generation cost per page (Kontext)
_KONTEXT_COST_USD = 0.04
_ANCHOR_INTERVAL = 8


class IllustrationPipeline:
    """Stateful pipeline for sequential illustration with consistency tracking.

    State per project:
        character_references — CharacterBible ID -> curated reference image paths
        character_ref_embeddings — cached CLIP embeddings for references
        style_lock — locked art direction from creative workshop
        previous_page_image — fal-hosted URL fed to Kontext as image_url
        anchor_image_url — curated reference URL, reset target every 8 pages
        consistency_scores — running CLIP scores per page
        collector — TraceCollector for production observability
    """

    def __init__(
        self,
        *,
        style_lock: StyleLock,
        job_id: str,
    ) -> None:
        self.style_lock = style_lock
        self.job_id = job_id
        self.character_references: dict[str, list[Path]] = {}
        self.character_ref_embeddings: dict[str, list[list[float]]] = {}
        self.previous_page_image: str | None = None  # fal-hosted URL
        self.anchor_image_url: str | None = None
        self.pages_since_anchor: int = 0
        self.total_pages: int = 0
        self.consistency_scores: list[float] = []
        self.collector = TraceCollector(job_id=job_id)

    def get_anchor_status(self) -> dict[str, int | float]:
        """Return current anchor state for operator visibility."""
        avg = (
            sum(self.consistency_scores) / len(self.consistency_scores)
            if self.consistency_scores
            else 0.0
        )
        return {
            "pages_since_anchor": self.pages_since_anchor,
            "total_pages": self.total_pages,
            "avg_consistency": round(avg, 4),
            "anchor_url": self.anchor_image_url or "",
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestPipelineInit -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `cd /Users/Executor/vizier && python3.11 -m pyright tools/illustrate.py`
Expected: 0 errors

---

### Task 5: Prompt Builder — `build_illustration_prompt()`

Composes the raw brief from illustration_shows + composition_guide + style_lock (art_style + palette) + character style notes + text-free instruction. This is then passed through `expand_brief()`.

**Files:**
- Modify: `tools/illustrate.py`
- Modify: `tests/test_illustrate.py`

- [ ] **Step 1: Write failing tests for prompt construction**

Add to `tests/test_illustrate.py`:

```python
from tools.illustrate import build_illustration_prompt


class TestBuildIllustrationPrompt:
    """Prompt is built from illustration_shows + composition + style, never page text."""

    def test_uses_illustration_shows(self) -> None:
        page = _sample_page()
        prompt = build_illustration_prompt(
            page=page,
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert "morning market" in prompt  # from illustration_shows
        assert "colourful fruit" in prompt

    def test_includes_composition_guide(self) -> None:
        page = _sample_page()
        prompt = build_illustration_prompt(
            page=page,
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert "medium_shot" in prompt or "medium shot" in prompt
        assert "warm" in prompt  # colour_temperature

    def test_includes_style_lock_art_style(self) -> None:
        page = _sample_page()
        prompt = build_illustration_prompt(
            page=page,
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert "watercolour" in prompt.lower()

    def test_includes_palette(self) -> None:
        page = _sample_page()
        prompt = build_illustration_prompt(
            page=page,
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert "#264653" in prompt or "264653" in prompt

    def test_includes_text_free_instruction(self) -> None:
        """Anti-drift #49: illustrations MUST be text-free."""
        page = _sample_page()
        prompt = build_illustration_prompt(
            page=page,
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        lower = prompt.lower()
        assert "no text" in lower or "text-free" in lower or "do not include any text" in lower

    def test_includes_character_style_notes(self) -> None:
        page = _sample_page()
        prompt = build_illustration_prompt(
            page=page,
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert "headscarf" in prompt.lower() or "baju kurung" in prompt.lower()

    def test_never_includes_page_text(self) -> None:
        """Anti-drift #49: prompt from illustration_shows, not page text."""
        page = _sample_page()
        page_text = "Si Arnab tinggal di tepi sungai yang sangat cantik."
        prompt = build_illustration_prompt(
            page=page,
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert page_text not in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestBuildIllustrationPrompt -v`
Expected: FAIL — `ImportError: cannot import name 'build_illustration_prompt'`

- [ ] **Step 3: Implement `build_illustration_prompt()`**

Add to `tools/illustrate.py`:

```python
def build_illustration_prompt(
    *,
    page: PageScaffold,
    style_lock: StyleLock,
    character_bibles: list[CharacterBible],
) -> str:
    """Build a structured illustration prompt from scaffold + style data.

    Composes: illustration_shows + composition_guide + style_lock
    (art_style + palette) + character style notes + text-free instruction.

    The result is intended to be passed through ``expand_brief()`` before
    being sent to ``generate_image()``.

    Args:
        page: PageScaffold with illustration_shows and composition_guide.
        style_lock: Locked visual parameters.
        character_bibles: Characters present on this page.

    Returns:
        Raw brief string for expansion.
    """
    guide = page.composition_guide
    parts: list[str] = [
        f"Scene: {page.illustration_shows}",
        f"Camera: {guide.camera}. Character position: {guide.character_position}.",
        f"Background: {guide.background_detail} detail. Colour temperature: {guide.colour_temperature}.",
        f"Art style: {style_lock.art_style}.",
        f"Colour palette: {', '.join(style_lock.palette)}.",
    ]

    # Character descriptions for characters present on this page
    present_ids = set(page.characters_present)
    for bible in character_bibles:
        if bible.character_id in present_ids:
            phys = bible.physical
            parts.append(
                f"Character '{bible.name}': {phys.ethnicity}, age {phys.age}, "
                f"{phys.build} build, {phys.hair.style} hair ({phys.hair.colour}), "
                f"skin tone {phys.skin_tone}. "
                f"Wearing {bible.clothing.default}. "
                f"Style: {bible.style_notes.art_style}, {bible.style_notes.line_weight} lines."
            )
            if bible.style_notes.always:
                parts.append(f"Always include: {', '.join(bible.style_notes.always)}.")
            if bible.style_notes.never:
                parts.append(f"Never include: {', '.join(bible.style_notes.never)}.")

    # Text-free enforcement (anti-drift #49)
    parts.append(
        "IMPORTANT: Do not include any text, words, letters, numbers, or writing "
        "in the illustration. The image must be completely text-free."
    )

    return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestBuildIllustrationPrompt -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `cd /Users/Executor/vizier && python3.11 -m pyright tools/illustrate.py`

---

### Task 6: `verify_consistency()` — Multi-Character CLIP Verification

Per-character position-aware cropping with cached reference embeddings. Returns minimum score across all characters present.

**Files:**
- Modify: `tools/illustrate.py`
- Modify: `tests/test_illustrate.py`

- [ ] **Step 1: Write failing tests for consistency verification**

Add to `tests/test_illustrate.py`:

```python
class TestVerifyConsistency:
    """CLIP consistency verification with position-aware cropping."""

    def test_identical_image_passes(self, tmp_path: Path) -> None:
        """Same image should produce very high similarity."""
        img_bytes = _make_test_image(color=(200, 100, 50))
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)
        gen_path = tmp_path / "gen.jpg"
        gen_path.write_bytes(img_bytes)

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        pipeline.character_references = {"aminah": [ref_path]}
        pipeline._cache_reference_embeddings()

        passed, score = pipeline.verify_consistency(
            generated_bytes=img_bytes,
            characters_present=["aminah"],
            character_position="centre",
        )
        assert passed is True
        assert score > 0.95

    def test_threshold_controls_result(self, tmp_path: Path) -> None:
        """Impossible threshold should fail."""
        img_bytes = _make_test_image()
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        pipeline.character_references = {"aminah": [ref_path]}
        pipeline._cache_reference_embeddings()

        passed, score = pipeline.verify_consistency(
            generated_bytes=img_bytes,
            characters_present=["aminah"],
            character_position="centre",
            threshold=1.01,
        )
        assert passed is False

    def test_cached_embeddings_used(self, tmp_path: Path) -> None:
        """Reference embeddings should be computed once and cached."""
        img_bytes = _make_test_image()
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        pipeline.character_references = {"aminah": [ref_path]}
        pipeline._cache_reference_embeddings()

        assert "aminah" in pipeline.character_ref_embeddings
        assert len(pipeline.character_ref_embeddings["aminah"]) == 1
        assert len(pipeline.character_ref_embeddings["aminah"][0]) == 512  # CLIP ViT-B/32

    def test_character_cropped_scores_more_stable_than_full_page(self, tmp_path: Path) -> None:
        """Character-cropped CLIP should be more stable when character is consistent
        but background varies (exit criterion)."""
        # Both images: same center character region, different edges
        base = Image.new("RGB", (100, 100), color=(200, 100, 50))
        # Image A: blue border
        img_a = Image.new("RGB", (100, 100), color=(0, 0, 255))
        img_a.paste(base.crop((20, 20, 80, 80)), (20, 20))
        buf_a = BytesIO()
        img_a.save(buf_a, format="JPEG")
        # Image B: green border
        img_b = Image.new("RGB", (100, 100), color=(0, 255, 0))
        img_b.paste(base.crop((20, 20, 80, 80)), (20, 20))
        buf_b = BytesIO()
        img_b.save(buf_b, format="JPEG")

        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(buf_a.getvalue())

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        pipeline.character_references = {"aminah": [ref_path]}
        pipeline._cache_reference_embeddings()

        # Cropped (centre) should yield higher similarity since centre is same
        _, cropped_score = pipeline.verify_consistency(
            generated_bytes=buf_b.getvalue(),
            characters_present=["aminah"],
            character_position="centre",
        )
        # Full-page CLIP for comparison
        from utils.retrieval import encode_image
        emb_a = encode_image(buf_a.getvalue())
        emb_b = encode_image(buf_b.getvalue())
        full_score = sum(a * b for a, b in zip(emb_a, emb_b))

        # Cropped should be >= full page (centre is same, borders differ)
        assert cropped_score >= full_score - 0.05  # small tolerance
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestVerifyConsistency -v`
Expected: FAIL

- [ ] **Step 3: Implement `verify_consistency()` and `_cache_reference_embeddings()`**

Add to `IllustrationPipeline` class in `tools/illustrate.py`:

```python
    def _cache_reference_embeddings(self) -> None:
        """Compute and cache CLIP embeddings for all character references.

        Called once after references are set. Avoids re-encoding 10+
        reference images on every page verification.
        """
        from utils.retrieval import encode_image

        self.character_ref_embeddings = {}
        for char_id, ref_paths in self.character_references.items():
            embeddings: list[list[float]] = []
            for ref_path in ref_paths:
                emb = encode_image(ref_path.read_bytes())
                embeddings.append(emb)
            self.character_ref_embeddings[char_id] = embeddings
            logger.info(
                "Cached %d reference embeddings for character '%s'",
                len(embeddings), char_id,
            )

    def verify_consistency(
        self,
        *,
        generated_bytes: bytes,
        characters_present: list[str],
        character_position: str = "centre",
        threshold: float = 0.75,
    ) -> tuple[bool, float]:
        """Verify character consistency via position-aware CLIP similarity.

        Crops the generated image based on character_position, encodes via
        CLIP, and compares against cached reference embeddings. Returns the
        minimum score across all characters present.

        Args:
            generated_bytes: Raw bytes of the generated illustration.
            characters_present: Character IDs to verify.
            character_position: From composition_guide.character_position.
            threshold: Minimum similarity to pass (default 0.75).

        Returns:
            Tuple of (passed, min_similarity_score).
        """
        from utils.image_processing import crop_character_region
        from utils.retrieval import encode_image

        cropped = crop_character_region(generated_bytes, character_position)
        gen_embedding = encode_image(cropped)

        min_score = 1.0
        for char_id in characters_present:
            ref_embeddings = self.character_ref_embeddings.get(char_id, [])
            if not ref_embeddings:
                logger.warning("No reference embeddings for character '%s'", char_id)
                continue

            # Average similarity across reference images for this character
            scores = [
                sum(a * b for a, b in zip(gen_embedding, ref_emb))
                for ref_emb in ref_embeddings
            ]
            char_score = max(scores)  # best match among references
            min_score = min(min_score, char_score)

        # If no characters had embeddings, default to low score
        if not any(
            self.character_ref_embeddings.get(cid)
            for cid in characters_present
        ):
            min_score = 0.0

        passed = min_score >= threshold
        logger.info(
            "Consistency check: %.4f (threshold=%.2f, %s) for characters %s",
            min_score, threshold, "PASS" if passed else "FAIL", characters_present,
        )
        return passed, min_score
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestVerifyConsistency -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `cd /Users/Executor/vizier && python3.11 -m pyright tools/illustrate.py`

- [ ] **Step 6: Commit pipeline core**

```bash
cd /Users/Executor/vizier
git add tools/illustrate.py tests/test_illustrate.py
git commit -m "feat(s15b): IllustrationPipeline core — init, prompt builder, CLIP verification"
```

---

## Chunk 3: Image Generation Methods

### Task 7: `generate_character_references()`

Generates 10+ candidate reference images from CharacterBible physical description via `generate_image()`. Operator selects best 2-3 as references. Uploads to MinIO, uploads first to fal.ai as anchor.

**Files:**
- Modify: `tools/illustrate.py`
- Modify: `tests/test_illustrate.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_illustrate.py`:

```python
class TestGenerateCharacterReferences:
    """generate_character_references() produces 10+ candidates from CharacterBible."""

    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    @patch("tools.illustrate.upload_bytes")
    def test_generates_requested_count(
        self, mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {"composition": "test prompt", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/refs/test.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        paths = pipeline.generate_character_references(
            character_bible=_sample_character_bible(),
            output_dir=tmp_path,
            count=10,
        )
        assert len(paths) == 10
        assert mock_gen.call_count == 10

    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    @patch("tools.illustrate.upload_bytes")
    def test_saves_images_to_disk(
        self, mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {"composition": "test", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/refs/test.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        paths = pipeline.generate_character_references(
            character_bible=_sample_character_bible(),
            output_dir=tmp_path,
            count=3,
        )
        for path in paths:
            assert path.exists()
            assert path.stat().st_size > 0

    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    @patch("tools.illustrate.upload_bytes")
    def test_prompt_uses_physical_description(
        self, mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {"composition": "test", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/refs/test.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        pipeline.generate_character_references(
            character_bible=_sample_character_bible(),
            output_dir=tmp_path,
            count=1,
        )
        # expand_brief receives the character description
        brief_arg = mock_expand.call_args[0][0]
        assert "Aminah" in brief_arg or "aminah" in brief_arg.lower()
        assert "Malay" in brief_arg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestGenerateCharacterReferences -v`
Expected: FAIL

- [ ] **Step 3: Implement `generate_character_references()`**

Add imports at top of `tools/illustrate.py`:

```python
from tools.image import expand_brief, generate_image
from utils.storage import upload_bytes, upload_to_fal
```

Add method to `IllustrationPipeline`:

```python
    def generate_character_references(
        self,
        *,
        character_bible: CharacterBible,
        output_dir: Path,
        count: int = 10,
    ) -> list[Path]:
        """Generate candidate reference images from CharacterBible.

        Operator selects best 2-3 as curated references. This method
        generates the candidates. Uses fal-ai/flux-2-dev (not Kontext)
        since no reference image exists yet.

        Args:
            character_bible: Character physical description + style notes.
            output_dir: Directory to save generated images.
            count: Number of candidates to generate (default 10).

        Returns:
            List of paths to generated candidate images.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        phys = character_bible.physical
        style = character_bible.style_notes

        raw_brief = (
            f"Character portrait of '{character_bible.name}': "
            f"{phys.ethnicity}, age {phys.age}, {phys.build} build, "
            f"{phys.height} height, {phys.hair.style} hair ({phys.hair.colour}), "
            f"skin tone {phys.skin_tone}, "
            f"{phys.face.shape} face, {phys.face.eyes} eyes, "
            f"{phys.face.nose} nose, {phys.face.mouth} mouth. "
            f"Wearing {character_bible.clothing.default}. "
            f"Art style: {style.art_style}. Line weight: {style.line_weight}. "
            f"Colour palette: {style.colour_palette}. "
            f"Colour palette hex: {', '.join(self.style_lock.palette)}. "
            "Full body, front view, neutral background. "
            "IMPORTANT: Do not include any text, words, letters, or writing."
        )

        paths: list[Path] = []
        for idx in range(count):
            with self.collector.step(f"generate_ref_{character_bible.character_id}_{idx}") as trace:
                expanded = expand_brief(raw_brief)
                prompt = expanded.get("composition", raw_brief)

                image_bytes = generate_image(
                    prompt=prompt,
                    model="fal-ai/flux-2-dev",
                    guidance_scale=3.5,
                )

                # Save locally
                filename = f"ref_{character_bible.character_id}_{idx:02d}.jpg"
                local_path = output_dir / filename
                local_path.write_bytes(image_bytes)

                # Upload to MinIO
                object_name = f"references/{self.job_id}/{filename}"
                upload_bytes(object_name, image_bytes, content_type="image/jpeg")

                paths.append(local_path)
                trace.model = "fal-ai/flux-2-dev"
                trace.cost_usd = 0.025  # flux-2-dev cost
                trace.proof = {"character": character_bible.character_id, "candidate": idx}

        logger.info(
            "Generated %d reference candidates for '%s'",
            len(paths), character_bible.name,
        )
        return paths

    def set_character_references(
        self,
        character_id: str,
        reference_paths: list[Path],
    ) -> None:
        """Set operator-curated references for a character and cache embeddings.

        Called after operator selects best 2-3 from generated candidates.
        Also uploads the first reference to fal.ai as the anchor image.

        Args:
            character_id: Character ID from CharacterBible.
            reference_paths: Operator-selected reference image paths.
        """
        self.character_references[character_id] = reference_paths
        self._cache_reference_embeddings()

        # Set anchor from first reference (front view preferred)
        if not self.anchor_image_url and reference_paths:
            self.anchor_image_url = upload_to_fal(
                reference_paths[0].read_bytes(), content_type="image/jpeg",
            )
            logger.info("Anchor image set from %s", reference_paths[0].name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestGenerateCharacterReferences -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `cd /Users/Executor/vizier && python3.11 -m pyright tools/illustrate.py`

---

### Task 8: `illustrate_page()` — Main Generation Method

The core method: builds prompt, expands via GPT-5.4-mini, generates via Kontext (or LoRA), verifies via CLIP, retries up to 2x, handles anchor reset every 8 pages.

**Files:**
- Modify: `tools/illustrate.py`
- Modify: `tests/test_illustrate.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_illustrate.py`:

```python
class TestIllustratePage:
    """illustrate_page() generates text-free illustrations with consistency tracking."""

    @patch("tools.illustrate.upload_to_fal")
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    def test_uses_illustration_shows_not_page_text(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        mock_upload: MagicMock, mock_fal_upload: MagicMock, tmp_path: Path,
    ) -> None:
        img_bytes = _make_test_image()
        mock_gen.return_value = img_bytes
        mock_expand.return_value = {"composition": "expanded prompt", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/pages/test.jpg"
        mock_fal_upload.return_value = "https://fal.media/files/test/page.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        # Set up minimal references to skip verification failure
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)
        pipeline.set_character_references("aminah", [ref_path])

        page = _sample_page(page_num=1)
        result = pipeline.illustrate_page(
            page=page,
            character_bibles=[_sample_character_bible()],
            output_dir=tmp_path,
        )
        # expand_brief receives the raw brief built from illustration_shows
        brief_arg = mock_expand.call_args[0][0]
        assert "morning market" in brief_arg
        assert isinstance(result, Path)

    @patch("tools.illustrate.upload_to_fal")
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    def test_anchor_reset_on_page_8(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        mock_upload: MagicMock, mock_fal_upload: MagicMock, tmp_path: Path,
    ) -> None:
        img_bytes = _make_test_image()
        mock_gen.return_value = img_bytes
        mock_expand.return_value = {"composition": "prompt", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/pages/test.jpg"
        mock_fal_upload.return_value = "https://fal.media/files/test/page.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)
        pipeline.set_character_references("aminah", [ref_path])
        pipeline.anchor_image_url = "https://fal.media/files/test/anchor.jpg"

        # Simulate pages 1-8
        for page_num in range(1, 9):
            page = _sample_page(page_num=page_num)
            pipeline.illustrate_page(
                page=page,
                character_bibles=[_sample_character_bible()],
                output_dir=tmp_path,
            )

        # On page 8 (divisible by 8), anchor should have been used
        # Check that pages_since_anchor was reset
        assert pipeline.pages_since_anchor < _ANCHOR_INTERVAL

    @patch("tools.illustrate.upload_to_fal")
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    def test_kontext_model_used(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        mock_upload: MagicMock, mock_fal_upload: MagicMock, tmp_path: Path,
    ) -> None:
        img_bytes = _make_test_image()
        mock_gen.return_value = img_bytes
        mock_expand.return_value = {"composition": "prompt", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/pages/test.jpg"
        mock_fal_upload.return_value = "https://fal.media/files/test/page.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)
        pipeline.set_character_references("aminah", [ref_path])

        pipeline.illustrate_page(
            page=_sample_page(),
            character_bibles=[_sample_character_bible()],
            output_dir=tmp_path,
        )
        # Verify Kontext model endpoint was used
        gen_kwargs = mock_gen.call_args[1]
        assert gen_kwargs["model"] == "fal-ai/flux-pro/kontext"

    @patch("tools.illustrate.upload_to_fal")
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    def test_previous_page_fed_to_kontext(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        mock_upload: MagicMock, mock_fal_upload: MagicMock, tmp_path: Path,
    ) -> None:
        img_bytes = _make_test_image()
        mock_gen.return_value = img_bytes
        mock_expand.return_value = {"composition": "prompt", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/pages/test.jpg"
        mock_fal_upload.return_value = "https://fal.media/files/test/prev.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)
        pipeline.set_character_references("aminah", [ref_path])

        # Generate page 1, then page 2
        pipeline.illustrate_page(page=_sample_page(1), character_bibles=[_sample_character_bible()], output_dir=tmp_path)
        pipeline.illustrate_page(page=_sample_page(2), character_bibles=[_sample_character_bible()], output_dir=tmp_path)

        # Page 2's generate_image call should have image_url set
        second_call_kwargs = mock_gen.call_args_list[1][1]
        assert second_call_kwargs.get("image_url") is not None

    @patch("tools.illustrate.upload_to_fal")
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    def test_tracks_consistency_scores(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        mock_upload: MagicMock, mock_fal_upload: MagicMock, tmp_path: Path,
    ) -> None:
        img_bytes = _make_test_image()
        mock_gen.return_value = img_bytes
        mock_expand.return_value = {"composition": "prompt", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/pages/test.jpg"
        mock_fal_upload.return_value = "https://fal.media/files/test/page.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)
        pipeline.set_character_references("aminah", [ref_path])

        pipeline.illustrate_page(page=_sample_page(), character_bibles=[_sample_character_bible()], output_dir=tmp_path)
        assert len(pipeline.consistency_scores) == 1
        assert pipeline.consistency_scores[0] > 0.0

    @patch("tools.illustrate.upload_to_fal")
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    def test_lora_path_when_lora_config_set(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        mock_upload: MagicMock, mock_fal_upload: MagicMock, tmp_path: Path,
    ) -> None:
        """If CharacterBible has LoRA config, use flux-lora model."""
        from contracts.publishing import LoRAConfig

        img_bytes = _make_test_image()
        mock_gen.return_value = img_bytes
        mock_expand.return_value = {"composition": "prompt", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/pages/test.jpg"
        mock_fal_upload.return_value = "https://fal.media/files/test/page.jpg"

        bible = _sample_character_bible()
        bible.lora = LoRAConfig(
            character_lora_url="https://example.com/lora.safetensors",
            trigger_word="aminah_character",
            training_images=20,
        )

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)
        pipeline.set_character_references("aminah", [ref_path])

        pipeline.illustrate_page(
            page=_sample_page(),
            character_bibles=[bible],
            output_dir=tmp_path,
        )
        gen_kwargs = mock_gen.call_args[1]
        # Should have used the standard model still (LoRA support is a prompt enhancement)
        # The lora trigger word should be in the prompt
        assert "aminah_character" in gen_kwargs["prompt"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestIllustratePage -v`
Expected: FAIL

- [ ] **Step 3: Implement `illustrate_page()`**

Add to `IllustrationPipeline` class:

```python
    def illustrate_page(
        self,
        *,
        page: PageScaffold,
        character_bibles: list[CharacterBible],
        output_dir: Path,
        max_retries: int = 2,
        consistency_threshold: float = 0.75,
    ) -> Path:
        """Generate a text-free illustration for a single page.

        Builds prompt from illustration_shows (NEVER page text), expands
        via GPT-5.4-mini, generates via Kontext (feeding previous page),
        verifies via CLIP, retries on low consistency.

        Re-anchors from curated reference every 8 pages to prevent
        cumulative drift.

        Args:
            page: PageScaffold with illustration_shows and composition_guide.
            character_bibles: Characters in this project.
            output_dir: Directory to save generated images.
            max_retries: Max retries on low CLIP score (default 2).
            consistency_threshold: CLIP threshold (default 0.75).

        Returns:
            Path to the generated illustration on disk.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        page_num = page.page

        # Determine image_url: anchor reset every 8 pages, else previous page
        if page_num > 1 and self.pages_since_anchor >= _ANCHOR_INTERVAL:
            image_url = self.anchor_image_url
            self.pages_since_anchor = 0
            logger.info("Anchor reset on page %d", page_num)
        elif page_num > 1 and self.previous_page_image:
            image_url = self.previous_page_image
        else:
            image_url = self.anchor_image_url  # first page uses anchor if available

        # Build and expand prompt
        raw_brief = build_illustration_prompt(
            page=page,
            style_lock=self.style_lock,
            character_bibles=character_bibles,
        )

        # Check for LoRA trigger words
        present_ids = set(page.characters_present)
        for bible in character_bibles:
            if bible.character_id in present_ids and bible.lora:
                raw_brief = f"{bible.lora.trigger_word} {raw_brief}"

        image_bytes = b""
        best_score = 0.0

        for attempt in range(max_retries + 1):
            with self.collector.step(f"illustrate_page_{page_num}_attempt_{attempt}") as trace:
                expanded = expand_brief(raw_brief)
                prompt = expanded.get("composition", raw_brief)

                image_bytes = generate_image(
                    prompt=prompt,
                    model="fal-ai/flux-pro/kontext",
                    guidance_scale=3.5,
                    image_url=image_url,
                )

                trace.model = "fal-ai/flux-pro/kontext"
                trace.cost_usd = _KONTEXT_COST_USD
                trace.proof = {"page": page_num, "attempt": attempt}

            # Verify consistency
            if self.character_ref_embeddings:
                passed, score = self.verify_consistency(
                    generated_bytes=image_bytes,
                    characters_present=page.characters_present,
                    character_position=page.composition_guide.character_position,
                    threshold=consistency_threshold,
                )
                best_score = max(best_score, score)

                if passed:
                    break

                if attempt < max_retries:
                    logger.warning(
                        "Page %d consistency %.4f < %.2f, retrying (%d/%d)",
                        page_num, score, consistency_threshold, attempt + 1, max_retries,
                    )
                else:
                    logger.warning(
                        "Page %d consistency %.4f still below threshold after %d retries. "
                        "Flagging for operator review.",
                        page_num, score, max_retries,
                    )
            else:
                best_score = 0.0
                break

        # Save locally
        filename = f"page_{page_num:03d}.jpg"
        local_path = output_dir / filename
        local_path.write_bytes(image_bytes)

        # Upload to MinIO
        object_name = f"illustrations/{self.job_id}/{filename}"
        upload_bytes(object_name, image_bytes, content_type="image/jpeg")

        # Upload to fal.ai for next page's Kontext reference
        fal_url = upload_to_fal(image_bytes, content_type="image/jpeg")
        self.previous_page_image = fal_url

        # Update state
        self.total_pages += 1
        self.pages_since_anchor += 1
        self.consistency_scores.append(best_score)

        logger.info(
            "Page %d illustrated (consistency=%.4f, anchor_in=%d pages)",
            page_num, best_score, _ANCHOR_INTERVAL - self.pages_since_anchor,
        )
        return local_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestIllustratePage -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `cd /Users/Executor/vizier && python3.11 -m pyright tools/illustrate.py`

- [ ] **Step 6: Commit generation methods**

```bash
cd /Users/Executor/vizier
git add tools/illustrate.py tests/test_illustrate.py
git commit -m "feat(s15b): illustrate_page() with Kontext iterative, anchor reset, CLIP retry"
```

---

## Chunk 4: Workshop Flow + Derivative + YAML Updates

### Task 9: Creative Workshop Flow Functions

Standalone functions callable by WorkflowExecutor stage-by-stage.

**Files:**
- Modify: `tools/illustrate.py`
- Modify: `tests/test_illustrate.py`

- [ ] **Step 1: Write failing tests for workshop flow**

Add to `tests/test_illustrate.py`:

```python
from contracts.context import RollingContext
from tools.illustrate import (
    run_creative_workshop,
    run_specimen_page,
    run_page_production,
    run_derivative_workshop,
)


class TestCreativeWorkshopFlow:
    """Creative workshop → specimen → production → assembly flow."""

    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.upload_to_fal")
    def test_full_flow_produces_images(
        self, mock_fal: MagicMock, mock_upload: MagicMock,
        mock_expand: MagicMock, mock_gen: MagicMock, tmp_path: Path,
    ) -> None:
        img_bytes = _make_test_image()
        mock_gen.return_value = img_bytes
        mock_expand.return_value = {"composition": "prompt", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/test.jpg"
        mock_fal.return_value = "https://fal.media/files/test/img.jpg"

        scaffold = NarrativeScaffold.decompose(
            target_age=AgeGroup.age_5_7, page_count=3,
            pages=[_sample_page(i + 1) for i in range(3)],
        )
        style_lock = _sample_style_lock()
        bibles = [_sample_character_bible()]

        # Step 1: Workshop produces references
        pipeline = run_creative_workshop(
            style_lock=style_lock,
            character_bibles=bibles,
            job_id="test-job",
            output_dir=tmp_path,
            ref_count=2,
        )
        assert isinstance(pipeline, IllustrationPipeline)

        # Step 2: Specimen page
        specimen = run_specimen_page(
            pipeline=pipeline,
            page=scaffold.pages[0],
            character_bibles=bibles,
            output_dir=tmp_path,
        )
        assert specimen.exists()

        # Step 3: Production run
        ctx = RollingContext(context_type="narrative", recent_window=8, medium_scope="not_needed")
        images = run_page_production(
            pipeline=pipeline,
            scaffold=scaffold,
            character_bibles=bibles,
            rolling_context=ctx,
            output_dir=tmp_path,
        )
        assert len(images) == 3
        # RollingContext should have been updated
        assert ctx.current_step == 3

    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.upload_to_fal")
    def test_rolling_context_updated_per_page(
        self, mock_fal: MagicMock, mock_upload: MagicMock,
        mock_expand: MagicMock, mock_gen: MagicMock, tmp_path: Path,
    ) -> None:
        img_bytes = _make_test_image()
        mock_gen.return_value = img_bytes
        mock_expand.return_value = {"composition": "prompt", "style": "", "brand": "", "technical": "", "text_content": ""}
        mock_upload.return_value = "vizier-assets/test.jpg"
        mock_fal.return_value = "https://fal.media/files/test/img.jpg"

        scaffold = NarrativeScaffold.decompose(
            target_age=AgeGroup.age_5_7, page_count=2,
            pages=[_sample_page(1), _sample_page(2)],
        )

        pipeline = run_creative_workshop(
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
            job_id="test-job",
            output_dir=tmp_path,
            ref_count=1,
        )

        ctx = RollingContext(context_type="narrative", recent_window=8, medium_scope="not_needed")
        run_page_production(
            pipeline=pipeline,
            scaffold=scaffold,
            character_bibles=[_sample_character_bible()],
            rolling_context=ctx,
            output_dir=tmp_path,
        )

        # Context should track characters
        entity_ids = [e.entity_id for e in ctx.entities]
        assert "aminah" in entity_ids


class TestDerivativeWorkshop:
    """Derivative workshop loads source StyleLock and proceeds to new content."""

    def test_inherits_style_lock(self) -> None:
        source_style = _sample_style_lock()
        pipeline = run_derivative_workshop(
            source_style_lock=source_style,
            job_id="derivative-job",
        )
        assert pipeline.style_lock == source_style
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestCreativeWorkshopFlow -v && python3.11 -m pytest tests/test_illustrate.py::TestDerivativeWorkshop -v`
Expected: FAIL

- [ ] **Step 3: Implement workshop flow functions**

Add to `tools/illustrate.py`:

```python
from contracts.context import RollingContext
from tools.publish import update_rolling_context_for_page


def run_creative_workshop(
    *,
    style_lock: StyleLock,
    character_bibles: list[CharacterBible],
    job_id: str,
    output_dir: Path,
    ref_count: int = 10,
) -> IllustrationPipeline:
    """Run the pre-production creative workshop.

    Generates character reference candidates and initialises the pipeline.
    Operator selects best references externally (this function generates
    candidates for selection).

    §42.6 steps covered: character reference generation, style direction lock.

    Args:
        style_lock: Locked visual parameters from workshop step 9.
        character_bibles: All characters in this project.
        job_id: Production job ID.
        output_dir: Directory for reference images.
        ref_count: Candidates per character (default 10).

    Returns:
        Initialised IllustrationPipeline ready for specimen/production.
    """
    pipeline = IllustrationPipeline(style_lock=style_lock, job_id=job_id)

    for bible in character_bibles:
        refs = pipeline.generate_character_references(
            character_bible=bible,
            output_dir=output_dir / "references" / bible.character_id,
            count=ref_count,
        )
        # Auto-select all as references (operator narrows externally)
        pipeline.set_character_references(bible.character_id, refs)

    return pipeline


def run_specimen_page(
    *,
    pipeline: IllustrationPipeline,
    page: PageScaffold,
    character_bibles: list[CharacterBible],
    output_dir: Path,
) -> Path:
    """Generate a single specimen page for operator approval.

    §42.6 step 10: specimen page approval gate.

    Returns:
        Path to the specimen illustration.
    """
    return pipeline.illustrate_page(
        page=page,
        character_bibles=character_bibles,
        output_dir=output_dir / "specimen",
    )


def run_page_production(
    *,
    pipeline: IllustrationPipeline,
    scaffold: NarrativeScaffold,
    character_bibles: list[CharacterBible],
    rolling_context: RollingContext,
    output_dir: Path,
) -> list[Path]:
    """Run sequential page production through the full scaffold.

    For each page: illustrate → verify → update RollingContext.
    RollingContext receives both visual and textual descriptions.

    Args:
        pipeline: Initialised IllustrationPipeline with references set.
        scaffold: NarrativeScaffold with all pages.
        character_bibles: All characters.
        rolling_context: RollingContext to update per page.
        output_dir: Directory for page images.

    Returns:
        Ordered list of paths to generated illustrations.
    """
    images: list[Path] = []
    pages_dir = output_dir / "pages"

    for page in scaffold.pages:
        img_path = pipeline.illustrate_page(
            page=page,
            character_bibles=character_bibles,
            output_dir=pages_dir,
        )
        images.append(img_path)

        # Update RollingContext with visual description
        visual_summary = (
            f"Page {page.page} ({page.emotional_beat}): "
            f"[Visual: {page.composition_guide.camera}, "
            f"character at {page.composition_guide.character_position}, "
            f"{page.composition_guide.colour_temperature} colour temperature, "
            f"{page.composition_guide.background_detail} background] "
            f"Scene: {page.illustration_shows}"
        )
        update_rolling_context_for_page(
            ctx=rolling_context,
            page=page,
            page_text=visual_summary,
        )

    return images


def run_derivative_workshop(
    *,
    source_style_lock: StyleLock,
    job_id: str,
) -> IllustrationPipeline:
    """Fast-path derivative workshop — inherits source project settings.

    §42.6.1: Inherits StyleLock, typography, illustration tier.
    New content (premise, characters, scaffold, specimen) created separately.
    Target: 45-60 min operator time (vs 2-4 hrs full workshop).

    Args:
        source_style_lock: StyleLock from the source project.
        job_id: New project's job ID.

    Returns:
        Pipeline initialised with inherited settings.
    """
    logger.info("Derivative workshop: inheriting StyleLock from source project")
    return IllustrationPipeline(style_lock=source_style_lock, job_id=job_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py::TestCreativeWorkshopFlow tests/test_illustrate.py::TestDerivativeWorkshop -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `cd /Users/Executor/vizier && python3.11 -m pyright tools/illustrate.py`

---

### Task 10: Update Workflow YAMLs — `draft_preview: nano-banana`

Add `draft_preview: nano-banana` to all workflow YAMLs that have `image_model_preference`.

**Files:**
- Modify: `manifests/workflows/poster_production.yaml`
- Modify: `manifests/workflows/brochure_production.yaml`
- Modify: `manifests/workflows/document_production.yaml`
- Modify: `manifests/workflows/ebook_production.yaml`
- Modify: `manifests/workflows/childrens_book_production.yaml`
- Modify: `manifests/workflows/serial_fiction_production.yaml`
- Modify: `manifests/workflows/social_batch.yaml`

- [ ] **Step 1: Add `draft_preview: nano-banana` to all 7 workflow YAMLs**

For each file, add `draft_preview: nano-banana` inside the `image_model_preference` block. Example for `poster_production.yaml`:

```yaml
image_model_preference:
  text_heavy: nano-banana-pro
  draft_preview: nano-banana          # S4 confirmed GO — fast draft tier
  photorealistic: flux-2-pro
  draft: flux-2-dev
```

- [ ] **Step 2: Verify YAMLs parse correctly**

Run: `cd /Users/Executor/vizier && python3.11 -c "import yaml; [yaml.safe_load(open(f'manifests/workflows/{f}')) for f in ['poster_production.yaml','brochure_production.yaml','document_production.yaml','ebook_production.yaml','childrens_book_production.yaml','serial_fiction_production.yaml','social_batch.yaml']]; print('All YAMLs valid')"`
Expected: "All YAMLs valid"

- [ ] **Step 3: Commit workshop flow + YAML updates**

```bash
cd /Users/Executor/vizier
git add tools/illustrate.py tests/test_illustrate.py manifests/workflows/*.yaml
git commit -m "feat(s15b): workshop flow, derivative support, draft_preview tier in workflow YAMLs"
```

---

## Chunk 5: Decision Doc + Final Verification

### Task 11: Document Center-Crop Decision

**Files:**
- Create: `docs/decisions/center_crop_clip.md`

- [ ] **Step 1: Write decision document**

```markdown
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
- `centre` → crop center 60% of image
- `left_third` → crop left 60%
- `right_third` → crop right 60%

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
```

- [ ] **Step 2: Commit decision doc**

```bash
cd /Users/Executor/vizier
git add docs/decisions/center_crop_clip.md
git commit -m "docs(s15b): decision record — position-aware center crop for CLIP"
```

---

### Task 12: Run Full Test Suite + Pyright

- [ ] **Step 1: Run all S15b tests**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/test_illustrate.py tests/test_image_processing.py tests/test_storage_fal.py tests/test_publish.py -v`
Expected: ALL PASS

- [ ] **Step 2: Run pyright on all modified/new files**

Run: `cd /Users/Executor/vizier && python3.11 -m pyright tools/illustrate.py utils/image_processing.py utils/storage.py tools/publish.py`
Expected: 0 errors

- [ ] **Step 3: Run existing tests to check for regressions**

Run: `cd /Users/Executor/vizier && python3.11 -m pytest tests/ -v --timeout=120`
Expected: No regressions

- [ ] **Step 4: Final commit if any fixes needed**

```bash
cd /Users/Executor/vizier
git add -A
git commit -m "fix(s15b): address test/pyright issues from full suite run"
```

---

## File Map Summary

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `tools/illustrate.py` | Stateful illustration pipeline + workshop flow |
| Create | `utils/image_processing.py` | Position-aware character cropping |
| Create | `tests/test_illustrate.py` | Pipeline tests (~200 lines) |
| Create | `tests/test_image_processing.py` | Cropping tests |
| Create | `tests/test_storage_fal.py` | fal.ai upload tests |
| Create | `docs/decisions/center_crop_clip.md` | Center-crop decision record |
| Modify | `utils/storage.py` | Add `upload_to_fal()` |
| Modify | `tools/publish.py:637-661` | Wire `check_visual_consistency()` with CLIP |
| Modify | `tests/test_publish.py:428-446` | Update stub tests to real CLIP tests |
| Modify | 7 workflow YAMLs | Add `draft_preview: nano-banana` |
