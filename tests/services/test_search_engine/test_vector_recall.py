# tests/services/test_search_engine/test_vector_recall.py
"""VectorRecall tests — real LanceDB vector index instead of mocks."""

import pytest

from tests.conftest import load_fixture_embeddings
from services.search_engine.recall.vector import VectorRecall


@pytest.fixture
async def vector(storage):
    return VectorRecall(storage.vector)


async def test_recall_finds_similar_vectors(vector):
    """Vector recall should find results when embeddings are loaded."""
    embeddings = load_fixture_embeddings()
    if not embeddings:
        pytest.skip("No fixture embeddings available")
    # Use an actual fixture embedding as query
    first_id = next(iter(embeddings))
    query_embedding = embeddings[first_id]
    results = await vector.recall(query_embedding, k=5)
    assert len(results) > 0
    # The query itself should be among the top results
    result_ids = [nid for nid, _ in results]
    assert first_id in result_ids


async def test_recall_empty_when_no_embeddings(storage_empty):
    """VectorRecall on empty storage returns empty list."""
    recall = VectorRecall(storage_empty.vector)
    results = await recall.recall([0.0] * 512, k=10)
    assert results == []


async def test_recall_respects_k(vector):
    """Results should be limited to k."""
    embeddings = load_fixture_embeddings()
    if not embeddings:
        pytest.skip("No fixture embeddings available")
    first_id = next(iter(embeddings))
    results = await vector.recall(embeddings[first_id], k=3)
    assert len(results) <= 3
