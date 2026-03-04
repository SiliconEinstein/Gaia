# tests/services/test_commit_engine/test_engine.py
"""CommitEngine tests — real storage instead of mocks."""

import pytest

from libs.models import (
    AddEdgeOp,
    CommitRequest,
    NewNode,
    NodeRef,
)
from services.commit_engine.engine import CommitEngine
from services.commit_engine.store import CommitStore


@pytest.fixture
async def engine(storage, tmp_path):
    """CommitEngine backed by real storage."""
    commit_store = CommitStore(storage_path=str(tmp_path / "commits"))
    return CommitEngine(
        storage=storage,
        commit_store=commit_store,
    )


def _add_edge_request(message="test", content="premise"):
    """Helper: a valid CommitRequest with one AddEdgeOp."""
    return CommitRequest(
        message=message,
        operations=[
            AddEdgeOp(
                tail=[NewNode(content=content)],
                head=[NodeRef(node_id=67)],  # fixture node
                type="induction",
                reasoning=["deduction"],
            )
        ],
    )


async def test_submit_creates_commit(engine):
    resp = await engine.submit(_add_edge_request("test submit"))
    assert resp.commit_id is not None
    assert resp.status == "pending_review"
    # Verify commit is actually persisted
    commit = await engine.get_commit(resp.commit_id)
    assert commit is not None
    assert commit.message == "test submit"
    assert commit.status == "pending_review"
    assert len(commit.operations) == 1


async def test_submit_rejects_invalid(engine):
    req = CommitRequest(
        message="invalid",
        operations=[
            AddEdgeOp(tail=[], head=[], type="induction", reasoning=[]),
        ],
    )
    resp = await engine.submit(req)
    assert resp.status == "rejected"
    # Verify rejected commit is persisted
    commit = await engine.get_commit(resp.commit_id)
    assert commit is not None
    assert commit.status == "rejected"


async def test_review_approves(engine):
    resp = await engine.submit(_add_edge_request())
    review = await engine.review(resp.commit_id)
    assert review["approved"] is True
    # Commit status updated in store
    commit = await engine.get_commit(resp.commit_id)
    assert commit.status == "reviewed"


async def test_merge_after_review(engine, storage):
    resp = await engine.submit(_add_edge_request("merge test", "new node for merge"))
    await engine.review(resp.commit_id)
    result = await engine.merge(resp.commit_id)
    assert result.success is True
    assert len(result.new_node_ids) == 1
    # Verify the new node actually exists in LanceDB
    new_node = await storage.lance.load_node(result.new_node_ids[0])
    assert new_node is not None
    assert new_node.content == "new node for merge"
    # Commit status is merged
    commit = await engine.get_commit(resp.commit_id)
    assert commit.status == "merged"


async def test_merge_without_review_fails(engine):
    resp = await engine.submit(_add_edge_request())
    result = await engine.merge(resp.commit_id)
    assert result.success is False


async def test_merge_force_skips_review(engine, storage):
    resp = await engine.submit(_add_edge_request("force merge", "forced node"))
    result = await engine.merge(resp.commit_id, force=True)
    assert result.success is True
    # Node actually persisted
    new_node = await storage.lance.load_node(result.new_node_ids[0])
    assert new_node is not None
    assert new_node.content == "forced node"


async def test_get_commit(engine):
    resp = await engine.submit(_add_edge_request("get test"))
    commit = await engine.get_commit(resp.commit_id)
    assert commit is not None
    assert commit.message == "get test"


async def test_get_nonexistent_commit(engine):
    commit = await engine.get_commit("nonexistent")
    assert commit is None
