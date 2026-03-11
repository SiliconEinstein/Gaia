"""Tests for LanceVectorStore — LanceDB-backed VectorStore implementation."""

import pytest

from libs.storage_v2.lance_vector_store import LanceVectorStore
from libs.storage_v2.models import KnowledgeEmbedding, ScoredKnowledge


@pytest.fixture
async def vector_store(tmp_path) -> LanceVectorStore:
    return LanceVectorStore(str(tmp_path / "lance_vec"))


def _make_embedding(dim: int, seed: float) -> list[float]:
    """Create a deterministic embedding vector."""
    return [seed + i * 0.01 for i in range(dim)]


def _make_items(dim: int = 8) -> list[KnowledgeEmbedding]:
    return [
        KnowledgeEmbedding(
            knowledge_id="pkg.mod.knowledge_a",
            version=1,
            embedding=_make_embedding(dim, 0.1),
        ),
        KnowledgeEmbedding(
            knowledge_id="pkg.mod.knowledge_b",
            version=1,
            embedding=_make_embedding(dim, 0.5),
        ),
        KnowledgeEmbedding(
            knowledge_id="pkg.mod.knowledge_c",
            version=1,
            embedding=_make_embedding(dim, 0.9),
        ),
    ]


class TestWriteEmbeddings:
    async def test_write_creates_table(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        tables = vector_store._db.list_tables().tables or []
        assert "knowledge_vectors" in tables

    async def test_write_empty_is_noop(self, vector_store):
        await vector_store.write_embeddings([])
        tables = vector_store._db.list_tables().tables or []
        assert "knowledge_vectors" not in tables

    async def test_write_upsert_replaces_embedding(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        updated = KnowledgeEmbedding(
            knowledge_id="pkg.mod.knowledge_a",
            version=1,
            embedding=_make_embedding(8, 9.0),
        )
        await vector_store.write_embeddings([updated])
        table = vector_store._db.open_table("knowledge_vectors")
        assert table.count_rows() == 3  # no extra rows
        results = await vector_store.search(_make_embedding(8, 9.0), top_k=1)
        assert results[0].knowledge.knowledge_id == "pkg.mod.knowledge_a"

    async def test_write_different_versions(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        v2 = KnowledgeEmbedding(
            knowledge_id="pkg.mod.knowledge_a",
            version=2,
            embedding=_make_embedding(8, 5.0),
        )
        await vector_store.write_embeddings([v2])
        table = vector_store._db.open_table("knowledge_vectors")
        assert table.count_rows() == 4

    async def test_write_upsert_deduplicates_same_batch(self, vector_store):
        """Duplicate (knowledge_id, version) in one batch — last occurrence wins."""
        items = [
            KnowledgeEmbedding(
                knowledge_id="pkg.mod.dup",
                version=1,
                embedding=_make_embedding(8, 0.1),
            ),
            KnowledgeEmbedding(
                knowledge_id="pkg.mod.dup",
                version=1,
                embedding=_make_embedding(8, 9.0),
            ),
        ]
        await vector_store.write_embeddings(items)
        table = vector_store._db.open_table("knowledge_vectors")
        assert table.count_rows() == 1
        results = await vector_store.search(_make_embedding(8, 9.0), top_k=2)
        assert len(results) == 1
        assert results[0].knowledge.knowledge_id == "pkg.mod.dup"

    async def test_write_rejects_empty_embedding(self, vector_store):
        items = [KnowledgeEmbedding(knowledge_id="pkg.mod.x", version=1, embedding=[])]
        with pytest.raises(ValueError, match="must not be empty"):
            await vector_store.write_embeddings(items)

    async def test_write_rejects_inconsistent_batch_dimensions(self, vector_store):
        items = [
            KnowledgeEmbedding(knowledge_id="a", version=1, embedding=_make_embedding(8, 0.1)),
            KnowledgeEmbedding(knowledge_id="b", version=1, embedding=_make_embedding(4, 0.1)),
        ]
        with pytest.raises(ValueError, match="inconsistent embedding dimensions"):
            await vector_store.write_embeddings(items)

    async def test_write_rejects_dimension_mismatch_with_existing_table(self, vector_store):
        await vector_store.write_embeddings(_make_items(dim=8))
        mismatched = [
            KnowledgeEmbedding(knowledge_id="new", version=1, embedding=_make_embedding(4, 0.1))
        ]
        with pytest.raises(ValueError, match="does not match stored dimension"):
            await vector_store.write_embeddings(mismatched)


class TestSearch:
    async def test_search_returns_scored_knowledge(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        query = _make_embedding(8, 0.1)  # same as knowledge_a
        results = await vector_store.search(query, top_k=3)
        assert len(results) == 3
        assert all(isinstance(r, ScoredKnowledge) for r in results)
        assert results[0].knowledge.knowledge_id == "pkg.mod.knowledge_a"

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

    async def test_search_returns_minimal_knowledge(self, vector_store):
        items = _make_items()
        await vector_store.write_embeddings(items)
        results = await vector_store.search(_make_embedding(8, 0.1), top_k=1)
        c = results[0].knowledge
        assert c.knowledge_id == "pkg.mod.knowledge_a"
        assert c.version == 1
        assert c.content == ""
        assert c.keywords == []

    async def test_search_rejects_empty_query(self, vector_store):
        await vector_store.write_embeddings(_make_items())
        with pytest.raises(ValueError, match="must not be empty"):
            await vector_store.search([], top_k=5)

    async def test_search_rejects_dimension_mismatch(self, vector_store):
        await vector_store.write_embeddings(_make_items(dim=8))
        with pytest.raises(ValueError, match="does not match stored dimension"):
            await vector_store.search(_make_embedding(4, 0.1), top_k=5)
