# Plan B: Feature Enhancement Layer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire async review pipeline, internalize search embeddings, and enhance read routes/filters to align with v3 API spec.

**Architecture:** Replace synchronous Reviewer with async Pipeline via JobManager. Promote EmbeddingModel ABC to shared `libs/embedding.py` for reuse by both search and review pipeline. Enhance read routes with subgraph parameters and filter fields.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, asyncio, LanceDB, Neo4j

---

## Task 1: Add DetailedReviewResult and supporting models

**Files:**
- Modify: `libs/models.py:100-114`
- Test: `tests/libs/test_models.py`

**Step 1: Write the failing test**

Add to `tests/libs/test_models.py`:

```python
from libs.models import (
    NNCandidate, QualityMetrics, AbstractionTreeResults, ContradictionResult,
    OverlapResult, OperationReviewDetail, BPResults, DetailedReviewResult,
)


def test_nn_candidate_defaults():
    c = NNCandidate(node_id="42", similarity=0.95)
    assert c.node_id == "42"
    assert c.similarity == 0.95


def test_quality_metrics():
    q = QualityMetrics(reasoning_valid=True, tightness=0.8, substantiveness=0.7, novelty=0.6)
    assert q.reasoning_valid is True
    assert q.novelty == 0.6


def test_operation_review_detail_defaults():
    detail = OperationReviewDetail(
        op_index=0,
        verdict="pass",
        embedding_generated=True,
        nn_candidates=[],
        abstraction_trees=AbstractionTreeResults(cc=[], cp=[]),
        contradictions=[],
        overlaps=[],
    )
    assert detail.verdict == "pass"
    assert detail.quality is None


def test_bp_results():
    bp = BPResults(
        belief_updates={"1": 0.8, "2": 0.6},
        iterations=5,
        converged=True,
        affected_nodes=["1", "2"],
    )
    assert bp.converged is True
    assert len(bp.affected_nodes) == 2


def test_detailed_review_result():
    result = DetailedReviewResult(
        overall_verdict="pass",
        operations=[
            OperationReviewDetail(
                op_index=0,
                verdict="pass",
                embedding_generated=True,
                nn_candidates=[NNCandidate(node_id="10", similarity=0.9)],
                abstraction_trees=AbstractionTreeResults(cc=[], cp=[]),
                contradictions=[],
                overlaps=[],
            )
        ],
        bp_results=BPResults(
            belief_updates={}, iterations=3, converged=True, affected_nodes=[]
        ),
    )
    assert result.overall_verdict == "pass"
    assert len(result.operations) == 1
    assert result.bp_results.converged is True


def test_detailed_review_result_no_bp():
    result = DetailedReviewResult(
        overall_verdict="has_overlap",
        operations=[],
    )
    assert result.bp_results is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/test_models.py::test_nn_candidate_defaults -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `libs/models.py` after the existing `ReviewResult` class (line ~105):

```python
class NNCandidate(BaseModel):
    node_id: str
    similarity: float


class QualityMetrics(BaseModel):
    reasoning_valid: bool
    tightness: float
    substantiveness: float
    novelty: float


class AbstractionTreeResults(BaseModel):
    cc: list[dict] = []
    cp: list[dict] = []


class ContradictionResult(BaseModel):
    node_id: str
    edge_id: str
    description: str


class OverlapResult(BaseModel):
    existing_node_id: str
    similarity: float
    recommendation: str  # "merge" | "keep_both"


class OperationReviewDetail(BaseModel):
    op_index: int
    verdict: str  # "pass" | "has_overlap" | "rejected"
    embedding_generated: bool
    nn_candidates: list[NNCandidate] = []
    quality: QualityMetrics | None = None
    abstraction_trees: AbstractionTreeResults = AbstractionTreeResults()
    contradictions: list[ContradictionResult] = []
    overlaps: list[OverlapResult] = []


class BPResults(BaseModel):
    belief_updates: dict[str, float] = {}
    iterations: int = 0
    converged: bool = False
    affected_nodes: list[str] = []


class DetailedReviewResult(BaseModel):
    overall_verdict: str  # "pass" | "has_overlap" | "rejected"
    operations: list[OperationReviewDetail] = []
    bp_results: BPResults | None = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/test_models.py -v -k "nn_candidate or quality_metrics or operation_review or bp_results or detailed_review"`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add libs/models.py tests/libs/test_models.py
git commit -m "feat: add DetailedReviewResult and supporting models (#7)"
```

---

## Task 2: Extend MergeResult with BP details (#14)

**Files:**
- Modify: `libs/models.py:108-114`
- Test: `tests/libs/test_models.py`

**Step 1: Write the failing test**

Add to `tests/libs/test_models.py`:

```python
def test_merge_result_with_bp_details():
    result = MergeResult(
        success=True,
        new_node_ids=["1", "2"],
        new_edge_ids=["10"],
        errors=[],
        bp_results=BPResults(
            belief_updates={"1": 0.9},
            iterations=5,
            converged=True,
            affected_nodes=["1"],
        ),
        abstraction_edges_created=["10"],
        beliefs_persisted={"1": 0.9},
    )
    assert result.bp_results.converged is True
    assert result.abstraction_edges_created == ["10"]
    assert result.beliefs_persisted == {"1": 0.9}


def test_merge_result_backward_compat():
    result = MergeResult(
        success=True,
        new_node_ids=[],
        new_edge_ids=[],
        errors=[],
    )
    assert result.bp_results is None
    assert result.abstraction_edges_created == []
    assert result.beliefs_persisted == {}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/test_models.py::test_merge_result_with_bp_details -v`
Expected: FAIL with validation error (unexpected fields)

**Step 3: Write minimal implementation**

Modify `MergeResult` in `libs/models.py`:

```python
class MergeResult(BaseModel):
    success: bool
    new_node_ids: list[str] = []
    new_edge_ids: list[str] = []
    errors: list[str] = []
    bp_results: BPResults | None = None
    abstraction_edges_created: list[str] = []
    beliefs_persisted: dict[str, float] = {}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/test_models.py -v -k "merge_result"`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/models.py tests/libs/test_models.py
git commit -m "feat: extend MergeResult with BP details (#14)"
```

---

## Task 3: Add review_job_id to Commit model

**Files:**
- Modify: `libs/models.py:117-128`
- Test: `tests/libs/test_models.py`

**Step 1: Write the failing test**

Add to `tests/libs/test_models.py`:

```python
def test_commit_review_job_id():
    commit = Commit(
        commit_id="c1",
        status="pending_review",
        message="test",
        operations=[],
        review_job_id="job-123",
    )
    assert commit.review_job_id == "job-123"


def test_commit_review_job_id_default_none():
    commit = Commit(
        commit_id="c1",
        status="pending_review",
        message="test",
        operations=[],
    )
    assert commit.review_job_id is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/test_models.py::test_commit_review_job_id -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add `review_job_id: str | None = None` to Commit model in `libs/models.py`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/test_models.py -v -k "commit_review_job"`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/models.py tests/libs/test_models.py
git commit -m "feat: add review_job_id to Commit model (#6)"
```

---

## Task 4: Promote EmbeddingModel ABC to libs/

**Files:**
- Create: `libs/embedding.py`
- Modify: `services/review_pipeline/operators/embedding.py`
- Test: `tests/libs/test_embedding.py`

**Step 1: Write the failing test**

Create `tests/libs/test_embedding.py`:

```python
import pytest
from libs.embedding import EmbeddingModel, StubEmbeddingModel


async def test_stub_embedding_model_returns_vectors():
    model = StubEmbeddingModel(dimensions=128)
    vectors = await model.embed(["hello world"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 128
    assert all(isinstance(v, float) for v in vectors[0])


async def test_stub_embedding_model_deterministic():
    model = StubEmbeddingModel(dimensions=64)
    v1 = await model.embed(["test"])
    v2 = await model.embed(["test"])
    assert v1 == v2


async def test_stub_embedding_model_different_texts():
    model = StubEmbeddingModel(dimensions=64)
    v1 = await model.embed(["hello"])
    v2 = await model.embed(["world"])
    assert v1 != v2


async def test_embedding_model_is_abstract():
    with pytest.raises(TypeError):
        EmbeddingModel()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/test_embedding.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Create `libs/embedding.py`:

```python
"""Embedding model abstraction shared by search and review pipeline."""

from abc import ABC, abstractmethod
import hashlib
import struct


class EmbeddingModel(ABC):
    """Abstract base class for embedding models."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a list of texts."""


class StubEmbeddingModel(EmbeddingModel):
    """Deterministic hash-based embedding model for testing."""

    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_embed(text) for text in texts]

    def _hash_embed(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        values = []
        for i in range(self.dimensions):
            seed = hashlib.sha256(h + struct.pack(">I", i)).digest()[:4]
            val = struct.unpack(">I", seed)[0] / (2**32) * 2 - 1
            values.append(val)
        return values
```

Then update `services/review_pipeline/operators/embedding.py` to import from `libs/embedding`:

```python
from libs.embedding import EmbeddingModel, StubEmbeddingModel  # re-export
```

Remove the duplicate `EmbeddingModel` and `StubEmbeddingModel` class definitions from `services/review_pipeline/operators/embedding.py`, keeping only `EmbeddingOperator`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/libs/test_embedding.py tests/services/test_review_pipeline/test_embedding_op.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add libs/embedding.py tests/libs/test_embedding.py services/review_pipeline/operators/embedding.py
git commit -m "refactor: promote EmbeddingModel ABC to libs/embedding (#8)"
```

---

## Task 5: Complete NodeFilters with new fields (#13)

**Files:**
- Modify: `services/search_engine/models.py:8-12`
- Modify: `services/search_engine/engine.py:157-172`
- Test: `tests/services/test_search_engine/test_engine.py`

**Step 1: Write the failing test**

Add to `tests/services/test_search_engine/test_engine.py`:

```python
from services.search_engine.models import NodeFilters


def test_node_filters_new_fields():
    f = NodeFilters(paper_id="arxiv:2301.12345", min_quality=3.0, edge_type=["abstraction"])
    assert f.paper_id == "arxiv:2301.12345"
    assert f.min_quality == 3.0
    assert f.edge_type == ["abstraction"]


def test_node_filters_new_fields_default_none():
    f = NodeFilters()
    assert f.paper_id is None
    assert f.min_quality is None
    assert f.edge_type is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_search_engine/test_engine.py::test_node_filters_new_fields -v`
Expected: FAIL with validation error

**Step 3: Write minimal implementation**

Modify `NodeFilters` in `services/search_engine/models.py`:

```python
class NodeFilters(BaseModel):
    type: list[str] | None = None
    status: list[str] = ["active"]
    min_belief: float | None = None
    keywords: list[str] | None = None
    paper_id: str | None = None
    min_quality: float | None = None
    edge_type: list[str] | None = None
```

Update `_passes_node_filters` in `services/search_engine/engine.py` to apply the new filters:

```python
@staticmethod
def _passes_node_filters(node, filters: NodeFilters | None) -> bool:
    if not filters:
        return True
    if filters.type and node.type not in filters.type:
        return False
    if filters.status and node.status not in filters.status:
        return False
    if filters.min_belief is not None and (node.belief is None or node.belief < filters.min_belief):
        return False
    if filters.keywords:
        node_kw = set(node.keywords or [])
        if not node_kw.intersection(filters.keywords):
            return False
    if filters.paper_id:
        node_paper = (node.metadata or {}).get("paper_id")
        if node_paper != filters.paper_id:
            return False
    if filters.min_quality is not None:
        node_quality = (node.metadata or {}).get("quality")
        if node_quality is None or node_quality < filters.min_quality:
            return False
    # edge_type filter requires Neo4j join — skipped in filter pass,
    # applied in search_nodes via topology recall
    return True
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_search_engine/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/search_engine/models.py services/search_engine/engine.py tests/services/test_search_engine/test_engine.py
git commit -m "feat: complete NodeFilters with paper_id, min_quality, edge_type (#13)"
```

---

## Task 6: Enhance subgraph endpoint with direction, max_nodes, edge_types (#12)

**Files:**
- Modify: `services/gateway/routes/read.py:27-52`
- Modify: `libs/storage/neo4j_store.py:166-180`
- Test: `tests/services/test_gateway/test_read.py`

**Step 1: Write the failing test**

Add to `tests/services/test_gateway/test_read.py`:

```python
async def test_subgraph_with_direction_param(client):
    resp = await client.get("/nodes/1/subgraph?hops=2&direction=upstream&max_nodes=100")
    assert resp.status_code == 200
    data = resp.json()
    assert "node_ids" in data
    assert "edge_ids" in data


async def test_subgraph_with_edge_types_param(client):
    resp = await client.get("/nodes/1/subgraph?hops=1&edge_types=abstraction,induction")
    assert resp.status_code == 200


async def test_subgraph_hydrated_with_params(client):
    resp = await client.get(
        "/nodes/1/subgraph/hydrated?hops=1&direction=downstream&max_nodes=50"
    )
    assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_read.py::test_subgraph_with_direction_param -v`
Expected: FAIL (422 — unexpected query params)

**Step 3: Write minimal implementation**

Update `services/gateway/routes/read.py` subgraph endpoints:

```python
from typing import Literal


@router.get("/nodes/{node_id}/subgraph")
async def get_node_subgraph(
    node_id: int,
    hops: int = 1,
    direction: Literal["upstream", "downstream", "both"] = "both",
    max_nodes: int = 500,
    edge_types: str | None = None,
):
    storage = deps.storage
    if not storage.neo4j:
        raise HTTPException(503, "Graph store not available")
    edge_type_list = edge_types.split(",") if edge_types else None
    node_ids, edge_ids = await storage.neo4j.get_subgraph(
        [node_id], hops=hops, direction=direction,
        max_nodes=max_nodes, edge_types=edge_type_list,
    )
    return {"node_ids": sorted(node_ids), "edge_ids": sorted(edge_ids)}
```

Apply same params to the hydrated endpoint.

Update `libs/storage/neo4j_store.py` `get_subgraph()` to accept and use `direction` and `max_nodes`:

```python
async def get_subgraph(
    self,
    node_ids: list[int],
    hops: int = 1,
    edge_types: list[str] | None = None,
    direction: str = "both",
    max_nodes: int = 500,
) -> tuple[set[int], set[int]]:
```

Update the Cypher query to respect `direction` (upstream = follow `:HEAD` back, downstream = follow `:TAIL` forward, both = either direction) and `LIMIT` to `max_nodes`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_gateway/test_read.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/gateway/routes/read.py libs/storage/neo4j_store.py tests/services/test_gateway/test_read.py
git commit -m "feat: enhance subgraph endpoint with direction, max_nodes, edge_types (#12)"
```

---

## Task 7: Wire Pipeline into CommitEngine as async review (#6)

This is the largest task. It replaces the synchronous Reviewer with async Pipeline execution via JobManager.

**Files:**
- Modify: `services/commit_engine/engine.py:24-92`
- Modify: `services/gateway/deps.py:25-37`
- Delete (or gut): `services/commit_engine/reviewer.py`
- Test: `tests/services/test_commit_engine/test_engine.py`

**Step 1: Write the failing test**

Add to `tests/services/test_commit_engine/test_engine.py`:

```python
import asyncio
from services.job_manager.models import JobStatus


async def test_submit_review_returns_job_id(commit_engine, sample_commit_request):
    """submit_review should create an async job and return a job_id."""
    resp = await commit_engine.submit(sample_commit_request)
    commit_id = resp.commit_id

    job = await commit_engine.submit_review(commit_id)
    assert job.job_id is not None
    assert job.job_type.value == "review"
    assert job.reference_id == commit_id


async def test_submit_review_stores_job_id_on_commit(commit_engine, sample_commit_request):
    """After submit_review, commit.review_job_id should be set."""
    resp = await commit_engine.submit(sample_commit_request)
    job = await commit_engine.submit_review(resp.commit_id)

    commit = await commit_engine.get_commit(resp.commit_id)
    assert commit.review_job_id == job.job_id


async def test_review_job_completes(commit_engine, sample_commit_request):
    """Review job should complete and produce a DetailedReviewResult."""
    resp = await commit_engine.submit(sample_commit_request)
    job = await commit_engine.submit_review(resp.commit_id)

    # Wait for the async job to complete
    for _ in range(50):
        status = await commit_engine.job_manager.get_status(job.job_id)
        if status.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break
        await asyncio.sleep(0.05)

    assert status.status == JobStatus.COMPLETED
    result = await commit_engine.job_manager.get_result(job.job_id)
    assert "overall_verdict" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_commit_engine/test_engine.py::test_submit_review_returns_job_id -v`
Expected: FAIL with AttributeError (no submit_review method)

**Step 3: Write minimal implementation**

Modify `services/commit_engine/engine.py`:

```python
from services.job_manager.manager import JobManager
from services.job_manager.models import Job, JobType
from services.review_pipeline.base import Pipeline
from services.review_pipeline.context import PipelineContext
from libs.models import DetailedReviewResult, OperationReviewDetail, AbstractionTreeResults


class CommitEngine:
    def __init__(
        self,
        storage: StorageManager,
        commit_store: CommitStore,
        pipeline: Pipeline | None = None,
        job_manager: JobManager | None = None,
        search_engine=None,
        llm_client=None,
    ):
        self.storage = storage
        self.commit_store = commit_store
        self.pipeline = pipeline
        self.job_manager = job_manager or JobManager()
        self.search_engine = search_engine
        # Keep llm_client for backward compat but unused
        ...

    async def submit_review(self, commit_id: str) -> Job:
        """Submit an async review job for a commit."""
        commit = await self.commit_store.get(commit_id)
        if not commit:
            raise ValueError(f"Commit {commit_id} not found")
        if commit.status != "pending_review":
            raise ValueError(f"Commit {commit_id} is not pending review")

        async def run_review(job_id: str) -> dict:
            context = PipelineContext.from_commit_request(commit.operations_as_request)
            if self.pipeline:
                context = await self.pipeline.execute(context)
            result = self._build_review_result(context)
            await self.commit_store.update(
                commit_id, status="reviewed", review_results=result.model_dump()
            )
            return result.model_dump()

        job = await self.job_manager.submit(JobType.REVIEW, commit_id, run_review)
        await self.commit_store.update(commit_id, review_job_id=job.job_id)
        return job

    def _build_review_result(self, context: PipelineContext) -> DetailedReviewResult:
        """Build DetailedReviewResult from pipeline context."""
        operations = []
        for i, node_info in enumerate(context.new_nodes):
            detail = OperationReviewDetail(
                op_index=node_info.op_index,
                verdict="pass",
                embedding_generated=i in context.embeddings,
                nn_candidates=[
                    {"node_id": str(nid), "similarity": sim}
                    for nid, sim in context.nn_results.get(i, [])
                ],
                abstraction_trees=AbstractionTreeResults(
                    cc=[t.model_dump() if hasattr(t, 'model_dump') else t.__dict__
                        for t in context.cc_abstraction_trees if t.source_node_index == i],
                    cp=[t.model_dump() if hasattr(t, 'model_dump') else t.__dict__
                        for t in context.cp_abstraction_trees if t.source_node_index == i],
                ),
                contradictions=[],
                overlaps=[],
            )
            operations.append(detail)

        bp = None
        if context.bp_results:
            bp = BPResults(**context.bp_results)

        return DetailedReviewResult(
            overall_verdict="pass",
            operations=operations,
            bp_results=bp,
        )
```

Remove the old `review()` method (or keep as a thin wrapper that calls `submit_review` and waits).

**Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_commit_engine/test_engine.py -v`
Expected: ALL PASS (including new tests)

Note: Existing tests that call `commit_engine.review()` will need updating — either adapt them to call `submit_review()` + wait, or add a synchronous convenience wrapper.

**Step 5: Commit**

```bash
git add services/commit_engine/engine.py tests/services/test_commit_engine/test_engine.py
git commit -m "feat: wire Pipeline into CommitEngine as async review (#6)"
```

---

## Task 8: Add review routes to gateway (#6)

**Files:**
- Modify: `services/gateway/routes/commits.py`
- Modify: `services/gateway/deps.py`
- Test: `tests/services/test_gateway/test_commits.py`

**Step 1: Write the failing test**

Add to `tests/services/test_gateway/test_commits.py`:

```python
import asyncio


async def test_post_review_returns_job_id(client, committed_id):
    """POST /commits/{id}/review should return a job_id."""
    resp = await client.post(f"/commits/{committed_id}/review")
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "running" or data["status"] == "pending"


async def test_get_review_status(client, committed_id):
    """GET /commits/{id}/review should return review progress."""
    post_resp = await client.post(f"/commits/{committed_id}/review")
    job_id = post_resp.json()["job_id"]

    resp = await client.get(f"/commits/{committed_id}/review")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


async def test_get_review_result(client, committed_id):
    """GET /commits/{id}/review/result should return DetailedReviewResult after completion."""
    post_resp = await client.post(f"/commits/{committed_id}/review")
    job_id = post_resp.json()["job_id"]

    # Wait for completion
    for _ in range(50):
        status_resp = await client.get(f"/commits/{committed_id}/review")
        if status_resp.json()["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.05)

    resp = await client.get(f"/commits/{committed_id}/review/result")
    assert resp.status_code == 200
    data = resp.json()
    assert "overall_verdict" in data


async def test_delete_review_cancels(client, committed_id):
    """DELETE /commits/{id}/review should cancel the review job."""
    post_resp = await client.post(f"/commits/{committed_id}/review")
    resp = await client.delete(f"/commits/{committed_id}/review")
    assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_commits.py::test_post_review_returns_job_id -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Update `services/gateway/routes/commits.py`:

```python
@router.post("/commits/{commit_id}/review")
async def review_commit(commit_id: str):
    """Submit async review job for a commit."""
    job = await deps.commit_engine.submit_review(commit_id)
    return {"job_id": job.job_id, "status": job.status.value}


@router.get("/commits/{commit_id}/review")
async def get_review_status(commit_id: str):
    """Get review job status and progress."""
    commit = await deps.commit_engine.get_commit(commit_id)
    if not commit or not commit.review_job_id:
        raise HTTPException(404, "No review job found for this commit")
    job = await deps.commit_engine.job_manager.get_status(commit.review_job_id)
    if not job:
        raise HTTPException(404, "Review job not found")
    return {"job_id": job.job_id, "status": job.status.value, "progress": job.progress}


@router.delete("/commits/{commit_id}/review")
async def cancel_review(commit_id: str):
    """Cancel a running review job."""
    commit = await deps.commit_engine.get_commit(commit_id)
    if not commit or not commit.review_job_id:
        raise HTTPException(404, "No review job found for this commit")
    cancelled = await deps.commit_engine.job_manager.cancel(commit.review_job_id)
    return {"cancelled": cancelled}


@router.get("/commits/{commit_id}/review/result")
async def get_review_result(commit_id: str):
    """Get the detailed review result after job completion."""
    commit = await deps.commit_engine.get_commit(commit_id)
    if not commit or not commit.review_job_id:
        raise HTTPException(404, "No review job found for this commit")
    result = await deps.commit_engine.job_manager.get_result(commit.review_job_id)
    if result is None:
        raise HTTPException(404, "Review result not available yet")
    return result
```

Update `services/gateway/deps.py` to wire Pipeline into CommitEngine:

```python
from services.review_pipeline.base import Pipeline
from services.review_pipeline.operators.embedding import EmbeddingOperator
from services.review_pipeline.operators.nn_search import NNSearchOperator
from services.review_pipeline.operators.abstraction import CCAbstractionOperator, CPAbstractionOperator, StubAbstractionLLM
from services.review_pipeline.operators.verify import AbstractionTreeVerifyOperator, VerifyAgainOperator, RefineOperator, StubVerifyLLM
from services.review_pipeline.operators.bp import BPOperator
from libs.embedding import StubEmbeddingModel


def initialize(self, ...):
    ...
    embedding_model = StubEmbeddingModel()
    pipeline = Pipeline(steps=[
        EmbeddingOperator(embedding_model),
        NNSearchOperator(self.storage.vector, k=20),
        CCJoinOperator(StubJoinLLM(), self.storage),
        CPJoinOperator(StubJoinLLM(), self.storage),
        AbstractionTreeVerifyOperator(StubVerifyLLM()),
        RefineOperator(),
        VerifyAgainOperator(StubVerifyLLM()),
        BPOperator(self.storage),
    ])
    self.commit_engine = CommitEngine(
        storage=self.storage,
        commit_store=commit_store,
        pipeline=pipeline,
        job_manager=self.job_manager,
    )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_gateway/test_commits.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/gateway/routes/commits.py services/gateway/deps.py tests/services/test_gateway/test_commits.py
git commit -m "feat: add async review routes to gateway (#6)"
```

---

## Task 9: Internalize embedding in search endpoints (#8)

**Files:**
- Modify: `services/search_engine/engine.py:28-85`
- Modify: `services/gateway/routes/search.py`
- Modify: `services/gateway/deps.py`
- Test: `tests/services/test_gateway/test_search.py`
- Test: `tests/services/test_search_engine/test_engine.py`

**Step 1: Write the failing test**

Add to `tests/services/test_gateway/test_search.py`:

```python
async def test_search_nodes_with_text_only(client):
    """POST /search/nodes should accept text without embedding."""
    resp = await client.post("/search/nodes", json={"text": "superconductivity", "k": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


async def test_search_edges_with_text_only(client):
    """POST /search/hyperedges should accept text without embedding."""
    resp = await client.post("/search/hyperedges", json={"text": "superconductivity", "k": 5})
    assert resp.status_code == 200
```

Add to `tests/services/test_search_engine/test_engine.py`:

```python
async def test_search_nodes_with_text(search_engine):
    """SearchEngine.search_nodes should accept text and generate embedding internally."""
    results = await search_engine.search_nodes(text="superconductivity", k=10)
    assert isinstance(results, list)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_gateway/test_search.py::test_search_nodes_with_text_only -v`
Expected: FAIL (422 — missing 'embedding' field, or 'text' unrecognized)

**Step 3: Write minimal implementation**

Modify `services/search_engine/engine.py`:

```python
from libs.embedding import EmbeddingModel


class SearchEngine:
    def __init__(self, storage: StorageManager, embedding_model: EmbeddingModel | None = None):
        self.storage = storage
        self.embedding_model = embedding_model
        ...

    async def search_nodes(
        self,
        text: str,
        k: int = 50,
        filters: NodeFilters | None = None,
        paths: list[str] | None = None,
    ) -> list[ScoredNode]:
        if not self.embedding_model:
            raise ValueError("No embedding model configured")
        embedding = (await self.embedding_model.embed([text]))[0]
        # ... rest of existing logic using embedding
```

Remove `query` and `embedding` params from `search_nodes` and `search_edges`, replace with `text`.

Modify `services/gateway/routes/search.py`:

```python
class SearchNodesRequest(BaseModel):
    text: str
    k: int = 20
    filters: NodeFilters | None = None
    paths: list[str] | None = None


class SearchEdgesRequest(BaseModel):
    text: str
    k: int = 20
    filters: EdgeFilters | None = None
    paths: list[str] | None = None


@router.post("/search/nodes")
async def search_nodes(request: SearchNodesRequest):
    results = await deps.search_engine.search_nodes(
        text=request.text, k=request.k, filters=request.filters, paths=request.paths,
    )
    return [r.model_dump() for r in results]
```

Remove the `/search/text` endpoint (now redundant).

Update `services/gateway/deps.py` to pass embedding_model to SearchEngine:

```python
self.search_engine = SearchEngine(self.storage, embedding_model=embedding_model)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_search_engine/ tests/services/test_gateway/test_search.py -v`
Expected: ALL PASS

Note: Existing tests that pass `embedding` directly will need updating to pass `text` instead.

**Step 5: Commit**

```bash
git add services/search_engine/engine.py services/gateway/routes/search.py services/gateway/deps.py tests/
git commit -m "feat: internalize embedding generation in search endpoints (#8)"
```

---

## Task 10: Enhance Merger to persist pipeline outputs

**Files:**
- Modify: `services/commit_engine/merger.py:29-54`
- Test: `tests/services/test_commit_engine/test_merger.py`

**Step 1: Write the failing test**

Add to `tests/services/test_commit_engine/test_merger.py`:

```python
from libs.models import BPResults, DetailedReviewResult, OperationReviewDetail, AbstractionTreeResults


async def test_merge_persists_belief_updates(merger, storage, reviewed_commit):
    """Merger should update node beliefs from review BP results."""
    reviewed_commit.review_results = DetailedReviewResult(
        overall_verdict="pass",
        operations=[],
        bp_results=BPResults(
            belief_updates={"1": 0.85},
            iterations=5,
            converged=True,
            affected_nodes=["1"],
        ),
    ).model_dump()

    result = await merger.merge(reviewed_commit)
    assert result.success is True
    assert result.beliefs_persisted == {"1": 0.85}

    # Verify node was actually updated in storage
    node = await storage.lance.load_node(1)
    assert node.belief == 0.85


async def test_merge_result_includes_bp(merger, reviewed_commit):
    """MergeResult should include BP results from review."""
    reviewed_commit.review_results = DetailedReviewResult(
        overall_verdict="pass",
        operations=[],
        bp_results=BPResults(
            belief_updates={}, iterations=3, converged=True, affected_nodes=[]
        ),
    ).model_dump()

    result = await merger.merge(reviewed_commit)
    assert result.bp_results is not None
    assert result.bp_results.converged is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_commit_engine/test_merger.py::test_merge_persists_belief_updates -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Update `services/commit_engine/merger.py` `merge()` method to:
1. Check `commit.review_results` for `DetailedReviewResult` data
2. After applying operations, persist belief updates: for each `(node_id, belief)` in `bp_results.belief_updates`, call `storage.lance.update_node(node_id, belief=belief)`
3. Create abstraction edges from verified abstraction trees in `review_results.operations[].abstraction_trees`
4. Populate `MergeResult.bp_results`, `abstraction_edges_created`, `beliefs_persisted`

```python
async def merge(self, commit: Commit) -> MergeResult:
    # ... existing operation application logic ...

    # Persist pipeline outputs
    bp_results_model = None
    beliefs_persisted = {}
    abstraction_edges_created = []

    review_data = commit.review_results
    if isinstance(review_data, dict) and "overall_verdict" in review_data:
        bp_data = review_data.get("bp_results")
        if bp_data:
            bp_results_model = BPResults(**bp_data)
            for node_id_str, belief in bp_data.get("belief_updates", {}).items():
                node_id = int(node_id_str)
                await self.storage.lance.update_node(node_id, belief=belief)
                beliefs_persisted[node_id_str] = belief

    return MergeResult(
        success=True,
        new_node_ids=new_node_ids,
        new_edge_ids=new_edge_ids,
        errors=errors,
        bp_results=bp_results_model,
        abstraction_edges_created=abstraction_edges_created,
        beliefs_persisted=beliefs_persisted,
    )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_commit_engine/test_merger.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/commit_engine/merger.py tests/services/test_commit_engine/test_merger.py
git commit -m "feat: enhance Merger to persist belief updates and abstraction edges (#14)"
```

---

## Task 11: Update existing tests and fix integration

**Files:**
- Modify: `tests/services/test_commit_engine/test_engine.py`
- Modify: `tests/services/test_commit_engine/test_reviewer.py`
- Modify: `tests/services/test_gateway/test_commits.py`
- Modify: `tests/integration/test_e2e.py`

**Step 1: Update commit engine tests**

Update existing tests in `tests/services/test_commit_engine/test_engine.py` that call `commit_engine.review()` to use the new `submit_review()` + wait pattern. Tests that create `CommitEngine` need to pass `pipeline` and `job_manager` instead of `llm_client`.

**Step 2: Update reviewer tests**

Tests in `test_reviewer.py` for the old `Reviewer` class can be removed or converted to test `_build_review_result()` logic.

**Step 3: Update gateway commit tests**

Ensure `test_commits.py` fixtures create the app with proper pipeline + job_manager DI.

**Step 4: Run full test suite**

Run: `pytest -x -v`
Expected: ALL PASS (224+ tests)

**Step 5: Commit**

```bash
git add tests/
git commit -m "test: update existing tests for async review pipeline"
```

---

## Task 12: Full integration test

**Files:**
- Modify: `tests/integration/test_e2e.py`

**Step 1: Write the integration test**

Add to `tests/integration/test_e2e.py`:

```python
class TestAsyncReviewPipeline:
    async def test_full_review_flow(self, client):
        """E2E: submit commit → review (async) → poll → get result → merge."""
        # Submit commit
        commit_resp = await client.post("/commits", json={...})
        commit_id = commit_resp.json()["commit_id"]

        # Submit review
        review_resp = await client.post(f"/commits/{commit_id}/review")
        assert review_resp.status_code == 200
        job_id = review_resp.json()["job_id"]

        # Poll until complete
        for _ in range(50):
            status_resp = await client.get(f"/commits/{commit_id}/review")
            if status_resp.json()["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.05)

        # Get result
        result_resp = await client.get(f"/commits/{commit_id}/review/result")
        assert result_resp.status_code == 200
        assert result_resp.json()["overall_verdict"] == "pass"

        # Merge
        merge_resp = await client.post(f"/commits/{commit_id}/merge")
        assert merge_resp.status_code == 200

    async def test_search_with_text(self, client):
        """E2E: search nodes with text only (no embedding)."""
        resp = await client.post("/search/nodes", json={"text": "superconductivity", "k": 5})
        assert resp.status_code == 200
```

**Step 2: Run integration tests**

Run: `pytest tests/integration/test_e2e.py -v`
Expected: ALL PASS

**Step 3: Run full test suite**

Run: `pytest --tb=short`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/integration/test_e2e.py
git commit -m "test: add E2E tests for async review and text search"
```

---

## Task 13: Lint and final cleanup

**Step 1: Run linter**

Run: `ruff check . --fix`
Run: `ruff format .`

**Step 2: Run full test suite one more time**

Run: `pytest -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: lint and format cleanup"
```

---

## Summary

| Task | Issue | Scope |
|------|-------|-------|
| 1 | #7 | Add DetailedReviewResult models |
| 2 | #14 | Extend MergeResult with BP details |
| 3 | #6 | Add review_job_id to Commit |
| 4 | #8 | Promote EmbeddingModel to libs/ |
| 5 | #13 | Complete NodeFilters |
| 6 | #12 | Enhance subgraph endpoint |
| 7 | #6 | Wire Pipeline into CommitEngine |
| 8 | #6 | Add review routes to gateway |
| 9 | #8 | Internalize search embedding |
| 10 | #14 | Enhance Merger persistence |
| 11 | — | Update existing tests |
| 12 | — | E2E integration tests |
| 13 | — | Lint and cleanup |

**Total:** 13 tasks covering all 6 issues (#6, #7, #8, #12, #13, #14)
