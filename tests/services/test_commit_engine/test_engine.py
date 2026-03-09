# tests/services/test_commit_engine/test_engine.py
"""CommitEngine tests — real storage instead of mocks."""

import asyncio

import pytest

from libs.models import (
    AddEdgeOp,
    CommitRequest,
    NewNode,
    NodeRef,
)
from services.commit_engine.engine import CommitEngine
from services.commit_engine.store import CommitStore
from services.job_manager.models import JobStatus


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
                premises=[NewNode(content=content)],
                conclusions=[NodeRef(node_id=67)],  # fixture node
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
            AddEdgeOp(premises=[], conclusions=[], type="induction", reasoning=[]),
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


# ------------------------------------------------------------------
# Pipeline / async review tests
# ------------------------------------------------------------------


async def test_submit_review_returns_job(engine):
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                premises=[NewNode(content="premise")],
                conclusions=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["r"],
            )
        ],
    )
    resp = await engine.submit(req)
    job = await engine.submit_review(resp.commit_id)
    assert job.job_id is not None
    assert job.job_type.value == "review"
    assert job.reference_id == resp.commit_id


async def test_submit_review_stores_job_id_on_commit(engine):
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                premises=[NewNode(content="p")],
                conclusions=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["r"],
            )
        ],
    )
    resp = await engine.submit(req)
    job = await engine.submit_review(resp.commit_id)

    commit = await engine.get_commit(resp.commit_id)
    assert commit.review_job_id == job.job_id


async def test_review_job_completes_with_result(engine):
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                premises=[NewNode(content="p")],
                conclusions=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["r"],
            )
        ],
    )
    resp = await engine.submit(req)
    job = await engine.submit_review(resp.commit_id)

    for _ in range(100):
        status = await engine.job_manager.get_status(job.job_id)
        if status.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break
        await asyncio.sleep(0.01)

    assert status.status == JobStatus.COMPLETED
    result = await engine.job_manager.get_result(job.job_id)
    assert "overall_verdict" in result
    assert result["overall_verdict"] == "pass"


async def test_submit_review_rejects_non_pending(engine):
    """submit_review raises ValueError if commit is not pending_review."""
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                premises=[NewNode(content="p")],
                conclusions=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["r"],
            )
        ],
    )
    resp = await engine.submit(req)
    # Review it first so status becomes "reviewed"
    await engine.review(resp.commit_id)
    with pytest.raises(ValueError, match="not pending review"):
        await engine.submit_review(resp.commit_id)


async def test_submit_review_not_found(engine):
    """submit_review raises ValueError for non-existent commit."""
    with pytest.raises(ValueError, match="not found"):
        await engine.submit_review("nonexistent")
