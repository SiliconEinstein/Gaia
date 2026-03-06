# tests/services/test_gateway/test_batch.py
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock

from libs.models import CommitResponse, MergeResult
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.job_manager.manager import JobManager
from services.job_manager.models import Job, JobStatus, JobType
from services.job_manager.store import InMemoryJobStore


def _make_completed_review_job():
    """Create a mock completed review job."""
    job = Job(job_type=JobType.REVIEW, reference_id="c1")
    job.status = JobStatus.COMPLETED
    job.result = {"overall_verdict": "pass"}
    return job


@pytest.fixture
def deps():
    d = Dependencies()
    d.storage = MagicMock()
    d.storage.graph = None
    d.storage.lance = MagicMock()
    d.storage.vector = AsyncMock()
    d.search_engine = MagicMock()
    d.commit_engine = MagicMock()
    d.commit_engine.submit = AsyncMock(
        return_value=CommitResponse(commit_id="c1", status="pending_review")
    )
    d.commit_engine.submit_review = AsyncMock(return_value=MagicMock(job_id="rj1"))
    d.commit_engine.job_manager = MagicMock()
    d.commit_engine.job_manager.get_status = AsyncMock(return_value=_make_completed_review_job())
    d.commit_engine.job_manager.get_result = AsyncMock(return_value={"overall_verdict": "pass"})
    d.commit_engine.merge = AsyncMock(
        return_value=MergeResult(success=True, new_node_ids=[1], new_edge_ids=[10])
    )
    d.job_manager = JobManager(store=InMemoryJobStore())
    d.inference_engine = MagicMock()
    return d


@pytest.fixture
async def client(deps):
    app = create_app(dependencies=deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_batch_commit_returns_job(client):
    resp = await client.post(
        "/commits/batch",
        json={
            "commits": [
                {"message": "paper 1", "operations": []},
                {"message": "paper 2", "operations": []},
            ],
            "auto_review": True,
            "auto_merge": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["total_commits"] == 2


async def test_batch_commit_result(client):
    resp = await client.post(
        "/commits/batch",
        json={
            "commits": [{"message": "paper 1", "operations": []}],
            "auto_review": True,
            "auto_merge": True,
        },
    )
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)

    resp = await client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert "commits" in result


# -- Batch Read (#10) ---------------------------------------------------------


async def test_batch_read_nodes(client):
    resp = await client.post("/nodes/batch", json={"node_ids": [1, 2, 3]})
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_read_edges(client):
    resp = await client.post("/hyperedges/batch", json={"edge_ids": [10, 20]})
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_subgraph(client):
    resp = await client.post(
        "/nodes/subgraph/batch",
        json={
            "queries": [
                {"node_id": 1, "hops": 2},
                {"node_id": 2, "hops": 3, "direction": "upstream"},
            ]
        },
    )
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_read_nodes_result(client, deps):
    from libs.models import Node

    deps.storage.lance.load_nodes_bulk = AsyncMock(
        return_value=[Node(id=1, type="paper-extract", content="test")]
    )
    resp = await client.post("/nodes/batch", json={"node_ids": [1]})
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)
    resp = await client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200
    assert "nodes" in resp.json()["result"]


# -- Batch Search (#11) -------------------------------------------------------


async def test_batch_search_nodes(client, deps):
    deps.search_engine.search_nodes = AsyncMock(return_value=[])
    resp = await client.post(
        "/search/nodes/batch",
        json={
            "queries": [
                {"text": "superconductor", "top_k": 10},
                {"text": "hydride", "top_k": 5},
            ]
        },
    )
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_search_edges(client, deps):
    deps.search_engine.search_edges = AsyncMock(return_value=[])
    resp = await client.post(
        "/search/hyperedges/batch",
        json={"queries": [{"text": "synthesis route"}]},
    )
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_search_nodes_result(client, deps):
    deps.search_engine.search_nodes = AsyncMock(return_value=[])
    resp = await client.post(
        "/search/nodes/batch",
        json={"queries": [{"text": "q1"}]},
    )
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)
    resp = await client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200
    assert "results" in resp.json()["result"]


# -- Batch Progress & Cancel --------------------------------------------------


async def test_get_batch_commit_progress(client):
    resp = await client.post(
        "/commits/batch",
        json={
            "commits": [
                {"message": "p1", "operations": []},
                {"message": "p2", "operations": []},
            ],
            "auto_review": True,
            "auto_merge": True,
        },
    )
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)

    resp = await client.get(f"/commits/batch/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "total_commits" in data


async def test_cancel_batch(client):
    resp = await client.post(
        "/commits/batch",
        json={"commits": [{"message": "p1", "operations": []}]},
    )
    job_id = resp.json()["job_id"]
    resp = await client.delete(f"/commits/batch/{job_id}")
    assert resp.status_code == 200


async def test_batch_commit_review_timeout():
    """When review polling times out, commit status should be 'review_timeout', not 'rejected'."""
    running_job = Job(job_type=JobType.REVIEW, reference_id="c1")
    running_job.status = JobStatus.RUNNING

    d = Dependencies()
    d.storage = MagicMock()
    d.storage.graph = None
    d.storage.lance = MagicMock()
    d.storage.vector = AsyncMock()
    d.search_engine = MagicMock()
    d.commit_engine = MagicMock()
    d.commit_engine.submit = AsyncMock(
        return_value=CommitResponse(commit_id="c1", status="pending_review")
    )
    d.commit_engine.submit_review = AsyncMock(return_value=MagicMock(job_id="rj1"))
    # Always return RUNNING — review never completes
    d.commit_engine.job_manager = MagicMock()
    d.commit_engine.job_manager.get_status = AsyncMock(return_value=running_job)
    d.commit_engine.merge = AsyncMock()
    d.job_manager = JobManager(store=InMemoryJobStore())
    d.inference_engine = MagicMock()

    app = create_app(dependencies=d)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/commits/batch",
            json={
                "commits": [{"message": "timeout paper", "operations": []}],
                "auto_review": True,
                "auto_merge": True,
            },
        )
        job_id = resp.json()["job_id"]
        # Wait for the batch job to complete (polling loop ~100*0.05s = 5s)
        await asyncio.sleep(6)

        resp = await client.get(f"/jobs/{job_id}/result")
        assert resp.status_code == 200
        result = resp.json()["result"]
        commit = result["commits"][0]
        assert commit["status"] == "review_timeout", (
            f"Expected 'review_timeout', got '{commit['status']}'"
        )
        # Merge should NOT have been called
        d.commit_engine.merge.assert_not_called()
