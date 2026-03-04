# tests/services/test_search_engine/test_bm25_recall.py
"""BM25Recall tests — real LanceDB FTS instead of mocks."""

import pytest

from services.search_engine.recall.bm25 import BM25Recall


@pytest.fixture
async def bm25(storage):
    return BM25Recall(storage.lance)


async def test_recall_finds_matching_content(bm25):
    """BM25 should find fixture nodes containing 'thallium'."""
    results = await bm25.recall("thallium oxide", k=50)
    assert len(results) > 0
    # Results are (node_id, score) tuples
    for node_id, score in results:
        assert isinstance(node_id, int)
        assert score > 0


async def test_recall_empty_for_nonsense(bm25):
    results = await bm25.recall("xyzzy9999nonsense", k=50)
    assert results == []


async def test_recall_respects_k(bm25):
    results = await bm25.recall("superconductor", k=3)
    assert len(results) <= 3
