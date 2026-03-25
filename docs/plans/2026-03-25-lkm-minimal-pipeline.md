# LKM Minimal Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal end-to-end pipeline under a new `gaia/` package: upload a `LocalCanonicalGraph` + `LocalParameterization` → persist → global canonicalization (with parameterization integration) → global BP → produce `BeliefState`.

**Architecture:** New `gaia/` top-level package, completely independent of old `libs/`/`services/`/`scripts/`. Models rewritten from scratch per `docs/foundations/graph-ir/`. `KnowledgeNode` and `FactorNode` are unified data classes shared by local and global layers (distinguished by `id` prefix `lcn_`/`gcn_`). Storage on LanceDB (content+vector) + Neo4j (topology). Core algorithms in a shared `core/` layer. LKM entry points in `pipelines/` (batch) and `services/` (API), both thin orchestration layers.

**Tech Stack:** Python 3.12+, Pydantic v2, LanceDB, Neo4j, NumPy, FastAPI

**Spec:** `docs/specs/2026-03-25-lkm-minimal-pipeline-spec.md`

**Key foundation docs:**
- `docs/foundations/graph-ir/` — Graph IR structural contract (all models derive from here)
- `docs/foundations/lkm/` — Pipeline stages, storage schema, canonicalization, global inference

**BP engine:** `gaia/bp/` is a placeholder. `core/global_bp.py` imports from existing `libs.inference` via `gaia.bp` bridge.

**Fixtures:** Use existing galileo/newton/einstein examples from `tests/fixtures/`. Do not invent synthetic data.

---

## File Structure

```
gaia/
  __init__.py

  libs/
    __init__.py
    models/
      __init__.py              # Re-exports all model classes
      graph_ir.py              # KnowledgeNode, FactorNode, LocalCanonicalGraph, GlobalCanonicalGraph
      parameterization.py      # PriorRecord, FactorParamRecord, ParameterizationSource, ResolutionPolicy
      belief_state.py          # BeliefState
      binding.py               # CanonicalBinding
    storage/
      __init__.py
      config.py                # StorageConfig (env → config)
      base.py                  # ABC: ContentStore, GraphStore
      lance.py                 # LanceDB: content + vector + FTS
      neo4j.py                 # Neo4j: topology
      manager.py               # StorageManager
    embedding.py               # EmbeddingModel ABC + DPEmbeddingModel + StubEmbeddingModel
    llm.py                     # LLM client (litellm wrapper)

  core/
    __init__.py
    local_params.py            # LocalParameterization (transient, not Graph IR contract)
    matching.py                # Embedding cosine + TF-IDF similarity matching
    canonicalize.py            # Global canonicalization + parameterization integration
    global_bp.py               # Assemble Parameterization → run BP → produce BeliefState

  lkm/
    __init__.py
    pipelines/
      __init__.py
      run_ingest.py            # Orchestrate modules 1-3: persist_local → canonicalize → persist_global
      run_global_bp.py         # Orchestrate module 4: global BP
      run_full.py              # Full pipeline orchestrator
    services/
      __init__.py
      app.py                   # FastAPI app factory
      deps.py                  # DI (StorageManager, EmbeddingModel)
      routes/
        __init__.py
        packages.py            # POST /packages/ingest, GET /packages/{id}
        knowledge.py           # GET /knowledge/{id}, GET /knowledge/{id}/beliefs
        inference.py           # POST /inference/run, GET /beliefs/{run_id}

  bp/
    __init__.py                # Placeholder — re-exports from libs.inference
  review/
    __init__.py                # Placeholder
  cli/
    __init__.py                # Placeholder

tests/gaia/
  __init__.py
  libs/
    __init__.py
    models/
      __init__.py
      test_graph_ir.py
      test_parameterization.py
      test_belief_state.py
      test_binding.py
    storage/
      __init__.py
      test_lance.py
      test_neo4j.py
      test_manager.py
  core/
    __init__.py
    test_matching.py
    test_canonicalize.py
    test_global_bp.py
  lkm/
    __init__.py
    test_pipelines.py
    services/
      __init__.py
      test_routes.py
  fixtures/
    __init__.py
    graphs.py                  # Builder functions for test graphs (galileo, newton, einstein)
    parameterizations.py       # Builder functions for LocalParameterization + expected params
```

---

## Chunk 1: Models — Graph IR Data Definitions

All Pydantic v2 models mirroring `docs/foundations/graph-ir/`. **Key change from previous plan:** `KnowledgeNode` is a single unified data class for both local (`lcn_`) and global (`gcn_`) layers — no separate `GlobalCanonicalNode`.

### Task 1.1: Project Scaffolding

**Files:**
- Create: all `__init__.py` files per file structure above

- [ ] **Step 1: Create package directory structure**

```bash
mkdir -p gaia/libs/models gaia/libs/storage gaia/core gaia/lkm/pipelines gaia/lkm/services/routes gaia/bp gaia/review gaia/cli
mkdir -p tests/gaia/libs/models tests/gaia/libs/storage tests/gaia/core tests/gaia/lkm/services tests/gaia/fixtures
```

- [ ] **Step 2: Create all `__init__.py` files**

Every directory gets an empty `__init__.py`, except `gaia/bp/__init__.py` which bridges old code:

```python
# gaia/bp/__init__.py
"""BP engine — placeholder, re-exports from libs.inference until migration."""
from libs.inference.factor_graph import FactorGraph, CROMWELL_EPS
from libs.inference.bp import BeliefPropagation, BPDiagnostics
```

- [ ] **Step 3: Verify import works**

```bash
python -c "import gaia; print('gaia package OK')"
```

- [ ] **Step 4: Commit**

```bash
git add gaia/ tests/gaia/
git commit -m "feat: scaffold gaia/ package structure with empty modules"
```

### Task 1.2: KnowledgeNode and FactorNode Models

**Files:**
- Create: `gaia/libs/models/graph_ir.py`
- Create: `tests/gaia/libs/models/test_graph_ir.py`

**Spec reference:** `docs/foundations/graph-ir/graph-ir.md` §1 (KnowledgeNode) and §2 (FactorNode)

**Key design:** `KnowledgeNode` is the unified data class for both local and global layers. Local nodes have `content` filled and `id` starting with `lcn_`. Global nodes have `representative_lcn` filled, `content` usually None, and `id` starting with `gcn_`.

- [ ] **Step 1: Write failing tests for KnowledgeNode**

```python
# tests/gaia/libs/models/test_graph_ir.py
"""Tests for Graph IR models — locks down every constraint from graph-ir.md."""
import pytest
from gaia.libs.models.graph_ir import (
    KnowledgeNode,
    KnowledgeType,
    FactorNode,
    FactorCategory,
    FactorStage,
    ReasoningType,
    Step,
    SourceRef,
    Parameter,
    LocalCanonicalGraph,
    GlobalCanonicalGraph,
    LocalCanonicalRef,
    PackageRef,
)


class TestKnowledgeNode:
    """§1: Knowledge nodes represent propositions. Unified data class for local + global."""

    def test_local_claim_node(self):
        """Local layer: content filled, id starts with lcn_."""
        node = KnowledgeNode(
            type=KnowledgeType.CLAIM,
            content="该样本在 90 K 以下表现出超导性",
        )
        assert node.type == KnowledgeType.CLAIM
        assert node.id.startswith("lcn_")
        assert node.content is not None

    def test_global_claim_node(self):
        """Global layer: id starts with gcn_, content usually None, has representative_lcn."""
        node = KnowledgeNode(
            id="gcn_abc123",
            type=KnowledgeType.CLAIM,
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_xyz", package_id="pkg1", version="1.0"
            ),
            member_local_nodes=[
                LocalCanonicalRef(local_canonical_id="lcn_xyz", package_id="pkg1", version="1.0")
            ],
            provenance=[PackageRef(package_id="pkg1", version="1.0")],
        )
        assert node.id.startswith("gcn_")
        assert node.content is None
        assert node.representative_lcn is not None

    def test_setting_node(self):
        node = KnowledgeNode(
            type=KnowledgeType.SETTING,
            content="高温超导研究的当前进展",
        )
        assert node.type == KnowledgeType.SETTING

    def test_template_node_with_parameters(self):
        node = KnowledgeNode(
            type=KnowledgeType.TEMPLATE,
            content="∀{x}. superconductor({x}) → zero_resistance({x})",
            parameters=[Parameter(name="x", type="material")],
        )
        assert len(node.parameters) == 1

    def test_local_id_deterministic_sha256(self):
        """§1.1: local id = SHA-256(type + content + sorted(parameters))."""
        node_a = KnowledgeNode(type=KnowledgeType.CLAIM, content="X superconducts")
        node_b = KnowledgeNode(type=KnowledgeType.CLAIM, content="X superconducts")
        assert node_a.id == node_b.id
        assert node_a.id.startswith("lcn_")

    def test_different_content_different_id(self):
        node_a = KnowledgeNode(type=KnowledgeType.CLAIM, content="A")
        node_b = KnowledgeNode(type=KnowledgeType.CLAIM, content="B")
        assert node_a.id != node_b.id

    def test_different_type_different_id(self):
        claim = KnowledgeNode(type=KnowledgeType.CLAIM, content="X")
        setting = KnowledgeNode(type=KnowledgeType.SETTING, content="X")
        assert claim.id != setting.id

    def test_parameters_sorted_for_id(self):
        node_a = KnowledgeNode(
            type=KnowledgeType.TEMPLATE, content="f({x}, {y})",
            parameters=[Parameter(name="x", type="int"), Parameter(name="y", type="str")],
        )
        node_b = KnowledgeNode(
            type=KnowledgeType.TEMPLATE, content="f({x}, {y})",
            parameters=[Parameter(name="y", type="str"), Parameter(name="x", type="int")],
        )
        assert node_a.id == node_b.id

    def test_global_id_preserved_as_given(self):
        """Global nodes get registry-allocated IDs, not computed."""
        node = KnowledgeNode(id="gcn_registry_001", type=KnowledgeType.CLAIM)
        assert node.id == "gcn_registry_001"

    def test_serialization_roundtrip(self):
        node = KnowledgeNode(
            type=KnowledgeType.CLAIM,
            content="该样本在 90 K 以下表现出超导性",
            metadata={"schema": "observation", "instrument": "四探针电阻率测量"},
            source_refs=[SourceRef(package="pkg1", version="1.0")],
        )
        roundtrip = KnowledgeNode.model_validate_json(node.model_dump_json())
        assert roundtrip == node
```

- [ ] **Step 2: Write failing tests for FactorNode**

```python
class TestFactorNode:
    """§2: Factor nodes — unified data class for local + global."""

    def test_infer_factor_initial(self):
        factor = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_a"],
            conclusion="lcn_b",
            steps=[Step(reasoning="基于超导样品的电阻率骤降...")],
        )
        assert factor.factor_id.startswith("f_")
        assert factor.reasoning_type is None  # initial can be None

    def test_candidate_infer_requires_reasoning_type(self):
        """§2.3 invariant 1."""
        with pytest.raises(ValueError):
            FactorNode(
                category=FactorCategory.INFER,
                stage=FactorStage.CANDIDATE,
                reasoning_type=None,
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_equivalent_has_no_conclusion_and_ge_2_premises(self):
        """§2.3 invariant 6."""
        factor = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.CANDIDATE,
            reasoning_type=ReasoningType.EQUIVALENT,
            premises=["lcn_a", "lcn_b"],
            conclusion=None,
        )
        assert factor.conclusion is None

    def test_bilateral_with_lt_2_premises_rejected(self):
        with pytest.raises(ValueError):
            FactorNode(
                category=FactorCategory.INFER,
                stage=FactorStage.CANDIDATE,
                reasoning_type=ReasoningType.EQUIVALENT,
                premises=["lcn_a"],
                conclusion=None,
            )

    def test_global_factor_no_steps(self):
        """Global layer: steps and weak_points are None."""
        factor = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=["gcn_a"],
            conclusion="gcn_b",
            steps=None,
            weak_points=None,
        )
        assert factor.steps is None
        assert factor.weak_points is None

    def test_factor_id_deterministic(self):
        f1 = FactorNode(
            category=FactorCategory.INFER, stage=FactorStage.INITIAL,
            premises=["lcn_a", "lcn_b"], conclusion="lcn_c",
        )
        f2 = FactorNode(
            category=FactorCategory.INFER, stage=FactorStage.INITIAL,
            premises=["lcn_a", "lcn_b"], conclusion="lcn_c",
        )
        assert f1.factor_id == f2.factor_id

    def test_serialization_roundtrip(self):
        factor = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.CANDIDATE,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=["lcn_a"], conclusion="lcn_b",
            steps=[Step(reasoning="step 1")],
            weak_points=["assumption may not hold"],
        )
        roundtrip = FactorNode.model_validate_json(factor.model_dump_json())
        assert roundtrip == factor
```

- [ ] **Step 3: Write failing tests for graph containers**

```python
class TestLocalCanonicalGraph:
    def test_graph_creation_and_hash(self):
        claim = KnowledgeNode(type=KnowledgeType.CLAIM, content="A superconducts")
        factor = FactorNode(
            category=FactorCategory.INFER, stage=FactorStage.INITIAL,
            premises=[claim.id], conclusion=claim.id,
        )
        graph = LocalCanonicalGraph(knowledge_nodes=[claim], factor_nodes=[factor])
        assert graph.scope == "local"
        assert graph.graph_hash.startswith("sha256:")

    def test_hash_deterministic(self):
        nodes = [KnowledgeNode(type=KnowledgeType.CLAIM, content="X")]
        g1 = LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=[])
        g2 = LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=[])
        assert g1.graph_hash == g2.graph_hash


class TestGlobalCanonicalGraph:
    def test_global_graph_with_gcn_nodes(self):
        gcn = KnowledgeNode(
            id="gcn_abc", type=KnowledgeType.CLAIM,
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_xyz", package_id="pkg1", version="1.0"
            ),
            member_local_nodes=[
                LocalCanonicalRef(local_canonical_id="lcn_xyz", package_id="pkg1", version="1.0")
            ],
            provenance=[PackageRef(package_id="pkg1", version="1.0")],
        )
        graph = GlobalCanonicalGraph(knowledge_nodes=[gcn], factor_nodes=[])
        assert graph.scope == "global"
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
pytest tests/gaia/libs/models/test_graph_ir.py -v
```

- [ ] **Step 5: Implement `gaia/libs/models/graph_ir.py`**

Unified `KnowledgeNode` class with all fields from graph-ir.md §1.1. Key behavior:
- If `id` is not provided and `content` is not None → compute `lcn_` ID via SHA-256
- If `id` is provided (e.g., `gcn_*`) → use as-is
- `FactorNode` validation: §2.3 invariants enforced via `@model_validator`
- Graph containers: `LocalCanonicalGraph` (auto-computes `graph_hash`), `GlobalCanonicalGraph`

- [ ] **Step 6: Run tests, verify pass**
- [ ] **Step 7: Commit**

```bash
git commit -m "feat(models): implement unified KnowledgeNode, FactorNode, graph containers"
```

### Task 1.3: Parameterization Models

**Files:**
- Create: `gaia/libs/models/parameterization.py`
- Create: `tests/gaia/libs/models/test_parameterization.py`

**Spec reference:** `docs/foundations/graph-ir/parameterization.md`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/libs/models/test_parameterization.py
import pytest
from gaia.libs.models.parameterization import (
    PriorRecord, FactorParamRecord, ParameterizationSource,
    ResolutionPolicy, CROMWELL_EPS,
)


class TestPriorRecord:
    def test_creation(self):
        r = PriorRecord(gcn_id="gcn_x", value=0.7, source_id="src_001")
        assert r.value == 0.7

    def test_cromwell_clamp_zero(self):
        r = PriorRecord(gcn_id="gcn_x", value=0.0, source_id="s")
        assert r.value == CROMWELL_EPS

    def test_cromwell_clamp_one(self):
        r = PriorRecord(gcn_id="gcn_x", value=1.0, source_id="s")
        assert r.value == 1.0 - CROMWELL_EPS


class TestFactorParamRecord:
    def test_cromwell_clamp(self):
        r = FactorParamRecord(factor_id="f_x", probability=0.0, source_id="s")
        assert r.probability == CROMWELL_EPS


class TestResolutionPolicy:
    def test_latest(self):
        p = ResolutionPolicy(strategy="latest")
        assert p.strategy == "latest"

    def test_source_without_id_rejected(self):
        with pytest.raises(ValueError):
            ResolutionPolicy(strategy="source", source_id=None)
```

- [ ] **Step 2: Run to verify fail**
- [ ] **Step 3: Implement** — Same as before: `CROMWELL_EPS = 1e-3`, clamping in `model_post_init`, `ResolutionPolicy` with validation.
- [ ] **Step 4: Run, verify pass**
- [ ] **Step 5: Commit**

### Task 1.4: BeliefState Model

**Files:**
- Create: `gaia/libs/models/belief_state.py`
- Create: `tests/gaia/libs/models/test_belief_state.py`

- [ ] **Step 1: Write failing tests** — creation, serialization roundtrip, empty beliefs edge case.
- [ ] **Step 2: Implement** — Straightforward Pydantic model per `belief-state.md`.
- [ ] **Step 3: Run, verify pass**
- [ ] **Step 4: Commit**

### Task 1.5: CanonicalBinding Model

**Files:**
- Create: `gaia/libs/models/binding.py`
- Create: `tests/gaia/libs/models/test_binding.py`

- [ ] **Step 1: Write failing tests** — `match_existing`, `create_new`, `equivalent_candidate` decisions.
- [ ] **Step 2: Implement** — `BindingDecision` enum + `CanonicalBinding` model per graph-ir.md §3.4.
- [ ] **Step 3: Run, verify pass**
- [ ] **Step 4: Commit**

### Task 1.6: Models `__init__.py` Re-exports + LocalParameterization

**Files:**
- Modify: `gaia/libs/models/__init__.py`
- Create: `gaia/core/local_params.py`

- [ ] **Step 1: Write models `__init__.py` re-exports** — all public types from graph_ir, parameterization, belief_state, binding.

- [ ] **Step 2: Write `gaia/core/local_params.py`**

```python
# gaia/core/local_params.py
"""LocalParameterization — transient container, not part of Graph IR contract."""
from pydantic import BaseModel


class LocalParameterization(BaseModel):
    """Temporary parameter container from CLI build/review. Not persisted."""
    graph_hash: str
    node_priors: dict[str, float] = {}       # lcn_id → prior
    factor_parameters: dict[str, float] = {} # factor_id → conditional_probability
```

- [ ] **Step 3: Verify imports**

```bash
python -c "from gaia.libs.models import KnowledgeNode, BeliefState, CanonicalBinding; print('OK')"
python -c "from gaia.core.local_params import LocalParameterization; print('OK')"
```

- [ ] **Step 4: Run all model tests**
- [ ] **Step 5: Commit**

### Task 1.7: Test Fixtures — Galileo/Newton/Einstein Graphs

**Files:**
- Create: `tests/gaia/fixtures/graphs.py`
- Create: `tests/gaia/fixtures/parameterizations.py`
- Create: `tests/gaia/fixtures/test_fixtures.py`

- [ ] **Step 1: Write fixture graph builders**

Build `make_galileo_falling_bodies()`, `make_newton_gravity()`, `make_einstein_equivalence()`, `make_minimal_claim_pair()` returning `LocalCanonicalGraph` instances from real scientific examples (see `tests/fixtures/examples/`).

Key: galileo's "vacuum prediction" and newton's reference to the same claim use identical `content` → same `lcn_` ID → cross-package match candidate.

- [ ] **Step 2: Write fixture parameterization builders**

```python
# tests/gaia/fixtures/parameterizations.py
from gaia.core.local_params import LocalParameterization
from gaia.libs.models import LocalCanonicalGraph, KnowledgeType


def make_default_local_params(graph: LocalCanonicalGraph, prior: float = 0.5, factor_prob: float = 0.8) -> LocalParameterization:
    """Create default LocalParameterization for a graph."""
    node_priors = {
        n.id: prior for n in graph.knowledge_nodes if n.type == KnowledgeType.CLAIM
    }
    factor_params = {f.factor_id: factor_prob for f in graph.factor_nodes}
    return LocalParameterization(
        graph_hash=graph.graph_hash,
        node_priors=node_priors,
        factor_parameters=factor_params,
    )
```

- [ ] **Step 3: Write smoke tests for fixtures**

Verify each builder produces valid graphs with expected node/factor counts and cross-package content matching.

- [ ] **Step 4: Run tests, commit**

---

## Chunk 2: Storage Layer

Unified tables for `knowledge_nodes` and `factor_nodes` (local + global in same table, filtered by `id` prefix).

### Task 2.1: StorageConfig

**Files:**
- Create: `gaia/libs/storage/config.py`

- [ ] **Step 1: Implement** — Port from `libs/storage/config.py`, Pydantic settings with `GAIA_` prefix.
- [ ] **Step 2: Commit**

### Task 2.2: Storage ABCs

**Files:**
- Create: `gaia/libs/storage/base.py`

- [ ] **Step 1: Define ContentStore and GraphStore interfaces**

`ContentStore` methods operate on unified `KnowledgeNode` (not separate local/global types):

```python
class ContentStore(ABC):
    async def write_knowledge_nodes(self, nodes: list[KnowledgeNode]) -> None: ...
    async def write_factor_nodes(self, factors: list[FactorNode]) -> None: ...
    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None: ...
    async def write_prior_records(self, records: list[PriorRecord]) -> None: ...
    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None: ...
    async def write_param_source(self, source: ParameterizationSource) -> None: ...
    async def write_belief_state(self, state: BeliefState) -> None: ...

    async def get_node(self, node_id: str) -> KnowledgeNode | None: ...
    async def get_knowledge_nodes(self, prefix: str | None = None) -> list[KnowledgeNode]: ...
    async def get_factor_nodes(self, prefix: str | None = None) -> list[FactorNode]: ...
    async def get_bindings(self, package_id: str | None = None) -> list[CanonicalBinding]: ...
    async def get_prior_records(self, gcn_id: str | None = None) -> list[PriorRecord]: ...
    async def get_factor_param_records(self, factor_id: str | None = None) -> list[FactorParamRecord]: ...
    async def get_belief_states(self, limit: int = 10) -> list[BeliefState]: ...
    async def clean_all(self) -> None: ...

class GraphStore(ABC):
    async def write_nodes(self, nodes: list[KnowledgeNode]) -> None: ...
    async def write_factors(self, factors: list[FactorNode]) -> None: ...
    async def get_neighbors(self, node_id: str) -> list[str]: ...
    async def get_subgraph(self, node_ids: list[str], depth: int = 1) -> tuple[list[str], list[str]]: ...
    async def clean_all(self) -> None: ...
```

Note: `get_knowledge_nodes(prefix="gcn_")` returns global nodes; `get_knowledge_nodes(prefix="lcn_")` returns local.

- [ ] **Step 2: Commit**

### Task 2.3: LanceDB Content Store

**Files:**
- Create: `gaia/libs/storage/lance.py`
- Create: `tests/gaia/libs/storage/test_lance.py`

- [ ] **Step 1: Write failing tests**

Test write + read roundtrip for each table: knowledge_nodes (both lcn_ and gcn_), factor_nodes, bindings, prior_records, factor_param_records, belief_states. Test prefix filtering. Test `clean_all`.

- [ ] **Step 2: Implement LanceContentStore**

Unified `knowledge_nodes` table with columns: `id`, `type`, `content`, `parameters_json`, `source_refs_json`, `metadata_json`, `representative_lcn_json`, `member_local_nodes_json`, `provenance_json`, `package_id`, `version`. Query by prefix: `WHERE id LIKE 'gcn_%'`.

Similarly unified `factor_nodes` table.

- [ ] **Step 3: Run, verify pass**
- [ ] **Step 4: Commit**

### Task 2.4: Neo4j Graph Store

**Files:**
- Create: `gaia/libs/storage/neo4j.py`
- Create: `tests/gaia/libs/storage/test_neo4j.py`

- [ ] **Step 1: Write failing tests** (marked `@pytest.mark.neo4j`)
- [ ] **Step 2: Implement Neo4jGraphStore** — nodes as `(:KnowledgeNode {id, type})`, factors create `:PREMISE`/`:CONCLUSION` edges.
- [ ] **Step 3: Run (with Neo4j), commit**

### Task 2.5: StorageManager

**Files:**
- Create: `gaia/libs/storage/manager.py`
- Create: `tests/gaia/libs/storage/test_manager.py`

- [ ] **Step 1: Write failing tests** — init, write+read through manager, graph store optional.
- [ ] **Step 2: Implement** — delegates to content store + optional graph store.
- [ ] **Step 3: Run, commit**

### Task 2.6: Port Embedding and LLM

**Files:**
- Create: `gaia/libs/embedding.py` (port from `libs/embedding.py`)
- Create: `gaia/libs/llm.py` (port from `libs/llm.py`)

- [ ] **Step 1: Port, verify imports**
- [ ] **Step 2: Commit**

---

## Chunk 3: Core Algorithms

### Task 3.1: Matching — Similarity Engine

**Files:**
- Create: `gaia/core/matching.py`
- Create: `tests/gaia/core/test_matching.py`

- [ ] **Step 1: Write failing tests** — identical content matches, different type never matches, below threshold returns None, TF-IDF fallback.
- [ ] **Step 2: Implement** — `find_best_match(query: KnowledgeNode, candidates: list[KnowledgeNode], ...) → KnowledgeNode | None`. Type filter first, then embedding cosine / TF-IDF.
- [ ] **Step 3: Run, commit**

### Task 3.2: Global Canonicalization

**Files:**
- Create: `gaia/core/canonicalize.py`
- Create: `tests/gaia/core/test_canonicalize.py`

**Spec reference:** spec §3.2 (module 2), graph-ir.md §3.1–§3.6

**Key change from previous plan:** canonicalize now takes `LocalParameterization` as input and outputs `PriorRecord`/`FactorParamRecord` (parameterization integration).

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/core/test_canonicalize.py
import pytest
from gaia.core.canonicalize import canonicalize_package, CanonicalizationResult
from gaia.core.local_params import LocalParameterization
from gaia.libs.models import GlobalCanonicalGraph, KnowledgeType
from gaia.libs.models.binding import BindingDecision
from gaia.libs.embedding import StubEmbeddingModel
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies, make_newton_gravity, make_minimal_claim_pair
from tests.gaia.fixtures.parameterizations import make_default_local_params


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


class TestCanonicalizeFirstPackage:
    async def test_all_create_new(self, embedding_model):
        graph = make_galileo_falling_bodies()
        params = make_default_local_params(graph)
        result = await canonicalize_package(
            local_graph=graph, local_params=params,
            global_graph=GlobalCanonicalGraph(),
            package_id="galileo", version="1.0",
            embedding_model=embedding_model,
        )
        assert isinstance(result, CanonicalizationResult)
        for b in result.bindings:
            assert b.decision == BindingDecision.CREATE_NEW
        # Parameterization records created
        assert len(result.prior_records) > 0
        assert len(result.factor_param_records) > 0
        # Global factors have gcn_ IDs, no steps
        for f in result.global_factors:
            assert f.steps is None
            for p in f.premises:
                assert p.startswith("gcn_")


class TestCanonicalizeParamIntegration:
    async def test_local_priors_converted_to_prior_records(self, embedding_model):
        """LocalParameterization node_priors → PriorRecord with gcn_ IDs."""
        graph = make_minimal_claim_pair()
        params = make_default_local_params(graph, prior=0.7, factor_prob=0.9)
        result = await canonicalize_package(
            local_graph=graph, local_params=params,
            global_graph=GlobalCanonicalGraph(),
            package_id="test", version="1.0",
            embedding_model=embedding_model,
        )
        # Prior records should reference gcn_ IDs, not lcn_
        for pr in result.prior_records:
            assert pr.gcn_id.startswith("gcn_")
        # Factor params should reference global factor IDs
        for fp in result.factor_param_records:
            assert fp.factor_id.startswith("f_")
        # Values should match input (modulo Cromwell clamping)
        assert any(abs(pr.value - 0.7) < 0.01 for pr in result.prior_records)


class TestFactorLifting:
    async def test_global_factors_drop_steps_and_weak_points(self, embedding_model):
        graph = make_galileo_falling_bodies()
        params = make_default_local_params(graph)
        result = await canonicalize_package(
            local_graph=graph, local_params=params,
            global_graph=GlobalCanonicalGraph(),
            package_id="galileo", version="1.0",
            embedding_model=embedding_model,
        )
        for f in result.global_factors:
            assert f.steps is None
            assert f.weak_points is None
```

- [ ] **Step 2: Implement `gaia/core/canonicalize.py`**

```python
async def canonicalize_package(
    local_graph: LocalCanonicalGraph,
    local_params: LocalParameterization,
    global_graph: GlobalCanonicalGraph,
    package_id: str,
    version: str,
    embedding_model: EmbeddingModel | None = None,
    threshold: float = 0.90,
) -> CanonicalizationResult:
    ...
```

Key steps:
1. Classify local nodes (premise-only / conclusion / both)
2. Match against global graph via `matching.find_best_match()`
3. Apply §3.1 rules → bindings + new global nodes
4. Factor lifting: lcn→gcn, drop steps/weak_points
5. **Parameterization integration:** convert `local_params.node_priors` to `PriorRecord` (lcn→gcn mapped), convert `local_params.factor_parameters` to `FactorParamRecord`, generate placeholders for equivalent_candidate

- [ ] **Step 3: Run, commit**

### Task 3.3: Global BP Orchestration

**Files:**
- Create: `gaia/core/global_bp.py`
- Create: `tests/gaia/core/test_global_bp.py`

- [ ] **Step 1: Write failing tests**

Test `assemble_parameterization` (latest policy, source policy, prior_cutoff filtering). Test `run_global_bp` end-to-end: canonicalize minimal graph → assemble → BP → verify BeliefState has beliefs only for claim nodes.

- [ ] **Step 2: Implement**

`assemble_parameterization(prior_records, factor_records, policy) → dict` and `run_global_bp(global_graph, prior_records, factor_records, policy) → BeliefState`. Bridge to old BP via `from gaia.bp import FactorGraph, BeliefPropagation`.

- [ ] **Step 3: Run, commit**

---

## Chunk 4: LKM Entry Points

All orchestration in `lkm/pipelines/`. No `lkm/ingest.py` — per spec §3.5.

### Task 4.1: Pipeline — run_ingest

**Files:**
- Create: `gaia/lkm/pipelines/run_ingest.py`
- Create: `tests/gaia/lkm/test_pipelines.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lkm/test_pipelines.py
import pytest
from gaia.lkm.pipelines.run_ingest import run_ingest
from gaia.libs.storage.manager import StorageManager
from gaia.libs.storage.config import StorageConfig
from gaia.libs.embedding import StubEmbeddingModel
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies, make_newton_gravity
from tests.gaia.fixtures.parameterizations import make_default_local_params


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "test.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr

@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


class TestRunIngest:
    async def test_first_package(self, storage, embedding_model):
        graph = make_galileo_falling_bodies()
        params = make_default_local_params(graph)
        result = await run_ingest(
            local_graph=graph, local_params=params,
            package_id="galileo", version="1.0",
            storage=storage, embedding_model=embedding_model,
        )
        assert len(result.bindings) > 0
        # Verify persisted
        global_nodes = await storage.get_knowledge_nodes(prefix="gcn_")
        assert len(global_nodes) > 0
        prior_records = await storage.get_prior_records()
        assert len(prior_records) > 0

    async def test_second_package(self, storage, embedding_model):
        g1 = make_galileo_falling_bodies()
        await run_ingest(
            local_graph=g1, local_params=make_default_local_params(g1),
            package_id="galileo", version="1.0",
            storage=storage, embedding_model=embedding_model,
        )
        g2 = make_newton_gravity()
        result = await run_ingest(
            local_graph=g2, local_params=make_default_local_params(g2),
            package_id="newton", version="1.0",
            storage=storage, embedding_model=embedding_model,
        )
        assert len(result.bindings) > 0
```

- [ ] **Step 2: Implement `run_ingest`**

Orchestrates spec modules 1-3:

```python
# gaia/lkm/pipelines/run_ingest.py
async def run_ingest(local_graph, local_params, package_id, version, storage, embedding_model):
    # Module 1: persist local
    await storage.write_knowledge_nodes(local_graph.knowledge_nodes)
    await storage.write_factor_nodes(local_graph.factor_nodes)

    # Module 2: canonicalize
    existing_nodes = await storage.get_knowledge_nodes(prefix="gcn_")
    existing_factors = await storage.get_factor_nodes(prefix="gcn_")  # global factors
    global_graph = GlobalCanonicalGraph(knowledge_nodes=existing_nodes, factor_nodes=existing_factors)
    result = await canonicalize_package(local_graph, local_params, global_graph, package_id, version, embedding_model)

    # Module 3: persist global
    await storage.write_knowledge_nodes(result.new_global_nodes)
    await storage.write_factor_nodes(result.global_factors)
    await storage.write_bindings(result.bindings)
    await storage.write_prior_records(result.prior_records)
    await storage.write_factor_param_records(result.factor_param_records)
    await storage.write_param_source(result.param_source)

    return result
```

- [ ] **Step 3: Run, commit**

### Task 4.2: Pipeline — run_global_bp and run_full

**Files:**
- Create: `gaia/lkm/pipelines/run_global_bp.py`
- Create: `gaia/lkm/pipelines/run_full.py`

- [ ] **Step 1: Implement `run_global_bp.py`** — loads global graph + param records from storage, calls `core.global_bp.run_global_bp()`, persists BeliefState.

- [ ] **Step 2: Implement `run_full.py`** — CLI entry: `--input-dir`, `--lancedb-path`, `--clean`. Loops over packages calling `run_ingest`, then `run_global_bp`.

- [ ] **Step 3: Commit**

### Task 4.3: FastAPI Services

**Files:**
- Create: `gaia/lkm/services/app.py`
- Create: `gaia/lkm/services/deps.py`
- Create: `gaia/lkm/services/routes/packages.py`
- Create: `gaia/lkm/services/routes/knowledge.py`
- Create: `gaia/lkm/services/routes/inference.py`
- Create: `tests/gaia/lkm/services/test_routes.py`

- [ ] **Step 1: Implement deps.py** — `Dependencies` class with `storage: StorageManager`, `embedding: EmbeddingModel | None`.

- [ ] **Step 2: Implement app.py** — FastAPI factory with lifespan, CORS, health endpoint, route includes.

- [ ] **Step 3: Implement routes**

`packages.py`: `POST /api/packages/ingest` accepts `{package_id, version, local_graph, local_params}`, calls `run_ingest()`.

`knowledge.py`: `GET /api/knowledge/{node_id}`, `GET /api/knowledge/{node_id}/beliefs`.

`inference.py`: `POST /api/inference/run` triggers global BP, `GET /api/beliefs` lists belief states.

- [ ] **Step 4: Write API tests** — health, ingest roundtrip, knowledge retrieval after ingest.

- [ ] **Step 5: Run, commit**

---

## Chunk 5: Integration Test — End-to-End Pipeline

### Task 5.1: Full Pipeline Integration Test

**Files:**
- Create: `tests/gaia/test_e2e_pipeline.py`

- [ ] **Step 1: Write integration test**

```python
# tests/gaia/test_e2e_pipeline.py
"""E2E: ingest galileo + newton + einstein → global BP → verify beliefs."""

class TestEndToEndPipeline:
    async def test_three_package_pipeline(self, storage, embedding_model):
        # Stage 1: Ingest all three
        for pkg_id, graph in [("galileo", galileo), ("newton", newton), ("einstein", einstein)]:
            params = make_default_local_params(graph)
            await run_ingest(local_graph=graph, local_params=params, ...)

        # Stage 2: Verify global graph
        global_nodes = await storage.get_knowledge_nodes(prefix="gcn_")
        assert len(global_nodes) > 0
        claim_nodes = [n for n in global_nodes if n.type == KnowledgeType.CLAIM]

        # Stage 3: Run global BP
        belief_state = await run_global_bp(storage, ResolutionPolicy(strategy="latest"))

        # Stage 4: Verify
        assert belief_state.converged
        assert len(belief_state.beliefs) == len(claim_nodes)
        for v in belief_state.beliefs.values():
            assert CROMWELL_EPS <= v <= 1.0 - CROMWELL_EPS
```

- [ ] **Step 2: Run, commit**

---

## Summary

| Chunk | Tasks | Focus |
|-------|-------|-------|
| 1. Models | 1.1–1.7 | Unified KnowledgeNode/FactorNode, parameterization, fixtures |
| 2. Storage | 2.1–2.6 | LanceDB (unified tables) + Neo4j + StorageManager |
| 3. Core | 3.1–3.3 | Matching, canonicalize (with param integration), global BP |
| 4. LKM | 4.1–4.3 | Pipelines (run_ingest, run_global_bp, run_full) + FastAPI |
| 5. E2E | 5.1 | Integration test: 3 packages → global BP → beliefs |

Execution order: Chunk 1 → 2 → 3 → 4 → 5 (strict sequential).
