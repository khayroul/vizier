# Vizier Poster Runtime Enhancement Report

Date: 2026-04-09  
Scope: governed poster production path, poster rendering/image generation choices, sample-poster adaptation readiness

## Summary

This remediation pass focused on the user-visible poster lane rather than the
general runtime alone. The target was simple:

1. A poster request should route through the governed poster path and deliver a
   strong result reliably.
2. The lane should prefer the stronger render stack already in the repo
   (Jinja2 + Playwright) and make more intelligent image-generation choices.
3. Reference datasets, swipe intelligence, QA, and tripwire should have a
   clearer path to improving poster quality instead of existing as side systems.
4. Sample-poster adaptation should be a first-class runtime capability rather
   than an implicit future feature.

The result of this pass is not "perfect cloning" yet, but the poster engine is
materially closer to the desired operating model. The runtime now has an
explicit seam for reference-poster inputs, uses portrait-aware image canvases
for posters, and can route poster reference jobs toward image-to-image
generation instead of treating every poster as a clean-room text-only prompt.

## Before

### What was already strong

- Poster delivery already preferred HTML/Jinja2 + Playwright, with Typst only
  as fallback.
- Governed execution, quality posture, budget profile, and stage knowledge were
  already active from the earlier quality-spine work.
- Visual QA already evaluated the rendered artifact instead of a placeholder
  status string.

### What was still weak

#### 1. Image generation was under-informed

The poster path still generated images with a narrow decision surface:

- model selection looked mostly at `language` and `artifact_family`
- client `image_mode` was not meaningfully used
- poster generation always used a generic image canvas instead of a poster-aware
  portrait canvas
- reference/sample posters had no canonical runtime input path

This meant the rendering stack was stronger than the image-generation setup
feeding it.

#### 2. Reference/sample adaptation was not first-class

The repo had ingredients:

- `tools.visual_dna`
- swipe ingestion in `tools.research`
- exemplar scoring in `tools.visual_scoring`
- image-to-image usage in the children's-book lane via Kontext

But the governed poster path itself had no stable contract for:

- `reference_image_path`
- `reference_image_url`
- `reference_notes`

As a result, a user showing a sample poster did not automatically produce a
poster runtime that could absorb layout/palette cues into prompting or model
selection.

#### 3. QA lacked the richer reference context available upstream

Poster QA already evaluated the real image, but it still built its evaluation
brief from a thinner context than the image stage had access to. This reduced
the chance that QA would judge the output against the same composition
intent/reference cues used during generation.

## Root-Cause Framing

This work aligns with the earlier graph-driven diagnosis:

- the strongest pieces of the poster quality stack existed
- but the active poster runtime still did not bind all the useful signals into
  one enforced path

For poster quality specifically, the root cause was:

1. a weak runtime seam for reference inputs
2. shallow image-model/image-size selection
3. incomplete reuse of generation-time visual intent in final QA

## Changes Implemented

### 1. Governed execution now accepts reference-poster inputs

`tools/orchestrate.py`

`run_governed(...)` now accepts optional poster/runtime fields:

- `platform`
- `reference_image_path`
- `reference_image_url`
- `reference_notes`

These values are injected into `job_context`, which gives the runtime a stable
place to receive poster-reference signals from future Telegram or gateway
callers.

This does not by itself wire Telegram attachments into Vizier, but it creates
the correct governed landing point for that integration.

### 1b. Live Telegram bridge now forwards cached reference images

`~/.hermes/plugins/vizier_tools/__init__.py`

After the governed seam was added, the remaining gap was outside the repo:
the Hermes `run_pipeline` plugin still only forwarded `request`, `client_id`,
and `job_id`.

That live plugin bridge has now been updated to:

- accept optional `platform`
- accept optional `reference_image_path`
- accept optional `reference_image_url`
- accept optional `reference_notes`
- auto-extract a cached local image path from gateway-enriched request text
  when the model does not pass `reference_image_path` explicitly

This matters because Hermes gateway already injects image hints like:

- `vision_analyze using image_url: /absolute/local/cache/path.png`

With the bridge update in place, a Telegram user can now send a sample poster
and have that cached path reach `run_governed(...)` as a real
`reference_image_path` input instead of remaining inert conversational text.

This change lives in the Hermes plugin layer rather than the Vizier repo, so it
is documented here even though it is not represented as a Git commit in this
repository.

### 2. Image model selection is now poster-aware and reference-aware

`tools/image.py`

Two upgrades were made:

- `select_image_model(...)` now understands:
  - `image_mode`
  - `reference_image_url`
- `select_image_dimensions(...)` was added to give poster generation a
  portrait canvas instead of a square default

Current behavior:

- draft-like jobs stay cheap
- photorealistic/image-mode jobs can route to the photorealistic model
- poster jobs with a reference image prefer Kontext-style image-to-image
  adaptation
- poster jobs now generate on portrait-friendly dimensions instead of an
  always-square canvas

This improves both quality and cost discipline by making the image stage better
matched to the actual downstream artifact.

### 3. Poster image generation now has a reference-style conditioning path

`tools/registry.py`

`_image_generate(...)` now:

- reads optional reference inputs from governed context
- analyzes a local reference poster through `tools.visual_dna`
- uploads a local reference poster to fal.ai when a hosted URL is needed
- converts the extracted layout/palette cues into explicit prompt guidance
- chooses a reference-adaptation model when appropriate

The prompt now gets guidance such as:

- echo layout rhythm
- follow composition type
- reuse palette cues
- do not copy original text/logos/trademarks

This is not full multimodal layout parsing, but it is materially better than
the previous state where reference posters were effectively out-of-band for the
governed poster lane.

### 4. Poster QA now reuses richer generation context

`tools/registry.py`

`_visual_qa(...)` now prefers the actual `expanded_brief` and any available
`reference_visual_dna` from the prior production stage when constructing the
QA brief.

This tightens the generation-to-evaluation loop:

- generation is guided by richer composition/reference context
- QA now sees more of that same context

That improves the chance that QA is scoring the poster against the intended
composition/style target rather than a thinner fallback summary.

### 5. Client brand loading now carries style-reference fields

`tools/registry.py`

Client defaults now preserve:

- `style_reference`
- `style_reference_options`

This does not fully operationalize client style-reference datasets yet, but it
removes an avoidable drop in the brand-context layer.

## Before vs After

### Before

- Posters rendered through the stronger Playwright path, but the upstream image
  generation layer still behaved too generically.
- Poster image generation used a weak decision surface and could ignore client
  image mode.
- Poster sample/reference images were not a real governed runtime input.
- QA could miss part of the generation-time visual intent.

### After

- The governed path can now carry poster-reference inputs deliberately.
- Poster image generation can route to a reference-adaptation model when a
  sample poster is provided.
- Poster image generation uses portrait-aware canvas sizing.
- Poster reference layout/palette cues now influence the prompt.
- QA reuses richer generation context, including expanded brief/reference
  signals when present.

## Why This Helps the User-Facing Poster Lane

Relative to the target expectations:

### Expectation 1: strong poster delivered reliably at reasonable cost

This pass improves the *quality of the upstream image* before delivery:

- better model choice
- better canvas choice
- better use of reference inputs

That should improve final poster quality without requiring a larger delivery
stack rewrite.

### Expectation 2: best available rendering + image config

The rendering path was already mostly correct:

- primary = Jinja2 + Playwright
- fallback = Typst

The improvement here is upstream:

- image model selection is now meaningfully richer
- image size is now better aligned to poster output geometry

### Expectation 3: datasets/QA/tripwires should actually matter

This pass does not complete the entire dataset-improvement loop, but it makes
poster-reference and visual-intent data more actionable at generation and QA
time. That is a real step toward "intelligence plumbing that improves the
artifact" instead of passive stored data.

### Expectation 4: cloning/sample adaptation should work better

This is the most directly improved area in this pass.

The poster runtime now has:

- a governed reference-image input seam
- reference visual-DNA extraction
- promptable layout/palette guidance
- model routing toward reference adaptation

It is still not a full "read every poster element perfectly and rebuild it"
system, but it is no longer missing the core runtime path entirely.

## Verification

Targeted verification completed successfully:

- `pytest -q tests/test_poster_reference_runtime.py tests/test_visual_intelligence.py tests/test_poster_pipeline.py`
  - `66 passed`
- `pytest -q tests/test_orchestrate.py tests/test_e2e_layer5b_semantics.py`
  - `28 passed`
- `pyright tools/image.py tools/orchestrate.py tools/registry.py tests/test_poster_reference_runtime.py`
  - `0 errors`

Live Telegram bridge verification also completed:

- the Hermes plugin loads successfully after the bridge update
- a smoke test with gateway-style text containing
  `vision_analyze with image_url: /tmp/...png`
  showed the plugin-generated subprocess script now includes
  `reference_image_path=<that cached path>`

## Residual Gaps

This pass improves the poster lane, but a few important gaps remain:

1. **Telegram attachment plumbing is not fully wired into Vizier yet**
   - the governed runtime now accepts reference fields
   - but the Hermes/Vizier bridge still needs to pass attachment-derived paths
     or URLs into `run_governed(...)`

2. **Reference understanding is still heuristic**
   - current adaptation uses visual DNA and prompt guidance
   - it does not yet do deep multimodal element extraction or fine-grained
     poster-block reconstruction

3. **Poster template coverage is still thin**
   - the HTML render path is strong
   - but there are still very few concrete poster templates

4. **Dataset richness still matters**
   - even with better runtime plumbing, sparse swipe/exemplar/client data will
     cap how differentiated the outputs can become

## Recommended Next Steps

1. Wire Telegram/gateway poster attachments into the new governed reference
   fields.
2. Add a poster-reference analysis module that goes beyond visual DNA into
   structured poster-block extraction.
3. Expand the HTML poster template library so design-system routing has more
   real render targets.
4. Track poster-reference usage, model choice, and QA outcome in trace so the
   cost/quality effect of these changes can be measured explicitly.

## Conclusion

This pass did not merely add another feature. It repaired a specific quality
gap in the main poster lane:

- posters already had a strong renderer
- but did not yet have a comparably strong reference-aware image-generation
  seam

That seam now exists, and it is governed, test-backed, and compatible with the
broader quality-spine and runtime-control work already completed.
