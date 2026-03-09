# tests/services/test_commit_engine/test_merger.py
"""Merger tests — real storage instead of mocks."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from libs.models import (
    AddEdgeOp,
    BPResults,
    Commit,
    DetailedReviewResult,
    ModifyEdgeOp,
    ModifyNodeOp,
    NewNode,
    NodeRef,
)
from services.commit_engine.merger import Merger


def _make_commit(ops, commit_id="merge-001", **kwargs):
    return Commit(
        commit_id=commit_id,
        message="test merge",
        operations=ops,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        **kwargs,
    )


def _mock_storage():
    storage = MagicMock()
    storage.ids = MagicMock()
    storage.ids.alloc_node_id = AsyncMock(side_effect=range(100, 200))
    storage.ids.alloc_hyperedge_id = AsyncMock(side_effect=range(200, 300))
    storage.lance = MagicMock()
    storage.lance.save_nodes = AsyncMock()
    storage.lance.update_node = AsyncMock()
    storage.graph = MagicMock()
    storage.graph.create_hyperedge = AsyncMock(return_value=200)
    storage.graph.update_hyperedge = AsyncMock()
    storage.vector = MagicMock()
    storage.vector.insert_batch = AsyncMock()
    return storage


@pytest.fixture
async def merger(storage):
    return Merger(storage)


async def test_merge_add_edge_with_new_nodes(merger, storage):
    commit = _make_commit(
        [
            AddEdgeOp(
                premises=[NewNode(content="premise A"), NewNode(content="premise B")],
                conclusions=[NodeRef(node_id=67)],  # fixture node
                type="induction",
                reasoning=["deduction from A and B"],
            )
        ]
    )
    result = await merger.merge(commit)
    assert result.success is True
    assert len(result.new_node_ids) == 2
    assert len(result.new_edge_ids) == 1
    # Verify nodes actually in LanceDB
    node_a = await storage.lance.load_node(result.new_node_ids[0])
    node_b = await storage.lance.load_node(result.new_node_ids[1])
    assert node_a is not None
    assert node_a.content == "premise A"
    assert node_b is not None
    assert node_b.content == "premise B"


async def test_merge_add_edge_with_existing_nodes_only(merger, storage):
    commit = _make_commit(
        [
            AddEdgeOp(
                premises=[NodeRef(node_id=67)],
                conclusions=[NodeRef(node_id=68)],
                type="abstraction",
                reasoning=["merge abstraction"],
            )
        ]
    )
    result = await merger.merge(commit)
    assert result.success is True
    assert len(result.new_node_ids) == 0
    assert len(result.new_edge_ids) == 1
    # Existing fixture nodes should be unchanged
    node = await storage.lance.load_node(67)
    assert node is not None
    assert "Synthesis precursors" in (node.title or "")


async def test_merge_modify_node(merger, storage):
    commit = _make_commit([ModifyNodeOp(node_id=67, changes={"content": "updated content"})])
    result = await merger.merge(commit)
    assert result.success is True
    # Verify node content was actually updated
    node = await storage.lance.load_node(67)
    assert node is not None
    assert node.content == "updated content"


async def test_merge_modify_edge(merger, storage):
    """ModifyEdgeOp requires graph; skip if unavailable."""
    if not storage.graph:
        pytest.skip("Neo4j not available")
    commit = _make_commit(
        [ModifyEdgeOp(edge_id=100, changes={"verified": True, "probability": 0.95})]
    )
    result = await merger.merge(commit)
    assert result.success is True


async def test_merge_no_graph_still_works(storage_empty):
    """When Neo4j is unavailable, merge should still work (skip graph ops)."""
    storage_empty.graph = None
    merger = Merger(storage_empty)
    commit = _make_commit(
        [
            AddEdgeOp(
                premises=[NewNode(content="p")],
                conclusions=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["test"],
            )
        ]
    )
    result = await merger.merge(commit)
    assert result.success is True
    # Node is in LanceDB despite no graph
    node = await storage_empty.lance.load_node(result.new_node_ids[0])
    assert node is not None
    assert node.content == "p"


async def test_merge_multiple_operations(merger, storage):
    commit = _make_commit(
        [
            AddEdgeOp(
                premises=[NewNode(content="new node")],
                conclusions=[NodeRef(node_id=67)],
                type="induction",
                reasoning=["reasoning"],
            ),
            ModifyNodeOp(node_id=68, changes={"status": "deleted"}),
        ]
    )
    result = await merger.merge(commit)
    assert result.success is True
    assert len(result.new_node_ids) == 1
    assert len(result.new_edge_ids) == 1
    # New node exists
    new_node = await storage.lance.load_node(result.new_node_ids[0])
    assert new_node is not None
    assert new_node.content == "new node"
    # Existing node was modified
    modified = await storage.lance.load_node(68)
    assert modified is not None
    assert modified.status == "deleted"


# ------------------------------------------------------------------
# BP persistence tests (mock-based for assert_any_call verification)
# ------------------------------------------------------------------


async def test_merge_persists_belief_updates():
    """Merger should update node beliefs from review BP results."""
    storage = _mock_storage()
    merger = Merger(storage)

    commit = _make_commit(
        [],
        commit_id="c1",
        status="reviewed",
        review_results=DetailedReviewResult(
            overall_verdict="pass",
            operations=[],
            bp_results=BPResults(
                belief_updates={"1": 0.85},
                iterations=5,
                converged=True,
                affected_nodes=["1"],
            ),
        ).model_dump(),
    )

    result = await merger.merge(commit)
    assert result.success is True
    assert result.beliefs_persisted == {"1": 0.85}
    assert result.bp_results is not None
    assert result.bp_results.converged is True
    storage.lance.update_node.assert_any_call(1, belief=0.85)


async def test_merge_result_includes_bp():
    """MergeResult should include BP results from review."""
    storage = _mock_storage()
    merger = Merger(storage)

    commit = _make_commit(
        [],
        commit_id="c2",
        status="reviewed",
        review_results=DetailedReviewResult(
            overall_verdict="pass",
            operations=[],
            bp_results=BPResults(
                belief_updates={},
                iterations=3,
                converged=True,
                affected_nodes=[],
            ),
        ).model_dump(),
    )

    result = await merger.merge(commit)
    assert result.bp_results is not None
    assert result.bp_results.converged is True
    assert result.bp_results.iterations == 3


async def test_merge_without_review_results():
    """Merge with no review results should work (backward compat)."""
    storage = _mock_storage()
    merger = Merger(storage)

    commit = _make_commit(
        [],
        commit_id="c3",
        status="reviewed",
    )

    result = await merger.merge(commit)
    assert result.success is True
    assert result.bp_results is None
    assert result.beliefs_persisted == {}
