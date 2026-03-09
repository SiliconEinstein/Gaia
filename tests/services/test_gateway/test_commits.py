import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from libs.storage import StorageConfig
from services.gateway.app import create_app
from services.gateway.deps import Dependencies


@pytest.fixture
def sync_deps(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    dep = Dependencies(config)
    dep.initialize(config)
    dep.storage.graph = None
    return dep


@pytest.fixture
async def client(sync_deps):
    app = create_app(dependencies=sync_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _valid_commit_payload():
    return {
        "message": "test commit",
        "operations": [
            {
                "op": "add_edge",
                "premises": [{"content": "premise A"}],
                "conclusions": [{"node_id": 42}],
                "type": "induction",
                "reasoning": ["deduction from A"],
            }
        ],
    }


async def test_submit_commit(client):
    resp = await client.post("/commits", json=_valid_commit_payload())
    assert resp.status_code == 200
    data = resp.json()
    assert "commit_id" in data
    assert data["status"] == "pending_review"


async def test_get_commit(client):
    resp = await client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    resp = await client.get(f"/commits/{commit_id}")
    assert resp.status_code == 200
    assert resp.json()["commit_id"] == commit_id


async def test_get_commit_not_found(client):
    resp = await client.get("/commits/nonexistent")
    assert resp.status_code == 404


async def test_review_commit(client):
    resp = await client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    resp = await client.post(f"/commits/{commit_id}/review")
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] in ("running", "pending", "completed")


async def test_merge_commit(client):
    resp = await client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    # Submit review
    resp = await client.post(f"/commits/{commit_id}/review")
    assert resp.status_code == 200
    # Wait for review completion
    for _ in range(50):
        resp = await client.get(f"/commits/{commit_id}/review")
        if resp.json()["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.02)
    # Merge
    resp = await client.post(f"/commits/{commit_id}/merge")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


async def test_merge_without_review_fails(client):
    resp = await client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    resp = await client.post(f"/commits/{commit_id}/merge")
    assert resp.status_code == 200
    assert resp.json()["success"] is False


async def test_merge_force(client):
    resp = await client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    resp = await client.post(f"/commits/{commit_id}/merge", json={"force": True})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


async def test_review_not_found(client):
    resp = await client.post("/commits/nonexistent/review")
    assert resp.status_code == 404


async def test_merge_not_found(client):
    resp = await client.post("/commits/nonexistent/merge")
    assert resp.status_code == 404


async def test_get_review_status(client):
    resp = await client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    await client.post(f"/commits/{commit_id}/review")
    resp = await client.get(f"/commits/{commit_id}/review")
    assert resp.status_code == 200
    assert "status" in resp.json()


async def test_get_review_result(client):
    resp = await client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    await client.post(f"/commits/{commit_id}/review")
    # Wait for completion
    for _ in range(50):
        resp = await client.get(f"/commits/{commit_id}/review")
        if resp.json()["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.02)
    resp = await client.get(f"/commits/{commit_id}/review/result")
    assert resp.status_code == 200
    assert "overall_verdict" in resp.json()


async def test_delete_review(client):
    resp = await client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    await client.post(f"/commits/{commit_id}/review")
    resp = await client.delete(f"/commits/{commit_id}/review")
    assert resp.status_code == 200


async def test_get_review_status_no_review(client):
    resp = await client.post("/commits", json=_valid_commit_payload())
    commit_id = resp.json()["commit_id"]
    resp = await client.get(f"/commits/{commit_id}/review")
    assert resp.status_code == 404


async def test_list_commits(client):
    """GET /commits returns list of commits."""
    # Submit a commit first
    resp = await client.post(
        "/commits",
        json={
            "message": "list test",
            "operations": [
                {
                    "op": "add_edge",
                    "premises": [{"content": "p"}],
                    "conclusions": [{"node_id": 1}],
                    "type": "induction",
                    "reasoning": ["test"],
                }
            ],
        },
    )
    assert resp.status_code == 200
    # List commits
    resp = await client.get("/commits")
    assert resp.status_code == 200
    commits = resp.json()
    assert isinstance(commits, list)
    assert len(commits) >= 1
