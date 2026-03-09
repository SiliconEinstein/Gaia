# Plan B: Feature Enhancement Layer

**Status:** Active
**Issues:** #6, #7, #8, #12, #13, #14
**Dependencies:** Plan A (shared fixtures, edge rename, Job infrastructure)
**Unblocks:** Plan C (batch APIs)

## Overview

Plan B enhances three subsystems to align with the v3 API spec:

1. **Async review pipeline** (#6, #7) — wire existing pipeline operators into commit workflow via Job infrastructure
2. **Search embedding internalization** (#8) — server generates embeddings, clients send text only
3. **Enhanced read routes & filters** (#12, #13, #14) — subgraph params, NodeFilters, MergeResult alignment

## Implementation Order

Pipeline-First: review pipeline → search embedding → read/filter enhancements.

The async review pipeline is the critical path — it's the most complex piece, establishes the async pattern, and unblocks Plan C's batch APIs.

---

## 1. Async Review Pipeline (#6, #7)

### Current Flow

```
POST /commits/{id}/review
  → CommitEngine.review()
  → Reviewer.review() (sync stub LLM)
  → ReviewResult(approved, issues, suggestions)
```

### New Flow

```
POST /commits/{id}/review
  → CommitEngine.submit_review(commit_id)
  → JobManager.submit(REVIEW, commit_id, pipeline.run())
  → Returns {job_id, status: "running"}

GET /commits/{id}/review
  → JobManager.get_status(job_id)
  → Returns {status, progress: {pipeline_steps: [...]}}

DELETE /commits/{id}/review
  → JobManager.cancel(job_id)

GET /commits/{id}/review/result
  → JobManager.get_result(job_id)
  → Returns DetailedReviewResult
```

### Changes

**CommitEngine:**
- Remove `review()` method and Reviewer dependency
- Add `submit_review(commit_id)` → creates Job running Pipeline
- Store `review_job_id` on Commit model

**Pipeline integration:**
- Pipeline.run() receives commit operations
- Runs 6 operators: embedding → NN search → CC abstraction → CP abstraction → verify → BP
- Returns DetailedReviewResult
- PipelineContext tracks step progress, reports to Job.progress

**New routes** (`services/gateway/routes/commits.py`):
- `GET /commits/{id}/review` — review job status + pipeline step progress
- `DELETE /commits/{id}/review` — cancel review job
- `GET /commits/{id}/review/result` — detailed review result

**Commit model update:**
- Add `review_job_id: str | None` field

### DetailedReviewResult Model (#7)

```python
class NNCandidate(BaseModel):
    node_id: str
    similarity: float

class QualityMetrics(BaseModel):
    reasoning_valid: bool
    tightness: float      # 0-1
    substantiveness: float # 0-1
    novelty: float         # 0-1

class AbstractionTreeResults(BaseModel):
    cc: list[dict]  # conclusion-conclusion trees
    cp: list[dict]  # conclusion-premise trees

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
    verdict: Literal["pass", "has_overlap", "rejected"]
    embedding_generated: bool
    nn_candidates: list[NNCandidate]
    quality: QualityMetrics | None
    abstraction_trees: AbstractionTreeResults
    contradictions: list[ContradictionResult]
    overlaps: list[OverlapResult]

class BPResults(BaseModel):
    belief_updates: dict[str, float]  # node_id → new belief
    iterations: int
    converged: bool
    affected_nodes: list[str]

class DetailedReviewResult(BaseModel):
    overall_verdict: Literal["pass", "has_overlap", "rejected"]
    operations: list[OperationReviewDetail]
    bp_results: BPResults | None
```

### Merge Persistence

When `POST /commits/{id}/merge` is called after review:
1. Merger reads DetailedReviewResult from the commit
2. Persists belief updates to node records in LanceDB
3. Creates new HyperEdge for each verified abstraction tree (type=abstraction/induction)
4. Creates contradiction edges if detected
5. Returns enriched MergeResult with BP details

---

## 2. Search Embedding Internalization (#8)

### Current Flow

```
POST /search/nodes {query: "...", embedding: [0.1, 0.2, ...], k: 50}
  → SearchEngine.search_nodes(embedding=..., ...)
```

### New Flow

```
POST /search/nodes {text: "...", k: 20}
  → Route calls EmbeddingModel.embed(text) → vector
  → SearchEngine.search_nodes(embedding=vector, ...)
```

### Changes

**EmbeddingModel ABC promotion:**
- Move `EmbeddingModel` ABC from `services/review_pipeline/operators/embedding.py` to `libs/embedding.py`
- Shared between SearchEngine and review Pipeline
- StubEmbeddingModel stays for tests

**SearchEngine:**
- Constructor gets `EmbeddingModel` injected
- `search_nodes()` and `search_edges()` accept `text: str` instead of `embedding: list[float]`
- Internally calls `EmbeddingModel.embed(text)` before vector recall

**Request models (breaking change):**
- `SearchNodesRequest`: replace `embedding: list[float]` with `text: str`
- `SearchEdgesRequest`: same change
- Remove `POST /search/text` endpoint (now redundant)

**DI wiring:**
- `Dependencies` creates one EmbeddingModel, passes to both SearchEngine and Pipeline

---

## 3. Enhanced Read Routes & Filters (#12, #13, #14)

### Subgraph Enhancement (#12)

Add query params to `GET /nodes/{id}/subgraph` and `/nodes/{id}/subgraph/hydrated`:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `direction` | `"upstream" \| "downstream" \| "both"` | `"both"` | Traversal direction |
| `max_nodes` | `int` | `500` | Max nodes returned |
| `edge_types` | `list[str]` | all | Filter by edge type |

Update `Neo4jGraphStore.get_subgraph()` to accept and apply these parameters.

### NodeFilters Completion (#13)

Add fields to NodeFilters:

| Field | Type | Filter logic |
|-------|------|-------------|
| `paper_id` | `str \| None` | Match `node.metadata.paper_id` (LanceDB where clause) |
| `min_quality` | `float \| None` | Minimum quality score 1-5 |
| `edge_type` | `list[str] \| None` | Nodes connected to edges of given types (Neo4j join) |

Update SearchEngine filtering and LanceStore queries.

### MergeResult Alignment (#14)

Add fields to MergeResult:

```python
class MergeResult(BaseModel):
    success: bool
    new_node_ids: list[str]
    new_edge_ids: list[str]
    errors: list[str]
    # New fields
    bp_results: BPResults | None
    abstraction_edges_created: list[str]
    beliefs_persisted: dict[str, float]  # node_id → new belief
```

Merger populates these from the review pipeline's DetailedReviewResult during merge.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pipeline integration | Replace Reviewer with Pipeline | Clean break, no dual-mode complexity |
| Embedding sharing | Reuse EmbeddingModel ABC | One interface, one DI injection point |
| Search API compat | Breaking change | Clean v3 API, no deprecation baggage |
| Pipeline output persistence | Full persistence in merge | Beliefs, abstraction edges, contradictions all written during merge |
| Implementation order | Pipeline-first | Critical path, highest risk, unblocks Plan C |
