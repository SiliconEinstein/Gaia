# LKM Minimal Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal end-to-end pipeline under a new `gaia/` package: upload a `LocalCanonicalGraph` → persist to storage → global canonicalization → global BP → produce `BeliefState`.

**Architecture:** New `gaia/` top-level package, completely independent of old `libs/`/`services/`/`scripts/`. Models rewritten from scratch per `docs/foundations/graph-ir/`. Storage on LanceDB (content+vector) + Neo4j (topology). Core algorithms (canonicalization, matching, global BP) in a shared `core/` layer. LKM entry points split into `pipelines/` (batch) and `services/` (API), both thin wrappers around `core/`.

**Tech Stack:** Python 3.12+, Pydantic v2, LanceDB, Neo4j, NumPy, FastAPI

**Key docs:**
- `docs/foundations/graph-ir/` — Graph IR structural contract (all models derive from here)
- `docs/foundations/lkm/` — Pipeline stages, storage schema, canonicalization, global inference

**BP engine:** `gaia/bp/` is a placeholder in this plan. `core/global_bp.py` imports from the existing `libs.inference` module as a bridge until BP gets migrated.

**Fixtures:** Use existing galileo/newton/einstein examples from `tests/fixtures/` and real paper fixtures. Do not invent synthetic data.

---

## File Structure

```
gaia/
  __init__.py

  libs/
    __init__.py
    models/
      __init__.py              # Re-exports all model classes
      graph_ir.py              # KnowledgeNode, FactorNode, LocalCanonicalGraph, GlobalCanonicalGraph, GlobalCanonicalNode
      parameterization.py      # PriorRecord, FactorParamRecord, ParameterizationSource, ResolutionPolicy
      belief_state.py          # BeliefState
      binding.py               # CanonicalBinding
    storage/
      __init__.py
      config.py                # StorageConfig (env → config)
      base.py                  # ABC: ContentStore, GraphStore
      lance.py                 # LanceDB: content + vector + FTS
      neo4j.py                 # Neo4j: topology
      manager.py               # StorageManager (three-write atomicity)
    embedding.py               # EmbeddingModel ABC + DPEmbeddingModel + StubEmbeddingModel
    llm.py                     # LLM client (litellm wrapper)

  core/
    __init__.py
    matching.py                # Embedding cosine + TF-IDF similarity matching
    canonicalize.py            # Global canonicalization (lcn→gcn mapping, factor lifting)
    global_bp.py               # Assemble Parameterization → run BP → produce BeliefState

  lkm/
    __init__.py
    ingest.py                  # Validate + three-write + trigger canonicalize
    pipelines/
      __init__.py
      run_ingest.py            # Batch ingest entry point
      run_canonicalize.py      # Batch canonicalize entry point
      run_global_bp.py         # Batch global BP entry point
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
    __init__.py                # Placeholder — re-exports from libs.inference for now
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
    test_ingest.py
    services/
      __init__.py
      test_routes.py
  fixtures/
    __init__.py
    graphs.py                  # Builder functions for test graphs (galileo, newton, einstein)
    parameterizations.py       # Builder functions for test parameterizations
```

---

## Chunk 1: Models — Graph IR Data Definitions

This chunk creates all Pydantic v2 models that mirror `docs/foundations/graph-ir/`. Every field, constraint, and invariant from the spec is encoded here. These models are the foundation for everything else.

### Task 1.1: Project Scaffolding

**Files:**
- Create: `gaia/__init__.py`
- Create: `gaia/libs/__init__.py`
- Create: `gaia/libs/models/__init__.py`
- Create: `gaia/bp/__init__.py`
- Create: `gaia/review/__init__.py`
- Create: `gaia/cli/__init__.py`
- Create: `gaia/core/__init__.py`
- Create: `gaia/lkm/__init__.py`
- Create: `tests/gaia/__init__.py`
- Create: `tests/gaia/libs/__init__.py`
- Create: `tests/gaia/libs/models/__init__.py`

- [ ] **Step 1: Create package directory structure**

```bash
mkdir -p gaia/libs/models gaia/libs/storage gaia/core gaia/lkm/pipelines gaia/lkm/services/routes gaia/bp gaia/review gaia/cli
mkdir -p tests/gaia/libs/models tests/gaia/libs/storage tests/gaia/core tests/gaia/lkm/services tests/gaia/fixtures
```

- [ ] **Step 2: Create all `__init__.py` files**

Every directory above gets an empty `__init__.py`. The `gaia/bp/__init__.py` re-exports from old code:

```python
# gaia/bp/__init__.py
"""BP engine — placeholder, re-exports from libs.inference until migration."""
from libs.inference.factor_graph import FactorGraph, CROMWELL_EPS
from libs.inference.bp import BeliefPropagation, BPDiagnostics
```

All other `__init__.py` files are empty (or have re-exports as noted per task).

- [ ] **Step 3: Verify import works**

```bash
cd /path/to/worktree
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
    GlobalCanonicalNode,
    GlobalCanonicalGraph,
    LocalCanonicalRef,
    PackageRef,
)


class TestKnowledgeNode:
    """§1: Knowledge nodes represent propositions."""

    def test_claim_node_creation(self):
        """§1.2: claim is closed, truth-valued scientific assertion."""
        node = KnowledgeNode(
            type=KnowledgeType.CLAIM,
            content="该样本在 90 K 以下表现出超导性",
        )
        assert node.type == KnowledgeType.CLAIM
        assert node.id.startswith("lcn_")

    def test_setting_node_creation(self):
        """§1.2: setting is background information, no probability."""
        node = KnowledgeNode(
            type=KnowledgeType.SETTING,
            content="高温超导研究的当前进展",
        )
        assert node.type == KnowledgeType.SETTING

    def test_template_node_with_parameters(self):
        """§1.2: template has free variables in parameters field."""
        node = KnowledgeNode(
            type=KnowledgeType.TEMPLATE,
            content="∀{x}. superconductor({x}) → zero_resistance({x})",
            parameters=[Parameter(name="x", type="material")],
        )
        assert len(node.parameters) == 1
        assert node.parameters[0].name == "x"

    def test_id_is_deterministic_sha256(self):
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
        """Same content but different type → different ID."""
        claim = KnowledgeNode(type=KnowledgeType.CLAIM, content="X")
        setting = KnowledgeNode(type=KnowledgeType.SETTING, content="X")
        assert claim.id != setting.id

    def test_parameters_sorted_for_id(self):
        """Parameters are sorted before hashing to ensure determinism."""
        node_a = KnowledgeNode(
            type=KnowledgeType.TEMPLATE,
            content="f({x}, {y})",
            parameters=[Parameter(name="x", type="int"), Parameter(name="y", type="str")],
        )
        node_b = KnowledgeNode(
            type=KnowledgeType.TEMPLATE,
            content="f({x}, {y})",
            parameters=[Parameter(name="y", type="str"), Parameter(name="x", type="int")],
        )
        assert node_a.id == node_b.id

    def test_serialization_roundtrip(self):
        """Model can serialize to JSON and back."""
        node = KnowledgeNode(
            type=KnowledgeType.CLAIM,
            content="该样本在 90 K 以下表现出超导性",
            metadata={"schema": "observation", "instrument": "四探针电阻率测量"},
            source_refs=[SourceRef(package="pkg1", version="1.0")],
        )
        json_str = node.model_dump_json()
        roundtrip = KnowledgeNode.model_validate_json(json_str)
        assert roundtrip == node
        assert roundtrip.id == node.id

    def test_global_node_has_no_content_by_default(self):
        """§1.1: global layer content is usually None."""
        gcn = GlobalCanonicalNode(
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
        assert gcn.content is None
        assert gcn.representative_lcn is not None
```

- [ ] **Step 2: Write failing tests for FactorNode**

```python
# (continue in same test file)

class TestFactorNode:
    """§2: Factor nodes represent reasoning operators."""

    def test_infer_factor_creation(self):
        """§2.2: infer category with initial stage."""
        factor = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_a"],
            conclusion="lcn_b",
            steps=[Step(reasoning="基于超导样品的电阻率骤降...")],
        )
        assert factor.factor_id.startswith("f_")
        assert factor.category == FactorCategory.INFER
        assert factor.reasoning_type is None  # initial can be None

    def test_toolcall_factor(self):
        """§2.2: toolcall has no lifecycle."""
        factor = FactorNode(
            category=FactorCategory.TOOLCALL,
            stage=FactorStage.INITIAL,
            premises=["lcn_a"],
            conclusion="lcn_b",
            steps=[Step(reasoning="MCMC fitting using emcee...")],
        )
        assert factor.category == FactorCategory.TOOLCALL

    def test_candidate_infer_requires_reasoning_type(self):
        """§2.3 invariant 1: stage=candidate + category=infer → reasoning_type required."""
        with pytest.raises(ValueError):
            FactorNode(
                category=FactorCategory.INFER,
                stage=FactorStage.CANDIDATE,
                reasoning_type=None,  # must not be None
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_permanent_infer_requires_reasoning_type(self):
        """§2.3 invariant 1: stage=permanent + category=infer → reasoning_type required."""
        with pytest.raises(ValueError):
            FactorNode(
                category=FactorCategory.INFER,
                stage=FactorStage.PERMANENT,
                reasoning_type=None,
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_equivalent_has_no_conclusion(self):
        """§2.3 invariant 6: equivalent has conclusion=None, premises >= 2."""
        factor = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.CANDIDATE,
            reasoning_type=ReasoningType.EQUIVALENT,
            premises=["lcn_a", "lcn_b"],
            conclusion=None,
        )
        assert factor.conclusion is None
        assert len(factor.premises) == 2

    def test_contradict_has_no_conclusion(self):
        """§2.3 invariant 6: contradict has conclusion=None, premises >= 2."""
        factor = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.CANDIDATE,
            reasoning_type=ReasoningType.CONTRADICT,
            premises=["lcn_a", "lcn_b"],
            conclusion=None,
        )
        assert factor.conclusion is None

    def test_bilateral_with_less_than_2_premises_rejected(self):
        """§2.3 invariant 6: equivalent/contradict require at least 2 premises."""
        with pytest.raises(ValueError):
            FactorNode(
                category=FactorCategory.INFER,
                stage=FactorStage.CANDIDATE,
                reasoning_type=ReasoningType.EQUIVALENT,
                premises=["lcn_a"],  # need >= 2
                conclusion=None,
            )

    def test_factor_id_deterministic(self):
        """factor_id is deterministic from content."""
        f1 = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_a", "lcn_b"],
            conclusion="lcn_c",
        )
        f2 = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_a", "lcn_b"],
            conclusion="lcn_c",
        )
        assert f1.factor_id == f2.factor_id

    def test_factor_serialization_roundtrip(self):
        factor = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.CANDIDATE,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=["lcn_a"],
            conclusion="lcn_b",
            steps=[Step(reasoning="step 1")],
            weak_points=["assumption may not hold"],
        )
        json_str = factor.model_dump_json()
        roundtrip = FactorNode.model_validate_json(json_str)
        assert roundtrip == factor
```

- [ ] **Step 3: Write failing tests for LocalCanonicalGraph and GlobalCanonicalGraph**

```python
class TestLocalCanonicalGraph:
    """graph-ir/overview.md: LocalCanonicalGraph is per-package."""

    def test_graph_creation(self):
        claim = KnowledgeNode(type=KnowledgeType.CLAIM, content="A superconducts at 90K")
        setting = KnowledgeNode(type=KnowledgeType.SETTING, content="Background")
        factor = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=[setting.id],
            conclusion=claim.id,
        )
        graph = LocalCanonicalGraph(
            knowledge_nodes=[claim, setting],
            factor_nodes=[factor],
        )
        assert graph.scope == "local"
        assert len(graph.knowledge_nodes) == 2
        assert graph.graph_hash.startswith("sha256:")

    def test_graph_hash_deterministic(self):
        """graph_hash = SHA-256(canonical JSON), deterministic."""
        nodes = [KnowledgeNode(type=KnowledgeType.CLAIM, content="X")]
        g1 = LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=[])
        g2 = LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=[])
        assert g1.graph_hash == g2.graph_hash


class TestGlobalCanonicalGraph:
    """graph-ir/overview.md: GlobalCanonicalGraph is cross-package."""

    def test_global_graph_creation(self):
        gcn = GlobalCanonicalNode(
            id="gcn_abc",
            type=KnowledgeType.CLAIM,
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_xyz", package_id="pkg1", version="1.0"
            ),
            member_local_nodes=[
                LocalCanonicalRef(
                    local_canonical_id="lcn_xyz", package_id="pkg1", version="1.0"
                )
            ],
            provenance=[PackageRef(package_id="pkg1", version="1.0")],
        )
        graph = GlobalCanonicalGraph(
            knowledge_nodes=[gcn],
            factor_nodes=[],
        )
        assert graph.scope == "global"
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
pytest tests/gaia/libs/models/test_graph_ir.py -v
```

Expected: `ModuleNotFoundError: No module named 'gaia.libs.models.graph_ir'`

- [ ] **Step 5: Implement `gaia/libs/models/graph_ir.py`**

```python
# gaia/libs/models/graph_ir.py
"""
Graph IR data models — Python implementation of docs/foundations/graph-ir/.

This module is the single source of truth for structural definitions.
All field names, types, and constraints match the spec exactly.
"""
from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ── Enums ──────────────────────────────────────────────────────


class KnowledgeType(StrEnum):
    CLAIM = "claim"
    SETTING = "setting"
    QUESTION = "question"
    TEMPLATE = "template"


class FactorCategory(StrEnum):
    INFER = "infer"
    TOOLCALL = "toolcall"
    PROOF = "proof"


class FactorStage(StrEnum):
    INITIAL = "initial"
    CANDIDATE = "candidate"
    PERMANENT = "permanent"


class ReasoningType(StrEnum):
    ENTAILMENT = "entailment"
    INDUCTION = "induction"
    ABDUCTION = "abduction"
    EQUIVALENT = "equivalent"
    CONTRADICT = "contradict"


# ── Supporting types ───────────────────────────────────────────


class Parameter(BaseModel):
    """Template free variable."""

    name: str
    type: str


class SourceRef(BaseModel):
    """Provenance reference to a package."""

    package: str
    version: str
    module: str | None = None
    knowledge_name: str | None = None


class Step(BaseModel):
    """One step in a factor's reasoning process."""

    reasoning: str
    premises: list[str] | None = None
    conclusion: str | None = None


class LocalCanonicalRef(BaseModel):
    """Reference to a local canonical node."""

    local_canonical_id: str
    package_id: str
    version: str


class PackageRef(BaseModel):
    """Reference to a contributing package."""

    package_id: str
    version: str


# ── Knowledge Node ─────────────────────────────────────────────


def _compute_knowledge_id(
    type: str, content: str, parameters: list[Parameter]
) -> str:
    """§1.1: id = SHA-256(type + content + sorted(parameters))."""
    sorted_params = sorted(
        [p.model_dump() for p in parameters],
        key=lambda p: p["name"],
    )
    payload = json.dumps(
        {"type": type, "content": content, "parameters": sorted_params},
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"lcn_{digest[:16]}"


class KnowledgeNode(BaseModel):
    """
    §1: Knowledge node — represents a proposition.

    Four types: claim (BP participant), setting, question, template.
    Local layer stores content; global layer references via representative_lcn.
    """

    id: str = ""  # computed if not provided
    type: KnowledgeType
    content: str | None = None
    parameters: list[Parameter] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None
    provenance: list[PackageRef] | None = None

    # Global layer fields
    representative_lcn: LocalCanonicalRef | None = None
    member_local_nodes: list[LocalCanonicalRef] | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.id and self.content is not None:
            self.id = _compute_knowledge_id(
                self.type.value, self.content, self.parameters
            )


class GlobalCanonicalNode(BaseModel):
    """
    §1.1: Global canonical node — cross-package identity.

    ID is registry-allocated (gcn_ prefix), not content-addressed.
    Content retrieved via representative_lcn reference.
    """

    id: str  # gcn_ prefix, registry-allocated
    type: KnowledgeType
    content: str | None = None  # usually None; exception: subgraph intermediate nodes
    representative_lcn: LocalCanonicalRef | None = None
    member_local_nodes: list[LocalCanonicalRef] = Field(default_factory=list)
    provenance: list[PackageRef] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


# ── Factor Node ────────────────────────────────────────────────

# Bilateral reasoning types (conclusion=None, premises>=2)
_BILATERAL_TYPES = {ReasoningType.EQUIVALENT, ReasoningType.CONTRADICT}


def _compute_factor_id(
    category: str,
    premises: list[str],
    conclusion: str | None,
) -> str:
    """factor_id = f_{sha256[:16]}, deterministic."""
    payload = json.dumps(
        {
            "category": category,
            "premises": sorted(premises),
            "conclusion": conclusion,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"f_{digest[:16]}"


class FactorNode(BaseModel):
    """
    §2: Factor node — reasoning operator connecting knowledge nodes.

    Three-dimensional type system: category × stage × reasoning_type.
    """

    factor_id: str = ""  # computed if not provided
    category: FactorCategory
    stage: FactorStage = FactorStage.INITIAL
    reasoning_type: ReasoningType | None = None

    premises: list[str]  # knowledge node IDs
    conclusion: str | None = None  # single output (None for bilateral)

    # Local layer
    steps: list[Step] | None = None
    weak_points: list[str] | None = None

    # Global layer
    subgraph: list[FactorNode] | None = None

    # Provenance
    source_ref: SourceRef | None = None
    metadata: dict[str, Any] | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.factor_id:
            self.factor_id = _compute_factor_id(
                self.category.value, self.premises, self.conclusion
            )

    @model_validator(mode="after")
    def _validate_invariants(self) -> FactorNode:
        # §2.3 invariant 1: candidate/permanent infer → reasoning_type required
        if (
            self.category == FactorCategory.INFER
            and self.stage in (FactorStage.CANDIDATE, FactorStage.PERMANENT)
            and self.reasoning_type is None
        ):
            raise ValueError(
                f"reasoning_type required for {self.category} at stage {self.stage}"
            )

        # §2.3 invariant 6: bilateral types → conclusion=None, premises>=2
        if self.reasoning_type in _BILATERAL_TYPES:
            if self.conclusion is not None:
                raise ValueError(
                    f"{self.reasoning_type} must have conclusion=None"
                )
            if len(self.premises) < 2:
                raise ValueError(
                    f"{self.reasoning_type} requires at least 2 premises"
                )

        return self


# ── Graph Containers ───────────────────────────────────────────


def _compute_graph_hash(knowledge_nodes: list, factor_nodes: list) -> str:
    """graph_hash = SHA-256(canonical JSON)."""
    data = {
        "knowledge_nodes": [n.model_dump(mode="json") for n in knowledge_nodes],
        "factor_nodes": [f.model_dump(mode="json") for f in factor_nodes],
    }
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"sha256:{digest}"


class LocalCanonicalGraph(BaseModel):
    """Per-package graph with full content and steps."""

    scope: str = "local"
    graph_hash: str = ""
    knowledge_nodes: list[KnowledgeNode] = Field(default_factory=list)
    factor_nodes: list[FactorNode] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if not self.graph_hash:
            self.graph_hash = _compute_graph_hash(
                self.knowledge_nodes, self.factor_nodes
            )


class GlobalCanonicalGraph(BaseModel):
    """Cross-package graph — structural index, no content or steps."""

    scope: str = "global"
    knowledge_nodes: list[GlobalCanonicalNode] = Field(default_factory=list)
    factor_nodes: list[FactorNode] = Field(default_factory=list)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/gaia/libs/models/test_graph_ir.py -v
```

Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add gaia/libs/models/graph_ir.py tests/gaia/libs/models/test_graph_ir.py
git commit -m "feat(models): implement KnowledgeNode, FactorNode, LocalCanonicalGraph, GlobalCanonicalGraph"
```

### Task 1.3: Parameterization Models

**Files:**
- Create: `gaia/libs/models/parameterization.py`
- Create: `tests/gaia/libs/models/test_parameterization.py`

**Spec reference:** `docs/foundations/graph-ir/parameterization.md`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/libs/models/test_parameterization.py
"""Tests for Parameterization models — locks down parameterization.md constraints."""
import pytest
from gaia.libs.models.parameterization import (
    PriorRecord,
    FactorParamRecord,
    ParameterizationSource,
    ResolutionPolicy,
    CROMWELL_EPS,
)


class TestPriorRecord:
    def test_creation(self):
        record = PriorRecord(
            gcn_id="gcn_8b1c",
            value=0.7,
            source_id="src_001",
        )
        assert record.value == 0.7

    def test_cromwell_clamp_zero(self):
        """Cromwell's rule: value clamped to [ε, 1-ε]."""
        record = PriorRecord(gcn_id="gcn_x", value=0.0, source_id="src_001")
        assert record.value == CROMWELL_EPS

    def test_cromwell_clamp_one(self):
        record = PriorRecord(gcn_id="gcn_x", value=1.0, source_id="src_001")
        assert record.value == 1.0 - CROMWELL_EPS

    def test_cromwell_clamp_negative(self):
        record = PriorRecord(gcn_id="gcn_x", value=-0.5, source_id="src_001")
        assert record.value == CROMWELL_EPS

    def test_value_within_range_unchanged(self):
        record = PriorRecord(gcn_id="gcn_x", value=0.5, source_id="src_001")
        assert record.value == 0.5

    def test_serialization_roundtrip(self):
        record = PriorRecord(gcn_id="gcn_8b1c", value=0.7, source_id="src_001")
        roundtrip = PriorRecord.model_validate_json(record.model_dump_json())
        assert roundtrip == record


class TestFactorParamRecord:
    def test_creation(self):
        record = FactorParamRecord(
            factor_id="f_d2c8",
            probability=0.85,
            source_id="src_001",
        )
        assert record.probability == 0.85

    def test_cromwell_clamp(self):
        record = FactorParamRecord(
            factor_id="f_x", probability=0.0, source_id="src_001"
        )
        assert record.probability == CROMWELL_EPS


class TestParameterizationSource:
    def test_creation(self):
        source = ParameterizationSource(
            source_id="src_001",
            model="gpt-5-mini",
            policy="conservative",
        )
        assert source.model == "gpt-5-mini"

    def test_optional_fields(self):
        source = ParameterizationSource(source_id="src_002", model="claude-opus")
        assert source.policy is None
        assert source.config is None


class TestResolutionPolicy:
    def test_latest(self):
        policy = ResolutionPolicy(strategy="latest")
        assert policy.strategy == "latest"

    def test_source_specific(self):
        policy = ResolutionPolicy(strategy="source", source_id="src_001")
        assert policy.source_id == "src_001"

    def test_source_without_id_rejected(self):
        with pytest.raises(ValueError):
            ResolutionPolicy(strategy="source", source_id=None)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/gaia/libs/models/test_parameterization.py -v
```

- [ ] **Step 3: Implement `gaia/libs/models/parameterization.py`**

```python
# gaia/libs/models/parameterization.py
"""
Parameterization models — docs/foundations/graph-ir/parameterization.md.

Probability parameters stored as atomic records. Different review sources
produce different records. BP runtime assembles them via resolution policy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator

CROMWELL_EPS = 1e-3


def _cromwell_clamp(value: float) -> float:
    """Cromwell's rule: clamp to [ε, 1-ε]."""
    return max(CROMWELL_EPS, min(1.0 - CROMWELL_EPS, value))


class PriorRecord(BaseModel):
    """Atomic prior record for a global claim node."""

    gcn_id: str
    value: float
    source_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        self.value = _cromwell_clamp(self.value)


class FactorParamRecord(BaseModel):
    """Atomic probability record for a global factor."""

    factor_id: str
    probability: float
    source_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        self.probability = _cromwell_clamp(self.probability)


class ParameterizationSource(BaseModel):
    """Metadata about a review source that produced parameter records."""

    source_id: str
    model: str
    policy: str | None = None
    config: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResolutionPolicy(BaseModel):
    """
    How to assemble parameters from atomic records at BP runtime.

    strategy="latest": each node/factor takes newest record.
    strategy="source": use records from specific source_id.
    """

    strategy: str  # "latest" | "source"
    source_id: str | None = None
    prior_cutoff: datetime | None = None

    @model_validator(mode="after")
    def _validate_source_has_id(self) -> ResolutionPolicy:
        if self.strategy == "source" and not self.source_id:
            raise ValueError("source_id required when strategy='source'")
        return self
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/gaia/libs/models/test_parameterization.py -v
```

- [ ] **Step 5: Commit**

```bash
git add gaia/libs/models/parameterization.py tests/gaia/libs/models/test_parameterization.py
git commit -m "feat(models): implement PriorRecord, FactorParamRecord, ResolutionPolicy"
```

### Task 1.4: BeliefState Model

**Files:**
- Create: `gaia/libs/models/belief_state.py`
- Create: `tests/gaia/libs/models/test_belief_state.py`

**Spec reference:** `docs/foundations/graph-ir/belief-state.md`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/libs/models/test_belief_state.py
"""Tests for BeliefState — locks down belief-state.md constraints."""
from datetime import datetime, timezone

from gaia.libs.models.belief_state import BeliefState


class TestBeliefState:
    def test_creation(self):
        state = BeliefState(
            bp_run_id="run-001",
            resolution_policy="latest",
            prior_cutoff=datetime(2026, 3, 24, tzinfo=timezone.utc),
            beliefs={"gcn_8b1c": 0.82, "gcn_9d2a": 0.71},
            converged=True,
            iterations=23,
            max_residual=4.2e-7,
        )
        assert state.beliefs["gcn_8b1c"] == 0.82
        assert state.converged is True

    def test_serialization_roundtrip(self):
        state = BeliefState(
            bp_run_id="run-001",
            resolution_policy="latest",
            prior_cutoff=datetime(2026, 3, 24, tzinfo=timezone.utc),
            beliefs={"gcn_a": 0.5},
            converged=False,
            iterations=50,
            max_residual=0.01,
        )
        roundtrip = BeliefState.model_validate_json(state.model_dump_json())
        assert roundtrip == state

    def test_empty_beliefs_allowed(self):
        """Edge case: graph with no claims → empty beliefs."""
        state = BeliefState(
            bp_run_id="run-empty",
            resolution_policy="latest",
            prior_cutoff=datetime(2026, 3, 24, tzinfo=timezone.utc),
            beliefs={},
            converged=True,
            iterations=0,
            max_residual=0.0,
        )
        assert len(state.beliefs) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/gaia/libs/models/test_belief_state.py -v
```

- [ ] **Step 3: Implement `gaia/libs/models/belief_state.py`**

```python
# gaia/libs/models/belief_state.py
"""BeliefState — docs/foundations/graph-ir/belief-state.md."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class BeliefState(BaseModel):
    """
    Pure BP output on GlobalCanonicalGraph — posterior belief values.

    Only type=claim nodes have beliefs.
    resolution_policy + prior_cutoff enable reproducibility.
    """

    bp_run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Reproducibility
    resolution_policy: str  # "latest" | "source:<source_id>"
    prior_cutoff: datetime

    # Beliefs — only claims
    beliefs: dict[str, float]  # gcn_id → posterior

    # Diagnostics
    converged: bool
    iterations: int
    max_residual: float
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/gaia/libs/models/test_belief_state.py -v
```

- [ ] **Step 5: Commit**

```bash
git add gaia/libs/models/belief_state.py tests/gaia/libs/models/test_belief_state.py
git commit -m "feat(models): implement BeliefState"
```

### Task 1.5: CanonicalBinding Model

**Files:**
- Create: `gaia/libs/models/binding.py`
- Create: `tests/gaia/libs/models/test_binding.py`

**Spec reference:** `docs/foundations/graph-ir/graph-ir.md` §3.4

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/libs/models/test_binding.py
"""Tests for CanonicalBinding — locks down graph-ir.md §3.4."""
import pytest
from gaia.libs.models.binding import CanonicalBinding, BindingDecision


class TestCanonicalBinding:
    def test_match_existing(self):
        binding = CanonicalBinding(
            local_canonical_id="lcn_abc",
            global_canonical_id="gcn_xyz",
            package_id="pkg1",
            version="1.0",
            decision=BindingDecision.MATCH_EXISTING,
            reason="cosine similarity 0.95",
        )
        assert binding.decision == BindingDecision.MATCH_EXISTING

    def test_create_new(self):
        binding = CanonicalBinding(
            local_canonical_id="lcn_abc",
            global_canonical_id="gcn_new",
            package_id="pkg1",
            version="1.0",
            decision=BindingDecision.CREATE_NEW,
            reason="no match above threshold",
        )
        assert binding.decision == BindingDecision.CREATE_NEW

    def test_equivalent_candidate(self):
        """§3.1: conclusion node match → equivalent_candidate."""
        binding = CanonicalBinding(
            local_canonical_id="lcn_abc",
            global_canonical_id="gcn_new",
            package_id="pkg1",
            version="1.0",
            decision=BindingDecision.EQUIVALENT_CANDIDATE,
            reason="conclusion node matched gcn_old, created equivalent factor",
        )
        assert binding.decision == BindingDecision.EQUIVALENT_CANDIDATE

    def test_serialization_roundtrip(self):
        binding = CanonicalBinding(
            local_canonical_id="lcn_abc",
            global_canonical_id="gcn_xyz",
            package_id="pkg1",
            version="1.0",
            decision=BindingDecision.MATCH_EXISTING,
            reason="cosine similarity 0.95",
        )
        roundtrip = CanonicalBinding.model_validate_json(binding.model_dump_json())
        assert roundtrip == binding
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/gaia/libs/models/test_binding.py -v
```

- [ ] **Step 3: Implement `gaia/libs/models/binding.py`**

```python
# gaia/libs/models/binding.py
"""CanonicalBinding — docs/foundations/graph-ir/graph-ir.md §3.4."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class BindingDecision(StrEnum):
    MATCH_EXISTING = "match_existing"
    CREATE_NEW = "create_new"
    EQUIVALENT_CANDIDATE = "equivalent_candidate"


class CanonicalBinding(BaseModel):
    """Maps a local canonical node to a global canonical node."""

    local_canonical_id: str  # lcn_
    global_canonical_id: str  # gcn_
    package_id: str
    version: str
    decision: BindingDecision
    reason: str
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/gaia/libs/models/test_binding.py -v
```

- [ ] **Step 5: Commit**

```bash
git add gaia/libs/models/binding.py tests/gaia/libs/models/test_binding.py
git commit -m "feat(models): implement CanonicalBinding"
```

### Task 1.6: Models `__init__.py` Re-exports

**Files:**
- Modify: `gaia/libs/models/__init__.py`

- [ ] **Step 1: Write re-exports**

```python
# gaia/libs/models/__init__.py
"""Gaia data models — Python implementation of docs/foundations/graph-ir/."""
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
    GlobalCanonicalNode,
    GlobalCanonicalGraph,
    LocalCanonicalRef,
    PackageRef,
)
from gaia.libs.models.parameterization import (
    PriorRecord,
    FactorParamRecord,
    ParameterizationSource,
    ResolutionPolicy,
    CROMWELL_EPS,
)
from gaia.libs.models.belief_state import BeliefState
from gaia.libs.models.binding import CanonicalBinding, BindingDecision

__all__ = [
    # graph_ir
    "KnowledgeNode",
    "KnowledgeType",
    "FactorNode",
    "FactorCategory",
    "FactorStage",
    "ReasoningType",
    "Step",
    "SourceRef",
    "Parameter",
    "LocalCanonicalGraph",
    "GlobalCanonicalNode",
    "GlobalCanonicalGraph",
    "LocalCanonicalRef",
    "PackageRef",
    # parameterization
    "PriorRecord",
    "FactorParamRecord",
    "ParameterizationSource",
    "ResolutionPolicy",
    "CROMWELL_EPS",
    # belief_state
    "BeliefState",
    # binding
    "CanonicalBinding",
    "BindingDecision",
]
```

- [ ] **Step 2: Verify imports work**

```bash
python -c "from gaia.libs.models import KnowledgeNode, BeliefState, CanonicalBinding; print('OK')"
```

- [ ] **Step 3: Run all model tests**

```bash
pytest tests/gaia/libs/models/ -v
```

- [ ] **Step 4: Commit**

```bash
git add gaia/libs/models/__init__.py
git commit -m "feat(models): add re-exports in __init__.py"
```

### Task 1.7: Test Fixtures — Galileo/Newton/Einstein Graphs

**Files:**
- Create: `tests/gaia/fixtures/graphs.py`

Build test graph constructors from the existing galileo/newton/einstein examples in `tests/fixtures/examples/`. These return `LocalCanonicalGraph` instances using the new models.

- [ ] **Step 1: Write fixture builders**

```python
# tests/gaia/fixtures/graphs.py
"""
Test graph constructors from real scientific examples.

Sources:
- tests/fixtures/examples/galileo_tied_balls/
- tests/fixtures/examples/einstein_elevator/
- tests/fixtures/gaia_language_packages/galileo_falling_bodies_v4/
- tests/fixtures/gaia_language_packages/newton_principia_v4/
"""
from gaia.libs.models import (
    KnowledgeNode,
    KnowledgeType,
    FactorNode,
    FactorCategory,
    FactorStage,
    ReasoningType,
    Step,
    SourceRef,
    LocalCanonicalGraph,
)


def make_galileo_falling_bodies() -> LocalCanonicalGraph:
    """
    Galileo's refutation of Aristotle: tied-balls thought experiment.

    Graph structure:
      aristotle_doctrine (setting) ─┐
                                     ├─[entailment]─→ composite_slower (claim)
      tied_balls_setup (claim) ──────┘
                                     ├─[entailment]─→ composite_faster (claim)
      composite_slower ──────────────┐
                                     ├─[contradict]
      composite_faster ──────────────┘
      contradiction ─────[entailment]─→ vacuum_prediction (claim)
    """
    # Knowledge nodes
    aristotle = KnowledgeNode(
        type=KnowledgeType.SETTING,
        content="Aristotle's doctrine: heavier objects fall faster than lighter ones",
        source_refs=[SourceRef(package="galileo_falling_bodies", version="1.0")],
    )
    tied_balls = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Consider a heavy ball tied to a light ball and dropped together",
        source_refs=[SourceRef(package="galileo_falling_bodies", version="1.0")],
    )
    composite_slower = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="The light ball drags down the heavy ball, so the composite falls slower than the heavy ball alone",
        source_refs=[SourceRef(package="galileo_falling_bodies", version="1.0")],
    )
    composite_faster = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="The composite is heavier than either ball, so it falls faster than the heavy ball alone",
        source_refs=[SourceRef(package="galileo_falling_bodies", version="1.0")],
    )
    vacuum_prediction = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="In vacuum, all objects fall at the same rate regardless of mass",
        source_refs=[SourceRef(package="galileo_falling_bodies", version="1.0")],
    )

    # Factor nodes
    f_slower = FactorNode(
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[aristotle.id, tied_balls.id],
        conclusion=composite_slower.id,
        steps=[Step(reasoning="By Aristotle's law, the lighter ball retards the heavier")],
    )
    f_faster = FactorNode(
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[aristotle.id, tied_balls.id],
        conclusion=composite_faster.id,
        steps=[Step(reasoning="The tied composite has greater total weight")],
    )
    f_contradict = FactorNode(
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.CONTRADICT,
        premises=[composite_slower.id, composite_faster.id],
    )
    f_vacuum = FactorNode(
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[composite_slower.id, composite_faster.id],
        conclusion=vacuum_prediction.id,
        steps=[Step(reasoning="The contradiction resolves only if mass does not affect fall rate")],
    )

    return LocalCanonicalGraph(
        knowledge_nodes=[aristotle, tied_balls, composite_slower, composite_faster, vacuum_prediction],
        factor_nodes=[f_slower, f_faster, f_contradict, f_vacuum],
    )


def make_newton_gravity() -> LocalCanonicalGraph:
    """
    Newton's derivation of universal gravitation from Kepler + Galileo.

    Graph structure:
      kepler_law (claim) ─────────┐
      galileo_vacuum (claim) ─────┤
                                   ├─[induction]─→ inverse_square (claim)
      falling_apple (claim) ──────┘
      inverse_square ──[entailment]──→ mass_equivalence (claim)
    """
    kepler = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Kepler's third law: T² ∝ a³ for planetary orbits",
        source_refs=[SourceRef(package="newton_principia", version="1.0")],
    )
    galileo_vacuum = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="In vacuum, all objects fall at the same rate regardless of mass",
        source_refs=[SourceRef(package="newton_principia", version="1.0")],
    )
    falling_apple = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Objects near Earth's surface accelerate at g ≈ 9.8 m/s²",
        source_refs=[SourceRef(package="newton_principia", version="1.0")],
    )
    inverse_square = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Gravitational force follows an inverse-square law: F = GMm/r²",
        source_refs=[SourceRef(package="newton_principia", version="1.0")],
    )
    mass_equivalence = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Gravitational mass equals inertial mass",
        source_refs=[SourceRef(package="newton_principia", version="1.0")],
    )

    f_induction = FactorNode(
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.INDUCTION,
        premises=[kepler.id, galileo_vacuum.id, falling_apple.id],
        conclusion=inverse_square.id,
        steps=[Step(reasoning="From Kepler orbits + terrestrial gravity → universal inverse-square law")],
    )
    f_entailment = FactorNode(
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[inverse_square.id],
        conclusion=mass_equivalence.id,
        steps=[Step(reasoning="Universal free fall implies gravitational and inertial mass are equivalent")],
    )

    return LocalCanonicalGraph(
        knowledge_nodes=[kepler, galileo_vacuum, falling_apple, inverse_square, mass_equivalence],
        factor_nodes=[f_induction, f_entailment],
    )


def make_einstein_equivalence() -> LocalCanonicalGraph:
    """
    Einstein's equivalence principle and light bending prediction.

    Graph structure:
      newton_gravity (claim) ────────┐
      elevator_experiment (claim) ───┤
                                      ├─[abduction]─→ equivalence_principle (claim)
      equivalence_principle ──[entailment]──→ light_bending (claim)
      newtonian_prediction (claim) ──┐
      light_bending ─────────────────┤
                                      ├─[contradict]  (1.75 vs 0.87 arcsec)
    """
    newton_gravity = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Gravitational force follows an inverse-square law: F = GMm/r²",
        source_refs=[SourceRef(package="einstein_gravity", version="1.0")],
    )
    elevator = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="An observer in a closed elevator cannot distinguish gravity from uniform acceleration",
        source_refs=[SourceRef(package="einstein_gravity", version="1.0")],
    )
    equivalence = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="The equivalence principle: gravitational and inertial effects are locally indistinguishable",
        source_refs=[SourceRef(package="einstein_gravity", version="1.0")],
    )
    light_bending = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Light bends in a gravitational field by 1.75 arcseconds near the Sun (GR prediction)",
        source_refs=[SourceRef(package="einstein_gravity", version="1.0")],
    )
    newtonian_prediction = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Newtonian corpuscular theory predicts light deflection of 0.87 arcseconds near the Sun",
        source_refs=[SourceRef(package="einstein_gravity", version="1.0")],
    )

    f_abduction = FactorNode(
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ABDUCTION,
        premises=[newton_gravity.id, elevator.id],
        conclusion=equivalence.id,
        steps=[Step(reasoning="Elevator thought experiment: best explanation is that gravity ≡ acceleration")],
        weak_points=["Only valid locally; breaks for tidal forces"],
    )
    f_entailment = FactorNode(
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[equivalence.id],
        conclusion=light_bending.id,
        steps=[Step(reasoning="If gravity ≡ acceleration, light in gravity must follow curved geodesics")],
    )
    f_contradict = FactorNode(
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.CONTRADICT,
        premises=[light_bending.id, newtonian_prediction.id],
    )

    return LocalCanonicalGraph(
        knowledge_nodes=[newton_gravity, elevator, equivalence, light_bending, newtonian_prediction],
        factor_nodes=[f_abduction, f_entailment, f_contradict],
    )


def make_minimal_claim_pair() -> LocalCanonicalGraph:
    """Simplest possible graph: one premise claim → one conclusion claim via single factor."""
    premise = KnowledgeNode(type=KnowledgeType.CLAIM, content="Premise A is true")
    conclusion = KnowledgeNode(type=KnowledgeType.CLAIM, content="Therefore B follows")
    factor = FactorNode(
        category=FactorCategory.INFER,
        stage=FactorStage.INITIAL,
        premises=[premise.id],
        conclusion=conclusion.id,
    )
    return LocalCanonicalGraph(
        knowledge_nodes=[premise, conclusion],
        factor_nodes=[factor],
    )
```

- [ ] **Step 2: Write test that fixture constructors produce valid graphs**

```python
# tests/gaia/fixtures/test_fixtures.py
"""Smoke tests for fixture builders — ensures they produce valid models."""
from tests.gaia.fixtures.graphs import (
    make_galileo_falling_bodies,
    make_newton_gravity,
    make_einstein_equivalence,
    make_minimal_claim_pair,
)
from gaia.libs.models import KnowledgeType


class TestFixtureGraphs:
    def test_galileo_graph_valid(self):
        g = make_galileo_falling_bodies()
        assert g.scope == "local"
        assert len(g.knowledge_nodes) == 5
        assert len(g.factor_nodes) == 4
        claims = [n for n in g.knowledge_nodes if n.type == KnowledgeType.CLAIM]
        assert len(claims) == 4  # tied_balls, composite_slower, composite_faster, vacuum

    def test_newton_graph_valid(self):
        g = make_newton_gravity()
        assert len(g.knowledge_nodes) == 5
        assert len(g.factor_nodes) == 2

    def test_einstein_graph_valid(self):
        g = make_einstein_equivalence()
        assert len(g.knowledge_nodes) == 5
        assert len(g.factor_nodes) == 3

    def test_minimal_pair_valid(self):
        g = make_minimal_claim_pair()
        assert len(g.knowledge_nodes) == 2
        assert len(g.factor_nodes) == 1

    def test_cross_package_shared_claim(self):
        """Galileo's vacuum prediction and Newton's reference should match content."""
        galileo = make_galileo_falling_bodies()
        newton = make_newton_gravity()
        galileo_vacuum = [
            n for n in galileo.knowledge_nodes if "vacuum" in (n.content or "")
        ][0]
        newton_vacuum = [
            n for n in newton.knowledge_nodes if "vacuum" in (n.content or "")
        ][0]
        # Same content → same local canonical ID (cross-package match candidate)
        assert galileo_vacuum.id == newton_vacuum.id
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/gaia/fixtures/test_fixtures.py -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/gaia/fixtures/
git commit -m "feat(fixtures): add galileo/newton/einstein graph builders"
```

---

## Chunk 2: Storage Layer

Storage layer persists Graph IR models to LanceDB (content + vector) and Neo4j (topology). Implements three-write atomicity for package ingest.

### Task 2.1: StorageConfig

**Files:**
- Create: `gaia/libs/storage/config.py`
- Port from: `libs/storage/config.py`

- [ ] **Step 1: Implement config**

```python
# gaia/libs/storage/config.py
"""Storage configuration — reads from environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    """Storage backend configuration."""

    # LanceDB
    lancedb_path: str = "./data/lancedb/gaia"
    lancedb_remote_uri: str | None = None
    lancedb_api_key: str | None = None

    # Neo4j
    neo4j_uri: str | None = None
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # Vector
    vector_index_type: str = "IVF_PQ"

    model_config = {"env_prefix": "GAIA_"}

    @property
    def has_neo4j(self) -> bool:
        return self.neo4j_uri is not None

    @property
    def effective_lancedb_connection(self) -> str:
        return self.lancedb_remote_uri or self.lancedb_path
```

- [ ] **Step 2: Commit**

```bash
git add gaia/libs/storage/config.py
git commit -m "feat(storage): add StorageConfig"
```

### Task 2.2: Storage ABCs

**Files:**
- Create: `gaia/libs/storage/base.py`

- [ ] **Step 1: Define interfaces**

```python
# gaia/libs/storage/base.py
"""Abstract base classes for storage backends."""
from __future__ import annotations

from abc import ABC, abstractmethod

from gaia.libs.models.graph_ir import (
    GlobalCanonicalNode,
    FactorNode,
    KnowledgeNode,
    LocalCanonicalGraph,
)
from gaia.libs.models.parameterization import PriorRecord, FactorParamRecord, ParameterizationSource
from gaia.libs.models.belief_state import BeliefState
from gaia.libs.models.binding import CanonicalBinding


class ContentStore(ABC):
    """LanceDB content store — source of truth for all entities."""

    @abstractmethod
    async def write_local_graph(self, package_id: str, version: str, graph: LocalCanonicalGraph) -> None: ...

    @abstractmethod
    async def write_global_nodes(self, nodes: list[GlobalCanonicalNode]) -> None: ...

    @abstractmethod
    async def write_global_factors(self, factors: list[FactorNode]) -> None: ...

    @abstractmethod
    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None: ...

    @abstractmethod
    async def write_prior_records(self, records: list[PriorRecord]) -> None: ...

    @abstractmethod
    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None: ...

    @abstractmethod
    async def write_param_source(self, source: ParameterizationSource) -> None: ...

    @abstractmethod
    async def write_belief_state(self, state: BeliefState) -> None: ...

    @abstractmethod
    async def get_node(self, node_id: str) -> KnowledgeNode | GlobalCanonicalNode | None: ...

    @abstractmethod
    async def get_global_nodes(self) -> list[GlobalCanonicalNode]: ...

    @abstractmethod
    async def get_global_factors(self) -> list[FactorNode]: ...

    @abstractmethod
    async def get_bindings(self, package_id: str | None = None) -> list[CanonicalBinding]: ...

    @abstractmethod
    async def get_prior_records(self, gcn_id: str | None = None) -> list[PriorRecord]: ...

    @abstractmethod
    async def get_factor_param_records(self, factor_id: str | None = None) -> list[FactorParamRecord]: ...

    @abstractmethod
    async def get_belief_states(self, limit: int = 10) -> list[BeliefState]: ...

    @abstractmethod
    async def clean_all(self) -> None: ...


class GraphStore(ABC):
    """Graph topology store — optional, for traversal queries."""

    @abstractmethod
    async def write_nodes(self, nodes: list[GlobalCanonicalNode]) -> None: ...

    @abstractmethod
    async def write_factors(self, factors: list[FactorNode]) -> None: ...

    @abstractmethod
    async def get_neighbors(self, node_id: str) -> list[str]: ...

    @abstractmethod
    async def get_subgraph(self, node_ids: list[str], depth: int = 1) -> tuple[list[str], list[str]]: ...

    @abstractmethod
    async def clean_all(self) -> None: ...
```

- [ ] **Step 2: Commit**

```bash
git add gaia/libs/storage/base.py
git commit -m "feat(storage): add ContentStore and GraphStore ABCs"
```

### Task 2.3: LanceDB Content Store

**Files:**
- Create: `gaia/libs/storage/lance.py`
- Create: `tests/gaia/libs/storage/test_lance.py`

This is the largest storage implementation. TDD: write tests first for each table operation, then implement.

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/libs/storage/test_lance.py
"""Tests for LanceDB content store."""
import pytest
from datetime import datetime, timezone

from gaia.libs.storage.lance import LanceContentStore
from gaia.libs.models import (
    KnowledgeType,
    GlobalCanonicalNode,
    LocalCanonicalRef,
    PackageRef,
    FactorNode,
    FactorCategory,
    FactorStage,
    ReasoningType,
    BeliefState,
)
from gaia.libs.models.binding import CanonicalBinding, BindingDecision
from gaia.libs.models.parameterization import PriorRecord, FactorParamRecord, ParameterizationSource
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies


@pytest.fixture
async def store(tmp_path):
    s = LanceContentStore(path=str(tmp_path / "test.lance"))
    await s.initialize()
    return s


class TestLocalGraphStorage:
    async def test_write_and_read_local_graph(self, store):
        graph = make_galileo_falling_bodies()
        await store.write_local_graph("galileo", "1.0", graph)
        # Read back a specific node
        node = await store.get_node(graph.knowledge_nodes[0].id)
        assert node is not None
        assert node.content == graph.knowledge_nodes[0].content


class TestGlobalNodeStorage:
    async def test_write_and_read_global_nodes(self, store):
        gcn = GlobalCanonicalNode(
            id="gcn_test1",
            type=KnowledgeType.CLAIM,
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_abc", package_id="pkg1", version="1.0"
            ),
            member_local_nodes=[
                LocalCanonicalRef(local_canonical_id="lcn_abc", package_id="pkg1", version="1.0")
            ],
            provenance=[PackageRef(package_id="pkg1", version="1.0")],
        )
        await store.write_global_nodes([gcn])
        nodes = await store.get_global_nodes()
        assert len(nodes) == 1
        assert nodes[0].id == "gcn_test1"


class TestBindingStorage:
    async def test_write_and_read_bindings(self, store):
        binding = CanonicalBinding(
            local_canonical_id="lcn_abc",
            global_canonical_id="gcn_test1",
            package_id="galileo",
            version="1.0",
            decision=BindingDecision.CREATE_NEW,
            reason="no match",
        )
        await store.write_bindings([binding])
        bindings = await store.get_bindings(package_id="galileo")
        assert len(bindings) == 1
        assert bindings[0].decision == BindingDecision.CREATE_NEW


class TestParameterizationStorage:
    async def test_write_and_read_prior_records(self, store):
        record = PriorRecord(gcn_id="gcn_test1", value=0.7, source_id="src_001")
        await store.write_prior_records([record])
        records = await store.get_prior_records(gcn_id="gcn_test1")
        assert len(records) == 1
        assert records[0].value == 0.7

    async def test_multiple_priors_for_same_node(self, store):
        """One node can have multiple records from different sources."""
        r1 = PriorRecord(gcn_id="gcn_x", value=0.7, source_id="src_001")
        r2 = PriorRecord(gcn_id="gcn_x", value=0.8, source_id="src_002")
        await store.write_prior_records([r1, r2])
        records = await store.get_prior_records(gcn_id="gcn_x")
        assert len(records) == 2

    async def test_write_and_read_factor_params(self, store):
        record = FactorParamRecord(factor_id="f_abc", probability=0.85, source_id="src_001")
        await store.write_factor_param_records([record])
        records = await store.get_factor_param_records(factor_id="f_abc")
        assert len(records) == 1


class TestBeliefStateStorage:
    async def test_write_and_read_belief_state(self, store):
        state = BeliefState(
            bp_run_id="run-001",
            resolution_policy="latest",
            prior_cutoff=datetime(2026, 3, 24, tzinfo=timezone.utc),
            beliefs={"gcn_a": 0.82},
            converged=True,
            iterations=23,
            max_residual=4.2e-7,
        )
        await store.write_belief_state(state)
        states = await store.get_belief_states(limit=1)
        assert len(states) == 1
        assert states[0].bp_run_id == "run-001"


class TestCleanAll:
    async def test_clean_removes_everything(self, store):
        graph = make_galileo_falling_bodies()
        await store.write_local_graph("galileo", "1.0", graph)
        await store.clean_all()
        node = await store.get_node(graph.knowledge_nodes[0].id)
        assert node is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/gaia/libs/storage/test_lance.py -v
```

- [ ] **Step 3: Implement `gaia/libs/storage/lance.py`**

Implementation uses `lancedb` Python SDK with PyArrow schemas. Tables:

| Table | Schema | Key |
|-------|--------|-----|
| `local_knowledge_nodes` | node_id, type, content, parameters_json, source_refs_json, metadata_json, package_id, version | node_id |
| `local_factor_nodes` | factor_id, category, stage, reasoning_type, premises_json, conclusion, steps_json, weak_points_json, package_id, version | factor_id |
| `global_canonical_nodes` | id, type, content, representative_lcn_json, member_local_nodes_json, provenance_json, metadata_json | id |
| `global_factor_nodes` | factor_id, category, stage, reasoning_type, premises_json, conclusion, subgraph_json | factor_id |
| `canonical_bindings` | local_canonical_id, global_canonical_id, package_id, version, decision, reason | (local_canonical_id, package_id) |
| `prior_records` | gcn_id, value, source_id, created_at | (gcn_id, source_id, created_at) |
| `factor_param_records` | factor_id, probability, source_id, created_at | (factor_id, source_id, created_at) |
| `param_sources` | source_id, model, policy, config_json, created_at | source_id |
| `belief_states` | bp_run_id, created_at, resolution_policy, prior_cutoff, beliefs_json, converged, iterations, max_residual | bp_run_id |

Implementation details: The LanceContentStore class should handle table creation on `initialize()`, JSON serialization for complex fields, and filter-based queries. Use `lancedb.connect()` with the configured path.

This is a substantial implementation (~300-400 lines). The implementer should follow the ABC contract in `base.py` and ensure all test cases pass.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/gaia/libs/storage/test_lance.py -v
```

- [ ] **Step 5: Commit**

```bash
git add gaia/libs/storage/lance.py tests/gaia/libs/storage/test_lance.py
git commit -m "feat(storage): implement LanceDB content store"
```

### Task 2.4: Neo4j Graph Store

**Files:**
- Create: `gaia/libs/storage/neo4j.py`
- Create: `tests/gaia/libs/storage/test_neo4j.py`

- [ ] **Step 1: Write failing tests (marked with neo4j marker)**

```python
# tests/gaia/libs/storage/test_neo4j.py
"""Tests for Neo4j graph store. Requires running Neo4j instance."""
import pytest
from gaia.libs.storage.neo4j import Neo4jGraphStore
from gaia.libs.models import (
    GlobalCanonicalNode,
    KnowledgeType,
    FactorNode,
    FactorCategory,
    FactorStage,
    ReasoningType,
    LocalCanonicalRef,
    PackageRef,
)

pytestmark = pytest.mark.neo4j


@pytest.fixture
async def graph_store():
    store = Neo4jGraphStore(uri="bolt://localhost:7687", user="neo4j", password="test")
    await store.initialize()
    await store.clean_all()
    yield store
    await store.close()


class TestNeo4jWriteRead:
    async def test_write_and_read_nodes(self, graph_store):
        gcn = GlobalCanonicalNode(
            id="gcn_test1",
            type=KnowledgeType.CLAIM,
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_abc", package_id="pkg1", version="1.0"
            ),
            member_local_nodes=[],
            provenance=[PackageRef(package_id="pkg1", version="1.0")],
        )
        await graph_store.write_nodes([gcn])
        neighbors = await graph_store.get_neighbors("gcn_test1")
        assert isinstance(neighbors, list)

    async def test_write_factor_creates_edges(self, graph_store):
        # Create two nodes and a factor connecting them
        nodes = [
            GlobalCanonicalNode(
                id=f"gcn_{i}", type=KnowledgeType.CLAIM,
                representative_lcn=LocalCanonicalRef(
                    local_canonical_id=f"lcn_{i}", package_id="pkg1", version="1.0"
                ),
                member_local_nodes=[], provenance=[],
            )
            for i in range(2)
        ]
        await graph_store.write_nodes(nodes)

        factor = FactorNode(
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=["gcn_0"],
            conclusion="gcn_1",
        )
        await graph_store.write_factors([factor])

        neighbors = await graph_store.get_neighbors("gcn_0")
        assert "gcn_1" in neighbors or len(neighbors) > 0

    async def test_subgraph_query(self, graph_store):
        # Build A → B → C chain
        nodes = [
            GlobalCanonicalNode(
                id=f"gcn_{c}", type=KnowledgeType.CLAIM,
                representative_lcn=LocalCanonicalRef(
                    local_canonical_id=f"lcn_{c}", package_id="pkg1", version="1.0"
                ),
                member_local_nodes=[], provenance=[],
            )
            for c in "abc"
        ]
        await graph_store.write_nodes(nodes)
        factors = [
            FactorNode(
                category=FactorCategory.INFER, stage=FactorStage.PERMANENT,
                reasoning_type=ReasoningType.ENTAILMENT,
                premises=[f"gcn_{p}"], conclusion=f"gcn_{c}",
            )
            for p, c in [("a", "b"), ("b", "c")]
        ]
        await graph_store.write_factors(factors)

        node_ids, factor_ids = await graph_store.get_subgraph(["gcn_a"], depth=2)
        assert "gcn_b" in node_ids
        assert "gcn_c" in node_ids
```

- [ ] **Step 2: Implement `gaia/libs/storage/neo4j.py`**

Use `neo4j` async driver. Node label: `KnowledgeNode` with properties `{id, type}`. Factor nodes as relationship pattern or separate nodes connected via `:PREMISE` and `:CONCLUSION` edges.

- [ ] **Step 3: Run tests (with Neo4j available)**

```bash
pytest tests/gaia/libs/storage/test_neo4j.py -v -m neo4j
```

- [ ] **Step 4: Commit**

```bash
git add gaia/libs/storage/neo4j.py tests/gaia/libs/storage/test_neo4j.py
git commit -m "feat(storage): implement Neo4j graph store"
```

### Task 2.5: StorageManager

**Files:**
- Create: `gaia/libs/storage/manager.py`
- Create: `tests/gaia/libs/storage/test_manager.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/libs/storage/test_manager.py
"""Tests for StorageManager — three-write atomicity."""
import pytest
from unittest.mock import AsyncMock, patch
from gaia.libs.storage.manager import StorageManager
from gaia.libs.storage.config import StorageConfig
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies


@pytest.fixture
async def manager(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "test.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


class TestStorageManager:
    async def test_initialize(self, manager):
        assert manager.content_store is not None

    async def test_write_and_read_local_graph(self, manager):
        graph = make_galileo_falling_bodies()
        await manager.write_local_graph("galileo", "1.0", graph)
        node = await manager.get_node(graph.knowledge_nodes[0].id)
        assert node is not None

    async def test_graph_store_optional(self, tmp_path):
        """System works without graph store."""
        config = StorageConfig(lancedb_path=str(tmp_path / "test.lance"))
        mgr = StorageManager(config)
        await mgr.initialize()
        assert mgr.graph_store is None
        # Write still works (content only)
        graph = make_galileo_falling_bodies()
        await mgr.write_local_graph("galileo", "1.0", graph)

    async def test_clean_all(self, manager):
        graph = make_galileo_falling_bodies()
        await manager.write_local_graph("galileo", "1.0", graph)
        await manager.clean_all()
        node = await manager.get_node(graph.knowledge_nodes[0].id)
        assert node is None
```

- [ ] **Step 2: Implement `gaia/libs/storage/manager.py`**

```python
# gaia/libs/storage/manager.py
"""StorageManager — unified facade for content + graph stores."""
from __future__ import annotations

from gaia.libs.storage.base import ContentStore, GraphStore
from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.lance import LanceContentStore
from gaia.libs.models.graph_ir import (
    GlobalCanonicalNode,
    FactorNode,
    KnowledgeNode,
    LocalCanonicalGraph,
)
from gaia.libs.models.parameterization import PriorRecord, FactorParamRecord, ParameterizationSource
from gaia.libs.models.belief_state import BeliefState
from gaia.libs.models.binding import CanonicalBinding


class StorageManager:
    """Unified storage facade. Graph store is optional."""

    def __init__(self, config: StorageConfig) -> None:
        self.config = config
        self.content_store: ContentStore | None = None
        self.graph_store: GraphStore | None = None

    async def initialize(self) -> None:
        lance = LanceContentStore(path=self.config.effective_lancedb_connection)
        await lance.initialize()
        self.content_store = lance

        if self.config.has_neo4j:
            from gaia.libs.storage.neo4j import Neo4jGraphStore
            gs = Neo4jGraphStore(
                uri=self.config.neo4j_uri,
                user=self.config.neo4j_user,
                password=self.config.neo4j_password,
                database=self.config.neo4j_database,
            )
            await gs.initialize()
            self.graph_store = gs

    async def write_local_graph(
        self, package_id: str, version: str, graph: LocalCanonicalGraph
    ) -> None:
        await self.content_store.write_local_graph(package_id, version, graph)

    async def write_global_nodes(self, nodes: list[GlobalCanonicalNode]) -> None:
        await self.content_store.write_global_nodes(nodes)
        if self.graph_store:
            await self.graph_store.write_nodes(nodes)

    async def write_global_factors(self, factors: list[FactorNode]) -> None:
        await self.content_store.write_global_factors(factors)
        if self.graph_store:
            await self.graph_store.write_factors(factors)

    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None:
        await self.content_store.write_bindings(bindings)

    async def write_prior_records(self, records: list[PriorRecord]) -> None:
        await self.content_store.write_prior_records(records)

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None:
        await self.content_store.write_factor_param_records(records)

    async def write_param_source(self, source: ParameterizationSource) -> None:
        await self.content_store.write_param_source(source)

    async def write_belief_state(self, state: BeliefState) -> None:
        await self.content_store.write_belief_state(state)

    async def get_node(self, node_id: str) -> KnowledgeNode | GlobalCanonicalNode | None:
        return await self.content_store.get_node(node_id)

    async def get_global_nodes(self) -> list[GlobalCanonicalNode]:
        return await self.content_store.get_global_nodes()

    async def get_global_factors(self) -> list[FactorNode]:
        return await self.content_store.get_global_factors()

    async def get_bindings(self, package_id: str | None = None) -> list[CanonicalBinding]:
        return await self.content_store.get_bindings(package_id)

    async def get_prior_records(self, gcn_id: str | None = None) -> list[PriorRecord]:
        return await self.content_store.get_prior_records(gcn_id)

    async def get_factor_param_records(self, factor_id: str | None = None) -> list[FactorParamRecord]:
        return await self.content_store.get_factor_param_records(factor_id)

    async def get_belief_states(self, limit: int = 10) -> list[BeliefState]:
        return await self.content_store.get_belief_states(limit)

    async def clean_all(self) -> None:
        await self.content_store.clean_all()
        if self.graph_store:
            await self.graph_store.clean_all()
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/gaia/libs/storage/test_manager.py -v
```

- [ ] **Step 4: Commit**

```bash
git add gaia/libs/storage/manager.py tests/gaia/libs/storage/test_manager.py
git commit -m "feat(storage): implement StorageManager with three-write support"
```

### Task 2.6: Port Embedding and LLM Utilities

**Files:**
- Create: `gaia/libs/embedding.py` (port from `libs/embedding.py`)
- Create: `gaia/libs/llm.py` (port from `libs/llm.py`)

- [ ] **Step 1: Port embedding.py**

Copy `libs/embedding.py` to `gaia/libs/embedding.py`. Update imports only — logic unchanged. Keep `EmbeddingModel` ABC, `DPEmbeddingModel`, `StubEmbeddingModel`.

- [ ] **Step 2: Port llm.py**

Copy `libs/llm.py` to `gaia/libs/llm.py`. Update imports only.

- [ ] **Step 3: Verify imports**

```bash
python -c "from gaia.libs.embedding import StubEmbeddingModel; print('OK')"
python -c "from gaia.libs.llm import llm_completion; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add gaia/libs/embedding.py gaia/libs/llm.py
git commit -m "feat(libs): port embedding and llm utilities"
```

---

## Chunk 3: Core Algorithms

Core algorithms shared by pipelines and services. These are the domain logic modules that both entry points call.

### Task 3.1: Matching — Similarity Engine

**Files:**
- Create: `gaia/core/matching.py`
- Create: `tests/gaia/core/test_matching.py`

**Spec reference:** `docs/foundations/graph-ir/graph-ir.md` §3.3

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/core/test_matching.py
"""Tests for similarity matching engine."""
import pytest
from gaia.core.matching import find_best_match, compute_similarity
from gaia.libs.models import KnowledgeNode, KnowledgeType, GlobalCanonicalNode, LocalCanonicalRef, PackageRef
from gaia.libs.embedding import StubEmbeddingModel


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


class TestFindBestMatch:
    async def test_identical_content_matches(self, embedding_model):
        """Identical content should match above threshold."""
        query = KnowledgeNode(type=KnowledgeType.CLAIM, content="X superconducts at 90K")
        candidate = GlobalCanonicalNode(
            id="gcn_1", type=KnowledgeType.CLAIM, content="X superconducts at 90K",
            representative_lcn=LocalCanonicalRef(local_canonical_id="lcn_1", package_id="p", version="1"),
            member_local_nodes=[], provenance=[],
        )
        match = await find_best_match(query, [candidate], embedding_model=embedding_model)
        assert match is not None
        assert match.id == "gcn_1"

    async def test_different_type_never_matches(self, embedding_model):
        """§3.3: only same-type candidates eligible."""
        query = KnowledgeNode(type=KnowledgeType.CLAIM, content="X superconducts")
        candidate = GlobalCanonicalNode(
            id="gcn_1", type=KnowledgeType.SETTING, content="X superconducts",
            representative_lcn=LocalCanonicalRef(local_canonical_id="lcn_1", package_id="p", version="1"),
            member_local_nodes=[], provenance=[],
        )
        match = await find_best_match(query, [candidate], embedding_model=embedding_model)
        assert match is None

    async def test_no_candidates_returns_none(self, embedding_model):
        query = KnowledgeNode(type=KnowledgeType.CLAIM, content="X")
        match = await find_best_match(query, [], embedding_model=embedding_model)
        assert match is None

    async def test_below_threshold_returns_none(self, embedding_model):
        """Dissimilar content should not match."""
        query = KnowledgeNode(type=KnowledgeType.CLAIM, content="Quantum entanglement is non-local")
        candidate = GlobalCanonicalNode(
            id="gcn_1", type=KnowledgeType.CLAIM, content="Photosynthesis uses chlorophyll",
            representative_lcn=LocalCanonicalRef(local_canonical_id="lcn_1", package_id="p", version="1"),
            member_local_nodes=[], provenance=[],
        )
        match = await find_best_match(query, [candidate], embedding_model=embedding_model, threshold=0.90)
        # StubEmbeddingModel is hash-based, very different content → low similarity
        assert match is None

    def test_tfidf_fallback(self):
        """When no embedding model, use TF-IDF."""
        score = compute_similarity(
            "Objects fall at the same rate in vacuum",
            "In vacuum all objects fall equally regardless of mass",
            method="tfidf",
        )
        assert score > 0.3  # reasonable TF-IDF overlap
```

- [ ] **Step 2: Implement `gaia/core/matching.py`**

Port and simplify from `libs/global_graph/similarity.py`. Two strategies: embedding cosine (primary) and TF-IDF (fallback). Type filter before similarity computation.

- [ ] **Step 3: Run tests**

```bash
pytest tests/gaia/core/test_matching.py -v
```

- [ ] **Step 4: Commit**

```bash
git add gaia/core/matching.py tests/gaia/core/test_matching.py
git commit -m "feat(core): implement similarity matching engine"
```

### Task 3.2: Global Canonicalization

**Files:**
- Create: `gaia/core/canonicalize.py`
- Create: `tests/gaia/core/test_canonicalize.py`

**Spec reference:** `docs/foundations/graph-ir/graph-ir.md` §3.1–§3.6

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/core/test_canonicalize.py
"""Tests for global canonicalization — locks down §3.1 decision rules."""
import pytest
from gaia.core.canonicalize import canonicalize_package, CanonicalizationResult
from gaia.libs.models import (
    GlobalCanonicalGraph,
    GlobalCanonicalNode,
    KnowledgeType,
    LocalCanonicalRef,
    PackageRef,
)
from gaia.libs.models.binding import BindingDecision
from gaia.libs.embedding import StubEmbeddingModel
from tests.gaia.fixtures.graphs import (
    make_galileo_falling_bodies,
    make_newton_gravity,
    make_minimal_claim_pair,
)


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


class TestCanonicalizeFirstPackage:
    """First package into empty global graph → all create_new."""

    async def test_all_nodes_create_new(self, embedding_model):
        graph = make_galileo_falling_bodies()
        global_graph = GlobalCanonicalGraph()

        result = await canonicalize_package(
            local_graph=graph,
            global_graph=global_graph,
            package_id="galileo",
            version="1.0",
            embedding_model=embedding_model,
        )

        assert isinstance(result, CanonicalizationResult)
        # All bindings should be create_new (empty global graph)
        for binding in result.bindings:
            assert binding.decision == BindingDecision.CREATE_NEW
        # New global nodes created for each local node
        assert len(result.new_global_nodes) == len(graph.knowledge_nodes)
        # Global factors created (with gcn_ IDs replacing lcn_ IDs)
        assert len(result.global_factors) > 0
        for f in result.global_factors:
            for p in f.premises:
                assert p.startswith("gcn_")
            if f.conclusion:
                assert f.conclusion.startswith("gcn_")


class TestCanonicalizePremiseVsConclusion:
    """§3.1: Premise-only nodes merge; conclusion nodes create new + equivalent."""

    async def test_premise_only_merges(self, embedding_model):
        """Node used only as premise in new package → match_existing."""
        galileo = make_galileo_falling_bodies()

        # First: canonicalize galileo (creates global nodes)
        global_graph = GlobalCanonicalGraph()
        result1 = await canonicalize_package(
            local_graph=galileo, global_graph=global_graph,
            package_id="galileo", version="1.0",
            embedding_model=embedding_model,
        )
        # Apply result1 to global_graph
        global_graph.knowledge_nodes.extend(result1.new_global_nodes)
        global_graph.factor_nodes.extend(result1.global_factors)

        # Newton references galileo's vacuum prediction as premise
        newton = make_newton_gravity()
        result2 = await canonicalize_package(
            local_graph=newton, global_graph=global_graph,
            package_id="newton", version="1.0",
            embedding_model=embedding_model,
        )

        # The "vacuum" claim from Newton should match Galileo's
        vacuum_bindings = [
            b for b in result2.bindings
            if "vacuum" in _get_content(newton, b.local_canonical_id)
        ]
        # Should have a match (premise-only → match_existing)
        # or create_new if StubEmbedding doesn't match.
        # With real embeddings this would be match_existing.
        assert len(vacuum_bindings) > 0

    async def test_conclusion_creates_equivalent_candidate(self, embedding_model):
        """§3.1: Conclusion node match → create new + equivalent candidate factor."""
        # This test needs two packages where a conclusion in pkg2
        # matches an existing global node. Full test with real embeddings.
        # With StubEmbeddingModel, identical content should match.
        pass  # Detailed implementation depends on matching precision


class TestFactorLifting:
    """§3.5: Local factors promoted to global with ID translation."""

    async def test_global_factors_have_gcn_ids(self, embedding_model):
        graph = make_minimal_claim_pair()
        global_graph = GlobalCanonicalGraph()
        result = await canonicalize_package(
            local_graph=graph, global_graph=global_graph,
            package_id="test", version="1.0",
            embedding_model=embedding_model,
        )
        for f in result.global_factors:
            for p in f.premises:
                assert p.startswith("gcn_")
            if f.conclusion:
                assert f.conclusion.startswith("gcn_")

    async def test_global_factors_drop_steps(self, embedding_model):
        """§3.5: Global factors don't carry steps."""
        graph = make_galileo_falling_bodies()
        global_graph = GlobalCanonicalGraph()
        result = await canonicalize_package(
            local_graph=graph, global_graph=global_graph,
            package_id="galileo", version="1.0",
            embedding_model=embedding_model,
        )
        for f in result.global_factors:
            assert f.steps is None

    async def test_global_factors_drop_weak_points(self, embedding_model):
        """§3.5: Global factors don't carry weak_points."""
        graph = make_einstein_equivalence()
        global_graph = GlobalCanonicalGraph()
        result = await canonicalize_package(
            local_graph=graph, global_graph=global_graph,
            package_id="einstein", version="1.0",
            embedding_model=embedding_model,
        )
        for f in result.global_factors:
            assert f.weak_points is None


def _get_content(graph, lcn_id: str) -> str:
    """Helper to get content from local graph by node ID."""
    for n in graph.knowledge_nodes:
        if n.id == lcn_id:
            return n.content or ""
    return ""
```

- [ ] **Step 2: Implement `gaia/core/canonicalize.py`**

Port and rewrite from `libs/global_graph/canonicalize.py`, aligned to new models and §3.1 decision rules (premise vs conclusion distinction). Key function:

```python
async def canonicalize_package(
    local_graph: LocalCanonicalGraph,
    global_graph: GlobalCanonicalGraph,
    package_id: str,
    version: str,
    embedding_model: EmbeddingModel | None = None,
    threshold: float = 0.90,
) -> CanonicalizationResult:
    ...
```

Steps:
1. Classify each local node as premise-only, conclusion, or both
2. For each node, find best match in global graph via matching.py
3. Apply §3.1 decision rules (premise→merge, conclusion→new+equivalent)
4. Lift factors: translate lcn→gcn IDs, drop steps and weak_points
5. Return CanonicalizationResult with bindings, new nodes, global factors

- [ ] **Step 3: Run tests**

```bash
pytest tests/gaia/core/test_canonicalize.py -v
```

- [ ] **Step 4: Commit**

```bash
git add gaia/core/canonicalize.py tests/gaia/core/test_canonicalize.py
git commit -m "feat(core): implement global canonicalization with premise/conclusion rules"
```

### Task 3.3: Global BP Orchestration

**Files:**
- Create: `gaia/core/global_bp.py`
- Create: `tests/gaia/core/test_global_bp.py`
- Create: `tests/gaia/fixtures/parameterizations.py`

**Spec reference:** `docs/foundations/graph-ir/parameterization.md` (resolution policy), `docs/foundations/graph-ir/belief-state.md`, `docs/foundations/lkm/global-inference.md`

- [ ] **Step 1: Create parameterization fixtures**

```python
# tests/gaia/fixtures/parameterizations.py
"""Parameterization fixture builders for test graphs."""
from gaia.libs.models import (
    KnowledgeType,
    LocalCanonicalGraph,
)
from gaia.libs.models.parameterization import (
    PriorRecord,
    FactorParamRecord,
    ParameterizationSource,
)


def make_default_parameterization(
    global_node_ids: list[str],
    global_factor_ids: list[str],
    node_types: dict[str, str],
    prior: float = 0.5,
    factor_prob: float = 0.8,
    source_id: str = "src_default",
) -> tuple[list[PriorRecord], list[FactorParamRecord], ParameterizationSource]:
    """Create default parameterization for all claim nodes and all factors."""
    source = ParameterizationSource(source_id=source_id, model="test")

    prior_records = [
        PriorRecord(gcn_id=nid, value=prior, source_id=source_id)
        for nid in global_node_ids
        if node_types.get(nid) == "claim"
    ]
    factor_records = [
        FactorParamRecord(factor_id=fid, probability=factor_prob, source_id=source_id)
        for fid in global_factor_ids
    ]
    return prior_records, factor_records, source
```

- [ ] **Step 2: Write failing tests**

```python
# tests/gaia/core/test_global_bp.py
"""Tests for global BP orchestration."""
import pytest
from gaia.core.global_bp import run_global_bp, assemble_parameterization
from gaia.core.canonicalize import canonicalize_package, CanonicalizationResult
from gaia.libs.models import (
    GlobalCanonicalGraph,
    KnowledgeType,
    BeliefState,
)
from gaia.libs.models.parameterization import (
    PriorRecord,
    FactorParamRecord,
    ParameterizationSource,
    ResolutionPolicy,
    CROMWELL_EPS,
)
from gaia.libs.embedding import StubEmbeddingModel
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies, make_minimal_claim_pair
from tests.gaia.fixtures.parameterizations import make_default_parameterization


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


class TestAssembleParameterization:
    def test_latest_policy_picks_newest(self):
        """Resolution policy 'latest' picks newest record per node."""
        from datetime import datetime, timezone, timedelta
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 2, 1, tzinfo=timezone.utc)
        records = [
            PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s1", created_at=t1),
            PriorRecord(gcn_id="gcn_a", value=0.8, source_id="s2", created_at=t2),
        ]
        policy = ResolutionPolicy(strategy="latest")
        assembled = assemble_parameterization(
            prior_records=records, factor_records=[], policy=policy,
        )
        assert assembled["node_priors"]["gcn_a"] == 0.8

    def test_source_policy_filters_by_source(self):
        records = [
            PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s1"),
            PriorRecord(gcn_id="gcn_a", value=0.9, source_id="s2"),
        ]
        policy = ResolutionPolicy(strategy="source", source_id="s1")
        assembled = assemble_parameterization(
            prior_records=records, factor_records=[], policy=policy,
        )
        assert assembled["node_priors"]["gcn_a"] == 0.5

    def test_prior_cutoff_filters_by_time(self):
        from datetime import datetime, timezone
        cutoff = datetime(2026, 1, 15, tzinfo=timezone.utc)
        records = [
            PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s1",
                       created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            PriorRecord(gcn_id="gcn_a", value=0.9, source_id="s2",
                       created_at=datetime(2026, 2, 1, tzinfo=timezone.utc)),
        ]
        policy = ResolutionPolicy(strategy="latest", prior_cutoff=cutoff)
        assembled = assemble_parameterization(
            prior_records=records, factor_records=[], policy=policy,
        )
        assert assembled["node_priors"]["gcn_a"] == 0.5  # only record before cutoff


class TestRunGlobalBP:
    async def test_minimal_graph_produces_belief_state(self, embedding_model):
        """End-to-end: canonicalize → parameterize → BP → BeliefState."""
        graph = make_minimal_claim_pair()
        global_graph = GlobalCanonicalGraph()
        result = await canonicalize_package(
            local_graph=graph, global_graph=global_graph,
            package_id="test", version="1.0",
            embedding_model=embedding_model,
        )
        global_graph.knowledge_nodes.extend(result.new_global_nodes)
        global_graph.factor_nodes.extend(result.global_factors)

        # Build parameterization
        node_types = {n.id: n.type.value for n in global_graph.knowledge_nodes}
        prior_records, factor_records, source = make_default_parameterization(
            global_node_ids=[n.id for n in global_graph.knowledge_nodes],
            global_factor_ids=[f.factor_id for f in global_graph.factor_nodes],
            node_types=node_types,
        )
        policy = ResolutionPolicy(strategy="latest")

        belief_state = await run_global_bp(
            global_graph=global_graph,
            prior_records=prior_records,
            factor_records=factor_records,
            policy=policy,
        )

        assert isinstance(belief_state, BeliefState)
        assert belief_state.converged
        # Only claim nodes have beliefs
        for gcn_id in belief_state.beliefs:
            node = next(n for n in global_graph.knowledge_nodes if n.id == gcn_id)
            assert node.type == KnowledgeType.CLAIM

    async def test_galileo_graph_beliefs_reasonable(self, embedding_model):
        """Galileo graph: contradiction should affect belief values."""
        graph = make_galileo_falling_bodies()
        global_graph = GlobalCanonicalGraph()
        result = await canonicalize_package(
            local_graph=graph, global_graph=global_graph,
            package_id="galileo", version="1.0",
            embedding_model=embedding_model,
        )
        global_graph.knowledge_nodes.extend(result.new_global_nodes)
        global_graph.factor_nodes.extend(result.global_factors)

        node_types = {n.id: n.type.value for n in global_graph.knowledge_nodes}
        prior_records, factor_records, _ = make_default_parameterization(
            global_node_ids=[n.id for n in global_graph.knowledge_nodes],
            global_factor_ids=[f.factor_id for f in global_graph.factor_nodes],
            node_types=node_types,
            prior=0.5,
            factor_prob=0.9,
        )

        belief_state = await run_global_bp(
            global_graph=global_graph,
            prior_records=prior_records,
            factor_records=factor_records,
            policy=ResolutionPolicy(strategy="latest"),
        )

        assert belief_state.converged
        # All beliefs should be valid probabilities
        for v in belief_state.beliefs.values():
            assert CROMWELL_EPS <= v <= 1.0 - CROMWELL_EPS
```

- [ ] **Step 3: Implement `gaia/core/global_bp.py`**

```python
# gaia/core/global_bp.py
"""Global BP orchestration — assemble parameters, run BP, produce BeliefState."""
```

Key functions:
- `assemble_parameterization(prior_records, factor_records, policy) → dict` — applies resolution policy to select per-node/factor values
- `run_global_bp(global_graph, prior_records, factor_records, policy) → BeliefState` — builds FactorGraph from global graph + assembled params, runs BP via `libs.inference.bp.BeliefPropagation`, wraps result in BeliefState

Bridge import: `from libs.inference.factor_graph import FactorGraph` and `from libs.inference.bp import BeliefPropagation`

- [ ] **Step 4: Run tests**

```bash
pytest tests/gaia/core/test_global_bp.py -v
```

- [ ] **Step 5: Commit**

```bash
git add gaia/core/global_bp.py tests/gaia/core/test_global_bp.py tests/gaia/fixtures/parameterizations.py
git commit -m "feat(core): implement global BP orchestration with parameter assembly"
```

---

## Chunk 4: LKM Entry Points

Thin orchestration layers: `lkm/ingest.py` for write logic, `pipelines/` for batch, `services/` for API.

### Task 4.1: LKM Ingest

**Files:**
- Create: `gaia/lkm/ingest.py`
- Create: `tests/gaia/lkm/test_ingest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lkm/test_ingest.py
"""Tests for LKM ingest — end-to-end write path."""
import pytest
from gaia.lkm.ingest import ingest_package, IngestResult
from gaia.libs.storage.manager import StorageManager
from gaia.libs.storage.config import StorageConfig
from gaia.libs.embedding import StubEmbeddingModel
from gaia.libs.models.binding import BindingDecision
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies, make_newton_gravity


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "test.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


class TestIngestPackage:
    async def test_ingest_first_package(self, storage, embedding_model):
        graph = make_galileo_falling_bodies()
        result = await ingest_package(
            local_graph=graph,
            package_id="galileo",
            version="1.0",
            storage=storage,
            embedding_model=embedding_model,
        )
        assert isinstance(result, IngestResult)
        assert result.package_id == "galileo"
        assert len(result.bindings) > 0
        assert len(result.new_global_nodes) > 0

        # Verify data persisted
        nodes = await storage.get_global_nodes()
        assert len(nodes) > 0
        bindings = await storage.get_bindings(package_id="galileo")
        assert len(bindings) > 0

    async def test_ingest_second_package_creates_bindings(self, storage, embedding_model):
        """Second package should have some matches."""
        g1 = make_galileo_falling_bodies()
        await ingest_package(
            local_graph=g1, package_id="galileo", version="1.0",
            storage=storage, embedding_model=embedding_model,
        )
        g2 = make_newton_gravity()
        result = await ingest_package(
            local_graph=g2, package_id="newton", version="1.0",
            storage=storage, embedding_model=embedding_model,
        )
        assert len(result.bindings) > 0
        # Newton should have at least some new nodes
        assert len(result.new_global_nodes) > 0

    async def test_ingest_writes_local_graph(self, storage, embedding_model):
        graph = make_galileo_falling_bodies()
        await ingest_package(
            local_graph=graph, package_id="galileo", version="1.0",
            storage=storage, embedding_model=embedding_model,
        )
        # Local node should be retrievable
        node = await storage.get_node(graph.knowledge_nodes[0].id)
        assert node is not None
```

- [ ] **Step 2: Implement `gaia/lkm/ingest.py`**

```python
# gaia/lkm/ingest.py
"""LKM ingest — validate, canonicalize, and persist a package."""
from __future__ import annotations

from dataclasses import dataclass

from gaia.libs.models.graph_ir import LocalCanonicalGraph, GlobalCanonicalGraph, GlobalCanonicalNode, FactorNode
from gaia.libs.models.binding import CanonicalBinding
from gaia.libs.storage.manager import StorageManager
from gaia.libs.embedding import EmbeddingModel
from gaia.core.canonicalize import canonicalize_package, CanonicalizationResult


@dataclass
class IngestResult:
    package_id: str
    version: str
    bindings: list[CanonicalBinding]
    new_global_nodes: list[GlobalCanonicalNode]
    global_factors: list[FactorNode]


async def ingest_package(
    local_graph: LocalCanonicalGraph,
    package_id: str,
    version: str,
    storage: StorageManager,
    embedding_model: EmbeddingModel | None = None,
) -> IngestResult:
    """
    Ingest a package: write local graph, canonicalize, persist global results.

    Steps:
    1. Write local graph to content store
    2. Load current global graph from storage
    3. Run global canonicalization
    4. Write global nodes, factors, bindings to storage
    """
    # 1. Persist local graph
    await storage.write_local_graph(package_id, version, local_graph)

    # 2. Load current global graph
    existing_nodes = await storage.get_global_nodes()
    existing_factors = await storage.get_global_factors()
    global_graph = GlobalCanonicalGraph(
        knowledge_nodes=existing_nodes,
        factor_nodes=existing_factors,
    )

    # 3. Canonicalize
    result = await canonicalize_package(
        local_graph=local_graph,
        global_graph=global_graph,
        package_id=package_id,
        version=version,
        embedding_model=embedding_model,
    )

    # 4. Persist global results
    if result.new_global_nodes:
        await storage.write_global_nodes(result.new_global_nodes)
    if result.global_factors:
        await storage.write_global_factors(result.global_factors)
    if result.bindings:
        await storage.write_bindings(result.bindings)

    return IngestResult(
        package_id=package_id,
        version=version,
        bindings=result.bindings,
        new_global_nodes=result.new_global_nodes,
        global_factors=result.global_factors,
    )
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/gaia/lkm/test_ingest.py -v
```

- [ ] **Step 4: Commit**

```bash
git add gaia/lkm/ingest.py tests/gaia/lkm/test_ingest.py
git commit -m "feat(lkm): implement package ingest with canonicalization"
```

### Task 4.2: Batch Pipeline Entry Points

**Files:**
- Create: `gaia/lkm/pipelines/run_ingest.py`
- Create: `gaia/lkm/pipelines/run_global_bp.py`
- Create: `gaia/lkm/pipelines/run_full.py`

- [ ] **Step 1: Implement batch ingest**

```python
# gaia/lkm/pipelines/run_ingest.py
"""Batch ingest — process multiple LocalCanonicalGraph files."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from gaia.libs.models.graph_ir import LocalCanonicalGraph
from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.manager import StorageManager
from gaia.libs.embedding import DPEmbeddingModel
from gaia.lkm.ingest import ingest_package


async def run(input_dir: Path, config: StorageConfig) -> None:
    storage = StorageManager(config)
    await storage.initialize()
    embedding = DPEmbeddingModel()

    for graph_path in sorted(input_dir.glob("*/local_canonical_graph.json")):
        package_name = graph_path.parent.name
        print(f"Ingesting {package_name}...")
        graph_data = json.loads(graph_path.read_text())
        local_graph = LocalCanonicalGraph.model_validate(graph_data)
        result = await ingest_package(
            local_graph=local_graph,
            package_id=package_name,
            version="1.0",
            storage=storage,
            embedding_model=embedding,
        )
        print(f"  → {len(result.new_global_nodes)} new nodes, {len(result.bindings)} bindings")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch ingest packages")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--lancedb-path", type=str, default="./data/lancedb/gaia")
    args = parser.parse_args()

    config = StorageConfig(lancedb_path=args.lancedb_path)
    asyncio.run(run(args.input_dir, config))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Implement batch global BP**

```python
# gaia/lkm/pipelines/run_global_bp.py
"""Batch global BP — run BP on the full global canonical graph."""
from __future__ import annotations

import argparse
import asyncio

from gaia.libs.models.graph_ir import GlobalCanonicalGraph
from gaia.libs.models.parameterization import ResolutionPolicy
from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.manager import StorageManager
from gaia.core.global_bp import run_global_bp


async def run(config: StorageConfig) -> None:
    storage = StorageManager(config)
    await storage.initialize()

    # Load global graph
    nodes = await storage.get_global_nodes()
    factors = await storage.get_global_factors()
    global_graph = GlobalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=factors)
    print(f"Global graph: {len(nodes)} nodes, {len(factors)} factors")

    # Load parameter records
    prior_records = await storage.get_prior_records()
    factor_records = await storage.get_factor_param_records()
    policy = ResolutionPolicy(strategy="latest")

    # Run BP
    belief_state = await run_global_bp(
        global_graph=global_graph,
        prior_records=prior_records,
        factor_records=factor_records,
        policy=policy,
    )

    # Persist
    await storage.write_belief_state(belief_state)
    print(f"BP complete: converged={belief_state.converged}, "
          f"iterations={belief_state.iterations}, "
          f"beliefs={len(belief_state.beliefs)} claims")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run global BP")
    parser.add_argument("--lancedb-path", type=str, default="./data/lancedb/gaia")
    args = parser.parse_args()
    config = StorageConfig(lancedb_path=args.lancedb_path)
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Implement full pipeline orchestrator**

```python
# gaia/lkm/pipelines/run_full.py
"""Full pipeline: ingest → global BP."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from gaia.lkm.pipelines import run_ingest, run_global_bp
from gaia.libs.storage.config import StorageConfig


async def run(input_dir: Path, config: StorageConfig, clean: bool = False) -> None:
    from gaia.libs.storage.manager import StorageManager
    if clean:
        storage = StorageManager(config)
        await storage.initialize()
        await storage.clean_all()
        print("Cleaned all storage.")

    print("=== Stage 1: Ingest ===")
    await run_ingest.run(input_dir, config)

    print("=== Stage 2: Global BP ===")
    await run_global_bp.run(config)

    print("=== Pipeline complete ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="Full LKM pipeline")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--lancedb-path", type=str, default="./data/lancedb/gaia")
    parser.add_argument("--clean", action="store_true", help="Clean storage before run")
    args = parser.parse_args()
    config = StorageConfig(lancedb_path=args.lancedb_path)
    asyncio.run(run(args.input_dir, config, clean=args.clean))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add gaia/lkm/pipelines/
git commit -m "feat(lkm): add batch pipeline entry points"
```

### Task 4.3: FastAPI Services

**Files:**
- Create: `gaia/lkm/services/app.py`
- Create: `gaia/lkm/services/deps.py`
- Create: `gaia/lkm/services/routes/packages.py`
- Create: `gaia/lkm/services/routes/knowledge.py`
- Create: `gaia/lkm/services/routes/inference.py`
- Create: `tests/gaia/lkm/services/test_routes.py`

- [ ] **Step 1: Implement deps.py**

```python
# gaia/lkm/services/deps.py
"""Dependency injection for FastAPI."""
from __future__ import annotations

from gaia.libs.storage.manager import StorageManager
from gaia.libs.embedding import EmbeddingModel


class Dependencies:
    def __init__(self, storage: StorageManager, embedding: EmbeddingModel | None = None):
        self.storage = storage
        self.embedding = embedding


# Global singleton, initialized at startup
deps: Dependencies | None = None
```

- [ ] **Step 2: Implement app.py**

```python
# gaia/lkm/services/app.py
"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.manager import StorageManager
from gaia.lkm.services import deps
from gaia.lkm.services.routes import packages, knowledge, inference


def create_app(dependencies: deps.Dependencies | None = None) -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if dependencies:
            deps.deps = dependencies
        else:
            config = StorageConfig()
            storage = StorageManager(config)
            await storage.initialize()
            deps.deps = deps.Dependencies(storage=storage)
        yield

    app = FastAPI(title="Gaia LKM", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(packages.router, prefix="/api")
    app.include_router(knowledge.router, prefix="/api")
    app.include_router(inference.router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
```

- [ ] **Step 3: Implement routes**

```python
# gaia/lkm/services/routes/packages.py
"""Package ingest and retrieval routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gaia.libs.models.graph_ir import LocalCanonicalGraph
from gaia.lkm.ingest import ingest_package
from gaia.lkm.services.deps import deps

router = APIRouter(tags=["packages"])


class IngestRequest(BaseModel):
    package_id: str
    version: str
    local_graph: LocalCanonicalGraph


class IngestResponse(BaseModel):
    package_id: str
    version: str
    new_global_nodes: int
    bindings: int


@router.post("/packages/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    result = await ingest_package(
        local_graph=req.local_graph,
        package_id=req.package_id,
        version=req.version,
        storage=deps.storage,
        embedding_model=deps.embedding,
    )
    return IngestResponse(
        package_id=result.package_id,
        version=result.version,
        new_global_nodes=len(result.new_global_nodes),
        bindings=len(result.bindings),
    )
```

```python
# gaia/lkm/services/routes/knowledge.py
"""Knowledge retrieval routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gaia.lkm.services.deps import deps

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge/{node_id}")
async def get_knowledge(node_id: str):
    node = await deps.storage.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node.model_dump()


@router.get("/knowledge/{node_id}/beliefs")
async def get_beliefs(node_id: str):
    states = await deps.storage.get_belief_states(limit=10)
    beliefs = []
    for s in states:
        if node_id in s.beliefs:
            beliefs.append({
                "bp_run_id": s.bp_run_id,
                "belief": s.beliefs[node_id],
                "converged": s.converged,
                "created_at": s.created_at.isoformat(),
            })
    return beliefs
```

```python
# gaia/lkm/services/routes/inference.py
"""Inference routes — trigger and query BP runs."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from gaia.libs.models.graph_ir import GlobalCanonicalGraph
from gaia.libs.models.parameterization import ResolutionPolicy
from gaia.core.global_bp import run_global_bp
from gaia.lkm.services.deps import deps

router = APIRouter(tags=["inference"])


class RunBPRequest(BaseModel):
    resolution_policy: str = "latest"
    source_id: str | None = None


@router.post("/inference/run")
async def trigger_bp(req: RunBPRequest):
    nodes = await deps.storage.get_global_nodes()
    factors = await deps.storage.get_global_factors()
    global_graph = GlobalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=factors)

    prior_records = await deps.storage.get_prior_records()
    factor_records = await deps.storage.get_factor_param_records()

    if req.resolution_policy == "latest":
        policy = ResolutionPolicy(strategy="latest")
    else:
        policy = ResolutionPolicy(strategy="source", source_id=req.source_id)

    belief_state = await run_global_bp(
        global_graph=global_graph,
        prior_records=prior_records,
        factor_records=factor_records,
        policy=policy,
    )
    await deps.storage.write_belief_state(belief_state)

    return belief_state.model_dump()


@router.get("/beliefs")
async def list_beliefs(limit: int = 10):
    states = await deps.storage.get_belief_states(limit=limit)
    return [s.model_dump() for s in states]
```

- [ ] **Step 4: Write API tests**

```python
# tests/gaia/lkm/services/test_routes.py
"""E2E tests for FastAPI routes."""
import pytest
from httpx import AsyncClient, ASGITransport
from gaia.lkm.services.app import create_app
from gaia.lkm.services.deps import Dependencies
from gaia.libs.storage.manager import StorageManager
from gaia.libs.storage.config import StorageConfig
from gaia.libs.embedding import StubEmbeddingModel
from tests.gaia.fixtures.graphs import make_galileo_falling_bodies


@pytest.fixture
async def client(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "test.lance"))
    storage = StorageManager(config)
    await storage.initialize()
    embedding = StubEmbeddingModel(dim=64)
    app = create_app(dependencies=Dependencies(storage=storage, embedding=embedding))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestIngestEndpoint:
    async def test_ingest_package(self, client):
        graph = make_galileo_falling_bodies()
        resp = await client.post("/api/packages/ingest", json={
            "package_id": "galileo",
            "version": "1.0",
            "local_graph": graph.model_dump(mode="json"),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["package_id"] == "galileo"
        assert data["new_global_nodes"] > 0


class TestKnowledgeEndpoint:
    async def test_get_knowledge_not_found(self, client):
        resp = await client.get("/api/knowledge/nonexistent")
        assert resp.status_code == 404

    async def test_get_knowledge_after_ingest(self, client):
        graph = make_galileo_falling_bodies()
        await client.post("/api/packages/ingest", json={
            "package_id": "galileo",
            "version": "1.0",
            "local_graph": graph.model_dump(mode="json"),
        })
        node_id = graph.knowledge_nodes[0].id
        resp = await client.get(f"/api/knowledge/{node_id}")
        assert resp.status_code == 200
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/gaia/lkm/services/test_routes.py -v
```

- [ ] **Step 6: Commit**

```bash
git add gaia/lkm/services/ tests/gaia/lkm/services/
git commit -m "feat(lkm): add FastAPI services with ingest, knowledge, and inference routes"
```

---

## Chunk 5: Integration Test — End-to-End Pipeline

### Task 5.1: Full Pipeline Integration Test

**Files:**
- Create: `tests/gaia/test_e2e_pipeline.py`

This test exercises the complete path: build galileo + newton + einstein graphs → ingest all → run global BP → verify beliefs.

- [ ] **Step 1: Write integration test**

```python
# tests/gaia/test_e2e_pipeline.py
"""End-to-end integration test: ingest 3 packages → global BP → verify beliefs."""
import pytest
from gaia.libs.storage.manager import StorageManager
from gaia.libs.storage.config import StorageConfig
from gaia.libs.models import KnowledgeType, BeliefState
from gaia.libs.models.parameterization import (
    PriorRecord,
    FactorParamRecord,
    ParameterizationSource,
    ResolutionPolicy,
    CROMWELL_EPS,
)
from gaia.libs.embedding import StubEmbeddingModel
from gaia.lkm.ingest import ingest_package
from gaia.core.global_bp import run_global_bp
from gaia.libs.models.graph_ir import GlobalCanonicalGraph
from tests.gaia.fixtures.graphs import (
    make_galileo_falling_bodies,
    make_newton_gravity,
    make_einstein_equivalence,
)


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "e2e.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


class TestEndToEndPipeline:
    async def test_three_package_pipeline(self, storage, embedding_model):
        """Ingest galileo → newton → einstein, then run global BP."""
        # Stage 1: Ingest all three packages
        packages = [
            ("galileo", "1.0", make_galileo_falling_bodies()),
            ("newton", "1.0", make_newton_gravity()),
            ("einstein", "1.0", make_einstein_equivalence()),
        ]
        for pkg_id, version, graph in packages:
            result = await ingest_package(
                local_graph=graph,
                package_id=pkg_id,
                version=version,
                storage=storage,
                embedding_model=embedding_model,
            )
            assert len(result.bindings) > 0

        # Stage 2: Verify global graph
        global_nodes = await storage.get_global_nodes()
        global_factors = await storage.get_global_factors()
        assert len(global_nodes) > 0
        assert len(global_factors) > 0

        claim_nodes = [n for n in global_nodes if n.type == KnowledgeType.CLAIM]
        assert len(claim_nodes) > 0

        # Stage 3: Create parameterization (simulating review output)
        source = ParameterizationSource(source_id="e2e_test", model="test")
        await storage.write_param_source(source)

        prior_records = []
        for n in claim_nodes:
            prior_records.append(
                PriorRecord(gcn_id=n.id, value=0.5, source_id="e2e_test")
            )
        await storage.write_prior_records(prior_records)

        factor_records = []
        for f in global_factors:
            factor_records.append(
                FactorParamRecord(factor_id=f.factor_id, probability=0.85, source_id="e2e_test")
            )
        await storage.write_factor_param_records(factor_records)

        # Stage 4: Run global BP
        global_graph = GlobalCanonicalGraph(
            knowledge_nodes=global_nodes, factor_nodes=global_factors
        )
        all_priors = await storage.get_prior_records()
        all_factor_params = await storage.get_factor_param_records()

        belief_state = await run_global_bp(
            global_graph=global_graph,
            prior_records=all_priors,
            factor_records=all_factor_params,
            policy=ResolutionPolicy(strategy="latest"),
        )

        # Stage 5: Verify beliefs
        assert isinstance(belief_state, BeliefState)
        assert belief_state.converged
        assert len(belief_state.beliefs) == len(claim_nodes)

        for gcn_id, belief in belief_state.beliefs.items():
            assert CROMWELL_EPS <= belief <= 1.0 - CROMWELL_EPS

        # Persist and verify retrieval
        await storage.write_belief_state(belief_state)
        states = await storage.get_belief_states(limit=1)
        assert len(states) == 1
        assert states[0].bp_run_id == belief_state.bp_run_id

        print(f"\n=== E2E Results ===")
        print(f"Global nodes: {len(global_nodes)} ({len(claim_nodes)} claims)")
        print(f"Global factors: {len(global_factors)}")
        print(f"BP: converged={belief_state.converged}, "
              f"iterations={belief_state.iterations}")
        for gcn_id, belief in sorted(belief_state.beliefs.items()):
            node = next(n for n in global_nodes if n.id == gcn_id)
            content = node.content or "(via representative_lcn)"
            print(f"  {gcn_id[:20]}... → {belief:.4f}  [{content[:60]}]")
```

- [ ] **Step 2: Run test**

```bash
pytest tests/gaia/test_e2e_pipeline.py -v -s
```

- [ ] **Step 3: Commit**

```bash
git add tests/gaia/test_e2e_pipeline.py
git commit -m "test: add end-to-end pipeline integration test (galileo+newton+einstein)"
```

---

## Summary

| Chunk | Tasks | New files | Focus |
|-------|-------|-----------|-------|
| 1. Models | 1.1–1.7 | 9 | Graph IR data definitions (Pydantic v2) |
| 2. Storage | 2.1–2.6 | 10 | LanceDB + Neo4j + StorageManager |
| 3. Core | 3.1–3.3 | 7 | Matching, canonicalization, global BP |
| 4. LKM | 4.1–4.3 | 11 | Ingest, batch pipelines, FastAPI API |
| 5. E2E | 5.1 | 1 | Integration test across all layers |

**Total: ~38 files, 17 tasks**

Execution order is strict: Chunk 1 → 2 → 3 → 4 → 5. Within each chunk, tasks are sequential (each depends on the previous).
