# Plan C: Batch APIs + Storage Test Enhancement

> **Status:** ACTIVE (not started)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** (1) Add batch (async) variants for all APIs: batch commit, batch search, batch read. (2) Enhance storage layer tests to use shared fixture data instead of ad-hoc synthetic data.

**Issues:** #9, #10, #11, #22

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, JobManager (already implemented), pytest, asyncio, LanceDB

**Depends on:** Plan A (Job infrastructure) + Plan B (embedding internalization, async review) -- both completed.

**Architecture:** All batch endpoints return a `job_id` immediately. The `JobManager` runs the work in the background. Each batch endpoint wraps the corresponding single-input logic in a loop. Storage tests reuse the shared `storage` fixture from `tests/conftest.py` with real fixture data.

---

## Part 1: Storage Test Enhancement (Issue #22)

### Task 1: Enhance LanceStore tests with fixture data

**Files:**
- Modify: `tests/libs/storage/test_lance_store.py`

**Current state:** 7 tests using `_make_node()` helper with ad-hoc data like `"DFT predicts fcc YH10 stable"`.

**Step 1: Read the current test file and conftest.py fixtures**

Read `tests/libs/storage/test_lance_store.py` and `tests/conftest.py` to understand current patterns.

**Step 2: Add fixture-data tests alongside existing tests**

Keep existing tests (they test basic CRUD with clean state). Add new tests that use fixture data for more realistic coverage.

```python
# Add at top of file
from tests.conftest import load_fixture_nodes


@pytest.fixture
async def seeded_store(tmp_path):
    """LanceStore pre-seeded with fixture nodes."""
    s = LanceStore(db_path=str(tmp_path / "lance"))
    nodes = load_fixture_nodes()
    await s.save_nodes(nodes)
    yield s
    await s.close()


async def test_load_fixture_node(seeded_store):
    """Load a real fixture node and verify content."""
    nodes = load_fixture_nodes()
    first = nodes[0]
    loaded = await seeded_store.load_node(first.id)
    assert loaded is not None
    assert loaded.content == first.content
    assert loaded.type == first.type


async def test_bulk_load_fixture_nodes(seeded_store):
    """Bulk load fixture nodes and verify count."""
    nodes = load_fixture_nodes()
    ids = [n.id for n in nodes]
    loaded = await seeded_store.load_nodes_bulk(ids)
    assert len(loaded) == len(nodes)


async def test_fts_search_fixture_content(seeded_store):
    """FTS search should find fixture nodes by real content keywords."""
    results = await seeded_store.fts_search("superconductor", k=10)
    assert len(results) >= 1
    # Results should be real fixture node IDs
    node_ids = [r[0] for r in results]
    fixture_ids = {n.id for n in load_fixture_nodes()}
    assert all(nid in fixture_ids for nid in node_ids)


async def test_update_beliefs_fixture_nodes(seeded_store):
    """Update beliefs on fixture nodes and verify persistence."""
    nodes = load_fixture_nodes()
    belief_map = {nodes[0].id: 0.95, nodes[1].id: 0.3}
    await seeded_store.update_beliefs(belief_map)
    beliefs = await seeded_store.get_beliefs_bulk(list(belief_map.keys()))
    for nid, expected in belief_map.items():
        assert beliefs[nid] == pytest.approx(expected)
```

**Step 3: Run tests**

Run: `pytest tests/libs/storage/test_lance_store.py -v`
Expected: ALL PASS (7 old + 4 new = 11 tests)

**Step 4: Commit**

```bash
git add tests/libs/storage/test_lance_store.py
git commit -m "test: enhance LanceStore tests with fixture data (#22)"
```

---

### Task 2: Enhance VectorSearch tests with fixture data

**Files:**
- Modify: `tests/libs/storage/test_vector_search.py`

**Current state:** 3 tests using `_random_embedding()` with random numpy vectors.

**Step 1: Read the current test file**

**Step 2: Add fixture-data tests**

Keep existing random-vector tests (they test basic insert/search mechanics). Add new tests that use deterministic StubEmbeddingModel vectors matching the conftest.py seeding approach.

```python
# Add at top of file
from libs.embedding import StubEmbeddingModel
from tests.conftest import load_fixture_nodes

_embedding_model = StubEmbeddingModel()


@pytest.fixture
async def seeded_client(tmp_path):
    """Vector client pre-seeded with fixture node embeddings."""
    config = StorageConfig(lancedb_path=str(tmp_path / "lance_vec"))
    c = create_vector_client(config)
    nodes = load_fixture_nodes()
    texts = [n.content if isinstance(n.content, str) else str(n.content) for n in nodes]
    vectors = await _embedding_model.embed(texts)
    node_ids = [n.id for n in nodes]
    await c.insert_batch(node_ids, vectors)
    return c


async def test_search_finds_similar_fixture_nodes(seeded_client):
    """Search with a fixture node's embedding should return that node first."""
    nodes = load_fixture_nodes()
    query_text = nodes[0].content if isinstance(nodes[0].content, str) else str(nodes[0].content)
    query_vec = (await _embedding_model.embed([query_text]))[0]
    results = await seeded_client.search(query_vec, k=5)
    assert len(results) >= 1
    assert results[0][0] == nodes[0].id  # exact match first


async def test_search_batch_fixture_nodes(seeded_client):
    """Batch search with fixture embeddings returns correct matches."""
    nodes = load_fixture_nodes()
    texts = [
        nodes[0].content if isinstance(nodes[0].content, str) else str(nodes[0].content),
        nodes[1].content if isinstance(nodes[1].content, str) else str(nodes[1].content),
    ]
    vecs = await _embedding_model.embed(texts)
    results = await seeded_client.search_batch(vecs, k=3)
    assert len(results) == 2
    assert results[0][0][0] == nodes[0].id
    assert results[1][0][0] == nodes[1].id
```

**Step 3: Run tests**

Run: `pytest tests/libs/storage/test_vector_search.py -v`
Expected: ALL PASS (3 old + 2 new = 5 tests)

**Step 4: Commit**

```bash
git add tests/libs/storage/test_vector_search.py
git commit -m "test: enhance VectorSearch tests with fixture data (#22)"
```

---

### Task 3: Enhance StorageManager tests with fixture data

**Files:**
- Modify: `tests/libs/storage/test_manager.py`

**Current state:** 3 tests creating minimal synthetic data.

**Step 1: Add fixture-seeded StorageManager tests**

```python
from tests.conftest import load_fixture_nodes


async def test_manager_with_fixture_data(tmp_path):
    """StorageManager can ingest and retrieve fixture nodes."""
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    manager = StorageManager(config)

    nodes = load_fixture_nodes()
    await manager.lance.save_nodes(nodes)

    # Verify nodes are retrievable
    loaded = await manager.lance.load_node(nodes[0].id)
    assert loaded is not None
    assert loaded.content == nodes[0].content

    # Verify bulk load
    ids = [n.id for n in nodes[:5]]
    bulk = await manager.lance.load_nodes_bulk(ids)
    assert len(bulk) == 5

    await manager.close()
```

**Step 2: Run tests**

Run: `pytest tests/libs/storage/test_manager.py -v`
Expected: ALL PASS (3 old + 1 new = 4 tests)

**Step 3: Commit**

```bash
git add tests/libs/storage/test_manager.py
git commit -m "test: enhance StorageManager tests with fixture data (#22)"
```

---

### Task 4: Enhance Neo4j tests with fixture data (optional, CI-only)

**Files:**
- Modify: `tests/libs/storage/test_neo4j_store.py`

**Current state:** 7 tests using `_edge()` helper with ad-hoc node IDs like `[10, 11, 12]`.

**Step 1: Add fixture-data tests**

```python
from tests.conftest import load_fixture_edges


async def test_create_fixture_edges(store):
    """Create real fixture edges and verify topology."""
    edges = load_fixture_edges()
    for edge in edges:
        await store.create_hyperedge(edge)

    # Verify first edge
    loaded = await store.get_hyperedge(edges[0].id)
    assert loaded is not None
    assert set(loaded.tail) == set(edges[0].tail)
    assert set(loaded.head) == set(edges[0].head)


async def test_subgraph_with_fixture_topology(store):
    """Subgraph traversal over real fixture edge topology."""
    edges = load_fixture_edges()
    for edge in edges:
        await store.create_hyperedge(edge)

    # Pick a tail node from the first edge and traverse
    seed = edges[0].tail[0]
    node_ids, edge_ids = await store.get_subgraph([seed], hops=2)
    assert seed in node_ids
    assert edges[0].id in edge_ids
    # Should discover connected nodes beyond hop 1
    assert len(node_ids) > 1
```

**Step 2: Run tests** (requires Neo4j)

Run: `pytest tests/libs/storage/test_neo4j_store.py -v`
Expected: ALL PASS (7 old + 2 new = 9 tests), or SKIP if no Neo4j

**Step 3: Commit**

```bash
git add tests/libs/storage/test_neo4j_store.py
git commit -m "test: enhance Neo4j tests with fixture data (#22)"
```

---

### Task 5: Verify and close #22

Run full test suite and lint:

```bash
pytest tests/ -v
ruff check . && ruff format --check .
```

Expected: ALL PASS. Close issue #22.

---

## Part 2: Batch APIs (Issues #9, #10, #11)

### Task 6: Batch routes module + batch commit endpoint (Issue #9)

**Files:**
- Create: `services/gateway/routes/batch.py`
- Modify: `services/gateway/app.py` (register router)
- Test: `tests/services/test_gateway/test_batch.py`

**Step 1: Write the failing test**

```python
# tests/services/test_gateway/test_batch.py
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from libs.models import CommitResponse, MergeResult


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
    d.commit_engine.merge = AsyncMock(
        return_value=MergeResult(success=True, new_node_ids=["1"], new_edge_ids=["10"])
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


async def test_batch_commit_result(client):
    resp = await client.post("/commits/batch", json={
        "commits": [{"message": "paper 1", "operations": []}],
        "auto_review": True,
        "auto_merge": True,
    })
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)

    resp = await client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert "commits" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_batch.py -v`
Expected: FAIL (no batch route)

**Step 3: Write implementation**

```python
# services/gateway/routes/batch.py
"""Batch API routes -- all async via JobManager."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from libs.models import CommitRequest
from services.gateway.deps import deps
from services.job_manager.models import JobType

router = APIRouter(tags=["batch"])


# -- Batch Commit (#9) -------------------------------------------------------


class BatchCommitRequest(BaseModel):
    commits: list[CommitRequest]
    auto_review: bool = True
    auto_merge: bool = True


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
                job = await deps.commit_engine.submit_review(commit_resp.commit_id)
                # Wait for review to finish (within batch context)
                import asyncio
                for _ in range(100):
                    status = await deps.commit_engine.job_manager.get_status(job.job_id)
                    if status.status.value in ("completed", "failed"):
                        break
                    await asyncio.sleep(0.05)

                review_result = await deps.commit_engine.job_manager.get_result(job.job_id)
                approved = (
                    review_result.get("overall_verdict") == "pass"
                    if isinstance(review_result, dict)
                    else False
                )
                entry["status"] = "reviewed" if approved else "rejected"

                if approved and request.auto_merge:
                    merge_result = await deps.commit_engine.merge(commit_resp.commit_id)
                    entry["status"] = "merged" if merge_result.success else "merge_failed"
                    entry["merge_result"] = merge_result.model_dump()

            results.append(entry)
        return {"commits": results, "total": len(results)}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_COMMIT,
        reference_id=f"batch_{len(request.commits)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "total_commits": len(request.commits), "status": job.status}
```

Register in `services/gateway/app.py`:

```python
from .routes.batch import router as batch_router
# ...
app.include_router(batch_router)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_gateway/test_batch.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/gateway/routes/batch.py services/gateway/app.py tests/services/test_gateway/test_batch.py
git commit -m "feat: add batch commit API with async job execution

Closes #9"
```

---

### Task 7: Batch read endpoints (Issue #10)

**Files:**
- Modify: `services/gateway/routes/batch.py`
- Modify: `tests/services/test_gateway/test_batch.py`

**Step 1: Write the failing tests**

Add to `tests/services/test_gateway/test_batch.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_batch.py::test_batch_read_nodes -v`
Expected: FAIL

**Step 3: Write implementation**

Add to `services/gateway/routes/batch.py`:

```python
# -- Batch Read Nodes (#10) ---------------------------------------------------


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


# -- Batch Read Hyperedges (#10) ----------------------------------------------


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


# -- Batch Subgraph (#10) -----------------------------------------------------


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
                [q.node_id], hops=q.hops, direction=q.direction,
            )
            results.append({
                "center_node_id": q.node_id,
                "node_ids": sorted(node_ids),
                "edge_ids": sorted(edge_ids),
            })
        return {"subgraphs": results}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_READ,
        reference_id=f"subgraph_batch_{len(request.queries)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}
```

**Step 4: Run tests**

Run: `pytest tests/services/test_gateway/test_batch.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/gateway/routes/batch.py tests/services/test_gateway/test_batch.py
git commit -m "feat: add batch read APIs (nodes, hyperedges, subgraph)

Closes #10"
```

---

### Task 8: Batch search endpoints (Issue #11)

**Files:**
- Modify: `services/gateway/routes/batch.py`
- Modify: `tests/services/test_gateway/test_batch.py`

**Step 1: Write the failing tests**

Add to `tests/services/test_gateway/test_batch.py`:

```python
async def test_batch_search_nodes(client, deps):
    deps.search_engine.search_nodes = AsyncMock(return_value=[])
    resp = await client.post("/search/nodes/batch", json={
        "queries": [
            {"text": "superconductor", "top_k": 10},
            {"text": "hydride", "top_k": 5},
        ]
    })
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_search_edges(client, deps):
    deps.search_engine.search_edges = AsyncMock(return_value=[])
    resp = await client.post("/search/hyperedges/batch", json={
        "queries": [{"text": "synthesis route"}]
    })
    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_batch_search_nodes_result(client, deps):
    deps.search_engine.search_nodes = AsyncMock(return_value=[])
    resp = await client.post("/search/nodes/batch", json={
        "queries": [{"text": "q1"}]
    })
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)
    resp = await client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200
    assert "results" in resp.json()["result"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_batch.py::test_batch_search_nodes -v`
Expected: FAIL

**Step 3: Write implementation**

Add to `services/gateway/routes/batch.py`:

```python
# -- Batch Search Nodes (#11) -------------------------------------------------


class BatchSearchQuery(BaseModel):
    text: str
    top_k: int = 50


class BatchSearchNodesRequest(BaseModel):
    queries: list[BatchSearchQuery]


@router.post("/search/nodes/batch")
async def batch_search_nodes(request: BatchSearchNodesRequest):
    async def work(job_id: str) -> dict:
        results = []
        for q in request.queries:
            scored = await deps.search_engine.search_nodes(text=q.text, k=q.top_k)
            results.append([s.model_dump() for s in scored])
        return {"results": results, "total_queries": len(results)}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_SEARCH,
        reference_id=f"search_batch_{len(request.queries)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}


# -- Batch Search Hyperedges (#11) --------------------------------------------


class BatchSearchEdgesRequest(BaseModel):
    queries: list[BatchSearchQuery]


@router.post("/search/hyperedges/batch")
async def batch_search_edges(request: BatchSearchEdgesRequest):
    async def work(job_id: str) -> dict:
        results = []
        for q in request.queries:
            scored = await deps.search_engine.search_edges(text=q.text, k=q.top_k)
            results.append([s.model_dump() for s in scored])
        return {"results": results, "total_queries": len(results)}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_SEARCH,
        reference_id=f"edge_search_batch_{len(request.queries)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}
```

**Step 4: Run tests**

Run: `pytest tests/services/test_gateway/test_batch.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/gateway/routes/batch.py tests/services/test_gateway/test_batch.py
git commit -m "feat: add batch search APIs (nodes, hyperedges)

Closes #11"
```

---

### Task 9: Batch progress and cancel endpoints

**Files:**
- Modify: `services/gateway/routes/batch.py`
- Modify: `tests/services/test_gateway/test_batch.py`

**Step 1: Write the failing tests**

```python
async def test_get_batch_commit_progress(client):
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

**Step 2: Write implementation**

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

**Step 3: Run tests**

Run: `pytest tests/services/test_gateway/test_batch.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add services/gateway/routes/batch.py tests/services/test_gateway/test_batch.py
git commit -m "feat: add batch commit progress and cancel endpoints"
```

---

### Task 10: Batch E2E integration test

**Files:**
- Create: `tests/integration/test_batch_e2e.py`

**Step 1: Write integration test**

```python
# tests/integration/test_batch_e2e.py
"""End-to-end test for batch APIs using real LanceDB (no Neo4j)."""

import pytest
import asyncio
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from libs.embedding import StubEmbeddingModel
from libs.storage import StorageConfig, StorageManager
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.search_engine.engine import SearchEngine
from services.commit_engine.engine import CommitEngine
from services.commit_engine.store import CommitStore
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore


@pytest.fixture
async def e2e_client(tmp_path: Path):
    config = StorageConfig(
        deployment_mode="local",
        lancedb_path=str(tmp_path / "lance"),
        neo4j_password="",
    )
    storage = StorageManager(config)
    embedding_model = StubEmbeddingModel()

    d = Dependencies()
    d.storage = storage
    d.search_engine = SearchEngine(storage, embedding_model=embedding_model)
    d.commit_engine = CommitEngine(
        storage=storage,
        commit_store=CommitStore(storage_path=str(tmp_path / "commits")),
        search_engine=d.search_engine,
    )
    d.job_manager = JobManager(store=InMemoryJobStore())
    d.inference_engine = None

    app = create_app(dependencies=d)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await storage.close()


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
    resp = await e2e_client.post("/search/nodes/batch", json={
        "queries": [{"text": "superconductor", "top_k": 5}]
    })
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    await asyncio.sleep(0.3)
    result = await e2e_client.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200
    assert "results" in result.json()["result"]
```

**Step 2: Run integration test**

Run: `pytest tests/integration/test_batch_e2e.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_batch_e2e.py
git commit -m "test: add batch API E2E integration tests"
```

---

### Task 11: Full suite verification + lint

**Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected: ALL PASS

**Step 2: Lint**

```bash
ruff check . --fix
ruff format .
```

**Step 3: Commit if any fixes**

```bash
git add -A
git commit -m "chore: lint and format cleanup"
```

---

## Summary

| Task | Part | Issue | Scope |
|------|------|-------|-------|
| 1 | Storage Tests | #22 | Enhance LanceStore tests with fixture data |
| 2 | Storage Tests | #22 | Enhance VectorSearch tests with fixture data |
| 3 | Storage Tests | #22 | Enhance StorageManager tests with fixture data |
| 4 | Storage Tests | #22 | Enhance Neo4j tests with fixture data (CI-only) |
| 5 | Storage Tests | #22 | Verify and close #22 |
| 6 | Batch APIs | #9 | Batch commit endpoint |
| 7 | Batch APIs | #10 | Batch read endpoints (nodes, edges, subgraph) |
| 8 | Batch APIs | #11 | Batch search endpoints (nodes, edges) |
| 9 | Batch APIs | — | Batch progress + cancel |
| 10 | Batch APIs | — | E2E integration test |
| 11 | — | — | Full suite lint + verification |

**Estimated new endpoints:** 8 routes (`/commits/batch`, `/nodes/batch`, `/hyperedges/batch`, `/nodes/subgraph/batch`, `/search/nodes/batch`, `/search/hyperedges/batch`, `/commits/batch/{id}` GET/DELETE)

**Estimated new tests:** ~20 (storage: ~9, batch gateway: ~8, batch E2E: ~3)
