# tests/services/test_commit_engine/test_merger.py
from unittest.mock import AsyncMock, MagicMock
from libs.models import (
    Commit,
    AddEdgeOp,
    ModifyEdgeOp,
    ModifyNodeOp,
    NewNode,
    NodeRef,
)
from services.commit_engine.merger import Merger


def _mock_storage():
    storage = MagicMock()
    storage.ids = MagicMock()
    storage.ids.alloc_node_id = AsyncMock(side_effect=[100, 101, 102, 103, 104])
    storage.ids.alloc_hyperedge_id = AsyncMock(side_effect=[200, 201, 202])
    storage.lance = MagicMock()
    storage.lance.save_nodes = AsyncMock(return_value=[])
    storage.lance.update_node = AsyncMock()
    storage.graph = MagicMock()
    storage.graph.create_hyperedge = AsyncMock(return_value=200)
    storage.graph.update_hyperedge = AsyncMock()
    storage.vector = MagicMock()
    storage.vector.insert_batch = AsyncMock()
    return storage


def _make_commit(ops):
    from datetime import datetime, timezone

    return Commit(
        commit_id="merge-001",
        message="test merge",
        operations=ops,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


async def test_merge_add_edge_with_new_nodes():
    storage = _mock_storage()
    commit = _make_commit(
        [
            AddEdgeOp(
                tail=[NewNode(content="premise A"), NewNode(content="premise B")],
                head=[NodeRef(node_id=42)],
                type="meet",
                reasoning=["deduction from A and B"],
            )
        ]
    )
    merger = Merger(storage)
    result = await merger.merge(commit)
    assert result.success is True
    assert len(result.new_node_ids) == 2  # two new nodes created
    assert len(result.new_edge_ids) == 1
    # Verify nodes were saved to lance
    storage.lance.save_nodes.assert_called()


async def test_merge_add_edge_with_existing_nodes_only():
    storage = _mock_storage()
    commit = _make_commit(
        [
            AddEdgeOp(
                tail=[NodeRef(node_id=10)],
                head=[NodeRef(node_id=20)],
                type="join",
                reasoning=["merge join"],
            )
        ]
    )
    merger = Merger(storage)
    result = await merger.merge(commit)
    assert result.success is True
    assert len(result.new_node_ids) == 0
    assert len(result.new_edge_ids) == 1


async def test_merge_modify_node():
    storage = _mock_storage()
    commit = _make_commit(
        [ModifyNodeOp(node_id=42, changes={"content": "updated content", "status": "deleted"})]
    )
    merger = Merger(storage)
    result = await merger.merge(commit)
    assert result.success is True
    storage.lance.update_node.assert_called_once_with(
        42, content="updated content", status="deleted"
    )


async def test_merge_modify_edge():
    storage = _mock_storage()
    commit = _make_commit(
        [ModifyEdgeOp(edge_id=100, changes={"verified": True, "probability": 0.95})]
    )
    merger = Merger(storage)
    result = await merger.merge(commit)
    assert result.success is True
    storage.graph.update_hyperedge.assert_called_once_with(100, verified=True, probability=0.95)


async def test_merge_no_graph_still_works():
    """When Neo4j is unavailable, merge should still work (just skip graph ops)."""
    storage = _mock_storage()
    storage.graph = None
    commit = _make_commit(
        [
            AddEdgeOp(
                tail=[NewNode(content="p")],
                head=[NodeRef(node_id=1)],
                type="meet",
                reasoning=["test"],
            )
        ]
    )
    merger = Merger(storage)
    result = await merger.merge(commit)
    assert result.success is True


async def test_merge_multiple_operations():
    storage = _mock_storage()
    commit = _make_commit(
        [
            AddEdgeOp(
                tail=[NewNode(content="new node")],
                head=[NodeRef(node_id=1)],
                type="meet",
                reasoning=["reasoning"],
            ),
            ModifyNodeOp(node_id=1, changes={"status": "deleted"}),
        ]
    )
    merger = Merger(storage)
    result = await merger.merge(commit)
    assert result.success is True
    assert len(result.new_node_ids) == 1
    assert len(result.new_edge_ids) == 1
