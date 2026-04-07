# S18 Knowledge Spine Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full knowledge retrieval pipeline with hybrid search, Wisdom Vault import, exemplar promotion, and outcome memory.

**Architecture:** Extend `utils/knowledge.py` with FTS + RRF merge + query variants + LLM reranking on top of existing pgvector search. Create `tools/knowledge.py` for ingestion/promotion/outcome tool actions. Extract shared `embed_text()` to `utils/embeddings.py`. Create `tools/wisdom_vault.py` for Obsidian import.

**Tech Stack:** PostgreSQL 16 (pgvector + FTS), OpenAI text-embedding-3-small, GPT-5.4-mini, psycopg2, httpx, PyYAML, Pydantic

**Spec:** `docs/superpowers/specs/2026-04-08-s18-knowledge-spine-design.md`

---

## Chunk 1: Foundation (migrations, embeddings utility, contracts)

### Task 1: Database migrations

**Files:**
- Modify: `migrations/extended.sql`

- [ ] **Step 1: Write the migration SQL**

Add to `migrations/extended.sql`:

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

-- S18: context_prefix column for storing contextualised prefix separately.
-- The prefix is used for embedding; raw content is served to production models.
ALTER TABLE knowledge_cards
  ADD COLUMN IF NOT EXISTS context_prefix text;

-- S18: FTS support via generated tsvector column.
-- Uses 'simple' dictionary (not 'english') for mixed BM/EN content.
ALTER TABLE knowledge_cards
  ADD COLUMN IF NOT EXISTS search_vector tsvector
  GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(title, '') || ' ' || content)
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_knowledge_cards_fts
  ON knowledge_cards USING gin(search_vector);
```

- [ ] **Step 2: Run the migration**

Run: `psql -d vizier -f migrations/extended.sql`
Expected: Statements complete without error. Tables `datasets`, `dataset_items` created. Columns `context_prefix`, `search_vector` added to `knowledge_cards`.

- [ ] **Step 3: Verify the migration**

Run: `psql -d vizier -c "\d knowledge_cards" | grep -E "context_prefix|search_vector"`
Expected: Both columns visible — `context_prefix text` and `search_vector tsvector`.

Run: `psql -d vizier -c "\d datasets"`
Expected: Table exists with `id`, `name`, `description`, `source_type`, `status`, `created_at`.

- [ ] **Step 4: Commit**

```bash
git add migrations/extended.sql
git commit -m "feat(s18): add FTS column, context_prefix, and preamble tables"
```

---

### Task 2: Extract `embed_text()` to shared utility

**Files:**
- Create: `utils/embeddings.py`
- Modify: `tools/research.py:400-419` (remove `_embed_text`, add import)
- Modify: `tools/seeding.py:261` (update import)

- [ ] **Step 1: Write the test for embed_text**

Create `tests/test_embeddings.py`:

```python
"""Tests for shared embedding utility."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from utils.embeddings import embed_text, format_embedding


def test_embed_text_returns_float_list() -> None:
    """embed_text returns a list of 1536 floats."""
    fake_vector = [0.1] * 1536
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"embedding": fake_vector}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("utils.embeddings.httpx.post", return_value=mock_resp):
        result = embed_text("test text")

    assert isinstance(result, list)
    assert len(result) == 1536
    assert all(isinstance(v, float) for v in result)


def test_format_embedding_produces_pgvector_string() -> None:
    """format_embedding produces a pgvector-compatible string."""
    vector = [0.1, 0.2, 0.3]
    result = format_embedding(vector)
    assert result == "[0.1,0.2,0.3]"
    assert result.startswith("[")
    assert result.endswith("]")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3.11 -m pytest tests/test_embeddings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.embeddings'`

- [ ] **Step 3: Write `utils/embeddings.py`**

```python
"""Shared text embedding utility.

Wraps OpenAI text-embedding-3-small API. Extracted from tools/research.py
so all modules share one embedding function.
"""
from __future__ import annotations

import os

import httpx


def embed_text(text: str) -> list[float]:
    """Generate 1536-dim embedding via text-embedding-3-small.

    Returns raw float list, reusable for both DB insertion
    and in-memory similarity computation.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        json={"model": "text-embedding-3-small", "input": text},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]  # type: ignore[no-any-return]


def format_embedding(embedding: list[float]) -> str:
    """Format float list as pgvector-compatible string '[0.1,0.2,...]'."""
    return "[" + ",".join(str(v) for v in embedding) + "]"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3.11 -m pytest tests/test_embeddings.py -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `pyright utils/embeddings.py`
Expected: 0 errors

- [ ] **Step 6: Update `tools/research.py` — remove `_embed_text`, use shared utility**

Replace `_embed_text` function (lines 400-419) with an import, and update `_store_knowledge_card` to use the new functions:

```python
# At top of tools/research.py, add:
from utils.embeddings import embed_text, format_embedding

# Remove the entire _embed_text function (lines 400-419)

# In _store_knowledge_card (line 348), change:
#   embedding = _embed_text(contextualised_text)
# to:
#   embedding = format_embedding(embed_text(contextualised_text))
```

- [ ] **Step 7: Update `tools/seeding.py` — use shared utility**

Change line 261:
```python
# Old:
from tools.research import _embed_text
# New:
from utils.embeddings import embed_text, format_embedding
```

Update `_store_card` (line 264):
```python
# Old:
embedding = _embed_text(contextualised_text)
# New:
embedding = format_embedding(embed_text(contextualised_text))
```

- [ ] **Step 8: Run existing tests to verify no regressions**

Run: `python3.11 -m pytest tests/test_research.py -v -k "not swipe_ingest and not visual_dna"`
Expected: All non-API-dependent tests pass

- [ ] **Step 9: Commit**

```bash
git add utils/embeddings.py tests/test_embeddings.py tools/research.py tools/seeding.py
git commit -m "refactor(s18): extract embed_text to utils/embeddings"
```

---

### Task 3: Knowledge contracts

**Files:**
- Create: `contracts/knowledge.py`

- [ ] **Step 1: Write the test**

Add to `tests/test_contracts.py` (or create `tests/test_knowledge_contracts.py`):

```python
"""Tests for knowledge contracts."""
from __future__ import annotations

from contracts.knowledge import RetrievedCard, PipelineConfig, SearchResult


def test_retrieved_card_from_dict() -> None:
    card = RetrievedCard(
        card_id="abc-123",
        title="Raya promo",
        content="30% discount on batik",
        context_prefix="This card is from DMB's Raya campaign.",
        score=0.85,
        source="hybrid",
        domain="marketing",
        tags=["raya", "batik"],
    )
    assert card.card_id == "abc-123"
    assert card.score == 0.85


def test_retrieved_card_optional_prefix() -> None:
    card = RetrievedCard(
        card_id="abc-123",
        title="Test",
        content="content",
        context_prefix=None,
        score=0.7,
        source="semantic",
        domain=None,
        tags=[],
    )
    assert card.context_prefix is None
    assert card.domain is None


def test_pipeline_config() -> None:
    config = PipelineConfig(
        embedding_model="text-embedding-3-small",
        embedding_dim=1536,
        min_score=0.65,
        rrf_weights={"dense": 1.0, "sparse": 0.25},
        reranker="gpt-5.4-mini",
        reranker_candidates=20,
        reranker_top_k=5,
        query_variants=4,
        lost_in_middle=True,
        fts_dictionary="simple",
    )
    assert config.query_variants == 4
    assert config.rrf_weights["dense"] == 1.0


def test_search_result() -> None:
    card = RetrievedCard(
        card_id="x", title="t", content="c", context_prefix=None,
        score=0.8, source="semantic", domain=None, tags=[],
    )
    config = PipelineConfig(
        embedding_model="text-embedding-3-small", min_score=0.65,
        rrf_weights={"dense": 1.0, "sparse": 0.25}, reranker="gpt-5.4-mini",
        reranker_candidates=20, reranker_top_k=5, query_variants=4,
        lost_in_middle=True, fts_dictionary="simple",
    )
    result = SearchResult(cards=[card], query_variants=["q1"], pipeline_config=config)
    assert len(result.cards) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3.11 -m pytest tests/test_knowledge_contracts.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `contracts/knowledge.py`**

```python
"""Knowledge spine contracts.

Pydantic models for retrieval pipeline return types.
"""
from __future__ import annotations

from pydantic import BaseModel


class RetrievedCard(BaseModel):
    """A knowledge card returned by the retrieval pipeline."""

    card_id: str
    title: str
    content: str
    context_prefix: str | None
    score: float
    source: str  # "semantic" | "keyword" | "hybrid"
    domain: str | None
    tags: list[str]


class PipelineConfig(BaseModel):
    """Retrieval pipeline configuration loaded from YAML."""

    embedding_model: str
    embedding_dim: int
    min_score: float
    rrf_weights: dict[str, float]
    reranker: str
    reranker_candidates: int
    reranker_top_k: int
    query_variants: int
    lost_in_middle: bool
    fts_dictionary: str


class SearchResult(BaseModel):
    """Result of a full knowledge search pipeline run."""

    cards: list[RetrievedCard]
    query_variants: list[str]
    pipeline_config: PipelineConfig
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3.11 -m pytest tests/test_knowledge_contracts.py -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `pyright contracts/knowledge.py`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add contracts/knowledge.py tests/test_knowledge_contracts.py
git commit -m "feat(s18): knowledge spine Pydantic contracts"
```

---

### Task 4: Extend retrieval_profiles.yaml

**Files:**
- Modify: `config/retrieval_profiles.yaml`

- [ ] **Step 1: Append `retrieval_pipeline` key to end of file**

Add at the bottom of `config/retrieval_profiles.yaml`:

```yaml

# ---------------------------------------------------------------------------
# Retrieval Pipeline Config (S18 — hybrid search, RRF, reranking)
# ---------------------------------------------------------------------------
# Controls HOW retrieval works. The 'profiles' section above controls
# WHAT gets retrieved per artifact type.

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
  query_variants: 4
  lost_in_middle: true
  fts_dictionary: simple
```

- [ ] **Step 2: Verify YAML parses correctly**

Run: `python3.11 -c "import yaml; d = yaml.safe_load(open('config/retrieval_profiles.yaml')); print(d['retrieval_pipeline']); print(d['profiles']['poster'])"`
Expected: Both sections print without error. `retrieval_pipeline` shows `query_variants: 4`, `profiles.poster` shows `knowledge_cards_top_k: 5`.

- [ ] **Step 3: Commit**

```bash
git add config/retrieval_profiles.yaml
git commit -m "feat(s18): add retrieval_pipeline config for hybrid search"
```

---

## Chunk 2: Hybrid Search Pipeline (utils/knowledge.py extensions)

### Task 5: FTS search function

**Files:**
- Modify: `utils/knowledge.py`
- Test: `tests/test_knowledge_spine.py`

- [ ] **Step 1: Write the FTS search test**

Create `tests/test_knowledge_spine.py` with shared fixtures:

```python
"""S18 — Tests for knowledge spine: hybrid retrieval, Wisdom Vault, exemplar promotion.

Requires: running Postgres (vizier db).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgres://localhost:5432/vizier")

from utils.database import get_cursor, run_migration
from utils.spans import DB_PATH as SPANS_DB_PATH
from utils.spans import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> None:
    """Run core.sql + extended.sql before the test session."""
    base = Path(__file__).resolve().parent.parent / "migrations"
    for sql_file in ["core.sql", "extended.sql"]:
        path = base / sql_file
        if path.exists():
            run_migration(path)


@pytest.fixture(autouse=True)
def _isolated_spans(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "spans.db"
    monkeypatch.setattr("utils.spans.DB_PATH", db_path)
    monkeypatch.setattr("utils.call_llm.DB_PATH", db_path)
    init_db(db_path)
    return db_path


@pytest.fixture()
def client_id() -> str:
    """Insert a test client and return its id."""
    cid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO clients (id, name, industry) VALUES (%s, %s, %s)",
            (cid, f"test-client-{cid[:8]}", "testing"),
        )
    return cid


@pytest.fixture()
def _seed_cards(client_id: str) -> list[str]:
    """Insert test knowledge cards with embeddings and return card ids.

    Creates 5 cards: 3 about Raya/batik (should match semantic + FTS),
    1 about DMB (should match FTS for exact term), 1 unrelated.
    """
    fake_embedding = "[" + ",".join(["0.1"] * 1536) + "]"
    card_ids: list[str] = []

    cards = [
        {"title": "Raya Batik Promo", "content": "Diskaun 30% untuk semua produk batik sempena Raya.", "domain": "marketing"},
        {"title": "Batik Design Guide", "content": "Traditional batik patterns use wax-resist dyeing technique.", "domain": "design"},
        {"title": "Festive Campaign", "content": "Raya promotional campaign for batik products in Malaysia.", "domain": "marketing"},
        {"title": "DMB Brand Profile", "content": "DMB is a leading Malaysian batik brand established in 1985.", "domain": "brand"},
        {"title": "Cloud Infrastructure", "content": "AWS EC2 instances for compute workloads.", "domain": "tech"},
    ]

    # Create a source first
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO knowledge_sources (client_id, source_type, title, domain, status) "
            "VALUES (%s, 'test', 'Test Source', 'testing', 'active') RETURNING id",
            (client_id,),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

        for card in cards:
            cur.execute(
                """INSERT INTO knowledge_cards
                    (source_id, client_id, card_type, title, content, tags,
                     domain, embedding, context_prefix, confidence, status)
                VALUES (%s, %s, 'test', %s, %s, %s, %s, %s, %s, 0.8, 'active')
                RETURNING id""",
                (
                    source_id, client_id, card["title"], card["content"],
                    ["test"], card["domain"], fake_embedding,
                    f"Test context for {card['title']}.",
                ),
            )
            row = cur.fetchone()
            assert row is not None
            card_ids.append(str(row["id"]))

    return card_ids


# ---------------------------------------------------------------------------
# FTS tests
# ---------------------------------------------------------------------------

def test_fts_catches_exact_term_dmb(client_id: str, _seed_cards: list[str]) -> None:
    """FTS keyword search catches exact term 'DMB' that semantic might miss."""
    from utils.knowledge import _search_fts

    results = _search_fts("DMB", client_id)
    assert len(results) >= 1
    titles = [r["title"] for r in results]
    assert "DMB Brand Profile" in titles


def test_fts_returns_ranked_results(client_id: str, _seed_cards: list[str]) -> None:
    """FTS returns results with ts_rank scores."""
    from utils.knowledge import _search_fts

    results = _search_fts("batik", client_id)
    assert len(results) >= 2
    # All results should have a rank score
    for r in results:
        assert "rank" in r
        assert r["rank"] >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_fts_catches_exact_term_dmb -v`
Expected: FAIL — `ImportError: cannot import name '_search_fts'`

- [ ] **Step 3: Implement `_search_fts` in `utils/knowledge.py`**

Add after the `_retrieve_by_recency` function (after line 209):

```python
def _search_fts(
    query: str,
    client_id: str,
    document_set_id: str | None = None,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """Full-text search against knowledge_cards using tsvector.

    Uses 'simple' dictionary for mixed BM/EN content.
    Filters by document_set_id if provided, else by client_id.
    """
    if document_set_id:
        sql = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence, kc.context_prefix,
                   ts_rank(kc.search_vector, plainto_tsquery('simple', %s)) AS rank
            FROM knowledge_cards kc
            JOIN document_set_members dsm ON dsm.knowledge_card_id = kc.id
            WHERE kc.client_id = %s
              AND kc.status = 'active'
              AND dsm.document_set_id = %s
              AND kc.search_vector @@ plainto_tsquery('simple', %s)
            ORDER BY rank DESC
            LIMIT %s
        """
        params = (query, client_id, document_set_id, query, top_k)
    else:
        sql = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence, kc.context_prefix,
                   ts_rank(kc.search_vector, plainto_tsquery('simple', %s)) AS rank
            FROM knowledge_cards kc
            WHERE kc.client_id = %s
              AND kc.status = 'active'
              AND kc.search_vector @@ plainto_tsquery('simple', %s)
            ORDER BY rank DESC
            LIMIT %s
        """
        params = (query, client_id, query, top_k)

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_fts_catches_exact_term_dmb tests/test_knowledge_spine.py::test_fts_returns_ranked_results -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add utils/knowledge.py tests/test_knowledge_spine.py
git commit -m "feat(s18): add FTS search to utils/knowledge"
```

---

### Task 6: RRF merge function

**Files:**
- Modify: `utils/knowledge.py`
- Modify: `tests/test_knowledge_spine.py`

- [ ] **Step 1: Write the RRF merge test**

Add to `tests/test_knowledge_spine.py`:

```python
def test_rrf_merge_combines_and_deduplicates() -> None:
    """RRF merge combines semantic + FTS results, deduplicates by card id."""
    from utils.knowledge import _rrf_merge

    semantic = [
        {"id": "a", "title": "Card A", "similarity": 0.9},
        {"id": "b", "title": "Card B", "similarity": 0.8},
        {"id": "c", "title": "Card C", "similarity": 0.7},
    ]
    fts = [
        {"id": "b", "title": "Card B", "rank": 0.5},
        {"id": "d", "title": "Card D", "rank": 0.4},
        {"id": "a", "title": "Card A", "rank": 0.3},
    ]

    merged = _rrf_merge(semantic, fts, dense_weight=1.0, sparse_weight=0.25)

    # Should have 4 unique cards (a, b, c, d)
    ids = [r["id"] for r in merged]
    assert len(ids) == 4
    assert len(set(ids)) == 4
    # Cards appearing in both lists should rank higher
    assert ids[0] in ("a", "b")  # a and b appear in both


def test_rrf_weights_configurable() -> None:
    """RRF merge respects dense and sparse weight parameters."""
    from utils.knowledge import _rrf_merge

    semantic = [{"id": "a", "similarity": 0.9}]
    fts = [{"id": "b", "rank": 0.5}]

    # With equal weights, both should appear
    merged = _rrf_merge(semantic, fts, dense_weight=1.0, sparse_weight=1.0)
    assert len(merged) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_rrf_merge_combines_and_deduplicates -v`
Expected: FAIL — `ImportError: cannot import name '_rrf_merge'`

- [ ] **Step 3: Implement `_rrf_merge`**

Add to `utils/knowledge.py`:

```python
_RRF_K = 60  # standard RRF constant


def _rrf_merge(
    semantic_results: list[dict[str, Any]],
    fts_results: list[dict[str, Any]],
    dense_weight: float = 1.0,
    sparse_weight: float = 0.25,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion merge of semantic and FTS results.

    score = dense_weight / (k + rank_in_semantic) + sparse_weight / (k + rank_in_fts)
    Deduplicates by card id, keeping the merged score.
    """
    scores: dict[str, float] = {}
    card_data: dict[str, dict[str, Any]] = {}

    for rank, item in enumerate(semantic_results):
        card_id = str(item["id"])
        scores[card_id] = scores.get(card_id, 0.0) + dense_weight / (_RRF_K + rank + 1)
        card_data[card_id] = item

    for rank, item in enumerate(fts_results):
        card_id = str(item["id"])
        scores[card_id] = scores.get(card_id, 0.0) + sparse_weight / (_RRF_K + rank + 1)
        if card_id not in card_data:
            card_data[card_id] = item

    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [{**card_data[cid], "rrf_score": scores[cid]} for cid in sorted_ids]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_rrf_merge_combines_and_deduplicates tests/test_knowledge_spine.py::test_rrf_weights_configurable -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add utils/knowledge.py tests/test_knowledge_spine.py
git commit -m "feat(s18): add RRF merge for hybrid search"
```

---

### Task 7: Query variant generation

**Files:**
- Modify: `utils/knowledge.py`
- Modify: `tests/test_knowledge_spine.py`

- [ ] **Step 1: Write the test**

Add to `tests/test_knowledge_spine.py`:

```python
def test_generate_query_variants_produces_four(
    _isolated_spans: Path,
) -> None:
    """Query transformation generates 4 variants including BM and EN."""
    from utils.knowledge import _generate_query_variants

    mock_response = {
        "content": '{"variants": ["promosi batik Raya untuk DMB", "Hari Raya batik marketing DMB", "DMB festive batik promotional"]}',
        "model": "gpt-5.4-mini",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.0001,
    }

    with patch("utils.knowledge.call_llm", return_value=mock_response):
        variants = _generate_query_variants("Raya batik promotion for DMB")

    assert len(variants) == 4
    # Original query is always first
    assert variants[0] == "Raya batik promotion for DMB"
    # Other variants are non-empty strings
    for v in variants[1:]:
        assert isinstance(v, str)
        assert len(v) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_generate_query_variants_produces_four -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `_generate_query_variants`**

Add import at top of `utils/knowledge.py`:
```python
import json

from utils.call_llm import call_llm
```

Add the function:

```python
_QUERY_VARIANT_PREFIX: list[dict[str, str]] = [
    {
        "role": "system",
        "content": (
            "You generate search query variants for a Malaysian marketing knowledge base. "
            "Given a query, produce exactly 3 variants:\n"
            "1. Bahasa Melayu translation\n"
            "2. English synonym expansion (different words, same meaning)\n"
            "3. Combined paraphrase (mix of BM/EN terms)\n"
            'Return JSON: {"variants": ["variant1", "variant2", "variant3"]}'
        ),
    },
]


def _generate_query_variants(query: str, n: int = 4) -> list[str]:
    """Generate query variants via GPT-5.4-mini for multi-lingual retrieval.

    Returns [original, BM_translation, EN_expansion, combined_paraphrase].
    On LLM failure, returns [original] as fallback.
    """
    try:
        result = call_llm(
            stable_prefix=_QUERY_VARIANT_PREFIX,
            variable_suffix=[{"role": "user", "content": query}],
            model="gpt-5.4-mini",
            temperature=0.5,
            max_tokens=200,
            response_format={"type": "json_object"},
            operation_type="extract",
        )
        raw = result["content"].strip()
        parsed = json.loads(raw)
        variants = parsed.get("variants", parsed) if isinstance(parsed, dict) else parsed
        if isinstance(variants, list):
            return [query, *[str(v) for v in variants[:n - 1]]]
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Query variant generation failed, using original query only")

    return [query]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_generate_query_variants_produces_four -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add utils/knowledge.py tests/test_knowledge_spine.py
git commit -m "feat(s18): add query variant generation for hybrid search"
```

---

### Task 8: LLM reranker

**Files:**
- Modify: `utils/knowledge.py`
- Modify: `tests/test_knowledge_spine.py`

- [ ] **Step 1: Write the test**

Add to `tests/test_knowledge_spine.py`:

```python
def test_reranker_selects_top_k(_isolated_spans: Path) -> None:
    """Reranker reorders 20 candidates and selects top 5 with scores."""
    from utils.knowledge import _rerank_with_llm

    candidates = [
        {"id": str(i), "title": f"Card {i}", "content": f"Content {i}", "rrf_score": 0.1}
        for i in range(20)
    ]

    # LLM returns indices [5, 3, 10, 1, 18] as the top 5
    mock_response = {
        "content": '{"indices": [5, 3, 10, 1, 18]}',
        "model": "gpt-5.4-mini",
        "input_tokens": 3000,
        "output_tokens": 20,
        "cost_usd": 0.001,
    }

    with patch("utils.knowledge.call_llm", return_value=mock_response):
        reranked = _rerank_with_llm("test query", candidates, top_k=5)

    assert len(reranked) == 5
    # First result should be candidate at index 5
    assert reranked[0]["id"] == "5"
    # All results should have a relevance_score
    for r in reranked:
        assert "relevance_score" in r


def test_reranker_fallback_on_bad_json(_isolated_spans: Path) -> None:
    """Reranker falls back to RRF order on malformed JSON."""
    from utils.knowledge import _rerank_with_llm

    candidates = [
        {"id": "a", "content": "A", "rrf_score": 0.9},
        {"id": "b", "content": "B", "rrf_score": 0.8},
        {"id": "c", "content": "C", "rrf_score": 0.7},
    ]

    mock_response = {
        "content": "not valid json!!!",
        "model": "gpt-5.4-mini",
        "input_tokens": 100,
        "output_tokens": 10,
        "cost_usd": 0.0001,
    }

    with patch("utils.knowledge.call_llm", return_value=mock_response):
        reranked = _rerank_with_llm("test", candidates, top_k=3)

    # Falls back to original order
    assert len(reranked) == 3
    assert reranked[0]["id"] == "a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_reranker_selects_top_k -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `_rerank_with_llm`**

Add to `utils/knowledge.py`:

```python
_RERANK_PREFIX: list[dict[str, str]] = [
    {
        "role": "system",
        "content": (
            "You are a relevance judge. Given a query and numbered candidate documents, "
            "return the indices (0-based) of the most relevant documents, "
            "ordered by relevance (most relevant first). "
            'Return JSON: {"indices": [0, 3, 7, ...]}'
        ),
    },
]


def _rerank_with_llm(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Score candidates jointly with query via GPT-5.4-mini.

    On JSON parse failure, falls back to input order (RRF-merged).
    """
    if len(candidates) <= top_k:
        return [{**c, "relevance_score": 1.0 - (idx * 0.1)} for idx, c in enumerate(candidates)]

    numbered = "\n".join(
        f"[{i}] {c.get('title', '')} — {c.get('content', '')[:200]}"
        for i, c in enumerate(candidates)
    )
    user_msg = f"Query: {query}\n\nCandidates:\n{numbered}\n\nReturn top {top_k} indices."

    try:
        result = call_llm(
            stable_prefix=_RERANK_PREFIX,
            variable_suffix=[{"role": "user", "content": user_msg}],
            model="gpt-5.4-mini",
            temperature=0.0,
            max_tokens=100,
            response_format={"type": "json_object"},
            operation_type="classify",
        )
        parsed = json.loads(result["content"].strip())
        indices = parsed.get("indices", parsed) if isinstance(parsed, dict) else parsed
        if isinstance(indices, list):
            reranked: list[dict[str, Any]] = []
            for rank, idx in enumerate(indices[:top_k]):
                if isinstance(idx, int) and 0 <= idx < len(candidates):
                    candidate = {**candidates[idx]}
                    candidate["relevance_score"] = 1.0 - (rank * 0.1)
                    reranked.append(candidate)
            if reranked:
                return reranked
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Reranker JSON parse failed, falling back to RRF order")

    # Fallback: return top_k in original order (immutable — no mutation)
    return [{**c, "relevance_score": 1.0 - (idx * 0.1)} for idx, c in enumerate(candidates[:top_k])]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_reranker_selects_top_k tests/test_knowledge_spine.py::test_reranker_fallback_on_bad_json -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add utils/knowledge.py tests/test_knowledge_spine.py
git commit -m "feat(s18): add LLM reranker with JSON fallback"
```

---

### Task 9: Wire hybrid search into `retrieve_knowledge()`

**Files:**
- Modify: `utils/knowledge.py`
- Modify: `tests/test_knowledge_spine.py`

- [ ] **Step 1: Write the hybrid search integration test**

Add to `tests/test_knowledge_spine.py`:

```python
def test_hybrid_search_uses_both_pgvector_and_fts(
    client_id: str,
    _seed_cards: list[str],
    _isolated_spans: Path,
) -> None:
    """Hybrid search returns results from BOTH pgvector AND FTS merged via RRF."""
    from utils.knowledge import retrieve_knowledge
    from utils.embeddings import embed_text

    fake_embedding = [0.1] * 1536

    # Mock call_llm for query variants and reranker
    variant_response = {
        "content": '["promosi batik Raya", "batik festive promo", "Raya batik kempen"]',
        "model": "gpt-5.4-mini", "input_tokens": 50, "output_tokens": 30, "cost_usd": 0.0,
    }
    rerank_response = {
        "content": "[0, 1, 2, 3, 4]",
        "model": "gpt-5.4-mini", "input_tokens": 500, "output_tokens": 10, "cost_usd": 0.0,
    }

    call_count = {"n": 0}
    def mock_call_llm(**kwargs: Any) -> dict[str, Any]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return variant_response
        return rerank_response

    with patch("utils.knowledge.call_llm", side_effect=mock_call_llm):
        results = retrieve_knowledge(
            client_id=client_id,
            query_embedding=fake_embedding,
            top_k=5,
        )

    assert len(results) >= 1
    # Results should be dicts with expected keys
    for r in results:
        assert "id" in r
        assert "title" in r


def test_retrieve_knowledge_with_document_set_filter(
    client_id: str,
    _seed_cards: list[str],
    _isolated_spans: Path,
) -> None:
    """Document set filtering: cards in set returned, cards outside excluded."""
    from utils.knowledge import retrieve_knowledge

    # Create a document set with only the first 2 cards
    card_ids = _seed_cards
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO document_sets (client_id, name, status) VALUES (%s, 'test-set', 'active') RETURNING id",
            (client_id,),
        )
        ds_row = cur.fetchone()
        assert ds_row is not None
        doc_set_id = str(ds_row["id"])

        for cid in card_ids[:2]:
            cur.execute(
                "INSERT INTO document_set_members (document_set_id, knowledge_card_id) VALUES (%s, %s)",
                (doc_set_id, cid),
            )

    fake_embedding = [0.1] * 1536

    variant_response = {
        "content": '["test variant 1", "test variant 2", "test variant 3"]',
        "model": "gpt-5.4-mini", "input_tokens": 50, "output_tokens": 30, "cost_usd": 0.0,
    }
    rerank_response = {
        "content": "[0, 1]",
        "model": "gpt-5.4-mini", "input_tokens": 200, "output_tokens": 10, "cost_usd": 0.0,
    }

    call_count = {"n": 0}
    def mock_call_llm(**kwargs: Any) -> dict[str, Any]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return variant_response
        return rerank_response

    with patch("utils.knowledge.call_llm", side_effect=mock_call_llm):
        results = retrieve_knowledge(
            client_id=client_id,
            query_embedding=fake_embedding,
            document_set_id=doc_set_id,
            top_k=5,
        )

    # Should only return cards from the document set
    result_ids = {str(r["id"]) for r in results}
    assert result_ids.issubset(set(card_ids[:2]))


def test_lost_in_middle_best_first_second_best_last() -> None:
    """Lost-in-middle: best at position 1, second-best at last position."""
    from utils.knowledge import lost_in_middle_reorder

    items = [
        {"id": "best", "score": 0.9},
        {"id": "second", "score": 0.8},
        {"id": "third", "score": 0.7},
        {"id": "fourth", "score": 0.6},
        {"id": "fifth", "score": 0.5},
    ]
    reordered = lost_in_middle_reorder(items)
    assert reordered[0]["id"] == "best"
    assert reordered[-1]["id"] == "second"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_hybrid_search_uses_both_pgvector_and_fts -v`
Expected: FAIL (retrieve_knowledge still uses old code path without hybrid)

- [ ] **Step 3: Update `retrieve_knowledge()` to use hybrid search**

Modify `utils/knowledge.py`. Add config loading helper and update both `retrieve_knowledge` and `assemble_context`:

```python
def _load_pipeline_config() -> dict[str, Any]:
    """Load retrieval_pipeline config from retrieval_profiles.yaml."""
    path = _CONFIG_DIR / "retrieval_profiles.yaml"
    with path.open() as fh:
        data = yaml.safe_load(fh)
    return data.get("retrieval_pipeline", {})  # type: ignore[no-any-return]
```

Update `retrieve_knowledge` signature to accept `query` text:

```python
def retrieve_knowledge(
    client_id: str,
    query: str = "",
    query_embedding: list[float] | None = None,
    document_set_id: str | None = None,
    top_k: int = 5,
    min_score: float = 0.65,
) -> list[dict[str, Any]]:
```

Update `assemble_context()` to accept and forward `query`:

```python
def assemble_context(
    client_id: str,
    query: str = "",
    query_embedding: list[float] | None = None,
    document_set_id: str | None = None,
    include_knowledge: bool = True,
    top_k: int = 5,
) -> dict[str, Any]:
    """Assemble production context for a job.

    Always includes client config + seasonal context.
    Optionally includes knowledge cards (lazy retrieval).
    """
    client_config = _load_client_config(client_id)
    seasonal = _load_seasonal_context()

    knowledge_cards: list[dict[str, Any]] = []
    if include_knowledge:
        knowledge_cards = retrieve_knowledge(
            client_id=client_id,
            query=query,
            query_embedding=query_embedding,
            document_set_id=document_set_id,
            top_k=top_k,
        )

    return {
        "client_config": client_config,
        "seasonal": seasonal,
        "knowledge_cards": knowledge_cards,
    }
```

Simplified `retrieve_knowledge` implementation (replaces the earlier pseudocode):

```python
def retrieve_knowledge(
    client_id: str,
    query: str = "",
    query_embedding: list[float] | None = None,
    document_set_id: str | None = None,
    top_k: int = 5,
    min_score: float = 0.65,
) -> list[dict[str, Any]]:
    """Query knowledge_cards via hybrid search (pgvector + FTS + RRF).

    Pipeline: query variants -> semantic + FTS per variant ->
    RRF merge -> LLM reranking -> lost-in-middle reordering.

    Falls back to recency if no embedding provided.
    """
    if query_embedding is None:
        return _retrieve_by_recency(client_id, document_set_id, top_k)

    config = _load_pipeline_config()
    rrf_w = config.get("rrf_weights", {"dense": 1.0, "sparse": 0.25})
    n_candidates = config.get("reranker_candidates", 20)
    n_top = config.get("reranker_top_k", top_k)
    n_variants = config.get("query_variants", 4)

    # Semantic search (embedding-based, same for all variants)
    semantic = _retrieve_by_embedding_raw(
        client_id, query_embedding, document_set_id, n_candidates, min_score,
    )

    # Generate query variants for FTS
    variants = _generate_query_variants(query, n=n_variants) if query else [query]

    # Hybrid: merge semantic + FTS per variant
    all_merged: list[dict[str, Any]] = []
    for variant in variants:
        fts = _search_fts(variant, client_id, document_set_id, n_candidates) if variant else []
        merged = _rrf_merge(semantic, fts, rrf_w.get("dense", 1.0), rrf_w.get("sparse", 0.25))
        all_merged.extend(merged)

    # Deduplicate across variants
    best: dict[str, dict[str, Any]] = {}
    for item in all_merged:
        cid = str(item["id"])
        if cid not in best or item.get("rrf_score", 0) > best[cid].get("rrf_score", 0):
            best[cid] = item
    deduped = sorted(best.values(), key=lambda x: x.get("rrf_score", 0), reverse=True)

    # Rerank
    query_text = variants[0] if variants else query
    reranked = _rerank_with_llm(query_text, deduped[:n_candidates], n_top)

    # Lost-in-middle
    return lost_in_middle_reorder(reranked[:top_k])
```

Also rename the old `_retrieve_by_embedding` to `_retrieve_by_embedding_raw` (remove the `lost_in_middle_reorder` call at the end since that now happens at the pipeline level):

```python
def _retrieve_by_embedding_raw(
    client_id: str,
    query_embedding: list[float],
    document_set_id: str | None,
    top_k: int,
    min_score: float,
) -> list[dict[str, Any]]:
    """Semantic search against knowledge_cards using pgvector.

    Returns raw results WITHOUT lost-in-middle reordering
    (reordering happens at the pipeline level after RRF merge).
    """
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    if document_set_id:
        query = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence, kc.context_prefix,
                   1 - (kc.embedding <=> %s::vector) AS similarity
            FROM knowledge_cards kc
            JOIN document_set_members dsm ON dsm.knowledge_card_id = kc.id
            WHERE kc.client_id = %s
              AND kc.status = 'active'
              AND dsm.document_set_id = %s
              AND 1 - (kc.embedding <=> %s::vector) >= %s
            ORDER BY similarity DESC
            LIMIT %s
        """
        params = (embedding_str, client_id, document_set_id, embedding_str, min_score, top_k)
    else:
        query = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence, kc.context_prefix,
                   1 - (kc.embedding <=> %s::vector) AS similarity
            FROM knowledge_cards kc
            WHERE kc.client_id = %s
              AND kc.status = 'active'
              AND 1 - (kc.embedding <=> %s::vector) >= %s
            ORDER BY similarity DESC
            LIMIT %s
        """
        params = (embedding_str, client_id, embedding_str, min_score, top_k)

    with get_cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [dict(row) for row in rows]  # no reordering here
```

Delete the old `_retrieve_by_embedding` function entirely (it is replaced by `_retrieve_by_embedding_raw`).

- [ ] **Step 4: Run all hybrid search tests**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run existing routing tests to verify no regressions**

Run: `python3.11 -m pytest tests/test_routing.py -v`
Expected: PASS (assemble_context still works with the new `query` param defaulting to "")

- [ ] **Step 6: Run pyright**

Run: `pyright utils/knowledge.py`
Expected: 0 errors

- [ ] **Step 7: Commit**

```bash
git add utils/knowledge.py tests/test_knowledge_spine.py
git commit -m "feat(s18): wire hybrid search pipeline into retrieve_knowledge"
```

---

## Chunk 3: Tool Functions (ingestion, promotion, outcome)

### Task 10: `ingest_card()` — canonical card ingestion

**Files:**
- Create: `tools/knowledge.py`
- Modify: `tests/test_knowledge_spine.py`

- [ ] **Step 1: Write the test**

Add to `tests/test_knowledge_spine.py`:

```python
def test_ingest_card_with_contextualised_embedding(
    client_id: str,
    _isolated_spans: Path,
) -> None:
    """Card ingested with contextualised embedding — prefix present."""
    from tools.knowledge import ingest_card

    # Create a source first
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO knowledge_sources (client_id, source_type, title, status) "
            "VALUES (%s, 'test', 'Test Source', 'active') RETURNING id",
            (client_id,),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

    mock_prefix = "This card is from DMB's Raya 2025 promotional campaign."
    fake_embedding = [0.1] * 1536

    with (
        patch("tools.knowledge.contextualise_card", return_value=mock_prefix),
        patch("tools.knowledge.embed_text", return_value=fake_embedding),
    ):
        card_id = ingest_card(
            source_id=source_id,
            content="Diskaun 30% untuk semua produk batik.",
            card_type="marketing",
            title="Raya Promo",
            tags=["raya", "batik"],
            domain="marketing",
            client_id=client_id,
        )

    assert card_id is not None

    # Verify the card was stored with context_prefix
    with get_cursor() as cur:
        cur.execute("SELECT content, context_prefix FROM knowledge_cards WHERE id = %s", (card_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["content"] == "Diskaun 30% untuk semua produk batik."
        assert row["context_prefix"] == mock_prefix


def test_contextualise_card_importable() -> None:
    """Verify: from utils.retrieval import contextualise_card works."""
    from utils.retrieval import contextualise_card
    assert callable(contextualise_card)


def test_contextualise_card_is_s12_function() -> None:
    """Contextualisation is the SAME function S12 built, not a copy."""
    from utils.retrieval import contextualise_card as original
    from tools.knowledge import contextualise_card as imported
    assert original is imported
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_ingest_card_with_contextualised_embedding -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.knowledge'`

- [ ] **Step 3: Write `tools/knowledge.py`**

```python
"""Knowledge tools — card ingestion, exemplar promotion, outcome memory.

Hermes tool functions for the knowledge spine.
Imports contextualise_card from S12 (utils.retrieval) — do NOT rebuild.
"""
from __future__ import annotations

import logging
from typing import Any

from utils.database import get_cursor
from utils.embeddings import embed_text, format_embedding
from utils.retrieval import contextualise_card

logger = logging.getLogger(__name__)


def ingest_card(
    *,
    source_id: str,
    content: str,
    card_type: str,
    title: str,
    tags: list[str],
    domain: str,
    client_id: str | None = None,
    prefix: str | None = None,
) -> str:
    """Ingest a knowledge card with contextualised embedding.

    Canonical ingestion function — all card creation should go through here.

    1. Contextualise via GPT-5.4-mini (50-100 token prefix) — skipped if prefix provided
    2. Embed contextualised text via text-embedding-3-small
    3. Store card with embedding and context_prefix in knowledge_cards

    Args:
        prefix: If provided, skip contextualise_card call (avoids double
            contextualisation when callers already have a prefix).

    Returns card_id (UUID string).
    """
    if prefix is None:
        card_dict = {
            "content": content,
            "card_type": card_type,
            "title": title,
            "domain": domain,
        }  # tags excluded — contextualise_card doesn't use them

        # Look up source info for contextualisation
        source_info: dict[str, str] = {"source_type": "knowledge", "title": title, "domain": domain}
        with get_cursor() as cur:
            cur.execute(
                "SELECT source_type, title, domain FROM knowledge_sources WHERE id = %s",
                (source_id,),
            )
            row = cur.fetchone()
            if row:
                source_info = {
                    "source_type": row["source_type"] or "knowledge",
                    "title": row["title"] or title,
                    "domain": row["domain"] or domain,
                }

        prefix = contextualise_card(card_dict, source_info)

    # Step 2: Embed contextualised text
    contextualised_text = f"{prefix} {content}"
    embedding = format_embedding(embed_text(contextualised_text))

    # Step 3: Store
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_cards
                (source_id, client_id, card_type, title, content, tags,
                 domain, embedding, context_prefix, confidence, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0.8, 'active')
            RETURNING id
            """,
            (source_id, client_id, card_type, title, content, tags,
             domain, embedding, prefix),
        )
        card_row = cur.fetchone()
        assert card_row is not None

    card_id = str(card_row["id"])
    logger.info("Ingested card %s (type=%s, prefix=%d chars)", card_id, card_type, len(prefix))
    return card_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_ingest_card_with_contextualised_embedding tests/test_knowledge_spine.py::test_contextualise_card_importable tests/test_knowledge_spine.py::test_contextualise_card_is_s12_function -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/knowledge.py tests/test_knowledge_spine.py
git commit -m "feat(s18): add canonical ingest_card tool function"
```

---

### Task 11: `promote_exemplar()` and `record_outcome()`

**Files:**
- Modify: `tools/knowledge.py`
- Modify: `tests/test_knowledge_spine.py`

- [ ] **Step 1: Write the tests**

Add to `tests/test_knowledge_spine.py`:

```python
def test_exemplar_promoted_from_rating_5(client_id: str) -> None:
    """Exemplar promoted only from artifact with operator rating 5."""
    from tools.knowledge import promote_exemplar

    # Create job, artifact, asset, and feedback
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO jobs (client_id, job_type, status) VALUES (%s, 'test', 'completed') RETURNING id",
            (client_id,),
        )
        job_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO assets (storage_path, mime_type) VALUES ('test/path.png', 'image/png') RETURNING id",
        )
        asset_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO artifacts (job_id, asset_id, artifact_type, status) "
            "VALUES (%s, %s, 'poster', 'completed') RETURNING id",
            (job_id, asset_id),
        )
        artifact_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO feedback (job_id, artifact_id, client_id, feedback_status, operator_rating, anchor_set) "
            "VALUES (%s, %s, %s, 'explicitly_approved', 5, false)",
            (job_id, artifact_id, client_id),
        )

    exemplar_id = promote_exemplar(
        artifact_id=artifact_id,
        client_id=client_id,
        operator_rating=5,
        job_id=job_id,
    )
    assert exemplar_id is not None

    # Verify exemplar exists
    with get_cursor() as cur:
        cur.execute("SELECT * FROM exemplars WHERE id = %s", (exemplar_id,))
        row = cur.fetchone()
        assert row is not None
        assert str(row["artifact_id"]) == artifact_id


def test_exemplar_not_promoted_from_low_rating(client_id: str) -> None:
    """Exemplar NOT promoted from rating < 5."""
    from tools.knowledge import promote_exemplar

    result = promote_exemplar(
        artifact_id=str(uuid4()),
        client_id=client_id,
        operator_rating=3,
        job_id=str(uuid4()),
    )
    assert result is None


def test_exemplar_anchor_set_blocked(client_id: str) -> None:
    """Anchor_set feedback excluded from exemplar promotion (anti-drift #56)."""
    from tools.knowledge import promote_exemplar

    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO jobs (client_id, job_type, status) VALUES (%s, 'test', 'completed') RETURNING id",
            (client_id,),
        )
        job_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO assets (storage_path, mime_type) VALUES ('test/anchor.png', 'image/png') RETURNING id",
        )
        asset_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO artifacts (job_id, asset_id, artifact_type, status) "
            "VALUES (%s, %s, 'poster', 'completed') RETURNING id",
            (job_id, asset_id),
        )
        artifact_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO feedback (job_id, artifact_id, client_id, feedback_status, operator_rating, anchor_set) "
            "VALUES (%s, %s, %s, 'explicitly_approved', 5, true)",
            (job_id, artifact_id, client_id),
        )

    result = promote_exemplar(
        artifact_id=artifact_id,
        client_id=client_id,
        operator_rating=5,
        job_id=job_id,
    )
    assert result is None


def test_outcome_memory_record_created(client_id: str) -> None:
    """Outcome memory record created after job completion."""
    from tools.knowledge import record_outcome

    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO jobs (client_id, job_type, status) VALUES (%s, 'test', 'completed') RETURNING id",
            (client_id,),
        )
        job_id = str(cur.fetchone()["id"])  # type: ignore[index]

    outcome_id = record_outcome(
        job_id=job_id,
        outcome_data={
            "artifact_id": None,
            "client_id": client_id,
            "first_pass_approved": True,
            "revision_count": 0,
            "accepted_as_on_brand": True,
            "human_feedback_summary": "Client loved the Raya design",
            "cost_summary": {"total_tokens": 5000, "cost_usd": 0.01},
            "quality_summary": {"overall": 4.5},
            "promote_to_exemplar": False,
        },
    )

    assert outcome_id is not None
    with get_cursor() as cur:
        cur.execute("SELECT * FROM outcome_memory WHERE id = %s", (outcome_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["first_pass_approved"] is True
        assert row["revision_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_exemplar_promoted_from_rating_5 -v`
Expected: FAIL — `ImportError: cannot import name 'promote_exemplar'`

- [ ] **Step 3: Implement `promote_exemplar` and `record_outcome`**

Add to `tools/knowledge.py`:

```python
import json


def promote_exemplar(
    *,
    artifact_id: str,
    client_id: str,
    operator_rating: int,
    job_id: str,
) -> str | None:
    """Promote an artifact to the exemplar library.

    Only promotes if operator_rating == 5 (explicitly_approved).
    Checks anchor_set flag on feedback — anchor set records are excluded
    from exemplar libraries per anti-drift #56.

    Returns exemplar_id or None if not promoted.
    """
    if operator_rating != 5:
        return None

    # Check anchor_set on the most recent feedback for this artifact+job
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT anchor_set FROM feedback
            WHERE artifact_id = %s AND job_id = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (artifact_id, job_id),
        )
        fb_row = cur.fetchone()
        if fb_row and fb_row["anchor_set"]:
            logger.info("Skipping exemplar promotion — anchor_set feedback (anti-drift #56)")
            return None

    # Get artifact metadata (artifact_family derived from artifact_type —
    # the artifacts table does not have artifact_family, only exemplars does)
    with get_cursor() as cur:
        cur.execute(
            "SELECT artifact_type FROM artifacts WHERE id = %s",
            (artifact_id,),
        )
        art_row = cur.fetchone()
        if art_row is None:
            logger.warning("Artifact %s not found for exemplar promotion", artifact_id)
            return None

        artifact_type = art_row["artifact_type"]

        cur.execute(
            """
            INSERT INTO exemplars
                (artifact_id, client_id, artifact_family, artifact_type,
                 approval_quality, status)
            VALUES (%s, %s, %s, %s, 'operator_5', 'active')
            RETURNING id
            """,
            (artifact_id, client_id, artifact_type, artifact_type),
        )
        ex_row = cur.fetchone()
        assert ex_row is not None

    exemplar_id = str(ex_row["id"])
    logger.info("Promoted artifact %s to exemplar %s", artifact_id, exemplar_id)
    return exemplar_id


def record_outcome(
    *,
    job_id: str,
    outcome_data: dict[str, Any],
) -> str:
    """Record job outcome in outcome_memory table.

    Args:
        job_id: The completed job's UUID.
        outcome_data: Dict with keys matching outcome_memory columns:
            artifact_id, client_id, first_pass_approved, revision_count,
            accepted_as_on_brand, human_feedback_summary, cost_summary,
            quality_summary, promote_to_exemplar.

    Returns outcome_memory record id.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO outcome_memory
                (job_id, artifact_id, client_id, first_pass_approved,
                 revision_count, accepted_as_on_brand, human_feedback_summary,
                 cost_summary, quality_summary, promote_to_exemplar)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                job_id,
                outcome_data.get("artifact_id"),
                outcome_data.get("client_id"),
                outcome_data.get("first_pass_approved"),
                outcome_data.get("revision_count", 0),
                outcome_data.get("accepted_as_on_brand"),
                outcome_data.get("human_feedback_summary"),
                json.dumps(outcome_data.get("cost_summary")) if outcome_data.get("cost_summary") else None,
                json.dumps(outcome_data.get("quality_summary")) if outcome_data.get("quality_summary") else None,
                outcome_data.get("promote_to_exemplar", False),
            ),
        )
        row = cur.fetchone()
        assert row is not None

    outcome_id = str(row["id"])
    logger.info("Recorded outcome %s for job %s", outcome_id, job_id)
    return outcome_id
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_exemplar_promoted_from_rating_5 tests/test_knowledge_spine.py::test_exemplar_not_promoted_from_low_rating tests/test_knowledge_spine.py::test_exemplar_anchor_set_blocked tests/test_knowledge_spine.py::test_outcome_memory_record_created -v`
Expected: All PASS

- [ ] **Step 5: Run pyright**

Run: `pyright tools/knowledge.py`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add tools/knowledge.py tests/test_knowledge_spine.py
git commit -m "feat(s18): add promote_exemplar and record_outcome tools"
```

---

## Chunk 4: Wisdom Vault + Refactoring + Final Verification

### Task 12: Wisdom Vault import

**Files:**
- Create: `tools/wisdom_vault.py`
- Modify: `tests/test_knowledge_spine.py`

- [ ] **Step 1: Write the tests**

Add to `tests/test_knowledge_spine.py`:

```python
def test_wisdom_vault_import_book(
    client_id: str,
    tmp_path: Path,
    _isolated_spans: Path,
) -> None:
    """Wisdom Vault imports test markdown -> contextualised knowledge cards."""
    from tools.wisdom_vault import import_book

    # Create test markdown file
    md_content = """---
title: Marketing Fundamentals
domain: marketing
---

## Chapter 1: Brand Building

A brand is a promise to the customer. It tells them what
they can expect from your products and services, and it
differentiates your offering from competitors.

## Chapter 2: Digital Marketing

Digital marketing encompasses all marketing efforts that
use an electronic device or the internet. Businesses leverage
digital channels to connect with current and prospective customers.

## Chapter 3: Content Strategy

Content strategy refers to the planning, development, and
management of content. It involves creating useful, usable
content that supports key business objectives.
"""
    md_path = tmp_path / "test_book.md"
    md_path.write_text(md_content)

    mock_prefix = "This card is from Marketing Fundamentals."
    fake_embedding = [0.1] * 1536

    with (
        patch("tools.knowledge.contextualise_card", return_value=mock_prefix),
        patch("tools.knowledge.embed_text", return_value=fake_embedding),
    ):
        result = import_book(
            vault_path=str(md_path),
            title="Marketing Fundamentals",
            domain="marketing",
            client_id=client_id,
        )

    assert result["card_count"] == 3  # 3 chapters = 3 cards
    assert result["title"] == "Marketing Fundamentals"
    assert result["source_id"] is not None

    # Verify cards exist in DB
    with get_cursor() as cur:
        cur.execute(
            "SELECT count(*) as cnt FROM knowledge_cards WHERE source_id = %s",
            (result["source_id"],),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["cnt"] == 3


def test_wisdom_vault_import_directory(
    client_id: str,
    tmp_path: Path,
    _isolated_spans: Path,
) -> None:
    """Batch import multiple books from vault directory."""
    from tools.wisdom_vault import import_vault_directory

    for i in range(3):
        (tmp_path / f"book_{i}.md").write_text(f"## Section\n\nContent for book {i} about marketing and design principles.")

    mock_prefix = "Test prefix."
    fake_embedding = [0.1] * 1536

    with (
        patch("tools.knowledge.contextualise_card", return_value=mock_prefix),
        patch("tools.knowledge.embed_text", return_value=fake_embedding),
    ):
        results = import_vault_directory(
            vault_dir=str(tmp_path),
            client_id=client_id,
        )

    assert len(results) == 3
    for r in results:
        assert r["card_count"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_wisdom_vault_import_book -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.wisdom_vault'`

- [ ] **Step 3: Write `tools/wisdom_vault.py`**

```python
"""Wisdom Vault — Obsidian markdown import to knowledge cards.

Reads markdown files, splits by headings into cards, contextualises
each card via S12's contextualise_card, and stores with embeddings.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from tools.knowledge import ingest_card
from utils.database import get_cursor

logger = logging.getLogger(__name__)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown. Returns (metadata, body)."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            return meta, body
    return {}, text


def _chunk_by_headings(body: str) -> list[str]:
    """Split markdown body by ## headings.

    Each chunk includes the heading and content up to the next heading.
    ### sub-headings are kept within their parent ## section.
    Falls back to ~100-word paragraph splits if no headings found.
    """
    # Split on ## (but not ### within sections)
    sections = re.split(r"(?=^## )", body, flags=re.MULTILINE)
    chunks = [s.strip() for s in sections if s.strip()]

    if len(chunks) <= 1 and len(body.split()) > 150:
        # Fallback: split into ~100-word paragraph chunks
        paragraphs = body.split("\n\n")
        chunks = []
        current: list[str] = []
        word_count = 0
        for para in paragraphs:
            words = len(para.split())
            if word_count + words > 150 and current:
                chunks.append("\n\n".join(current))
                current = [para]
                word_count = words
            else:
                current.append(para)
                word_count += words
        if current:
            chunks.append("\n\n".join(current))

    return chunks


def import_book(
    vault_path: str,
    title: str,
    domain: str | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    """Import an Obsidian markdown file as knowledge cards.

    Splits by ## headings, contextualises each chunk, embeds, and stores.

    Returns: {"source_id": str, "card_count": int, "title": str}
    """
    path = Path(vault_path)
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)

    resolved_domain = domain or meta.get("domain", "general")
    resolved_title = title or meta.get("title", path.stem)

    # Create knowledge_source for the book
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_sources
                (client_id, source_type, title, domain, status)
            VALUES (%s, 'book', %s, %s, 'active')
            RETURNING id
            """,
            (client_id, resolved_title, resolved_domain),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

    # Chunk and ingest
    chunks = _chunk_by_headings(body)
    card_count = 0

    for idx, chunk in enumerate(chunks):
        if not chunk.strip():
            continue

        # Extract heading as card title if present
        lines = chunk.strip().split("\n")
        card_title = lines[0].lstrip("#").strip() if lines[0].startswith("#") else f"{resolved_title} — Part {idx + 1}"
        card_content = "\n".join(lines[1:]).strip() if lines[0].startswith("#") else chunk

        if len(card_content.split()) < 10:
            continue  # Skip very short chunks

        ingest_card(
            source_id=source_id,
            content=card_content,
            card_type="book",
            title=card_title,
            tags=meta.get("tags", []),
            domain=resolved_domain,
            client_id=client_id,
        )
        card_count += 1

    logger.info("Imported book '%s': %d cards from %s", resolved_title, card_count, path.name)
    return {"source_id": source_id, "card_count": card_count, "title": resolved_title}


def import_vault_directory(
    vault_dir: str,
    domain_map: dict[str, str] | None = None,
    client_id: str | None = None,
) -> list[dict[str, Any]]:
    """Batch import markdown files from an Obsidian vault directory.

    Args:
        vault_dir: Path to directory containing .md files.
        domain_map: Optional {filename_pattern: domain} for auto-tagging.
        client_id: Optional client to associate cards with.

    Returns list of import results from import_book().
    """
    vault_path = Path(vault_dir)
    results: list[dict[str, Any]] = []

    for md_file in sorted(vault_path.glob("*.md")):
        domain = None
        if domain_map:
            for pattern, dom in domain_map.items():
                if pattern in md_file.name:
                    domain = dom
                    break

        result = import_book(
            vault_path=str(md_file),
            title=md_file.stem.replace("_", " ").title(),
            domain=domain,
            client_id=client_id,
        )
        results.append(result)

    logger.info("Vault import: %d files processed from %s", len(results), vault_dir)
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_wisdom_vault_import_book tests/test_knowledge_spine.py::test_wisdom_vault_import_directory -v`
Expected: PASS

- [ ] **Step 5: Run pyright**

Run: `pyright tools/wisdom_vault.py`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add tools/wisdom_vault.py tests/test_knowledge_spine.py
git commit -m "feat(s18): add Wisdom Vault markdown import"
```

---

### Task 13: Refactor existing ingestion to use `ingest_card`

**Files:**
- Modify: `tools/research.py:332-397`
- Modify: `tools/seeding.py:253-319`

- [ ] **Step 1: Refactor `tools/research.py:_store_knowledge_card`**

Replace the card insertion logic to delegate to `ingest_card`. Keep source creation in-place:

```python
# In tools/research.py, update _store_knowledge_card:
def _store_knowledge_card(
    *,
    card_data: dict[str, str],
    prefix: str,
    client_id: str | None,
    source_type: str,
    source_title: str,
    asset_id: str | None = None,
) -> dict[str, Any]:
    """Create a knowledge source + card with contextualised embedding.

    Delegates card insertion to tools.knowledge.ingest_card (canonical).
    """
    from tools.knowledge import ingest_card

    # Create knowledge source (stays here — source creation is context-specific)
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_sources
                (source_type, title, domain, asset_id, status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING id
            """,
            (source_type, source_title, card_data.get("domain", "general"), asset_id),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

    # Delegate card insertion — pass prefix to skip double contextualisation
    card_id = ingest_card(
        source_id=source_id,
        content=card_data["content"],
        card_type=card_data.get("card_type", "general"),
        title=card_data.get("title", ""),
        tags=card_data.get("tags", "").split(",") if isinstance(card_data.get("tags"), str) else card_data.get("tags", []),
        domain=card_data.get("domain", "general"),
        client_id=client_id,
        prefix=prefix,  # caller already contextualised — skip re-contextualisation
    )

    return {
        "card_id": card_id,
        "source_id": source_id,
        "card_type": card_data.get("card_type", "general"),
        "title": card_data.get("title", ""),
        "content": card_data["content"],
        "prefix": prefix,
        "client_id": client_id,
    }
```

- [ ] **Step 2: Refactor `tools/seeding.py:_store_card`**

Same pattern — keep source creation, delegate card insertion:

```python
# In tools/seeding.py, update _store_card:
def _store_card(
    card_data: dict[str, Any],
    prefix: str,
    client_id: str,
    source_type: str,
    source_title: str,
) -> dict[str, Any]:
    """Store a contextualised knowledge card. Delegates to ingest_card."""
    from tools.knowledge import ingest_card

    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_sources
                (client_id, source_type, title, domain, status)
            VALUES (
                (SELECT id FROM clients WHERE id::text = %s OR name = %s LIMIT 1),
                %s, %s, %s, 'active')
            RETURNING id
            """,
            (client_id, client_id, source_type, source_title, card_data.get("domain", "general")),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

    tags = card_data.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    card_id = ingest_card(
        source_id=source_id,
        content=card_data["content"],
        card_type=card_data.get("card_type", "general"),
        title=card_data.get("title", ""),
        tags=tags,
        domain=card_data.get("domain", "general"),
        client_id=client_id,
        prefix=prefix,  # caller already contextualised — skip re-contextualisation
    )

    return {
        "card_id": card_id,
        "source_id": source_id,
        "card_type": card_data.get("card_type", "general"),
        "title": card_data.get("title", ""),
        "prefix": prefix,
        "client_id": client_id,
    }
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `python3.11 -m pytest tests/test_research.py -v -k "not swipe_ingest and not visual_dna and not pytrends"`
Expected: PASS — contextualisation and card storage still work

- [ ] **Step 4: Commit**

```bash
git add tools/research.py tools/seeding.py
git commit -m "refactor(s18): delegate card ingestion to canonical ingest_card"
```

---

### Task 14: Config loading test + final retrieval profile verification

**Files:**
- Modify: `tests/test_knowledge_spine.py`

- [ ] **Step 1: Add config and semantic search tests**

```python
def test_retrieval_pipeline_config_loaded() -> None:
    """Retrieval pipeline config loads from retrieval_profiles.yaml."""
    from utils.knowledge import _load_pipeline_config

    config = _load_pipeline_config()
    assert config["embedding_model"] == "text-embedding-3-small"
    assert config["query_variants"] == 4
    assert config["rrf_weights"]["dense"] == 1.0
    assert config["rrf_weights"]["sparse"] == 0.25
    assert config["reranker"] == "gpt-5.4-mini"
    assert config["lost_in_middle"] is True
    assert config["fts_dictionary"] == "simple"


def test_semantic_search_raya_batik(
    client_id: str,
    _seed_cards: list[str],
) -> None:
    """pgvector semantic search returns relevant cards for 'Raya batik promotion'."""
    from utils.knowledge import _retrieve_by_embedding_raw

    # All test cards have the same fake embedding, so all will match
    fake_embedding = [0.1] * 1536
    results = _retrieve_by_embedding_raw(
        client_id, fake_embedding, None, 5, 0.0,  # min_score=0 to match fake embeddings
    )
    assert len(results) >= 1
    # Should include Raya/batik cards
    titles = [r["title"] for r in results]
    assert any("Raya" in t or "Batik" in t or "batik" in t for t in titles)
```

- [ ] **Step 2: Run tests**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py::test_retrieval_pipeline_config_loaded tests/test_knowledge_spine.py::test_semantic_search_raya_batik -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_knowledge_spine.py
git commit -m "test(s18): add config loading and semantic search verification"
```

---

### Task 15: Full test suite + pyright + final commit

- [ ] **Step 1: Run full test suite**

Run: `python3.11 -m pytest tests/test_knowledge_spine.py tests/test_embeddings.py tests/test_knowledge_contracts.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run pyright on all new/modified files**

Run: `pyright utils/embeddings.py utils/knowledge.py tools/knowledge.py tools/wisdom_vault.py contracts/knowledge.py tools/research.py tools/seeding.py`
Expected: 0 errors

- [ ] **Step 3: Run full existing test suite for regressions**

Run: `python3.11 -m pytest tests/ -v --ignore=tests/test_visual_intelligence.py`
Expected: All PASS (ignore visual_intelligence as it needs special fixtures)

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(s18): knowledge spine — hybrid retrieval, Wisdom Vault, exemplar promotion"
```

---

## Exit Criteria Checklist

| # | Criterion | Task |
|---|-----------|------|
| 1 | Card ingested with contextualised embedding (prefix present) | Task 10 |
| 2 | Hybrid search from BOTH pgvector AND FTS via RRF | Task 9 |
| 3 | Query transformation generates 4 variants incl BM/EN | Task 7 |
| 4 | Reranker reorders candidates and selects top_k | Task 8 |
| 5 | Lost-in-middle: best at pos 1, second-best at last | Task 9 |
| 6 | Exemplar promoted from rating 5 | Task 11 |
| 7 | Outcome memory created | Task 11 |
| 8 | pgvector returns for "Raya batik promotion" | Task 14 |
| 9 | FTS catches exact "DMB" | Task 5 |
| 10 | Wisdom Vault imports -> cards | Task 12 |
| 11 | `from utils.retrieval import contextualise_card` works | Task 10 |
| 12 | contextualise_card is S12's function, not a copy | Task 10 |
| 13 | Document set filtering works | Task 9 |
| 14 | pyright clean, all tests pass | Task 15 |
