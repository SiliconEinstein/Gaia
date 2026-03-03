# Plan 3: Batch Processing APIs

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add batch (async) variants for all APIs: batch commit (with auto review/merge), batch search, batch read.

**Architecture:** All batch endpoints return a `job_id` immediately. The `JobManager` from Plan 2 runs the work in the background. Each batch endpoint wraps the corresponding single-input logic in a loop, collecting results into the job's result dict.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, JobManager from Plan 2

**Depends on:** Plan 1 (Operator Layer) + Plan 2 (Single-Input APIs) must be completed first.

---

### Task 1: Batch Commit API

**Files:**
- Create: `services/gateway/routes/batch.py`
- Modify: `services/gateway/app.py` (register router)
- Test: `tests/services/test_gateway/test_batch_commit.py`

**Step 1: Write the failing test**

```python
# tests/services/test_gateway/test_batch_commit.py
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from libs.models import CommitResponse, MergeResult, ReviewResult


@pytest.fixture
def test_deps():
    deps = Dependencies()
    deps.storage = MagicMock()
    deps.storage.graph = None
    deps.storage.vector = AsyncMock()
    deps.search_engine = MagicMock()
    deps.commit_engine = MagicMock()
    deps.commit_engine.submit = AsyncMock(
        return_value=CommitResponse(commit_id="c1", status="pending_review")
    )
    deps.commit_engine.review = AsyncMock(
        return_value=ReviewResult(approved=True).model_dump()
    )
    deps.commit_engine.merge = AsyncMock(
        return_value=MergeResult(success=True, new_node_ids=[1], new_edge_ids=[2])
    )
    deps.job_manager = JobManager(store=InMemoryJobStore())
    deps.review_pipeline_config = MagicMock()
    deps.inference_engine = MagicMock()
    return deps


@pytest.fixture
async def client(test_deps):
    app = create_app(dependencies=test_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_batch_commit_returns_job(client):
    resp = await client.post("/commits/batch", json={
        "commits": [
            {"message": "paper 1", "operations": []},
            {"message": "paper 2", "operations": []},
        ],
        "auto_review": True,
        "auto_merge": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["total_commits"] == 2
    assert data["status"] == "running"


async def test_batch_commit_progress(client, test_deps):
    resp = await client.post("/commits/batch", json={
        "commits": [
            {"message": "paper 1", "operations": []},
        ],
        "auto_review": True,
        "auto_merge": True,
    })
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.2)

    resp = await client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert "commits" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_batch_commit.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# services/gateway/routes/batch.py
"""Batch API routes — all async via JobManager."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from libs.models import CommitRequest
from services.gateway.deps import deps
from services.job_manager.models import JobType

router = APIRouter(tags=["batch"])


# ── Batch Commit ──────────────────────────────────────────────────────


class BatchCommitRequest(BaseModel):
    commits: list[CommitRequest]
    auto_review: bool = True
    auto_merge: bool = True
    review_depth: str = "standard"


@router.post("/commits/batch")
async def batch_commit(request: BatchCommitRequest):
    async def work(job_id: str) -> dict:
        results = []
        for req in request.commits:
            commit_resp = await deps.commit_engine.submit(req)
            entry = {
                "commit_id": commit_resp.commit_id,
                "message": req.message,
                "status": commit_resp.status,
            }
            if commit_resp.status == "rejected":
                results.append(entry)
                continue

            if request.auto_review:
                review_result = await deps.commit_engine.review(
                    commit_resp.commit_id, depth=request.review_depth
                )
                reviewed = review_result.get("approved", False) if isinstance(review_result, dict) else False
                entry["status"] = "reviewed" if reviewed else "rejected"

                if reviewed and request.auto_merge:
                    merge_result = await deps.commit_engine.merge(
                        commit_resp.commit_id, force=False
                    )
                    entry["status"] = "merged" if merge_result.success else "merge_failed"
                    entry["merge_result"] = merge_result.model_dump()

            results.append(entry)

        return {"commits": results, "total": len(results)}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_COMMIT,
        reference_id=f"batch_{len(request.commits)}",
        work_fn=work,
    )
    return {
        "job_id": job.job_id,
        "total_commits": len(request.commits),
        "status": job.status,
    }


# ── Batch Search Nodes ────────────────────────────────────────────────


class BatchSearchQuery(BaseModel):
    text: str
    top_k: int = 50


class BatchSearchNodesRequest(BaseModel):
    queries: list[BatchSearchQuery]
    filters: dict | None = None


@router.post("/search/nodes/batch")
async def batch_search_nodes(request: BatchSearchNodesRequest):
    async def work(job_id: str) -> dict:
        results = []
        for q in request.queries:
            scored = await deps.search_engine.search_nodes(
                query=q.text, k=q.top_k,
            )
            results.append([s.model_dump() for s in scored])
        return {"results": results, "total_queries": len(results)}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_SEARCH,
        reference_id=f"search_batch_{len(request.queries)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}


# ── Batch Search Hyperedges ───────────────────────────────────────────


class BatchSearchEdgesRequest(BaseModel):
    queries: list[BatchSearchQuery]
    filters: dict | None = None


@router.post("/search/hyperedges/batch")
async def batch_search_edges(request: BatchSearchEdgesRequest):
    async def work(job_id: str) -> dict:
        results = []
        for q in request.queries:
            scored = await deps.search_engine.search_edges(
                query=q.text, k=q.top_k,
            )
            results.append([s.model_dump() for s in scored])
        return {"results": results, "total_queries": len(results)}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_SEARCH,
        reference_id=f"edge_search_batch_{len(request.queries)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}


# ── Batch Read Nodes ──────────────────────────────────────────────────


class BatchReadNodesRequest(BaseModel):
    node_ids: list[int]


@router.post("/nodes/batch")
async def batch_read_nodes(request: BatchReadNodesRequest):
    async def work(job_id: str) -> dict:
        nodes = await deps.storage.lance.load_nodes_bulk(request.node_ids)
        return {"nodes": [n.model_dump() for n in nodes]}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_READ,
        reference_id=f"read_nodes_{len(request.node_ids)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}


# ── Batch Read Hyperedges ─────────────────────────────────────────────


class BatchReadEdgesRequest(BaseModel):
    edge_ids: list[int]


@router.post("/hyperedges/batch")
async def batch_read_edges(request: BatchReadEdgesRequest):
    async def work(job_id: str) -> dict:
        if not deps.storage.graph:
            return {"edges": [], "error": "Graph store not available"}
        edges = []
        for eid in request.edge_ids:
            edge = await deps.storage.graph.get_hyperedge(eid)
            if edge:
                edges.append(edge.model_dump())
        return {"edges": edges}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_READ,
        reference_id=f"read_edges_{len(request.edge_ids)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}


# ── Batch Subgraph ────────────────────────────────────────────────────


class SubgraphQuery(BaseModel):
    node_id: int
    hops: int = 3
    direction: str = "both"


class BatchSubgraphRequest(BaseModel):
    queries: list[SubgraphQuery]


@router.post("/nodes/subgraph/batch")
async def batch_subgraph(request: BatchSubgraphRequest):
    async def work(job_id: str) -> dict:
        if not deps.storage.graph:
            return {"subgraphs": [], "error": "Graph store not available"}
        results = []
        for q in request.queries:
            node_ids, edge_ids = await deps.storage.graph.get_subgraph(
                [q.node_id], hops=q.hops
            )
            results.append({
                "center_node_id": q.node_id,
                "node_ids": list(node_ids),
                "edge_ids": list(edge_ids),
            })
        return {"subgraphs": results}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_READ,
        reference_id=f"subgraph_batch_{len(request.queries)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}
```

Register in `services/gateway/app.py`:

```python
from .routes.batch import router as batch_router
# ...
app.include_router(batch_router)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_gateway/test_batch_commit.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/gateway/routes/batch.py services/gateway/app.py tests/services/test_gateway/test_batch_commit.py
git commit -m "feat: add batch commit API with auto review/merge"
```

---

### Task 2: Batch Search + Read Tests

**Files:**
- Test: `tests/services/test_gateway/test_batch_search.py`
- Test: `tests/services/test_gateway/test_batch_read.py`

**Step 1: Write the failing tests**

```python
# tests/services/test_gateway/test_batch_search.py
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore


@pytest.fixture
def test_deps():
    deps = Dependencies()
    deps.storage = MagicMock()
    deps.storage.graph = None
    deps.storage.vector = AsyncMock()
    deps.search_engine = MagicMock()
    deps.search_engine.search_nodes = AsyncMock(return_value=[])
    deps.search_engine.search_edges = AsyncMock(return_value=[])
    deps.commit_engine = MagicMock()
    deps.job_manager = JobManager(store=InMemoryJobStore())
    deps.review_pipeline_config = MagicMock()
    deps.inference_engine = MagicMock()
    return deps


@pytest.fixture
async def client(test_deps):
    app = create_app(dependencies=test_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_batch_search_nodes(client):
    resp = await client.post("/search/nodes/batch", json={
        "queries": [
            {"text": "query 1", "top_k": 10},
            {"text": "query 2", "top_k": 5},
        ]
    })
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_search_edges(client):
    resp = await client.post("/search/hyperedges/batch", json={
        "queries": [{"text": "query 1"}]
    })
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_search_result(client):
    resp = await client.post("/search/nodes/batch", json={
        "queries": [{"text": "q1"}]
    })
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.2)
    resp = await client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200
    assert "results" in resp.json()["result"]
```

```python
# tests/services/test_gateway/test_batch_read.py
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from libs.models import Node


@pytest.fixture
def test_deps():
    deps = Dependencies()
    deps.storage = MagicMock()
    deps.storage.lance = MagicMock()
    deps.storage.lance.load_nodes_bulk = AsyncMock(
        return_value=[Node(id=1, type="paper-extract", content="a")]
    )
    deps.storage.graph = MagicMock()
    deps.storage.graph.get_hyperedge = AsyncMock(return_value=None)
    deps.storage.graph.get_subgraph = AsyncMock(return_value=({1}, {10}))
    deps.search_engine = MagicMock()
    deps.commit_engine = MagicMock()
    deps.job_manager = JobManager(store=InMemoryJobStore())
    deps.review_pipeline_config = MagicMock()
    deps.inference_engine = MagicMock()
    return deps


@pytest.fixture
async def client(test_deps):
    app = create_app(dependencies=test_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_batch_read_nodes(client):
    resp = await client.post("/nodes/batch", json={"node_ids": [1, 2, 3]})
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_read_edges(client):
    resp = await client.post("/hyperedges/batch", json={"edge_ids": [10, 20]})
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_subgraph(client):
    resp = await client.post("/nodes/subgraph/batch", json={
        "queries": [
            {"node_id": 1, "hops": 2},
            {"node_id": 2, "hops": 3, "direction": "upstream"},
        ]
    })
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_read_nodes_result(client):
    resp = await client.post("/nodes/batch", json={"node_ids": [1]})
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.2)
    resp = await client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200
    assert "nodes" in resp.json()["result"]
```

**Step 2: Run tests to verify they pass** (implementation already done in Task 1)

Run: `pytest tests/services/test_gateway/test_batch_search.py tests/services/test_gateway/test_batch_read.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/services/test_gateway/test_batch_search.py tests/services/test_gateway/test_batch_read.py
git commit -m "test: add batch search and batch read API tests"
```

---

### Task 3: Batch Commit Progress Endpoint

**Files:**
- Modify: `services/gateway/routes/batch.py` (add GET /commits/batch/{batch_id})
- Test: `tests/services/test_gateway/test_batch_progress.py`

**Step 1: Write the failing test**

```python
# tests/services/test_gateway/test_batch_progress.py
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from libs.models import CommitResponse, MergeResult, ReviewResult


@pytest.fixture
def test_deps():
    deps = Dependencies()
    deps.storage = MagicMock()
    deps.storage.graph = None
    deps.storage.vector = AsyncMock()
    deps.search_engine = MagicMock()
    deps.commit_engine = MagicMock()
    deps.commit_engine.submit = AsyncMock(
        return_value=CommitResponse(commit_id="c1", status="pending_review")
    )
    deps.commit_engine.review = AsyncMock(
        return_value=ReviewResult(approved=True).model_dump()
    )
    deps.commit_engine.merge = AsyncMock(
        return_value=MergeResult(success=True)
    )
    deps.job_manager = JobManager(store=InMemoryJobStore())
    deps.review_pipeline_config = MagicMock()
    deps.inference_engine = MagicMock()
    return deps


@pytest.fixture
async def client(test_deps):
    app = create_app(dependencies=test_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_get_batch_progress(client):
    resp = await client.post("/commits/batch", json={
        "commits": [
            {"message": "p1", "operations": []},
            {"message": "p2", "operations": []},
        ],
        "auto_review": True,
        "auto_merge": True,
    })
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)

    resp = await client.get(f"/commits/batch/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "total_commits" in data


async def test_cancel_batch(client):
    resp = await client.post("/commits/batch", json={
        "commits": [{"message": "p1", "operations": []}],
    })
    job_id = resp.json()["job_id"]
    resp = await client.delete(f"/commits/batch/{job_id}")
    assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_batch_progress.py -v`
Expected: FAIL

**Step 3: Add batch progress routes**

Add to `services/gateway/routes/batch.py`:

```python
@router.get("/commits/batch/{batch_id}")
async def get_batch_progress(batch_id: str):
    job = await deps.job_manager.get_status(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    result = job.result or {}
    commits = result.get("commits", [])
    progress = {}
    for c in commits:
        s = c.get("status", "unknown")
        progress[s] = progress.get(s, 0) + 1
    return {
        "job_id": job.job_id,
        "status": job.status,
        "total_commits": result.get("total", 0),
        "progress": progress,
        "commits": commits,
    }


@router.delete("/commits/batch/{batch_id}")
async def cancel_batch(batch_id: str):
    job = await deps.job_manager.get_status(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    await deps.job_manager.cancel(batch_id)
    return {"job_id": job.job_id, "status": "cancelled"}
```

Add `from fastapi import HTTPException` import.

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_gateway/test_batch_progress.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/gateway/routes/batch.py tests/services/test_gateway/test_batch_progress.py
git commit -m "feat: add batch commit progress and cancel endpoints"
```

---

### Task 4: Full Integration Test

**Files:**
- Test: `tests/integration/test_batch_e2e.py`

**Step 1: Write the integration test**

```python
# tests/integration/test_batch_e2e.py
"""End-to-end test for batch APIs using real LanceDB (no Neo4j)."""

import pytest
import asyncio
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from libs.storage import StorageConfig, StorageManager
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.search_engine.engine import SearchEngine
from services.commit_engine.engine import CommitEngine
from services.commit_engine.store import CommitStore
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from services.review_pipeline.operators.embedding import StubEmbeddingModel
from services.review_pipeline.pipeline import ReviewPipelineConfig


@pytest.fixture
async def e2e_client(tmp_path: Path):
    config = StorageConfig(
        deployment_mode="local",
        lancedb_path=str(tmp_path / "lance"),
        neo4j_password="",
    )
    storage = StorageManager(config)
    deps = Dependencies(config=config)
    deps.storage = storage
    deps.search_engine = SearchEngine(storage)
    deps.commit_engine = CommitEngine(
        storage=storage,
        commit_store=CommitStore(str(tmp_path / "commits")),
        search_engine=deps.search_engine,
    )
    deps.job_manager = JobManager(store=InMemoryJobStore())
    deps.review_pipeline_config = ReviewPipelineConfig(
        embedding_model=StubEmbeddingModel(dim=128),
    )

    app = create_app(dependencies=deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await storage.close()


async def test_batch_commit_e2e(e2e_client):
    """Submit batch → auto review/merge → check results."""
    resp = await e2e_client.post("/commits/batch", json={
        "commits": [
            {
                "message": "paper 1",
                "operations": [{
                    "op": "add_edge",
                    "tail": [{"content": "premise A"}],
                    "head": [{"content": "conclusion B"}],
                    "type": "paper-extract",
                    "reasoning": [{"title": "r", "content": "because"}],
                }],
            },
        ],
        "auto_review": True,
        "auto_merge": True,
    })
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    # Wait for completion
    for _ in range(20):
        await asyncio.sleep(0.1)
        status = await e2e_client.get(f"/jobs/{job_id}")
        if status.json()["status"] in ("completed", "failed"):
            break

    result = await e2e_client.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200


async def test_batch_read_nodes_e2e(e2e_client):
    resp = await e2e_client.post("/nodes/batch", json={"node_ids": [1, 2]})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.2)
    result = await e2e_client.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200
```

**Step 2: Run integration test**

Run: `pytest tests/integration/test_batch_e2e.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/integration/test_batch_e2e.py
git commit -m "test: add batch API end-to-end integration tests"
```
