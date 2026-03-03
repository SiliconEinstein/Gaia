"""Tests for DedupChecker — duplicate detection when submitting new nodes."""

from unittest.mock import AsyncMock, MagicMock

from libs.models import Node
from services.commit_engine.dedup import DedupChecker
from services.search_engine.models import ScoredNode


def _mock_search_engine(search_results):
    engine = MagicMock()
    engine.search_nodes = AsyncMock(return_value=search_results)
    return engine


async def test_check_finds_duplicates():
    results = [
        ScoredNode(
            node=Node(id=1, type="paper-extract", content="YH10 is stable at 400GPa"),
            score=0.95,
            sources=["vector"],
        ),
        ScoredNode(
            node=Node(id=2, type="paper-extract", content="YH10 stability"),
            score=0.85,
            sources=["bm25"],
        ),
    ]
    engine = _mock_search_engine(results)
    checker = DedupChecker(engine)
    candidates = await checker.check(
        contents=["YH10 is stable under high pressure"],
        embeddings=[[0.1] * 1024],
    )
    assert len(candidates) == 1  # one input
    assert len(candidates[0]) == 2  # two candidates above threshold
    assert candidates[0][0].node_id == 1
    assert candidates[0][0].score == 0.95


async def test_check_filters_below_threshold():
    results = [
        ScoredNode(
            node=Node(id=1, type="paper-extract", content="related but different"),
            score=0.6,
            sources=["vector"],
        ),
    ]
    engine = _mock_search_engine(results)
    checker = DedupChecker(engine)
    candidates = await checker.check(
        contents=["something new"],
        embeddings=[[0.1] * 1024],
        threshold=0.8,
    )
    assert len(candidates) == 1
    assert len(candidates[0]) == 0  # below threshold


async def test_check_multiple_contents():
    engine = MagicMock()
    engine.search_nodes = AsyncMock(
        side_effect=[
            [
                ScoredNode(
                    node=Node(id=1, type="t", content="match1"), score=0.9, sources=["vector"]
                )
            ],
            [],  # no matches for second content
        ]
    )
    checker = DedupChecker(engine)
    candidates = await checker.check(
        contents=["content A", "content B"],
        embeddings=[[0.1] * 1024, [0.2] * 1024],
    )
    assert len(candidates) == 2
    assert len(candidates[0]) == 1
    assert len(candidates[1]) == 0


async def test_check_empty_input():
    engine = _mock_search_engine([])
    checker = DedupChecker(engine)
    candidates = await checker.check(contents=[], embeddings=[])
    assert candidates == []
