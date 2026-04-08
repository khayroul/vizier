# Ring Enforcement + Contract-Storage Alignment — Design Spec

**Date:** 2026-04-08
**Scope:** 9 surgical fixes to enforce the Three-Ring model (§0.1) and align contracts with storage.
**Constraint:** No new features. No runtime cost. Existing tests must keep passing.
**Review status:** Revised after code reviewer pass. All CRITICAL and HIGH issues resolved.

---

## Problem Statement

The Three-Ring architecture model (§0.1) defines:
- **Ring 1 (Structure):** Contracts, gates, policy. Changes rare, high-stakes.
- **Ring 2 (Config):** Workflow YAMLs, model prefs, client configs. Changes frequent, low-risk.
- **Ring 3 (Data):** Traces, exemplars, outcome memory. Fed by production.

The codebase has 4 categories of violation:
1. Ring 2 config hardcoded in Ring 1 structural code
2. Contract-storage schema mismatch (policy_logs)
3. Missing persistence bridge (policy decisions computed but not stored)
4. Unenforced immutability doctrine (ArtifactSpec)

These violations are convention failures, not bugs — they work today but will silently recur because nothing structurally prevents them.

---

## Fix 1: Workflow Registry YAML

**Ring violation:** `contracts/routing.py` hardcodes `_ACTIVE_WORKFLOWS` (line 191), `_ARTIFACT_DENSITY` (line 109), `_workflow_to_family()` (line 559). `tools/orchestrate.py` hardcodes `_WORKFLOW_FAMILY_MAP` (line 24). These are Ring 2 config in Ring 1 code.

**New file: `config/workflow_registry.yaml`**

```yaml
# Single source of truth for workflow metadata.
# Routing, orchestration, and validation all read from here.
# Adding a new workflow = adding an entry here + a YAML in manifests/workflows/.

workflows:
  poster_production:
    description: "Visual posters, banners, flyers, graphics"
    artifact_family: poster
    phase_gate: core

  document_production:
    description: "Reports, plans, proposals, written documents"
    artifact_family: document
    phase_gate: core

  brochure_production:
    description: "Brochures, pamphlets, bifold/trifold"
    artifact_family: brochure
    phase_gate: core

  childrens_book_production:
    description: "Children's picture books, illustrated stories"
    artifact_family: childrens_book
    phase_gate: publishing

  ebook_production:
    description: "Ebooks, guides, long-form content, novels"
    artifact_family: ebook
    phase_gate: core

  serial_fiction_production:
    description: "Serialised fiction with recurring characters"
    artifact_family: serial_fiction
    phase_gate: publishing

  research:
    description: "Market research, competitor analysis, audits"
    artifact_family: document
    phase_gate: research

  refinement:
    description: "Vague requests needing clarification"
    artifact_family: document
    phase_gate: core

  onboarding:
    description: "New client setup and calibration"
    artifact_family: document
    phase_gate: core

  rework:
    description: "Corrections to previous deliverables"
    artifact_family: document
    phase_gate: core

  invoice:
    description: "Invoice PDF generation"
    artifact_family: invoice
    phase_gate: extended_ops

  proposal:
    description: "Business proposals"
    artifact_family: proposal
    phase_gate: extended_ops

  company_profile:
    description: "Company profile documents"
    artifact_family: company_profile
    phase_gate: extended_ops

  social_batch:
    description: "Batch social media post generation"
    artifact_family: social_post
    phase_gate: social

  social_caption:
    description: "Social media caption generation"
    artifact_family: social_post
    phase_gate: social

  content_calendar:
    description: "Content calendar planning"
    artifact_family: content_calendar
    phase_gate: social

# Density is a property of the artifact FAMILY, not the workflow.
# Multiple workflows can share a family (e.g. research + document_production → document).
# select_design_systems() receives an artifact_family, so density must be keyed by family.
artifact_family_density:
  poster: moderate
  brochure: moderate
  document: minimal
  childrens_book: dense
  ebook: minimal
  social_post: moderate
  invoice: minimal
  proposal: minimal
  company_profile: minimal
  serial_fiction: dense
  content_calendar: moderate
```

**Code changes:**

1. **New `utils/workflow_registry.py`** (~80 lines):
   - `load_workflow_registry()` — reads YAML, returns full dict, cached with `@lru_cache`
   - `get_workflow_description(name: str) -> str`
   - `get_workflow_family(name: str) -> str` — returns string (e.g. `"poster"`). Callers needing the enum wrap with `ArtifactFamily(get_workflow_family(name))`
   - `get_density_for_family(family: str) -> str` — reads from `artifact_family_density` section. Used by `select_design_systems()` which receives a family, not a workflow name
   - `get_active_workflow_descriptions() -> list[tuple[str, str]]` — returns (name, description) tuples filtered by phase.yaml activation. **Behavior change:** the LLM routing prompt will now include `serial_fiction_production` (in active `publishing` phase), which the old hardcoded list omitted. This is correct behavior — it IS active.
   - `reload_workflow_registry() -> None` — clears `@lru_cache`, parallel to `PolicyEvaluator.reload_config()`
   - `validate_workflow_registry() -> None` — see Fix 2

2. **`contracts/routing.py`**:
   - Delete `_ACTIVE_WORKFLOWS` (line 191), `_ARTIFACT_DENSITY` (line 109), `_workflow_to_family()` (line 559)
   - `llm_route()`: build prompt from `get_active_workflow_descriptions()`
   - `select_design_systems()`: replace `_ARTIFACT_DENSITY.get(...)` with `get_density_for_family(artifact_family)`
   - `route()`: replace `_workflow_to_family(result.workflow)` with `get_workflow_family(result.workflow)`

3. **`tools/orchestrate.py`**:
   - Delete `_WORKFLOW_FAMILY_MAP` (line 24) and `_workflow_to_family()` (line 40)
   - Replace with: `ArtifactFamily(get_workflow_family(workflow_name))`, falling back to `ArtifactFamily.document` for unknown workflows

4. **`tests/test_routing.py`**:
   - Delete `TestWorkflowToFamily` class (imports the deleted `_workflow_to_family`)
   - Equivalent coverage moves to `tests/test_ring_enforcement.py` (Fix 3)
   - Update any LLM mock tests that assert on the routing prompt content, since the prompt now includes `serial_fiction_production`

---

## Fix 2: Startup Validation

**New function in `utils/workflow_registry.py`:**

`validate_workflow_registry()` — called by ring enforcement tests (mandatory) and at first registry load (fail-fast). Checks:

1. Every workflow in the registry has a matching `manifests/workflows/{name}.yaml` file
2. Every YAML file in `manifests/workflows/` has an entry in the registry
3. Every `artifact_family` is a valid `ArtifactFamily` enum member
4. Every `phase_gate` matches a phase key in `config/phase.yaml`
5. Every workflow in `phase.yaml` `includes` lists exists in the registry
6. Every family in `artifact_family_density` is a valid `ArtifactFamily` enum member

Raises `ConfigValidationError` with all violations listed (not fail-on-first). Run inside `load_workflow_registry()` on first load so mismatches surface immediately, not at request time.

---

## Fix 3: Ring Audit Test

**New test file: `tests/test_ring_enforcement.py`** (~80 lines)

Tests that enforce Ring 1/Ring 2 separation:

1. `test_no_ring2_constants_in_routing()` — asserts that `contracts.routing` module has no attributes named `_ACTIVE_WORKFLOWS`, `_ARTIFACT_DENSITY`, `_WORKFLOW_FAMILY_MAP`. Uses `hasattr()`, not source-code grep (avoids false positives in comments/docstrings).
2. `test_no_ring2_constants_in_orchestrate()` — asserts that `tools.orchestrate` module has no `_WORKFLOW_FAMILY_MAP`.
3. `test_workflow_registry_valid()` — calls `validate_workflow_registry()`.
4. `test_registry_matches_phase_yaml()` — every workflow in phase.yaml includes exists in registry.
5. `test_all_workflow_yamls_registered()` — every YAML file in `manifests/workflows/` is in the registry.
6. `test_workflow_family_lookup()` — registry returns correct families (replaces deleted `TestWorkflowToFamily` from `test_routing.py`).
7. `test_density_for_family()` — registry returns correct density values.

---

## Fix 4: policy_logs Schema Alignment

**Migration: `migrations/core.sql` update**

Update the CREATE TABLE statement to match the `PolicyDecision` contract:

```sql
CREATE TABLE IF NOT EXISTS policy_logs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id     uuid,
    job_id          uuid REFERENCES jobs(id),
    client_id       uuid REFERENCES clients(id),
    capability      text,
    action          text NOT NULL,
    gate            text NOT NULL,
    reason          text NOT NULL,
    constraints     jsonb DEFAULT '{}'::jsonb,
    evaluated_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_policy_logs_client_id ON policy_logs(client_id);
CREATE INDEX IF NOT EXISTS idx_policy_logs_gate ON policy_logs(gate);
```

Drop `outcome` column unconditionally (no production data exists yet). Remove old CREATE TABLE, replace with new.

---

## Fix 5: Policy Persistence Bridge

**Changes to `middleware/policy.py`:**

New function:
```python
def persist_policy_decision(decision: PolicyDecision) -> None:
    """Persist a policy decision to policy_logs. Non-fatal."""
```

Uses `utils.database.get_cursor()` (existing Postgres connection utility) to INSERT into `policy_logs`. Wrapped in try/except — DB failures logged but don't crash production.

**Wire into `evaluate()`:**

At the end of `evaluate()`, before returning the decision:
```python
persist_policy_decision(decision)
```

The `capability` field is already on the decision (see Fix 6), so no separate parameter needed.

Every decision (allow, block, degrade, escalate) gets logged. No caller opt-in required.

---

## Fix 6: PolicyDecision Capability Field

**Change to `contracts/policy.py`:**

Add one field to `PolicyDecision`:
```python
capability: str | None = Field(default=None, description="What was being evaluated, e.g. 'poster_production'")
```

**Change to `middleware/policy.py`:**

Update all `PolicyDecision(...)` constructor calls in `PolicyEvaluator` to include `capability=request.capability`. There are ~8 constructor sites across `_phase_gate()`, `_tool_gate()`, `_budget_gate()`, `_cost_gate()`. Each gets `capability=request.capability` added to its kwargs.

No post-construction mutation — the field is set at construction time in every code path.

---

## Fix 7: ArtifactSpec Frozen

**Change to `contracts/artifact_spec.py`:**

```python
from pydantic import ConfigDict

class ArtifactSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
```

`ProvisionalArtifactSpec` stays mutable (it's shaped during refinement).

**Note:** `RoutingResult` in `contracts/routing.py` is NOT frozen — it is mutated after construction at lines 535/540/547/553 (`result.job_id = ...`, `result.design_system = ...`). This is fine because `RoutingResult` is not `ArtifactSpec` — it's a transient routing output, not a production contract. No changes needed to `RoutingResult`.

Verified: no existing code mutates `ArtifactSpec` instances after construction. Tests only read fields. `frozen=True` is safe.

---

## Fix 8: Refinement Default Family

**Change to `contracts/artifact_spec.py`:**

Add field to `ProvisionalArtifactSpec`:
```python
family_resolved: bool = Field(default=False, description="True once artifact_family has been classified, not just defaulted")
```

**Change to `contracts/routing.py`:**

In `refine_request()`, the first-cycle provisional spec keeps `ArtifactFamily.document` as default but explicitly marks it unresolved:

```python
spec = ProvisionalArtifactSpec(
    client_id=client_id,
    artifact_family=ArtifactFamily.document,
    family_resolved=False,  # placeholder until routing classifies
    confidence=0.0,
    ...
)
```

After LLM classification resolves the family, set `family_resolved=True`.

**Change to `select_design_systems()`:** When `family_resolved=False`, skip family-based density scoring (use `"moderate"` default). This prevents wrong-family density from distorting design system selection on unclassified specs.

**Follow-up (not in scope):** `tools/orchestrate.py` line 96 also hardcodes `language="en"` when constructing a ProvisionalArtifactSpec. This is another Ring 2 value in Ring 1 code. Noted for a future pass — client config should provide the default language.

---

## Fix 9: Inline httpx Import

**Change to `tools/image.py`:**

Move `import httpx` from inside `generate_image()` function body (line 180) to module-level imports at the top of the file. `httpx` is already an indirect dependency via `fal_client`.

Trivial, 2-line change.

---

## Implementation Order

Fixes have dependencies. Implement in this order:

1. **Fix 1 + Fix 2** (registry + validation) — enables Fix 3
2. **Fix 3** (ring audit tests) — proves Fix 1 worked
3. **Fix 6** (capability field on PolicyDecision) — enables Fix 5
4. **Fix 4** (policy_logs schema) — enables Fix 5
5. **Fix 5** (persistence bridge) — depends on Fix 4 + Fix 6
6. **Fix 7** (ArtifactSpec frozen) — independent
7. **Fix 8** (family_resolved) — independent
8. **Fix 9** (httpx import) — independent

Fixes 6-9 can be parallelized after Fix 5.

---

## Files Changed (Summary)

| File | Change Type |
|------|------------|
| `config/workflow_registry.yaml` | NEW |
| `utils/workflow_registry.py` | NEW (~80 lines) |
| `tests/test_ring_enforcement.py` | NEW (~80 lines) |
| `contracts/routing.py` | MODIFY — delete 3 hardcoded dicts/functions, use registry |
| `tools/orchestrate.py` | MODIFY — delete `_WORKFLOW_FAMILY_MAP`, use registry |
| `middleware/policy.py` | MODIFY — add `persist_policy_decision()`, wire into `evaluate()`, update 8 constructor sites |
| `contracts/policy.py` | MODIFY — add `capability` field |
| `contracts/artifact_spec.py` | MODIFY — add `frozen=True` on ArtifactSpec, add `family_resolved` on ProvisionalArtifactSpec |
| `migrations/core.sql` | MODIFY — replace policy_logs CREATE TABLE, add indexes |
| `tools/image.py` | MODIFY — move httpx import to module level |
| `tests/test_routing.py` | MODIFY — delete `TestWorkflowToFamily`, update LLM mock assertions |

---

## What Won't Change

- No runtime cost — all config reads are `@lru_cache`
- No new dependencies
- No changes to workflow YAMLs
- No changes to the Hermes submodule
- No changes to the 16 workflow execution paths
- All 646 existing tests must pass (some test assertions updated)

---

## Success Criteria

After implementation:
1. `_ACTIVE_WORKFLOWS`, `_ARTIFACT_DENSITY`, `_workflow_to_family()` no longer exist in `contracts/routing.py`
2. `_WORKFLOW_FAMILY_MAP` no longer exists in `tools/orchestrate.py`
3. Adding a new workflow requires only: a YAML in `manifests/workflows/` + an entry in `config/workflow_registry.yaml`
4. `test_ring_enforcement.py` passes and would catch future hardcoded workflow lists
5. `validate_workflow_registry()` catches config-filesystem mismatches at boot
6. Every policy decision (allow/block/degrade/escalate) is persisted to `policy_logs` with `capability` and `gate`
7. `ArtifactSpec` instances raise `ValidationError` on mutation
8. Unclassified provisional specs are explicitly marked with `family_resolved=False`
9. All 646+ tests pass, pyright clean
