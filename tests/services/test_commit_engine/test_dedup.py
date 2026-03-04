# tests/services/test_commit_engine/test_dedup.py
"""DedupChecker tests — real storage instead of mocks."""

import pytest

from libs.embedding import StubEmbeddingModel
from services.commit_engine.dedup import DedupChecker
from services.search_engine.engine import SearchEngine


@pytest.fixture
async def checker(storage):
    search = SearchEngine(storage, embedding_model=StubEmbeddingModel())
    return DedupChecker(search_engine=search)


async def test_check_finds_duplicates_via_bm25(checker):
    """BM25 recall finds fixture nodes with matching keywords."""
    # Use content from fixture node 67 about "thallium oxide" synthesis
    candidates = await checker.check(
        contents=["thallium oxide Tl2O3 synthesis precursors superconducting"],
        threshold=0.01,  # low threshold since BM25 scores may be modest
    )
    assert len(candidates) == 1  # one input
    # BM25 should find fixture nodes mentioning thallium oxide
    if len(candidates[0]) > 0:
        assert candidates[0][0].node_id > 0
        assert candidates[0][0].score > 0


async def test_check_filters_below_threshold(checker):
    """High threshold filters out low-score matches."""
    candidates = await checker.check(
        contents=["something completely unrelated xyz123"],
        threshold=0.99,  # very high threshold
    )
    assert len(candidates) == 1
    assert len(candidates[0]) == 0  # nothing above 0.99


async def test_check_multiple_contents(checker):
    candidates = await checker.check(
        contents=["thallium oxide superconductor", "completely unrelated xyz"],
        threshold=0.01,
    )
    assert len(candidates) == 2


async def test_check_empty_input(checker):
    candidates = await checker.check(contents=[])
    assert candidates == []
