"""Tests for LanceVectorStore — LanceDB-backed VectorStore implementation."""

import pytest

from libs.storage_v2.lance_vector_store import LanceVectorStore
from libs.storage_v2.models import ClosureEmbedding, ScoredClosure


@pytest.fixture
async def vector_store(tmp_path) -> LanceVectorStore:
    return LanceVectorStore(str(tmp_path / "lance_vec"))


def _make_embedding(dim: int, seed: float) -> list[float]:
    """Create a deterministic embedding vector."""
    return [seed + i * 0.01 for i in range(dim)]


def _make_items(dim: int = 8) -> list[ClosureEmbedding]:
    return [
        ClosureEmbedding(
            closure_id="pkg.mod.closure_a",
            version=1,
            embedding=_make_embedding(dim, 0.1),
        ),
        ClosureEmbedding(
            closure_id="pkg.mod.closure_b",
            version=1,
            embedding=_make_embedding(dim, 0.5),
        ),
        ClosureEmbedding(
            closure_id="pkg.mod.closure_c",
            version=1,
            embedding=_make_embedding(dim, 0.9),
        ),
    ]


class TestWriteEmbeddings:
    async def test_write_creates_table(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        tables = vector_store._db.list_tables().tables or []
        assert "closure_vectors" in tables

    async def test_write_empty_is_noop(self, vector_store):
        await vector_store.write_embeddings([])
        tables = vector_store._db.list_tables().tables or []
        assert "closure_vectors" not in tables

    async def test_write_upsert_replaces_embedding(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        updated = ClosureEmbedding(
            closure_id="pkg.mod.closure_a",
            version=1,
            embedding=_make_embedding(8, 9.0),
        )
        await vector_store.write_embeddings([updated])
        table = vector_store._db.open_table("closure_vectors")
        assert table.count_rows() == 3  # no extra rows
        results = await vector_store.search(_make_embedding(8, 9.0), top_k=1)
        assert results[0].closure.closure_id == "pkg.mod.closure_a"

    async def test_write_different_versions(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        v2 = ClosureEmbedding(
            closure_id="pkg.mod.closure_a",
            version=2,
            embedding=_make_embedding(8, 5.0),
        )
        await vector_store.write_embeddings([v2])
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
        assert c.content == ""
        assert c.keywords == []
