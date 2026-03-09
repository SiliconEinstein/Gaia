# Plan D: Test Rewrite — Mock Tests → Real Storage

> **Status:** ACTIVE

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite ~35 mock-based service tests to use real StorageManager with fixture data, so tests verify actual data correctness instead of just "method was called."

**Issues:** #18, #19, #20, #21

**Tech Stack:** Python 3.12+, pytest, asyncio, LanceDB, Neo4j (optional, CI provides service container)

**Depends on:** Plan A Task 1 (shared fixture StorageManager in conftest.py) must be completed first.

**Guiding principle:** Each test should assert on **data results** (e.g., "the node content is X", "search returns node 42") rather than **method calls** (e.g., `mock.assert_called_once_with(...)`).

---

### Task 1: Rewrite Commit Engine Tests (Issue #18)

**Files to modify:**
- `tests/services/test_commit_engine/test_engine.py` (8 tests)
- `tests/services/test_commit_engine/test_merger.py` (6 tests)
- `tests/services/test_commit_engine/test_dedup.py` (4 tests)

**Files NOT to modify (already real or pure logic):**
- `test_store.py` — already uses real file I/O with tmp_path
- `test_validator.py` — pure validation logic, no storage
- `test_reviewer.py` — tests LLM interface stubs, no storage

**Step 1: Read all three test files to understand current mock patterns**

Read `test_engine.py`, `test_merger.py`, `test_dedup.py` thoroughly. Note which `MagicMock`/`AsyncMock` patterns they use and what assertions they make.

**Step 2: Rewrite test_engine.py**

Replace mock-based `storage` fixture with the shared `storage` fixture from conftest.py. The `CommitEngine` needs a real `StorageManager`, `CommitStore`, and `SearchEngine`.

Pattern for the new fixture:

```python
@pytest.fixture
async def engine(storage, tmp_path):
    """CommitEngine backed by real storage."""
    from services.commit_engine.engine import CommitEngine
    from services.commit_engine.store import CommitStore
    from services.search_engine.engine import SearchEngine

    commit_store = CommitStore(storage_path=str(tmp_path / "commits"))
    search_engine = SearchEngine(storage)
    return CommitEngine(
        storage=storage,
        commit_store=commit_store,
        search_engine=search_engine,
    )
```

Rewrite each test to assert on data outcomes:

| Test | Old assertion (mock) | New assertion (real) |
|------|---------------------|---------------------|
| `test_submit_creates_commit` | mock.save called | `engine.get_commit(id)` returns commit with correct fields |
| `test_submit_rejects_invalid` | returns rejected status | same — check status field |
| `test_review_approves` | mock status updated | `engine.get_commit(id).status == "reviewed"` |
| `test_merge_after_review` | mock.save_node called | `storage.lance.load_node(new_id)` returns the node |
| `test_merge_without_review_fails` | raises/returns error | same behavior check |
| `test_merge_force_skips_review` | mock.save_node called | node actually in storage |
| `test_get_commit` | mock returns commit | real commit from store |
| `test_get_nonexistent_commit` | returns None | same |

**Step 3: Rewrite test_merger.py**

The Merger does triple-write (LanceDB → Neo4j → Vector). Test that data actually lands in each store.

```python
@pytest.fixture
async def merger(storage):
    from services.commit_engine.merger import Merger
    return Merger(storage=storage)
```

| Test | New assertion |
|------|-------------|
| `test_merge_add_edge_with_new_nodes` | `storage.lance.load_node(id)` returns node; if graph: `storage.graph.get_hyperedge(id)` returns edge |
| `test_merge_add_edge_with_existing_nodes` | existing node unchanged, new edge created |
| `test_merge_modify_node` | `storage.lance.load_node(id).content` updated |
| `test_merge_modify_edge` | `storage.graph.get_hyperedge(id)` fields updated (skip if no graph) |
| `test_merge_no_graph_still_works` | set `storage.graph = None`, verify lance still works |
| `test_merge_multiple_operations` | all operations applied, all data retrievable |

**Step 4: Rewrite test_dedup.py**

DedupChecker uses SearchEngine to find similar nodes. With real storage + fixture data, we can test actual semantic similarity.

```python
@pytest.fixture
async def checker(storage):
    from services.commit_engine.dedup import DedupChecker
    from services.search_engine.engine import SearchEngine
    search = SearchEngine(storage)
    return DedupChecker(search_engine=search)
```

Use fixture nodes' actual content to test duplicate detection. Pick two nodes from fixtures that are semantically similar (or insert a near-duplicate).

**Step 5: Run tests**

Run: `pytest tests/services/test_commit_engine/ -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add tests/services/test_commit_engine/
git commit -m "test: rewrite commit engine tests with real storage

Closes #18"
```

---

### Task 2: Rewrite Search Engine Tests (Issue #19)

**Files to modify:**
- `tests/services/test_search_engine/test_engine.py` (8 tests)
- `tests/services/test_search_engine/test_bm25_recall.py` (3 tests)
- `tests/services/test_search_engine/test_vector_recall.py` (3 tests)

**Files NOT to modify:**
- `test_merger.py` — pure score-merging algorithm, no storage
- `test_topology_recall.py` — keep 2 mock tests for edge cases (`test_recall_no_seeds`, `test_recall_empty_graph`)

**Step 1: Read all test files to understand current mock patterns**

**Step 2: Rewrite test_engine.py**

```python
@pytest.fixture
async def search(storage):
    from services.search_engine.engine import SearchEngine
    return SearchEngine(storage)
```

Rewrite assertions to verify search results contain expected fixture data:

| Test | New assertion |
|------|-------------|
| `test_search_nodes_basic` | results contain fixture nodes with matching content |
| `test_search_nodes_with_filters` | filtered results only contain matching types |
| `test_search_nodes_specific_paths` | BM25-only or vector-only results |
| `test_search_edges_no_graph` | returns empty list (storage.graph=None) |
| `test_search_nodes_min_belief_filter` | only nodes with belief >= threshold |
| `test_search_nodes_status_filter` | only active nodes |
| `test_search_edges_with_graph` | skip if no graph, otherwise verify edge results |
| `test_search_edges_with_filters` | filtered edge results |

Important: The search tests need actual embeddings in the vector index to test vector recall. If `embeddings.json` is not available, the `storage` fixture should still work — vector recall will just return empty, and BM25 recall handles text search.

**Step 3: Rewrite test_bm25_recall.py**

```python
@pytest.fixture
async def bm25(storage):
    from services.search_engine.recall.bm25 import BM25Recall
    return BM25Recall(storage)
```

Test with real fixture node content. Pick a keyword that appears in fixture nodes and verify BM25 finds them.

**Step 4: Rewrite test_vector_recall.py**

```python
@pytest.fixture
async def vector(storage):
    from services.search_engine.recall.vector import VectorRecall
    return VectorRecall(storage)
```

If embeddings are available, test real vector search. If not, test that it returns empty gracefully.

**Step 5: Update test_topology_recall.py (partial)**

Keep `test_recall_no_seeds` and `test_recall_empty_graph` as mock tests (they test edge cases). If graph is available, add 1-2 real topology tests using fixture edges.

**Step 6: Run tests**

Run: `pytest tests/services/test_search_engine/ -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add tests/services/test_search_engine/
git commit -m "test: rewrite search engine tests with real storage

Closes #19"
```

---

### Task 3: Rewrite Inference Engine Tests (Issue #20)

**Files to modify:**
- `tests/services/test_inference_engine/test_engine.py` (5 tests → 4 real, 1 mock)

**Files NOT to modify:**
- `test_factor_graph.py` — pure data structure, no storage
- `test_bp.py` — pure BP algorithm, no storage

**Step 1: Read test_engine.py**

**Step 2: Rewrite test_engine.py**

```python
@pytest.fixture
async def engine(storage):
    from services.inference_engine.engine import InferenceEngine
    return InferenceEngine(storage)
```

| Test | Change |
|------|--------|
| `test_compute_local_bp` | Use fixture node ID, verify beliefs are valid floats in [0,1] |
| `test_compute_local_bp_calls_subgraph` | Remove mock assertion, verify beliefs computed from real subgraph |
| `test_compute_local_bp_loads_edges` | Remove mock assertion, verify specific belief values |
| `test_compute_local_bp_no_graph` | **Keep mock** — set `storage.graph = None`, verify empty result |
| `test_compute_local_bp_custom_params` | Use real storage with custom damping/max_iterations |

Note: Local BP requires graph topology (Neo4j). If the `storage` fixture has no graph, these tests should be skipped with `pytest.mark.skipif` or use a conditional:

```python
@pytest.fixture
async def engine_with_graph(storage):
    if not storage.graph:
        pytest.skip("Neo4j not available")
    engine = InferenceEngine(storage)
    return engine
```

For CI (which has Neo4j service container), all tests should run. Locally without Neo4j, 3-4 tests will skip.

**Step 3: Run tests**

Run: `pytest tests/services/test_inference_engine/ -v`
Expected: ALL PASS (some may skip without Neo4j)

**Step 4: Commit**

```bash
git add tests/services/test_inference_engine/
git commit -m "test: rewrite inference engine tests with real storage

Closes #20"
```

---

### Task 4: Rewrite Review Pipeline Operator Tests (Issue #21)

**Files to modify:**
- `tests/services/test_review_pipeline/test_nn_search_op.py` (2 tests → 1 real, 1 mock)
- `tests/services/test_review_pipeline/test_bp_op.py` (2 tests → 1 real, 1 mock)

**Files NOT to modify (keep mocks — external API dependencies):**
- `test_base.py` — pure pipeline framework
- `test_context.py` — pure data model
- `test_embedding_op.py` — tests StubEmbeddingModel, no storage
- `test_abstraction_op.py` — tests AbstractionLLM interface, no storage
- `test_verify_op.py` — tests VerifyLLM interface, no storage
- `test_llm_client.py` — mocks litellm
- `test_embedding_dashscope.py` — mocks external HTTP
- `test_abstraction_llm.py` — mocks LLMClient
- `test_verify_llm.py` — mocks LLMClient
- `test_xml_parser.py` — pure XML parsing
- `test_integration_api.py` — already uses real APIs (skip if no creds)

**Step 1: Read test_nn_search_op.py and test_bp_op.py**

**Step 2: Rewrite test_nn_search_op.py**

```python
async def test_nn_search_returns_neighbors(storage):
    """NNSearchOperator finds real neighbors from fixture embeddings."""
    if not storage.vector:
        pytest.skip("Vector index not available")

    from services.review_pipeline.operators.nn_search import NNSearchOperator
    from services.review_pipeline.context import PipelineContext

    op = NNSearchOperator(vector_client=storage.vector, k=5)
    ctx = PipelineContext(...)  # Build with fixture embedding
    ctx.embeddings = {0: [0.1] * 128}  # Use a fixture embedding
    result = await op.execute(ctx)
    # Verify nn_results has real node IDs from fixtures
    assert len(result.nn_results) > 0 or not load_fixture_embeddings()
```

Keep `test_nn_search_skips_if_no_embeddings` as-is (tests empty input edge case).

**Step 3: Rewrite test_bp_op.py**

```python
async def test_bp_operator_computes_beliefs(storage):
    """BPOperator computes real beliefs from fixture graph topology."""
    if not storage.graph:
        pytest.skip("Neo4j not available")

    from services.review_pipeline.operators.bp import BPOperator
    from services.review_pipeline.context import PipelineContext

    # Pick a fixture node ID that has edges
    op = BPOperator(storage=storage)
    ctx = PipelineContext(...)
    ctx.affected_node_ids = [fixture_node_id]
    result = await op.execute(ctx)
    assert result.bp_results  # Has belief values
    for belief in result.bp_results.values():
        assert 0.0 <= belief <= 1.0
```

Keep `test_bp_operator_skips_without_graph` as mock (tests degradation).

**Step 4: Run tests**

Run: `pytest tests/services/test_review_pipeline/ -v`
Expected: ALL PASS (NN search and BP may skip without Neo4j/embeddings)

**Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

Run: `ruff check . && ruff format --check .`
Expected: PASS

**Step 6: Commit**

```bash
git add tests/services/test_review_pipeline/
git commit -m "test: rewrite review pipeline operator tests with real storage

Closes #21"
```
