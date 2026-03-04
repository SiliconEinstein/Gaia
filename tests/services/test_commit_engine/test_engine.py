# tests/services/test_commit_engine/test_engine.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from libs.models import (
    CommitRequest,
    AddEdgeOp,
    NewNode,
    NodeRef,
)
from services.commit_engine.engine import CommitEngine


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
def engine(tmp_path):
    storage = _mock_storage()
    from services.commit_engine.store import CommitStore

    commit_store = CommitStore(storage_path=str(tmp_path / "commits"))
    return CommitEngine(
        storage=storage,
        commit_store=commit_store,
    )


async def test_submit_creates_commit(engine):
    req = CommitRequest(
        message="test submit",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="premise")],
                head=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["deduction"],
            )
        ],
    )
    resp = await engine.submit(req)
    assert resp.commit_id is not None
    assert resp.status == "pending_review"


async def test_submit_rejects_invalid(engine):
    req = CommitRequest(
        message="invalid",
        operations=[
            AddEdgeOp(tail=[], head=[], type="induction", reasoning=[]),
        ],
    )
    resp = await engine.submit(req)
    assert resp.status == "rejected"


async def test_review_approves(engine):
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="p")],
                head=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["r"],
            )
        ],
    )
    resp = await engine.submit(req)
    review = await engine.review(resp.commit_id)
    assert review["approved"] is True
    # Commit should be updated to reviewed
    commit = await engine.get_commit(resp.commit_id)
    assert commit.status == "reviewed"


async def test_merge_after_review(engine):
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="p")],
                head=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["r"],
            )
        ],
    )
    resp = await engine.submit(req)
    await engine.review(resp.commit_id)
    result = await engine.merge(resp.commit_id)
    assert result.success is True
    commit = await engine.get_commit(resp.commit_id)
    assert commit.status == "merged"


async def test_merge_without_review_fails(engine):
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="p")],
                head=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["r"],
            )
        ],
    )
    resp = await engine.submit(req)
    # Try to merge without review
    result = await engine.merge(resp.commit_id)
    assert result.success is False


async def test_merge_force_skips_review(engine):
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="p")],
                head=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["r"],
            )
        ],
    )
    resp = await engine.submit(req)
    result = await engine.merge(resp.commit_id, force=True)
    assert result.success is True


async def test_get_commit(engine):
    req = CommitRequest(
        message="get test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="p")],
                head=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["r"],
            )
        ],
    )
    resp = await engine.submit(req)
    commit = await engine.get_commit(resp.commit_id)
    assert commit is not None
    assert commit.message == "get test"


async def test_get_nonexistent_commit(engine):
    commit = await engine.get_commit("nonexistent")
    assert commit is None
