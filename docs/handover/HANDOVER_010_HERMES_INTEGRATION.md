# Hermes × Vizier Integration Handover

**Generated:** 2026-04-09
**Handover number:** 010
**Reason:** User requested stop point and clean handoff before implementation
**Prior context:** Runtime quality spine, MemPalace runtime adoption, poster
reference runtime, and Hermes integration audit were completed/continued in the
current thread.

## What Was Done In This Session

1. Audited Hermes capabilities against the current Vizier integration.
2. Inspected the live Hermes plugin bridge at:
   - `~/.hermes/plugins/vizier_tools/__init__.py`
3. Inspected Hermes seams relevant to integration:
   - plugin hooks
   - gateway media enrichment
   - session lifecycle
   - memory providers
   - session/cost telemetry
4. Wrote the implementation roadmap:
   - `docs/superpowers/plans/2026-04-09-hermes-vizier-integration.md`

## Current Conclusion

Vizier is using Hermes correctly at the **outer shell** level, but not deeply.

Current architecture:

- Hermes owns the user chat shell and gateway session
- Vizier is invoked as a single `run_pipeline` tool
- the live plugin shells out to `run_governed(...)`

This means Hermes is helping with:

- session persistence
- gateway media caching
- platform routing
- outer session lifecycle

But Hermes is **not** helping much with Vizier's inner runtime because the
governed pipeline still sits behind a black-box subprocess boundary.

## Lesson Learned

The first integration pass optimized for **getting Vizier callable from Hermes
quickly**, not for defining a durable Hermes↔Vizier boundary.

That gave us a bridge that worked, but it also introduced four kinds of drift:

1. **We treated Hermes mostly as a launcher, not as the owner of session-layer
   concerns.**
   - The live plugin focused on exposing `run_pipeline`
   - But it did not use Hermes hooks, memory-provider lifecycle, or session
     seams that already existed for context, feedback, and continuity

2. **We solved missing structured seams with text parsing.**
   - Telegram image references became recoverable only by regex-parsing
     gateway-enriched text
   - This was a useful compatibility bridge, but it is the wrong long-term
     contract for media/session metadata

3. **We left critical bridge logic outside repo ownership.**
   - The active integration seam lives in `~/.hermes/plugins/vizier_tools/`
   - That made the bridge harder to review, test, version, and reason about as
     part of Vizier itself

4. **We let boundary pressure turn into custom glue instead of using official
   Hermes seams first.**
   - Example: a failed `on_agent_ready` hook attempt and tool-only plugin design
     show that we were still feeling around the platform rather than building on
     the supported hook contract
   - More generally, we compensated for boundary gaps with adapter logic before
     fully exploiting `pre_llm_call`, `post_llm_call`, `on_session_start`, and
     `on_session_end`

The practical lesson is:

- **Integrate at the correct layer first.**
- Hermes should own session, hook, media-intake, compression, and operator
  memory concerns.
- Vizier should own governed artifact production concerns.
- When the seam is missing, prefer a temporary bridge with an explicit
  replacement plan over quietly normalizing the workaround into architecture.

In short: the first pass got us a working bridge, but it underinvested in the
boundary itself. The next pass should reduce glue by moving session-layer
problems onto Hermes-native seams while keeping the governed runtime in Vizier.

## Key Audit Takeaways

### Good

- Hermes plugin system is in use correctly
- Telegram cached image path flow is already useful
- Hermes hooks and memory-provider lifecycle are real and available
- Hermes session/cost telemetry is already available at the outer layer

### Still weak

- the live plugin currently registers tools only; it does not use Hermes hooks
- Telegram reference intake still relies on regex parsing of gateway-enriched
  text as a fallback contract
- there is no Hermes-backed session/operator memory integration yet
- Hermes session telemetry and Vizier job telemetry are not explicitly linked

## Recommended Boundary

### Hermes should own

- chat sessions
- gateway media intake
- platform/session lifecycle
- plugin hooks
- cross-session operator memory
- compression-safe session fact persistence
- outer telemetry

### Vizier should own

- governed routing
- readiness and policy
- workflow execution
- artifact QA / tripwire / delivery
- templates and rendering
- artifact datasets and retrieval
- stage/job traces and outcome memory

This boundary is now written down in:

- `docs/superpowers/plans/2026-04-09-hermes-vizier-integration.md`

## Important Files Read During The Audit

### Live deployment seam

- `~/.hermes/plugins/vizier_tools/__init__.py`

### Hermes internals

- `hermes-agent/run_agent.py`
- `hermes-agent/model_tools.py`
- `hermes-agent/hermes_cli/plugins.py`
- `hermes-agent/agent/memory_provider.py`
- `hermes-agent/agent/memory_manager.py`
- `hermes-agent/gateway/run.py`

### Existing Vizier runtime seam

- `tools/orchestrate.py`
- `middleware/runtime_controls.py`
- `tools/executor.py`

## Repo State At Handover

### Git status

At the stop point, the repo has one untracked file:

- `docs/superpowers/plans/2026-04-09-hermes-vizier-integration.md`

No implementation code was changed in this session.

### Important external state

The live Hermes plugin file outside the repo is still the active deployment
bridge:

- `~/.hermes/plugins/vizier_tools/__init__.py`

It currently:

- registers `run_pipeline`
- registers `query_logs`
- shells out to `run_governed(...)`
- recovers `reference_image_path` / `reference_image_url` by parsing request
  text when explicit args are absent

## The Next Best Move

Do **not** jump straight into deep memory-provider work first.

The next session should start with **Chunk 1** from the new plan:

### Chunk 1: Use Hermes hooks in the live Vizier plugin

Implement:

- `pre_llm_call`
- `post_llm_call`
- `on_session_start`
- `on_session_end`

Why first:

- lowest-risk improvement
- uses existing Hermes seams
- strengthens the integration without changing the governed runtime contract
- creates a clean place for platform/session hints and outcome capture

## Recommended Implementation Sequence

1. Create a **repo-owned source of truth** for the Hermes plugin logic.
   - Avoid leaving the deployment bridge only in `~/.hermes/plugins/...`
   - Prefer a repo module that the live plugin imports

2. Make the live plugin a **thin loader/wrapper**.
   - Keep deployment stable
   - Move logic into repo version control

3. Add hook registration in the repo-owned plugin module.
   - `pre_llm_call` for ephemeral guidance/context
   - `post_llm_call` for outcome logging
   - `on_session_start` / `on_session_end` for session-local bridge lifecycle

4. Add tests for the repo-owned plugin module.
   - registration behavior
   - hook return values
   - session-local state handling
   - current path/url extraction fallback

5. Only after hook integration is stable:
   - replace regex attachment recovery with a structured bridge
   - then consider Hermes-backed operator/session memory

## Constraints For The Next Session

- Do not move artifact routing/QA/delivery logic into Hermes
- Do not replace Vizier knowledge cards with Hermes memory
- Do not build a second context-control stack
- Do not couple Telegram-specific behavior into Vizier core
- Do not remove the current regex fallback until a structured media contract is
  live

## Good-Version Checklist

The next session should preserve these rules:

- Hermes integration must reduce custom glue, not create overlapping runtimes
- plugin code should remain an adapter, not a second production engine
- session memory and artifact memory must remain separate concerns
- telemetry should be linked, not duplicated

## Suggested First Task For The Next Session

Start by creating a repo-owned Hermes bridge module and switching the live
plugin to import it.

That single move gives:

- version-controlled source of truth
- testability
- a safe place to add hooks
- less deployment drift

## Files To Read First Next Session

1. `docs/superpowers/plans/2026-04-09-hermes-vizier-integration.md`
2. `docs/VIZIER_POSTER_RUNTIME_ENHANCEMENT_REPORT_2026-04-09.md`
3. `docs/VIZIER_QUALITY_SPINE_REMEDIATION_REPORT_2026-04-08.md`
4. `~/.hermes/plugins/vizier_tools/__init__.py`
5. `hermes-agent/hermes_cli/plugins.py`
6. `hermes-agent/run_agent.py`

## Verification Status

No tests were run in this session because this stop point was planning and
handover only.
