"""End-to-end test for batch APIs using real LanceDB (no Neo4j)."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from libs.storage import StorageConfig
from services.gateway.app import create_app
from services.gateway.deps import Dependencies


@pytest.fixture
async def e2e_client(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    dep = Dependencies(config)
    dep.initialize(config)
    dep.storage.graph = None

    app = create_app(dependencies=dep)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await dep.cleanup()


async def test_batch_read_nodes_e2e(e2e_client):
    """Batch read on empty DB returns empty."""
    resp = await e2e_client.post("/nodes/batch", json={"node_ids": [1, 2]})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)
    result = await e2e_client.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200
    assert "nodes" in result.json()["result"]


async def test_batch_search_e2e(e2e_client):
    """Batch search on empty DB returns empty results."""
    resp = await e2e_client.post(
        "/search/nodes/batch",
        json={"queries": [{"text": "superconductor", "top_k": 5}]},
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)
    result = await e2e_client.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200
    assert "results" in result.json()["result"]


async def test_batch_commit_e2e(e2e_client):
    """Batch commit with empty operations succeeds."""
    resp = await e2e_client.post(
        "/commits/batch",
        json={
            "commits": [
                {"message": "test paper 1", "operations": []},
                {"message": "test paper 2", "operations": []},
            ],
            "auto_review": True,
            "auto_merge": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["total_commits"] == 2

    job_id = data["job_id"]
    await asyncio.sleep(1.0)
    result = await e2e_client.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200
    assert "commits" in result.json()["result"]
