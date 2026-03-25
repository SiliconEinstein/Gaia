# LKM Minimal Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal end-to-end pipeline under `gaia/`: upload `LocalCanonicalGraph` + `LocalParameterization` → persist → global canonicalization (with parameterization integration) → global BP → `BeliefState`.

**Spec:** `docs/specs/2026-03-25-lkm-minimal-pipeline-spec.md` (v0.2)

**Architecture:** New `gaia/` package, independent of old code. Unified `KnowledgeNode` (`lcn_`/`gcn_`) and `FactorNode` (`lcf_`/`gcf_` + `scope`). All knowledge types participate in canonicalization. Embedding vector table (`node_embeddings`) for matching. BP bridged via `gaia.bp` → old `libs.inference`.

**Fixtures:** galileo/newton/einstein from `tests/fixtures/`. No synthetic data.

---

## PR Strategy

| PR | Scope | Verification |
|----|-------|-------------|
| **PR 1: Models + Fixtures** (Chunk 1) | `gaia/libs/models/`, `gaia/core/local_params.py`, `tests/gaia/fixtures/`, `tests/gaia/libs/models/` | `pytest tests/gaia/libs/models/ tests/gaia/fixtures/` 全绿 + owner review 模型 vs graph-ir 文档对齐 |
| **PR 2: Storage** (Chunk 2) | `gaia/libs/storage/`, `gaia/libs/embedding.py`, `gaia/libs/llm.py`, `tests/gaia/libs/storage/` | `pytest tests/gaia/libs/storage/` 全绿（不含 neo4j）+ owner review 表结构 vs spec §2.5 |
| **PR 3: Core Algorithms** (Chunk 3) | `gaia/core/`, `gaia/bp/__init__.py`, `tests/gaia/core/` | `pytest tests/gaia/core/` 全绿 + owner review canonicalize 决策规则 + 参数整合 + BP adapter |
| **PR 4: LKM + E2E** (Chunk 4-5) | `gaia/lkm/`, `tests/gaia/lkm/`, `tests/gaia/test_e2e_pipeline.py` | `pytest tests/gaia/` 全部全绿 + E2E 3 包 pipeline 通过 + FastAPI smoke test |

执行顺序严格 PR 1 → 2 → 3 → 4。

---

## File Structure

```
gaia/
  __init__.py
  libs/
    __init__.py
    models/
      __init__.py              # Re-exports
      graph_ir.py              # KnowledgeNode (lcn_/gcn_), FactorNode (lcf_/gcf_ + scope),
                               # LocalCanonicalGraph, GlobalCanonicalGraph
      parameterization.py      # PriorRecord, FactorParamRecord, ParameterizationSource, ResolutionPolicy
      belief_state.py          # BeliefState
      binding.py               # CanonicalBinding, BindingDecision
    storage/
      __init__.py
      config.py                # StorageConfig
      base.py                  # ABC: ContentStore, GraphStore
      lance.py                 # LanceDB implementation (knowledge_nodes, factor_nodes,
                               # canonical_bindings, prior_records, factor_param_records,
                               # param_sources, belief_states, node_embeddings)
      neo4j.py                 # Neo4j implementation
      manager.py               # StorageManager
    embedding.py               # Port from libs/embedding.py
    llm.py                     # Port from libs/llm.py
  core/
    __init__.py
    local_params.py            # LocalParameterization (transient)
    matching.py                # Similarity matching (queries node_embeddings table)
    canonicalize.py            # Global canonicalization + param integration
    global_bp.py               # Param assembly + BP orchestration + adapter (new→old models)
  lkm/
    __init__.py
    pipelines/
      __init__.py
      run_ingest.py            # Orchestrate: persist_local → canonicalize → persist_global
      run_global_bp.py         # Orchestrate: global BP
      run_full.py              # Full pipeline
    services/
      __init__.py
      app.py                   # FastAPI factory
      deps.py                  # DI
      routes/
        __init__.py
        packages.py            # POST /api/packages/ingest
        knowledge.py           # GET /api/knowledge/{id}
        inference.py           # POST /api/inference/run
  bp/
    __init__.py                # Bridge: re-export libs.inference
  review/__init__.py           # Placeholder
  cli/__init__.py              # Placeholder

tests/gaia/
  libs/models/test_graph_ir.py, test_parameterization.py, test_belief_state.py, test_binding.py
  libs/storage/test_lance.py, test_neo4j.py, test_manager.py
  core/test_matching.py, test_canonicalize.py, test_global_bp.py
  lkm/test_pipelines.py, services/test_routes.py
  fixtures/graphs.py, parameterizations.py
  test_e2e_pipeline.py
```

---

## Chunk 1: Models + Fixtures (PR 1)

### Task 1.1: Scaffolding

Create all directories and `__init__.py` files. `gaia/bp/__init__.py` bridges `libs.inference`.

### Task 1.2: KnowledgeNode + FactorNode + Graph Containers

**Files:** `gaia/libs/models/graph_ir.py`, `tests/gaia/libs/models/test_graph_ir.py`

**Spec:** graph-ir.md §1 (KnowledgeNode), §2 (FactorNode)

**Key design points for implementing agent:**

`KnowledgeNode`: unified data class.
- If `id` not provided and `content` not None → compute `lcn_{sha256[:16]}`
- If `id` provided (e.g., `gcn_*`) → use as-is
- All fields from graph-ir.md §1.1: `id`, `type`, `parameters`, `source_refs`, `metadata`, `content`, `provenance`, `representative_lcn`, `member_local_nodes`

`FactorNode`: unified data class with `scope` field.
- `factor_id`: `lcf_{sha256[:16]}` (local) or `gcf_{sha256[:16]}` (global), computed from `scope + category + sorted(premises) + conclusion`
- `scope`: `"local"` | `"global"` — required field
- Invariants enforced via `@model_validator`: §2.3 invariant 1 (candidate/permanent infer needs reasoning_type), §2.3 invariant 6 (bilateral types need conclusion=None, premises>=2)

`LocalCanonicalGraph`: `scope="local"`, `graph_hash = sha256(canonical JSON)`, `knowledge_nodes`, `factor_nodes`

`GlobalCanonicalGraph`: `scope="global"`, `knowledge_nodes` (gcn_ prefixed), `factor_nodes` (gcf_ prefixed)

**Tests must cover:** local/global node creation, deterministic ID, different content → different ID, type affects ID, parameter sort order, serialization roundtrip, all invariant violations.

### Task 1.3: Parameterization Models

**Files:** `gaia/libs/models/parameterization.py`, `tests/gaia/libs/models/test_parameterization.py`

`PriorRecord`, `FactorParamRecord`: Cromwell clamping in `model_post_init`. `ResolutionPolicy`: validate `source_id` when `strategy="source"`. `ParameterizationSource`: model, policy, config.

### Task 1.4: BeliefState + CanonicalBinding

**Files:** `gaia/libs/models/belief_state.py`, `gaia/libs/models/binding.py`, tests for both.

Straightforward Pydantic models. `BindingDecision` enum: `match_existing`, `create_new`, `equivalent_candidate`.

### Task 1.5: Re-exports + LocalParameterization

**Files:** `gaia/libs/models/__init__.py`, `gaia/core/local_params.py`

`LocalParameterization` is transient — `graph_hash`, `node_priors: dict[str, float]`, `factor_parameters: dict[str, float]`. Lives in `core/`, not `libs/models/`.

### Task 1.6: Fixtures

**Files:** `tests/gaia/fixtures/graphs.py`, `tests/gaia/fixtures/parameterizations.py`, `tests/gaia/fixtures/test_fixtures.py`

`make_galileo_falling_bodies()`, `make_newton_gravity()`, `make_einstein_equivalence()`, `make_minimal_claim_pair()` — all return `LocalCanonicalGraph`. `make_default_local_params(graph)` returns `LocalParameterization`.

Key: galileo "vacuum prediction" content == newton's same claim → same `lcn_` ID → cross-package match.

---

## Chunk 2: Storage (PR 2)

### Task 2.1: Config + ABCs

**Files:** `gaia/libs/storage/config.py`, `gaia/libs/storage/base.py`

`ContentStore` ABC operates on unified `KnowledgeNode` and `FactorNode`:
- `write_knowledge_nodes(nodes)`, `get_knowledge_nodes(prefix=None)` — prefix filter `lcn_`/`gcn_`
- `write_factor_nodes(factors)`, `get_factor_nodes(scope=None)` — filter by `scope` field
- `write_node_embeddings(gcn_id, vector)`, `get_node_embedding(gcn_id)`, `search_similar_nodes(query_vector, top_k, type_filter)`
- Standard CRUD for bindings, prior_records, factor_param_records, param_sources, belief_states

`GraphStore` ABC: `write_nodes`, `write_factors`, `get_neighbors`, `get_subgraph`, `clean_all`

### Task 2.2: LanceDB Content Store

**Files:** `gaia/libs/storage/lance.py`, `tests/gaia/libs/storage/test_lance.py`

8 tables: `knowledge_nodes`, `factor_nodes`, `canonical_bindings`, `prior_records`, `factor_param_records`, `param_sources`, `belief_states`, `node_embeddings`.

`node_embeddings` table: `gcn_id (str)`, `vector (list[float])`, `content_preview (str)`. Used by `matching.py` for similarity search.

Tests: write+read roundtrip per table, prefix filtering for knowledge nodes, scope filtering for factors, embedding vector write+search, clean_all.

### Task 2.3: Neo4j Graph Store

**Files:** `gaia/libs/storage/neo4j.py`, `tests/gaia/libs/storage/test_neo4j.py`

Tests marked `@pytest.mark.neo4j`. Nodes as `(:KnowledgeNode {id, type})`, factors via `:PREMISE`/`:CONCLUSION` edges.

### Task 2.4: StorageManager

**Files:** `gaia/libs/storage/manager.py`, `tests/gaia/libs/storage/test_manager.py`

Delegates to content store + optional graph store. No three-write atomicity in MVP (deferred, see spec §6).

### Task 2.5: Port Embedding + LLM

**Files:** `gaia/libs/embedding.py`, `gaia/libs/llm.py`

Port from old code. Logic unchanged.

---

## Chunk 3: Core Algorithms (PR 3)

### Task 3.1: Matching

**Files:** `gaia/core/matching.py`, `tests/gaia/core/test_matching.py`

`find_best_match(query_node, embedding_model, storage, threshold=0.90) → KnowledgeNode | None`

Approach:
1. Embed query node content
2. Search `node_embeddings` table via `storage.search_similar_nodes(vector, top_k, type_filter=query_node.type)`
3. Return best match above threshold, or None
4. TF-IDF fallback when no embedding model

Tests: identical content matches, different type never matches, below threshold returns None.

### Task 3.2: Canonicalization

**Files:** `gaia/core/canonicalize.py`, `tests/gaia/core/test_canonicalize.py`

```python
async def canonicalize_package(
    local_graph, local_params, global_graph,
    package_id, version, embedding_model, storage, threshold=0.90
) -> CanonicalizationResult
```

**All knowledge types** (claim, setting, question, template) participate — per graph-ir.md §3.2.

Key steps per spec §3.2:
1. Classify nodes (premise-only / conclusion / both)
2. Match each against global graph via `matching.find_best_match()`
3. Apply §3.1 decision rules
4. Factor lifting: lcn→gcn ID rewrite, `scope="local"` → `scope="global"`, drop steps/weak_points, prefix `lcf_` → `gcf_`
5. Parameterization integration: convert `local_params` to `PriorRecord`/`FactorParamRecord` with gcn_/gcf_ IDs
6. Write new node embeddings for newly created gcn_ nodes

Tests: first package all create_new, param conversion lcn→gcn, factor lifting drops steps, global factors have gcf_ prefix.

### Task 3.3: Global BP + Adapter

**Files:** `gaia/core/global_bp.py`, `tests/gaia/core/test_global_bp.py`

Two responsibilities:

**1. Parameter assembly** (`assemble_parameterization`): apply ResolutionPolicy to select per-node/factor values from atomic records. Tests: latest picks newest, source filters, prior_cutoff filters.

**2. BP adapter + execution** (`run_global_bp`): convert new `GlobalCanonicalGraph` + assembled params → old `FactorGraph` format → run `BeliefPropagation` → wrap in `BeliefState`.

Adapter mapping (new → old):
- `KnowledgeNode` (type=claim, gcn_ prefix) → `FactorGraph.add_variable(int_id, prior)`
- Non-claim premises skipped (no BP edge)
- `FactorNode` → `FactorGraph.add_factor(...)` with edge_type mapped from `ReasoningType`
- `ReasoningType.ENTAILMENT` → old `"deduction"`, `CONTRADICT` → `"contradiction"`, etc.

Tests: minimal graph produces valid BeliefState, only claim nodes have beliefs, galileo contradiction affects values.

---

## Chunk 4: LKM + E2E (PR 4)

### Task 4.1: Pipelines

**Files:** `gaia/lkm/pipelines/run_ingest.py`, `run_global_bp.py`, `run_full.py`, `tests/gaia/lkm/test_pipelines.py`

`run_ingest` orchestrates spec modules 1-3:
```python
async def run_ingest(local_graph, local_params, package_id, version, storage, embedding_model):
    # Module 1: persist local
    await storage.write_knowledge_nodes(local_graph.knowledge_nodes)
    await storage.write_factor_nodes(local_graph.factor_nodes)
    # Module 2: canonicalize (loads global graph from storage internally)
    result = await canonicalize_package(local_graph, local_params, ..., storage, embedding_model)
    # Module 3: persist global
    await storage.write_knowledge_nodes(result.new_global_nodes)
    await storage.write_factor_nodes(result.global_factors)
    await storage.write_bindings(result.bindings)
    await storage.write_prior_records(result.prior_records)
    await storage.write_factor_param_records(result.factor_param_records)
    await storage.write_param_source(result.param_source)
    return result
```

`run_global_bp`: load global graph + params from storage, call `core.global_bp.run_global_bp()`, persist BeliefState.

`run_full`: CLI entry with `--input-dir`, `--lancedb-path`, `--clean`.

### Task 4.2: FastAPI Services

**Files:** `gaia/lkm/services/app.py`, `deps.py`, `routes/packages.py`, `knowledge.py`, `inference.py`, `tests/gaia/lkm/services/test_routes.py`

`POST /api/packages/ingest` → calls `run_ingest`. `POST /api/inference/run` → calls `run_global_bp`. Read endpoints for knowledge and beliefs.

### Task 4.3: E2E Test

**Files:** `tests/gaia/test_e2e_pipeline.py`

Ingest galileo + newton + einstein → verify global graph → run global BP → verify BeliefState has beliefs for all claim nodes, all values in Cromwell bounds.
