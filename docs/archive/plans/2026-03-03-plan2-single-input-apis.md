# Plan 2: Single-Input API Layer

> **Status:** SUPERSEDED — Job infra (Tasks 1-2, 5) moved to Plan A; remaining tasks (async review, search embedding, enhanced read) to be re-planned as Plan B

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the v3 single-input APIs: async review with job management, updated commit/merge, search without external embedding, and enhanced read routes.

**Architecture:** A `JobManager` handles async job lifecycle (submit/cancel/status/result). Review route submits a background pipeline job. Search generates embeddings internally via the same `EmbeddingModel`. Merge persists review pipeline results (embeddings, beliefs, abstraction edges).

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, asyncio, review_pipeline from Plan 1

**Depends on:** Plan 1 (Operator Layer) must be completed first.

---

### Task 1: Job Manager — Model + Store

**Files:**
- Create: `services/job_manager/__init__.py`
- Create: `services/job_manager/models.py`
- Create: `services/job_manager/store.py`
- Test: `tests/services/test_job_manager/__init__.py`
- Test: `tests/services/test_job_manager/test_models.py`
- Test: `tests/services/test_job_manager/test_store.py`

**Step 1: Write the failing test**

```python
# tests/services/test_job_manager/test_models.py
from services.job_manager.models import Job, JobStatus, JobType


def test_job_creation():
    job = Job(job_type=JobType.REVIEW, reference_id="commit_abc123")
    assert job.status == JobStatus.PENDING
    assert job.job_id.startswith("job_")
    assert job.reference_id == "commit_abc123"
    assert job.progress == {}
    assert job.result is None


def test_job_status_transitions():
    job = Job(job_type=JobType.REVIEW, reference_id="x")
    job.status = JobStatus.RUNNING
    assert job.status == JobStatus.RUNNING
    job.status = JobStatus.COMPLETED
    assert job.status == JobStatus.COMPLETED
```

```python
# tests/services/test_job_manager/test_store.py
import pytest
from services.job_manager.models import Job, JobType
from services.job_manager.store import InMemoryJobStore


@pytest.fixture
def store():
    return InMemoryJobStore()


async def test_save_and_get(store):
    job = Job(job_type=JobType.REVIEW, reference_id="c1")
    await store.save(job)
    loaded = await store.get(job.job_id)
    assert loaded is not None
    assert loaded.job_id == job.job_id


async def test_get_missing_returns_none(store):
    assert await store.get("nonexistent") is None


async def test_update(store):
    job = Job(job_type=JobType.REVIEW, reference_id="c1")
    await store.save(job)
    job.status = "running"
    await store.update(job)
    loaded = await store.get(job.job_id)
    assert loaded.status == "running"


async def test_get_by_reference(store):
    job = Job(job_type=JobType.REVIEW, reference_id="commit_abc")
    await store.save(job)
    loaded = await store.get_by_reference("commit_abc", JobType.REVIEW)
    assert loaded is not None
    assert loaded.job_id == job.job_id
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_job_manager/ -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# services/job_manager/__init__.py
"""Job management for async operations."""

# services/job_manager/models.py
"""Job data models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(StrEnum):
    REVIEW = "review"
    BATCH_COMMIT = "batch_commit"
    BATCH_SEARCH = "batch_search"
    BATCH_READ = "batch_read"


class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}")
    job_type: JobType
    reference_id: str  # e.g. commit_id for review jobs
    status: JobStatus = JobStatus.PENDING
    progress: dict = {}
    result: dict | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# services/job_manager/store.py
"""Job persistence — in-memory for Phase 1."""

from __future__ import annotations

from services.job_manager.models import Job, JobType


class InMemoryJobStore:
    """Thread-safe in-memory job store."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    async def save(self, job: Job) -> None:
        self._jobs[job.job_id] = job

    async def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def update(self, job: Job) -> None:
        self._jobs[job.job_id] = job

    async def get_by_reference(
        self, reference_id: str, job_type: JobType
    ) -> Job | None:
        for job in self._jobs.values():
            if job.reference_id == reference_id and job.job_type == job_type:
                return job
        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_job_manager/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/job_manager/ tests/services/test_job_manager/
git commit -m "feat: add Job model and InMemoryJobStore"
```

---

### Task 2: JobManager — Orchestrator

**Files:**
- Create: `services/job_manager/manager.py`
- Test: `tests/services/test_job_manager/test_manager.py`

**Step 1: Write the failing test**

```python
# tests/services/test_job_manager/test_manager.py
import pytest
import asyncio
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from services.job_manager.models import JobStatus, JobType


@pytest.fixture
def manager():
    return JobManager(store=InMemoryJobStore())


async def test_submit_job(manager):
    async def work(job_id: str):
        return {"answer": 42}

    job = await manager.submit(
        job_type=JobType.REVIEW,
        reference_id="commit_1",
        work_fn=work,
    )
    assert job.status == JobStatus.RUNNING
    # Wait for background task
    await asyncio.sleep(0.1)
    result = await manager.get_result(job.job_id)
    assert result == {"answer": 42}


async def test_cancel_job(manager):
    async def slow_work(job_id: str):
        await asyncio.sleep(10)
        return {}

    job = await manager.submit(
        job_type=JobType.REVIEW,
        reference_id="commit_2",
        work_fn=slow_work,
    )
    cancelled = await manager.cancel(job.job_id)
    assert cancelled is True
    loaded = await manager.get_status(job.job_id)
    assert loaded.status == JobStatus.CANCELLED


async def test_get_status(manager):
    async def work(job_id: str):
        return {"done": True}

    job = await manager.submit(
        job_type=JobType.REVIEW,
        reference_id="c3",
        work_fn=work,
    )
    status = await manager.get_status(job.job_id)
    assert status is not None


async def test_failed_job(manager):
    async def failing_work(job_id: str):
        raise ValueError("something broke")

    job = await manager.submit(
        job_type=JobType.REVIEW,
        reference_id="c4",
        work_fn=failing_work,
    )
    await asyncio.sleep(0.1)
    loaded = await manager.get_status(job.job_id)
    assert loaded.status == JobStatus.FAILED
    assert "something broke" in loaded.error
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_job_manager/test_manager.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# services/job_manager/manager.py
"""JobManager — submit, cancel, and track async jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

from services.job_manager.models import Job, JobStatus, JobType
from services.job_manager.store import InMemoryJobStore


class JobManager:
    """Manages async job lifecycle."""

    def __init__(self, store: InMemoryJobStore | None = None) -> None:
        self._store = store or InMemoryJobStore()
        self._tasks: dict[str, asyncio.Task] = {}

    async def submit(
        self,
        job_type: JobType,
        reference_id: str,
        work_fn: Callable[[str], Coroutine[Any, Any, dict]],
    ) -> Job:
        """Submit an async job. work_fn receives job_id and returns result dict."""
        job = Job(job_type=job_type, reference_id=reference_id)
        job.status = JobStatus.RUNNING
        await self._store.save(job)

        task = asyncio.create_task(self._run(job.job_id, work_fn))
        self._tasks[job.job_id] = task
        return job

    async def _run(
        self,
        job_id: str,
        work_fn: Callable[[str], Coroutine[Any, Any, dict]],
    ) -> None:
        job = await self._store.get(job_id)
        if not job:
            return
        try:
            result = await work_fn(job_id)
            job.status = JobStatus.COMPLETED
            job.result = result
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
        job.updated_at = datetime.now(timezone.utc)
        await self._store.update(job)
        self._tasks.pop(job_id, None)

    async def cancel(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            job = await self._store.get(job_id)
            if job:
                job.status = JobStatus.CANCELLED
                job.updated_at = datetime.now(timezone.utc)
                await self._store.update(job)
            return True
        return False

    async def get_status(self, job_id: str) -> Job | None:
        return await self._store.get(job_id)

    async def get_result(self, job_id: str) -> dict | None:
        job = await self._store.get(job_id)
        if job and job.status == JobStatus.COMPLETED:
            return job.result
        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_job_manager/test_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/job_manager/manager.py tests/services/test_job_manager/test_manager.py
git commit -m "feat: add JobManager for async job lifecycle"
```

---

### Task 3: Refactor Review Route to Async Job

**Files:**
- Modify: `services/gateway/routes/commits.py`
- Modify: `services/gateway/deps.py`
- Test: `tests/services/test_gateway/test_commits.py` (update existing)

**Step 1: Write the failing test**

```python
# tests/services/test_gateway/test_review_async.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from libs.models import Commit


@pytest.fixture
def test_deps():
    deps = Dependencies()
    deps.storage = MagicMock()
    deps.storage.graph = None
    deps.storage.vector = AsyncMock()
    deps.search_engine = MagicMock()
    deps.commit_engine = MagicMock()
    deps.commit_engine.get_commit = AsyncMock(
        return_value=Commit(
            commit_id="test123",
            message="test",
            operations=[],
            status="pending_review",
        )
    )
    deps.job_manager = JobManager(store=InMemoryJobStore())
    deps.review_pipeline_config = MagicMock()
    return deps


@pytest.fixture
async def client(test_deps):
    app = create_app(dependencies=test_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_submit_review_returns_job_id(client):
    resp = await client.post("/commits/test123/review", json={"depth": "standard"})
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "running"


async def test_get_review_status(client):
    # Submit first
    resp = await client.post("/commits/test123/review", json={"depth": "standard"})
    job_id = resp.json()["job_id"]
    # Check status
    resp = await client.get("/commits/test123/review")
    assert resp.status_code == 200
    assert "status" in resp.json()


async def test_delete_review_cancels(client):
    resp = await client.post("/commits/test123/review", json={"depth": "standard"})
    resp = await client.delete("/commits/test123/review")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_review_not_found(client):
    deps = client._transport.app  # noqa
    # Override to return None
    from services.gateway.deps import deps as global_deps
    global_deps.commit_engine.get_commit = AsyncMock(return_value=None)
    resp = await client.post("/commits/nonexistent/review", json={})
    assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_review_async.py -v`
Expected: FAIL

**Step 3: Update deps.py to include JobManager and ReviewPipelineConfig**

```python
# services/gateway/deps.py — updated
"""Dependency injection — singleton services created at startup."""

from __future__ import annotations

from libs.storage import StorageConfig, StorageManager
from services.search_engine.engine import SearchEngine
from services.commit_engine.engine import CommitEngine
from services.commit_engine.store import CommitStore
from services.inference_engine.engine import InferenceEngine
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from services.review_pipeline.operators.embedding import StubEmbeddingModel
from services.review_pipeline.pipeline import ReviewPipelineConfig


class Dependencies:
    """Holds all service singletons."""

    def __init__(self, config: StorageConfig | None = None):
        self.config = config or StorageConfig()
        self.storage: StorageManager | None = None
        self.search_engine: SearchEngine | None = None
        self.commit_engine: CommitEngine | None = None
        self.inference_engine: InferenceEngine | None = None
        self.job_manager: JobManager | None = None
        self.review_pipeline_config: ReviewPipelineConfig | None = None

    def initialize(self, storage_config: StorageConfig | None = None):
        """Create all services. Call once at startup."""
        config = storage_config or self.config
        self.storage = StorageManager(config)
        self.search_engine = SearchEngine(self.storage)
        commit_store = CommitStore(storage_path=config.lancedb_path + "/commits")
        self.commit_engine = CommitEngine(
            storage=self.storage,
            commit_store=commit_store,
            search_engine=self.search_engine,
        )
        self.inference_engine = InferenceEngine(self.storage)
        self.job_manager = JobManager(store=InMemoryJobStore())
        self.review_pipeline_config = ReviewPipelineConfig(
            embedding_model=StubEmbeddingModel(dim=1024),
        )

    async def cleanup(self):
        """Shut down services gracefully."""
        if self.storage:
            await self.storage.close()


# Global instance
deps = Dependencies()
```

**Step 4: Update commits route**

```python
# services/gateway/routes/commits.py — updated
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from libs.models import CommitRequest, CommitResponse, MergeResult
from services.gateway.deps import deps
from services.job_manager.models import JobType
from services.review_pipeline.context import PipelineContext
from services.review_pipeline.pipeline import build_review_pipeline

router = APIRouter(prefix="/commits", tags=["commits"])


class ReviewRequest(BaseModel):
    depth: str = "standard"


class MergeRequest(BaseModel):
    force: bool = False


@router.post("", response_model=CommitResponse)
async def submit_commit(request: CommitRequest):
    return await deps.commit_engine.submit(request)


@router.get("/{commit_id}")
async def get_commit(commit_id: str):
    commit = await deps.commit_engine.get_commit(commit_id)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    return commit.model_dump()


@router.post("/{commit_id}/review")
async def submit_review(commit_id: str, request: ReviewRequest = ReviewRequest()):
    commit = await deps.commit_engine.get_commit(commit_id)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    async def run_review(job_id: str) -> dict:
        pipeline = build_review_pipeline(deps.review_pipeline_config, deps.storage)
        ctx = PipelineContext.from_commit_request(
            CommitRequest(message=commit.message, operations=commit.operations)
        )
        result = await pipeline.execute(ctx)
        return {
            "bp_results": result.bp_results,
            "verified_trees": [t.model_dump() for t in result.verified_trees],
            "embeddings_count": len(result.embeddings),
        }

    job = await deps.job_manager.submit(
        job_type=JobType.REVIEW,
        reference_id=commit_id,
        work_fn=run_review,
    )
    return {"job_id": job.job_id, "status": job.status}


@router.get("/{commit_id}/review")
async def get_review_status(commit_id: str):
    job = await deps.job_manager._store.get_by_reference(commit_id, JobType.REVIEW)
    if not job:
        raise HTTPException(status_code=404, detail="No review job for this commit")
    return {"job_id": job.job_id, "status": job.status, "progress": job.progress}


@router.delete("/{commit_id}/review")
async def cancel_review(commit_id: str):
    job = await deps.job_manager._store.get_by_reference(commit_id, JobType.REVIEW)
    if not job:
        raise HTTPException(status_code=404, detail="No review job for this commit")
    await deps.job_manager.cancel(job.job_id)
    return {"job_id": job.job_id, "status": "cancelled"}


@router.get("/{commit_id}/review/result")
async def get_review_result(commit_id: str):
    job = await deps.job_manager._store.get_by_reference(commit_id, JobType.REVIEW)
    if not job:
        raise HTTPException(status_code=404, detail="No review job for this commit")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail=f"Review status is {job.status}")
    return {"job_id": job.job_id, "status": job.status, "review_results": job.result}


@router.post("/{commit_id}/merge", response_model=MergeResult)
async def merge_commit(commit_id: str, request: MergeRequest = MergeRequest()):
    commit = await deps.commit_engine.get_commit(commit_id)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    return await deps.commit_engine.merge(commit_id, force=request.force)
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/services/test_gateway/test_review_async.py -v`
Expected: PASS

**Step 6: Run existing tests to ensure no regression**

Run: `pytest tests/ -v --ignore=tests/services/test_gateway/test_review_async.py`
Expected: existing tests still PASS (may need minor fixture updates)

**Step 7: Commit**

```bash
git add services/gateway/routes/commits.py services/gateway/deps.py tests/services/test_gateway/test_review_async.py
git commit -m "feat: refactor review to async job with pipeline execution"
```

---

### Task 4: Update Search to Generate Embeddings Internally

**Files:**
- Modify: `services/search_engine/engine.py`
- Modify: `services/gateway/routes/search.py`
- Test: `tests/services/test_gateway/test_search_v3.py`

**Step 1: Write the failing test**

```python
# tests/services/test_gateway/test_search_v3.py
import pytest
from services.search_engine.engine import SearchEngine
from services.review_pipeline.operators.embedding import EmbeddingModel


async def test_search_engine_accepts_text_only():
    """SearchEngine.search_nodes should work with text only (no embedding param)."""
    from unittest.mock import MagicMock, AsyncMock
    from services.review_pipeline.operators.embedding import StubEmbeddingModel

    storage = MagicMock()
    storage.vector = AsyncMock()
    storage.vector.search = AsyncMock(return_value=[])
    storage.lance = MagicMock()
    storage.lance.fts_search = AsyncMock(return_value=[])
    storage.graph = None

    engine = SearchEngine(storage, embedding_model=StubEmbeddingModel(dim=128))
    results = await engine.search_nodes(query="test query", k=10)
    assert isinstance(results, list)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_search_v3.py -v`
Expected: FAIL — SearchEngine doesn't accept embedding_model

**Step 3: Update SearchEngine**

Add `embedding_model` parameter to `SearchEngine.__init__`. When `embedding` is not provided to `search_nodes`, generate it internally.

Modify `services/search_engine/engine.py`:
- Add `embedding_model: EmbeddingModel | None = None` to `__init__`
- In `search_nodes`, make `embedding` optional — if not provided, generate via model
- Same for `search_edges`

Modify `services/gateway/routes/search.py`:
- Change `SearchNodesRequest.embedding` from required to optional
- Change request field `embedding: list[float]` to `embedding: list[float] | None = None`

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_gateway/test_search_v3.py -v`
Expected: PASS

**Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: PASS

**Step 6: Commit**

```bash
git add services/search_engine/engine.py services/gateway/routes/search.py tests/services/test_gateway/test_search_v3.py
git commit -m "feat: search generates embeddings internally, external embedding optional"
```

---

### Task 5: Job Management Routes

**Files:**
- Create: `services/gateway/routes/jobs.py`
- Modify: `services/gateway/app.py` (register new router)
- Test: `tests/services/test_gateway/test_jobs.py`

**Step 1: Write the failing test**

```python
# tests/services/test_gateway/test_jobs.py
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from services.job_manager.models import JobType


@pytest.fixture
def test_deps():
    deps = Dependencies()
    deps.storage = MagicMock()
    deps.storage.graph = None
    deps.storage.vector = AsyncMock()
    deps.search_engine = MagicMock()
    deps.commit_engine = MagicMock()
    deps.job_manager = JobManager(store=InMemoryJobStore())
    deps.review_pipeline_config = MagicMock()
    return deps


@pytest.fixture
async def client(test_deps):
    app = create_app(dependencies=test_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_get_job_status(client, test_deps):
    async def work(job_id):
        return {"done": True}

    job = await test_deps.job_manager.submit(
        JobType.REVIEW, "ref1", work
    )
    await asyncio.sleep(0.1)
    resp = await client.get(f"/jobs/{job.job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


async def test_get_job_result(client, test_deps):
    async def work(job_id):
        return {"answer": 42}

    job = await test_deps.job_manager.submit(
        JobType.REVIEW, "ref2", work
    )
    await asyncio.sleep(0.1)
    resp = await client.get(f"/jobs/{job.job_id}/result")
    assert resp.status_code == 200
    assert resp.json()["result"] == {"answer": 42}


async def test_delete_job(client, test_deps):
    async def slow(job_id):
        await asyncio.sleep(10)

    job = await test_deps.job_manager.submit(
        JobType.REVIEW, "ref3", slow
    )
    resp = await client.delete(f"/jobs/{job.job_id}")
    assert resp.status_code == 200


async def test_get_nonexistent_job(client):
    resp = await client.get("/jobs/nonexistent")
    assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_jobs.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# services/gateway/routes/jobs.py
"""Job management routes — GET/DELETE /jobs/{job_id}."""

from fastapi import APIRouter, HTTPException
from services.gateway.deps import deps

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job_status(job_id: str):
    job = await deps.job_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.job_id,
        "type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


@router.get("/{job_id}/result")
async def get_job_result(job_id: str):
    job = await deps.job_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(
            status_code=409, detail=f"Job status is {job.status}, not completed"
        )
    return {"job_id": job.job_id, "status": job.status, "result": job.result}


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    job = await deps.job_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await deps.job_manager.cancel(job_id)
    return {"job_id": job.job_id, "status": "cancelled"}
```

Register in app.py — add `from .routes.jobs import router as jobs_router` and `app.include_router(jobs_router)`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_gateway/test_jobs.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/gateway/routes/jobs.py services/gateway/app.py tests/services/test_gateway/test_jobs.py
git commit -m "feat: add /jobs API routes for job status, result, and cancellation"
```

---

### Task 6: Enhanced Read Routes (subgraph params)

**Files:**
- Modify: `services/gateway/routes/read.py`
- Test: `tests/services/test_gateway/test_read_v3.py`

**Step 1: Write the failing test**

```python
# tests/services/test_gateway/test_read_v3.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from libs.models import Node


@pytest.fixture
def test_deps():
    deps = Dependencies()
    deps.storage = MagicMock()
    deps.storage.lance = MagicMock()
    deps.storage.lance.load_node = AsyncMock(
        return_value=Node(id=1, type="paper-extract", content="test")
    )
    deps.storage.graph = MagicMock()
    deps.storage.graph.get_subgraph = AsyncMock(return_value=({1, 2}, {10}))
    deps.storage.graph.get_hyperedge = AsyncMock(return_value=None)
    deps.storage.lance.load_nodes_bulk = AsyncMock(
        return_value=[Node(id=1, type="paper-extract", content="a")]
    )
    deps.search_engine = MagicMock()
    deps.commit_engine = MagicMock()
    deps.job_manager = MagicMock()
    deps.review_pipeline_config = MagicMock()
    return deps


@pytest.fixture
async def client(test_deps):
    app = create_app(dependencies=test_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_subgraph_with_direction(client):
    resp = await client.get("/nodes/1/subgraph?hops=2&direction=upstream&max_nodes=100")
    assert resp.status_code == 200


async def test_subgraph_with_edge_types(client):
    resp = await client.get("/nodes/1/subgraph?hops=1&edge_types=paper-extract,abstraction")
    assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_read_v3.py -v`
Expected: FAIL — new params not supported

**Step 3: Update read route**

Add `direction`, `max_nodes`, `edge_types` query params to `/nodes/{id}/subgraph`. Pass `edge_types` to `get_subgraph()`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_gateway/test_read_v3.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/gateway/routes/read.py tests/services/test_gateway/test_read_v3.py
git commit -m "feat: add direction, max_nodes, edge_types params to subgraph route"
```

---

### Task 7: Update app.py Dependencies Wiring

**Files:**
- Modify: `services/gateway/app.py`

**Step 1: Verify app.py includes all new routers and deps**

Ensure `create_app` propagates `job_manager` and `review_pipeline_config` when custom dependencies are injected.

**Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add services/gateway/app.py services/gateway/deps.py
git commit -m "feat: wire JobManager and ReviewPipelineConfig into app dependencies"
```
