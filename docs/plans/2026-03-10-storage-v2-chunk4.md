# LanceVectorStore Implementation Plan (Chunk 4/6)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `LanceVectorStore` — a LanceDB-backed `VectorStore` with ANN embedding search over closures.

**Architecture:** A single LanceDB table `closure_vectors` stores `(closure_id, version, embedding)`. The embedding column uses a fixed-size `pa.list_(pa.float32(), dim)` PyArrow type for ANN search. Search returns minimal `ScoredClosure` objects (following the KuzuGraphStore pattern — stub Closure with id/version/type/prior filled, content and other fields empty). The StorageManager (Chunk 5) enriches these from ContentStore.

**Tech Stack:** Python 3.12, LanceDB >=0.6, PyArrow >=15.0, Pydantic v2

---

## Context

**ABC to implement:** `libs/storage_v2/vector_store.py` — 2 abstract methods:
- `write_embeddings(items: list[ClosureEmbedding]) -> None`
- `search(embedding: list[float], top_k: int) -> list[ScoredClosure]`

**Models:** `libs/storage_v2/models.py` — `ClosureEmbedding(closure_id, version, embedding)`, `ScoredClosure(closure, score)`, `Closure`

**v1 reference:** `libs/storage/vector_search/lancedb_client.py` — patterns for LanceDB vector table creation, ANN search, `_distance` scoring.

**Key design decisions:**
- Embedding dimension is detected from the first write (like v1 `_ensure_table(dim)`)
- Upsert semantics: `(closure_id, version)` is the dedup key — re-writing the same pair replaces the embedding
- Search returns `ScoredClosure` with minimal Closure stubs (closure_id, version only; content="", keywords=[], etc.)
- Distance is converted to similarity score: `score = 1.0 / (1.0 + distance)` so higher = more similar
- Table created lazily on first `write_embeddings` call

---

### Task 1: LanceVectorStore skeleton + tests

**Files:**
- Create: `libs/storage_v2/lance_vector_store.py`
- Create: `tests/libs/storage_v2/test_vector_store.py`
- Modify: `tests/libs/storage_v2/conftest.py` (add `vector_store` fixture)

**Step 1: Write the test file with all test cases**

```python
"""Tests for LanceVectorStore — LanceDB-backed VectorStore implementation."""

import pytest

from libs.storage_v2.lance_vector_store import LanceVectorStore
from libs.storage_v2.models import ClosureEmbedding, ScoredClosure


@pytest.fixture
async def vector_store(tmp_path) -> LanceVectorStore:
    store = LanceVectorStore(str(tmp_path / "lance_vec"))
    return store


def _make_embedding(dim: int, seed: float) -> list[float]:
    """Create a deterministic embedding vector."""
    return [seed + i * 0.01 for i in range(dim)]


def _make_items(dim: int = 8) -> list[ClosureEmbedding]:
    return [
        ClosureEmbedding(
            closure_id="pkg.mod.closure_a", version=1,
            embedding=_make_embedding(dim, 0.1),
        ),
        ClosureEmbedding(
            closure_id="pkg.mod.closure_b", version=1,
            embedding=_make_embedding(dim, 0.5),
        ),
        ClosureEmbedding(
            closure_id="pkg.mod.closure_c", version=1,
            embedding=_make_embedding(dim, 0.9),
        ),
    ]


class TestWriteEmbeddings:
    async def test_write_creates_table(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        assert "closure_vectors" in vector_store._db.table_names()

    async def test_write_empty_is_noop(self, vector_store):
        await vector_store.write_embeddings([])
        # No table created
        assert "closure_vectors" not in (vector_store._db.list_tables().tables or [])

    async def test_write_upsert_replaces_embedding(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        # Write same closure_id+version with different embedding
        updated = ClosureEmbedding(
            closure_id="pkg.mod.closure_a", version=1,
            embedding=_make_embedding(8, 9.0),
        )
        await vector_store.write_embeddings([updated])
        # Search with the new embedding should find it at top
        results = await vector_store.search(_make_embedding(8, 9.0), top_k=1)
        assert results[0].closure.closure_id == "pkg.mod.closure_a"

    async def test_write_different_versions(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        v2 = ClosureEmbedding(
            closure_id="pkg.mod.closure_a", version=2,
            embedding=_make_embedding(8, 5.0),
        )
        await vector_store.write_embeddings([v2])
        # Should have 4 entries total (3 original + 1 new version)
        table = vector_store._db.open_table("closure_vectors")
        assert table.count_rows() == 4


class TestSearch:
    async def test_search_returns_scored_closures(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        query = _make_embedding(8, 0.1)  # same as closure_a
        results = await vector_store.search(query, top_k=3)
        assert len(results) == 3
        assert all(isinstance(r, ScoredClosure) for r in results)
        # Closest match should be closure_a
        assert results[0].closure.closure_id == "pkg.mod.closure_a"

    async def test_search_respects_top_k(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        results = await vector_store.search(_make_embedding(8, 0.1), top_k=1)
        assert len(results) == 1

    async def test_search_scores_are_positive(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        results = await vector_store.search(_make_embedding(8, 0.1), top_k=3)
        assert all(r.score > 0 for r in results)

    async def test_search_scores_descending(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        results = await vector_store.search(_make_embedding(8, 0.1), top_k=3)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    async def test_search_empty_store(self, vector_store):
        results = await vector_store.search(_make_embedding(8, 0.1), top_k=5)
        assert results == []

    async def test_search_returns_minimal_closure(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        results = await vector_store.search(_make_embedding(8, 0.1), top_k=1)
        c = results[0].closure
        assert c.closure_id == "pkg.mod.closure_a"
        assert c.version == 1
        # Stub fields
        assert c.content == ""
        assert c.keywords == []
```

**Step 2: Write the implementation**

Create `libs/storage_v2/lance_vector_store.py`.

**Step 3: Run tests**

Run: `pytest tests/libs/storage_v2/test_vector_store.py -v`
Expected: All PASS

**Step 4: Lint**

Run: `ruff check libs/storage_v2/lance_vector_store.py tests/libs/storage_v2/test_vector_store.py && ruff format --check libs/storage_v2/lance_vector_store.py tests/libs/storage_v2/test_vector_store.py`

**Step 5: Run full storage_v2 test suite**

Run: `pytest tests/libs/storage_v2/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add libs/storage_v2/lance_vector_store.py tests/libs/storage_v2/test_vector_store.py docs/plans/2026-03-10-storage-v2-chunk4.md
git commit -m "feat(storage-v2): chunk 4 — LanceVectorStore implementation"
```

---

## Summary

After completing this chunk:
- `LanceVectorStore` implements the `VectorStore` ABC with LanceDB ANN search
- Lazy table creation with auto-detected embedding dimension
- Upsert semantics by `(closure_id, version)`
- Distance-to-similarity score conversion
- Full test coverage: write, upsert, search, empty store, score ordering
