# S18 Knowledge Spine -- Design Spec

## Overview

Build the full knowledge retrieval pipeline: query transformation, hybrid search (pgvector + Postgres FTS), RRF merge, LLM reranking, lost-in-the-middle reordering. Also: Wisdom Vault import, exemplar promotion, outcome memory recording, and document set filtering.

**Session:** S18
**Blocks:** S19 (Self-Improvement)
**Dependencies:** S10a (tables), S11 (routing + retrieval utils), S12 (contextualise_card, seeding)
**Estimated scope:** ~350-400 lines of production code, ~150-200 lines of tests

---

## Architecture Decisions

### AD1. Preamble tables + FTS column

The `datasets`/`dataset_items` tables are §16.7 Calibration tables owned by S19, but the build plan instructs S18 to create them as a preamble via `CREATE TABLE IF NOT EXISTS`. S18 creates the DDL; S19 populates them. Wisdom Vault books use the existing `knowledge_sources` table with `source_type = 'book'`.

S18 adds DDL for:
- `datasets` and `dataset_items` tables (preamble for S19)
- A `context_prefix text` column on `knowledge_cards` (stores the contextualised prefix separately from content)
- A `search_vector tsvector GENERATED ALWAYS AS (...)` column on `knowledge_cards`
- A GIN index on `search_vector`

### AD2. Hybrid search lives in `utils/knowledge.py`

The existing `retrieve_knowledge()` does pgvector-only semantic search. S18 extends it with FTS + RRF merge, making hybrid search the default path. `assemble_context()` continues to call `retrieve_knowledge()` -- no caller changes needed.

Tool-level actions (`ingest_card`, `promote_exemplar`, `record_outcome`) go in `tools/knowledge.py` as Hermes tool functions.

### AD3. Extend `retrieval_profiles.yaml`, don't overwrite

S11 created the existing `profiles:` section controlling per-artifact-type retrieval. S18 adds a new `retrieval_pipeline:` top-level key for hybrid search config. Both sections coexist.

### AD4. Extract `embed_text()` to shared utility

`_embed_text()` in `tools/research.py` is private but used across modules. S18 extracts it to `utils/embeddings.py` as public `embed_text()`, then updates `tools/research.py` and `tools/seeding.py` to import from the new location.

### AD5. 4 query variants per architecture spec

The architecture §22.2 and exit criteria require 4 query variants (original, BM translation, EN synonym expansion, combined paraphrase). The config parameter `query_variants: 4` is set to match. For a 200-400 card corpus the 8 DB queries are fast enough on local Postgres. The config allows scaling down if needed for latency-sensitive paths.

### AD6. FTS uses `'simple'` dictionary

Mixed BM/EN content means the `'english'` stemmer would mangle Bahasa Melayu words. `'simple'` dictionary does tokenisation without language-specific stemming -- correct for keyword fallback on brand names, product codes, proper nouns.

### AD7. `ingest_card()` becomes canonical ingestion

`tools/research.py:_store_knowledge_card()` and `tools/seeding.py:_store_card()` duplicate card ingestion logic. S18's `ingest_card()` becomes the canonical implementation. The two existing functions are updated to delegate to it.

---

## File Changes

### New Files

#### `utils/embeddings.py` (~30 lines)
Extracted from `tools/research.py:_embed_text()`:

**`embed_text(text: str) -> list[float]`** — returns raw 1536-dim float list via OpenAI text-embedding-3-small API. Reusable for both DB insertion and in-memory similarity.

**`format_embedding(embedding: list[float]) -> str`** — formats as pgvector-compatible string `[0.1, 0.2, ...]` for SQL insertion.

#### `tools/knowledge.py` (~150 lines)
Hermes tool functions:

**`ingest_card(source_id, content, card_type, title, tags, domain, client_id=None) -> str`**
- Calls `contextualise_card()` from `utils.retrieval` (S12)
- Embeds contextualised text via `embed_text()` from `utils.embeddings`
- Inserts into `knowledge_cards` table
- Returns card_id (UUID string)

**`promote_exemplar(artifact_id, client_id, operator_rating, job_id) -> str | None`**
- Only promotes if `operator_rating == 5` (explicitly_approved)
- Queries `feedback` table via `job_id` + `artifact_id` to check `anchor_set` flag per anti-drift #56 — anchor set feedback never enters exemplar library
- If multiple feedback records exist for the artifact, checks the most recent one for the given job
- Creates `exemplars` record from artifact metadata
- Returns exemplar_id or None if not promoted

**`record_outcome(job_id, outcome_data: dict) -> str`**
- Inserts into `outcome_memory` table
- Fields: `first_pass_approved`, `revision_count`, `accepted_as_on_brand`, `human_feedback_summary`, `cost_summary`, `quality_summary`, `promote_to_exemplar`
- Returns outcome_memory record id

#### `tools/wisdom_vault.py` (~80 lines)

**`import_book(vault_path, title, domain=None, client_id=None) -> dict`**
- Reads Obsidian markdown file
- Parses YAML frontmatter for metadata
- Splits content into cards: by markdown headings (## or ###), fallback to ~100-word paragraph chunks if no headings. Target: 50-150 words per card
- Creates `knowledge_sources` record with `source_type = 'book'`
- For each chunk: calls `ingest_card()` (which contextualises + embeds)
- Returns `{"source_id": str, "card_count": int, "title": str}`

**`import_vault_directory(vault_dir, domain_map=None, client_id=None) -> list[dict]`**
- Glob `*.md` files in directory
- Optional `domain_map: {filename_pattern: domain}` for auto-tagging
- Calls `import_book()` per file
- Returns list of import results

#### `config/retrieval_profiles.yaml` -- EXTEND (not overwrite)

Add new `retrieval_pipeline:` key:
```yaml
retrieval_pipeline:
  embedding_model: text-embedding-3-small
  embedding_dim: 1536
  min_score: 0.65
  rrf_weights:
    dense: 1.0
    sparse: 0.25
  reranker: gpt-5.4-mini
  reranker_candidates: 20
  reranker_top_k: 5
  query_variants: 4        # 4 per architecture §22.2 (original, BM, EN expansion, paraphrase)
  lost_in_middle: true
  fts_dictionary: simple    # 'simple' for mixed BM/EN content
```

#### `migrations/extended.sql` -- Preamble tables + FTS column

```sql
-- S18 preamble: datasets/dataset_items for S19 calibration (§16.7)
CREATE TABLE IF NOT EXISTS datasets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  description text,
  source_type text,
  status text DEFAULT 'active',
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dataset_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id uuid REFERENCES datasets(id) ON DELETE CASCADE,
  content jsonb NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- S18: context_prefix column for storing contextualised prefix separately
-- The prefix is used for embedding; raw content is served to production models.
ALTER TABLE knowledge_cards
  ADD COLUMN IF NOT EXISTS context_prefix text;

-- S18: FTS support via generated tsvector column
-- Uses 'simple' dictionary (not 'english') for mixed BM/EN content.
-- Safe for existing rows (auto-computed on ADD COLUMN).
-- Column must not pre-exist as a non-generated column.
ALTER TABLE knowledge_cards
  ADD COLUMN IF NOT EXISTS search_vector tsvector
  GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(title, '') || ' ' || content)
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_knowledge_cards_fts
  ON knowledge_cards USING gin(search_vector);
```

#### `contracts/knowledge.py` (~30 lines)

Pydantic models for structured return types:
```python
class RetrievedCard(BaseModel):
    card_id: str
    title: str
    content: str
    context_prefix: str | None  # stored on knowledge_cards, populated during ingestion
    score: float
    source: str  # "semantic" | "keyword" | "hybrid"
    domain: str | None
    tags: list[str]

class PipelineConfig(BaseModel):
    embedding_model: str
    min_score: float
    rrf_weights: dict[str, float]
    reranker: str
    reranker_candidates: int
    reranker_top_k: int
    query_variants: int
    lost_in_middle: bool
    fts_dictionary: str

class SearchResult(BaseModel):
    cards: list[RetrievedCard]
    query_variants: list[str]
    pipeline_config: PipelineConfig
```

### Modified Files

#### `utils/knowledge.py` -- EXTEND

Add to existing module:

**`_search_fts(query, client_id, document_set_id=None, top_k=20) -> list[dict]`**
- Postgres FTS via `plainto_tsquery('simple', query)` against `search_vector` column
- `client_id` is required (matches `_retrieve_by_embedding` contract)
- Filters by `document_set_id` via JOIN if provided, else by `client_id`
- Returns top_k results with `ts_rank` scores

**`_generate_query_variants(query, n=4) -> list[str]`**
- GPT-5.4-mini single call: generate original + BM translation + EN synonym expansion + combined paraphrase
- Returns list of 4 variant strings including original

**`_rrf_merge(semantic_results, fts_results, dense_weight=1.0, sparse_weight=0.25) -> list[dict]`**
- Reciprocal Rank Fusion: `score = sum(weight / (k + rank))` for each result across both lists
- Deduplicates by card_id
- Returns merged list sorted by RRF score descending

**`_rerank_with_llm(query, candidates, top_k=5) -> list[dict]`**
- Single GPT-5.4-mini call: pass query + all candidate texts, ask for ranked indices by relevance
- Returns top_k candidates with relevance scores
- Prompt returns JSON array of indices
- On JSON parse failure: falls back to RRF-merged order (skip reranking gracefully)

**Update `retrieve_knowledge()`:**
- Load `retrieval_pipeline` config from `retrieval_profiles.yaml`
- For each query variant: run pgvector search + FTS search in sequence, merge via RRF
- Merge results across variants, deduplicate
- Rerank with LLM
- Apply lost-in-middle reordering (existing function)
- Return `list[RetrievedCard]`

**Update `assemble_context()`:**
- No interface change -- it already calls `retrieve_knowledge()` internally
- The hybrid search upgrade is transparent to callers

#### `tools/research.py` -- REFACTOR

- Remove `_embed_text()` function body, replace with: `from utils.embeddings import embed_text, format_embedding`
- Refactor `_store_knowledge_card()`: extract source creation to remain in-place, delegate card insertion (contextualise + embed + INSERT) to `tools.knowledge.ingest_card(source_id, ...)`
- The function still creates its own `knowledge_sources` record, then passes `source_id` to `ingest_card()`

#### `tools/seeding.py` -- REFACTOR

- Refactor `_store_card()`: same pattern — keep source creation logic, delegate card insertion to `tools.knowledge.ingest_card(source_id, ...)`
- Import `embed_text` from `utils.embeddings` if still needed for non-card embedding tasks

### Test File

#### `tests/test_knowledge_spine.py` (~120 lines)

Tests with mocked DB and LLM calls:

1. **Card ingestion**: card inserted with contextualised prefix ("This card is from...")
2. **Hybrid search**: results from BOTH pgvector AND FTS merged via RRF
3. **Query variants**: generates 4 variants (original, BM, EN expansion, paraphrase) for test query
4. **Reranker**: reorders candidates and selects top_k with scores
5. **Lost-in-middle**: best at position 1, second-best at last position
6. **Document set filtering**: cards in set returned, cards outside excluded
7. **Exemplar promotion**: promoted only from rating 5
8. **Exemplar NOT promoted**: from rating < 5
9. **Exemplar anchor_set blocked**: anchor_set feedback excluded from promotion
10. **Outcome memory**: record created with required fields
11. **Semantic search**: relevant results for "Raya batik promotion"
12. **FTS keyword search**: catches exact "DMB" that semantic might miss
13. **Wisdom Vault import**: test markdown -> contextualised knowledge cards
14. **Import path**: `from utils.retrieval import contextualise_card` works
15. **Same function**: contextualisation is S12's function, not a copy
16. **Config loaded**: retrieval pipeline config from YAML
17. **RRF weights**: configurable (dense 1.0, sparse 0.25)

---

## Pipeline Data Flow

```
Query: "Raya batik promotion for DMB"
    |
    v
_generate_query_variants(query, n=4)
    |-> ["Raya batik promotion for DMB",
    |    "promosi batik Raya untuk DMB",           # BM translation
    |    "Hari Raya batik marketing campaign DMB",  # EN synonym expansion
    |    "DMB festive batik promotional material"]   # combined paraphrase
    |
    v (for each of 4 variants)
    +---> _retrieve_by_embedding(variant_embedding) -> top 20 semantic
    +---> _search_fts(variant) ---------------------> top 20 keyword
    |         |
    |         v
    |    _rrf_merge(semantic, fts, dense=1.0, sparse=0.25)
    |         |-> top 20 unique per variant
    |
    v (merge across all variants, deduplicate by card_id, keep best score)
    |-> ~20-60 unique candidates
    |
    v
_rerank_with_llm(query, candidates, top_k=5)
    |-> top 5 with relevance scores
    |   (on JSON parse failure: skip, use RRF order)
    |
    v
lost_in_middle_reorder(top_5)
    |-> [best, 3rd, 4th, 5th, 2nd-best]
    |
    v
Return: list[RetrievedCard]
```

---

## Edge Cases

- **Empty corpus**: If no knowledge cards exist for a client (fresh onboarding), `retrieve_knowledge()` returns empty list. `_rerank_with_llm()` and `lost_in_middle_reorder()` handle empty/single-item inputs gracefully (pass-through).
- **Reranker failure**: On JSON parse failure from GPT-5.4-mini, fall back to RRF-merged order. Log the failure via `track_span`.
- **Wisdom Vault nested headings**: `##` creates top-level card splits. `###` creates sub-splits only within each `##` section. Avoid creating very small chunks from deeply nested headings.
- **Duplicate cards**: `ingest_card()` does not deduplicate — callers are responsible for checking existing cards before re-ingesting. Wisdom Vault checks for existing `knowledge_sources` with same title before importing.

---

## Anti-Drift Compliance

| Rule | How addressed |
|------|--------------|
| #54 GPT-5.4-mini only | All model_preference = gpt-5.4-mini (reranker, query variants, contextualisation) |
| #3 Retrieval before generation | Pipeline runs before any production prompt |
| #13 Silence not approval | promote_exemplar requires explicit rating 5 |
| #56 Anchor set sacred | promote_exemplar checks and excludes anchor_set feedback |
| #7 Binaries in MinIO | No binary storage in this session |
| Import don't rebuild | contextualise_card from S12, lost_in_middle_reorder from S11 |

---

## Exit Criteria Mapping

| Criterion | Verified by |
|-----------|------------|
| Card ingested with contextualised embedding | Test 1 |
| Hybrid search from BOTH pgvector AND FTS via RRF | Test 2 |
| Query transformation generates variants incl BM/EN | Test 3 |
| Reranker reorders and selects top_k | Test 4 |
| Lost-in-middle: best at pos 1, second-best at last | Test 5 |
| Exemplar promoted from rating 5 | Test 7 |
| Outcome memory created | Test 10 |
| pgvector returns for "Raya batik promotion" | Test 11 |
| FTS catches "DMB" | Test 12 |
| Wisdom Vault imports -> cards | Test 13 |
| contextualise_card imported from S12 | Test 14, 15 |
| Document set filtering works | Test 6 |
| pyright clean, all tests pass | CI |
