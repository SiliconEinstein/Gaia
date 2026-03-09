# Plan A: Foundation — Fixtures, Edge Type Rename, Job Infrastructure

> **Status:** ACTIVE

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Lay the groundwork for v3 by (1) creating shared test fixtures with real storage, (2) renaming join/meet edge types to abstraction/induction, (3) building the Job management infrastructure.

**Issues:** #17, #25, #5

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, asyncio, LanceDB, Neo4j (optional)

**Depends on:** Plan 1 (Operator Layer) — already completed.

---

### Task 1: Shared Fixture StorageManager (Issue #17)

**Files:**
- Modify: `tests/conftest.py`
- Test: self-validating (fixtures used by subsequent tasks)

**Step 1: Read existing fixtures to understand available data**

Read `tests/fixtures/nodes.json`, `tests/fixtures/edges.json` to understand the data shape. Check if `tests/fixtures/embeddings.json` exists (it's git-ignored but may exist locally).

**Step 2: Write conftest.py with shared fixtures**

```python
# tests/conftest.py
"""Shared test fixtures — real storage backends seeded with fixture data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.models import Node, HyperEdge
from libs.storage import StorageConfig, StorageManager

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture_nodes() -> list[Node]:
    """Load nodes from tests/fixtures/nodes.json."""
    with open(FIXTURES_DIR / "nodes.json") as f:
        raw = json.load(f)
    return [Node.model_validate(n) for n in raw]


def load_fixture_edges() -> list[HyperEdge]:
    """Load edges from tests/fixtures/edges.json."""
    with open(FIXTURES_DIR / "edges.json") as f:
        raw = json.load(f)
    return [HyperEdge.model_validate(e) for e in raw]


def load_fixture_embeddings() -> dict[int, list[float]] | None:
    """Load embeddings from tests/fixtures/embeddings.json if it exists."""
    path = FIXTURES_DIR / "embeddings.json"
    if not path.exists():
        return None
    with open(path) as f:
        raw = json.load(f)
    return {int(k): v for k, v in raw.items()}


@pytest.fixture
async def storage(tmp_path: Path) -> StorageManager:
    """Real StorageManager seeded with fixture data (LanceDB only, no Neo4j)."""
    config = StorageConfig(
        deployment_mode="local",
        lancedb_path=str(tmp_path / "lance"),
        neo4j_password="",
    )
    manager = StorageManager(config)

    # Seed nodes
    nodes = load_fixture_nodes()
    for node in nodes:
        await manager.lance.save_node(node)

    # Seed edges (Neo4j only if available)
    edges = load_fixture_edges()
    if manager.graph:
        for edge in edges:
            await manager.graph.save_hyperedge(edge)

    # Seed embeddings (vector index)
    embeddings = load_fixture_embeddings()
    if embeddings and manager.vector:
        for node_id, embedding in embeddings.items():
            await manager.vector.upsert(node_id, embedding)

    yield manager
    await manager.close()


@pytest.fixture
async def storage_empty(tmp_path: Path) -> StorageManager:
    """Empty real StorageManager — no fixture data loaded."""
    config = StorageConfig(
        deployment_mode="local",
        lancedb_path=str(tmp_path / "lance"),
        neo4j_password="",
    )
    manager = StorageManager(config)
    yield manager
    await manager.close()
```

**Step 3: Verify fixtures load correctly**

Run: `python -c "from tests.conftest import load_fixture_nodes, load_fixture_edges; print(len(load_fixture_nodes()), 'nodes,', len(load_fixture_edges()), 'edges')"`

If models fail validation (e.g., due to missing fields or type mismatches), fix the fixture loading to handle optional fields gracefully. The fixture JSON may not match the current Pydantic models exactly — use `model_validate` with lenient parsing or adjust the loader.

**Step 4: Write a smoke test to verify the fixture works**

```python
# tests/test_fixture_smoke.py (temporary, delete after confirming)
async def test_storage_fixture_has_nodes(storage):
    """Verify the shared storage fixture loads real data."""
    nodes = load_fixture_nodes()
    assert len(nodes) > 0
    # Verify at least one node is retrievable
    node = await storage.lance.load_node(nodes[0].id)
    assert node is not None
    assert node.content == nodes[0].content
```

Run: `pytest tests/test_fixture_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: add shared fixture-seeded StorageManager in conftest.py

Closes #17"
```

Delete the smoke test file after confirming it works.

---

### Task 2: Rename Edge Types — join→abstraction, meet→induction (Issue #25) ✅ DONE

This cross-cutting rename has been completed. The edge type `join` was renamed to `abstraction` and `meet` to `induction` across all code, tests, fixtures, frontend, and documentation.

**Step 1: Audit all occurrences**

Search the codebase for `"join"` and `"meet"` used as edge type strings (not Python keywords or method names). Key locations:

- `libs/models.py` — type annotations/comments
- `tests/fixtures/edges.json` — fixture data
- `services/review_pipeline/operators/join.py` — operator names in comments/docstrings
- `services/review_pipeline/prompts/*.md` — prompt templates
- `services/review_pipeline/xml_parser.py` — type mappings
- `services/gateway/routes/read.py` — edge type filtering
- `frontend/src/lib/node-styles.ts` — style config
- `frontend/src/lib/graph-transform.ts` — graph transform
- `docs/` — all design documents
- `CLAUDE.md`, `README.md`
- All test files that reference edge type strings

**Step 2: Update models and core code**

In `libs/models.py`:
- HyperEdge type comment/annotation updated: `join` → `abstraction`, `meet` → `induction`
- Node type comment updated: `join` → `abstraction`

In `services/review_pipeline/operators/join.py`:
- Docstrings and comments updated: "join" relationship → "abstraction" relationship
- Class names `CCJoinOperator`, `CPJoinOperator` — **kept** (they describe the operation pattern CC/CP join, not the edge type). Only the edge `type` string they produce was updated.

In `services/review_pipeline/xml_parser.py`:
- Update any type string mappings

In `services/review_pipeline/prompts/*.md`:
- Update terminology in prompt templates

**Step 3: Update fixture data**

In `tests/fixtures/edges.json`:
- Replace `"type": "abstraction"` (was `"type": "join"`)
- Replace `"type": "induction"` (was `"type": "meet"`)

In `tests/fixtures/nodes.json`:
- Replace `"type": "abstraction"` (was `"type": "join"`) if present

**Step 4: Update all test files**

Search all `tests/` for edge type string references and update:
- `"abstraction"` (was `"join"` as edge type)
- `"induction"` (was `"meet"` as edge type)

Be careful not to change:
- Python `join()` method calls
- `CCJoinOperator` / `CPJoinOperator` class names
- `abstraction_trees` field names (these refer to the abstraction operation)

**Step 5: Update frontend**

In `frontend/src/lib/node-styles.ts`:
- Update style entries for `join` → `abstraction`, `meet` → `induction`

In `frontend/src/lib/graph-transform.ts`:
- Update any type references

**Step 6: Update documentation**

Update the following docs with new terminology:
- `CLAUDE.md` — edge type list
- `docs/plans/2026-03-03-lkm-api-design-v3.md` — type table
- `docs/design/theoretical_foundations.md`
- `docs/design/related_work.md`

In documentation, add a brief note explaining the rename rationale where edge types are defined.

**Step 7: Update migration scripts**

In `scripts/seed_database.py` and `scripts/migrate_old_graph.py`:
- Update any hardcoded type strings

**Step 8: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

Run: `ruff check . && ruff format --check .`
Expected: PASS

**Step 9: Commit**

```bash
git add -A
git commit -m "refactor: rename edge types join→abstraction, meet→induction

Closes #25"
```

---

### Task 3: Job Model + Store (Issue #5, part 1)

**Files:**
- Create: `services/job_manager/__init__.py`
- Create: `services/job_manager/models.py`
- Create: `services/job_manager/store.py`
- Test: `tests/services/test_job_manager/__init__.py`
- Test: `tests/services/test_job_manager/test_models.py`
- Test: `tests/services/test_job_manager/test_store.py`

**Step 1: Write the failing tests**

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

**Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_job_manager/ -v`
Expected: FAIL (import errors)

**Step 3: Write implementation**

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
    reference_id: str
    status: JobStatus = JobStatus.PENDING
    progress: dict = {}
    result: dict | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

```python
# services/job_manager/store.py
"""Job persistence — in-memory for now."""

from __future__ import annotations

from services.job_manager.models import Job, JobType


class InMemoryJobStore:
    """In-memory job store."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    async def save(self, job: Job) -> None:
        self._jobs[job.job_id] = job

    async def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def update(self, job: Job) -> None:
        self._jobs[job.job_id] = job

    async def get_by_reference(self, reference_id: str, job_type: JobType) -> Job | None:
        for job in self._jobs.values():
            if job.reference_id == reference_id and job.job_type == job_type:
                return job
        return None
```

**Step 4: Run tests**

Run: `pytest tests/services/test_job_manager/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/job_manager/ tests/services/test_job_manager/
git commit -m "feat: add Job model and InMemoryJobStore"
```

---

### Task 4: JobManager Orchestrator (Issue #5, part 2)

**Files:**
- Create: `services/job_manager/manager.py`
- Test: `tests/services/test_job_manager/test_manager.py`

**Step 1: Write the failing tests**

```python
# tests/services/test_job_manager/test_manager.py
import asyncio

import pytest

from services.job_manager.manager import JobManager
from services.job_manager.models import JobStatus, JobType
from services.job_manager.store import InMemoryJobStore


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

**Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_job_manager/test_manager.py -v`
Expected: FAIL

**Step 3: Write implementation**

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

**Step 4: Run tests**

Run: `pytest tests/services/test_job_manager/test_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/job_manager/manager.py tests/services/test_job_manager/test_manager.py
git commit -m "feat: add JobManager for async job lifecycle"
```

---

### Task 5: Job API Routes + Dependency Wiring (Issue #5, part 3)

**Files:**
- Create: `services/gateway/routes/jobs.py`
- Modify: `services/gateway/app.py` (register router)
- Modify: `services/gateway/deps.py` (add JobManager)
- Test: `tests/services/test_gateway/test_jobs.py`

**Step 1: Write the failing tests**

```python
# tests/services/test_gateway/test_jobs.py
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock

from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from services.job_manager.manager import JobManager
from services.job_manager.models import JobType
from services.job_manager.store import InMemoryJobStore


@pytest.fixture
def test_deps():
    deps = Dependencies()
    deps.storage = MagicMock()
    deps.storage.graph = None
    deps.storage.vector = AsyncMock()
    deps.search_engine = MagicMock()
    deps.commit_engine = MagicMock()
    deps.job_manager = JobManager(store=InMemoryJobStore())
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

    job = await test_deps.job_manager.submit(JobType.REVIEW, "ref1", work)
    await asyncio.sleep(0.1)
    resp = await client.get(f"/jobs/{job.job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


async def test_get_job_result(client, test_deps):
    async def work(job_id):
        return {"answer": 42}

    job = await test_deps.job_manager.submit(JobType.REVIEW, "ref2", work)
    await asyncio.sleep(0.1)
    resp = await client.get(f"/jobs/{job.job_id}/result")
    assert resp.status_code == 200
    assert resp.json()["result"] == {"answer": 42}


async def test_delete_job(client, test_deps):
    async def slow(job_id):
        await asyncio.sleep(10)

    job = await test_deps.job_manager.submit(JobType.REVIEW, "ref3", slow)
    resp = await client.delete(f"/jobs/{job.job_id}")
    assert resp.status_code == 200


async def test_get_nonexistent_job(client):
    resp = await client.get("/jobs/nonexistent")
    assert resp.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_gateway/test_jobs.py -v`
Expected: FAIL

**Step 3: Update deps.py**

Add `job_manager: JobManager | None = None` to `Dependencies`. In `initialize()`, create `self.job_manager = JobManager(store=InMemoryJobStore())`.

**Step 4: Write jobs route**

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
        raise HTTPException(status_code=409, detail=f"Job status is {job.status}")
    return {"job_id": job.job_id, "status": job.status, "result": job.result}


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    job = await deps.job_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await deps.job_manager.cancel(job_id)
    return {"job_id": job.job_id, "status": "cancelled"}
```

**Step 5: Register router in app.py**

Add `from .routes.jobs import router as jobs_router` and `app.include_router(jobs_router)` in `create_app()`.

**Step 6: Run tests**

Run: `pytest tests/services/test_gateway/test_jobs.py -v`
Expected: PASS

**Step 7: Run full test suite to check for regressions**

Run: `pytest tests/ -v`
Expected: ALL PASS

Run: `ruff check . && ruff format --check .`
Expected: PASS

**Step 8: Commit**

```bash
git add services/gateway/routes/jobs.py services/gateway/app.py services/gateway/deps.py tests/services/test_gateway/test_jobs.py
git commit -m "feat: add /jobs API routes and wire JobManager into dependencies

Closes #5"
```
