# tests/services/test_commit_engine/test_store.py
import pytest
from datetime import datetime, timezone
from libs.models import Commit, AddEdgeOp, NewNode, NodeRef
from services.commit_engine.store import CommitStore


@pytest.fixture
def store(tmp_path):
    return CommitStore(storage_path=str(tmp_path / "commits"))


def _make_commit(commit_id: str = "test-001") -> Commit:
    return Commit(
        commit_id=commit_id,
        message="test commit",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="premise")],
                head=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["test reasoning"],
            )
        ],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


async def test_save_and_get(store):
    commit = _make_commit("abc-123")
    cid = await store.save(commit)
    assert cid == "abc-123"
    loaded = await store.get("abc-123")
    assert loaded is not None
    assert loaded.commit_id == "abc-123"
    assert loaded.message == "test commit"
    assert loaded.status == "pending_review"


async def test_get_nonexistent(store):
    result = await store.get("nonexistent")
    assert result is None


async def test_update(store):
    await store.save(_make_commit("upd-001"))
    await store.update("upd-001", status="reviewed", review_results={"approved": True})
    loaded = await store.get("upd-001")
    assert loaded.status == "reviewed"
    assert loaded.review_results == {"approved": True}


async def test_save_multiple(store):
    await store.save(_make_commit("c1"))
    await store.save(_make_commit("c2"))
    c1 = await store.get("c1")
    c2 = await store.get("c2")
    assert c1 is not None
    assert c2 is not None
    assert c1.commit_id != c2.commit_id
