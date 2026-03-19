# Simplified Global Canonicalization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automatic global canonicalization that maps LocalCanonicalNodes to GlobalCanonicalNodes at publish time, using embedding similarity with a conservative threshold.

**Architecture:** New `libs/global_graph/` module with Pydantic models for GlobalCanonicalNode, CanonicalBinding, GlobalInferenceState, and a GlobalGraph container. A `canonicalize()` function takes a LocalCanonicalGraph + LocalParameterization + existing GlobalGraph and produces bindings + updated global graph. V1 stores global graph as JSON files under `global_graph/`. A pipeline script `scripts/pipeline/canonicalize_global.py` exercises the full flow. Similarity is computed via cosine on content embeddings (using a lightweight sentence-transformer or simple TF-IDF for V1).

**Tech Stack:** Python 3.12, Pydantic v2, scikit-learn TfidfVectorizer (V1 similarity — no external embedding service dependency), JSON file storage

**Spec:** `docs/superpowers/specs/2026-03-17-simplified-global-canonicalization-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| Create: `libs/global_graph/__init__.py` | Package exports |
| Create: `libs/global_graph/models.py` | GlobalCanonicalNode, CanonicalBinding, GlobalInferenceState, GlobalGraph, CanonicalizationResult |
| Create: `libs/global_graph/similarity.py` | `find_best_match()` — TF-IDF cosine similarity between a node and candidates |
| Create: `libs/global_graph/canonicalize.py` | `canonicalize_package()` — main flow: embed → search → match/create → record |
| Create: `libs/global_graph/serialize.py` | Load/save GlobalGraph to/from JSON files in `global_graph/` directory |
| Create: `tests/libs/global_graph/test_models.py` | Model validation tests |
| Create: `tests/libs/global_graph/test_similarity.py` | Similarity function tests |
| Create: `tests/libs/global_graph/test_canonicalize.py` | End-to-end canonicalization tests |
| Create: `tests/libs/global_graph/__init__.py` | Test package init |
| Create: `scripts/pipeline/canonicalize_global.py` | CLI: canonicalize one or more packages into a shared global graph |

---

## Chunk 1: Global Graph Models

### Task 1: GlobalCanonicalNode, CanonicalBinding, GlobalInferenceState models

**Files:**
- Create: `libs/global_graph/__init__.py`
- Create: `libs/global_graph/models.py`
- Create: `tests/libs/global_graph/__init__.py`
- Create: `tests/libs/global_graph/test_models.py`

- [ ] **Step 1: Write tests for global graph models**

```python
# tests/libs/global_graph/test_models.py
"""Tests for global graph data models."""

from libs.global_graph.models import (
    CanonicalBinding,
    CanonicalizationResult,
    GlobalCanonicalNode,
    GlobalGraph,
    GlobalInferenceState,
    LocalCanonicalRef,
    PackageRef,
)
from libs.graph_ir.models import FactorNode, FactorParams, Parameter


class TestGlobalCanonicalNode:
    def test_create_minimal(self):
        node = GlobalCanonicalNode(
            global_canonical_id="gcn_001",
            knowledge_type="claim",
            representative_content="Test claim",
        )
        assert node.global_canonical_id == "gcn_001"
        assert node.kind is None
        assert node.parameters == []
        assert node.member_local_nodes == []
        assert node.provenance == []

    def test_create_with_members(self):
        node = GlobalCanonicalNode(
            global_canonical_id="gcn_002",
            knowledge_type="claim",
            representative_content="Shared claim",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg_a", version="1.0.0", local_canonical_id="lcn_aaa"),
                LocalCanonicalRef(package="pkg_b", version="1.0.0", local_canonical_id="lcn_bbb"),
            ],
            provenance=[
                PackageRef(package="pkg_a", version="1.0.0"),
                PackageRef(package="pkg_b", version="1.0.0"),
            ],
        )
        assert len(node.member_local_nodes) == 2
        assert len(node.provenance) == 2

    def test_with_parameters(self):
        node = GlobalCanonicalNode(
            global_canonical_id="gcn_003",
            knowledge_type="action",
            kind="infer_action",
            representative_content="Apply {method} to {input}",
            parameters=[
                Parameter(name="method", constraint="unknown"),
                Parameter(name="input", constraint="unknown"),
            ],
        )
        assert len(node.parameters) == 2
        assert node.kind == "infer_action"


class TestCanonicalBinding:
    def test_match_existing(self):
        binding = CanonicalBinding(
            package="pkg_a",
            version="1.0.0",
            local_graph_hash="sha256:abc123",
            local_canonical_id="lcn_aaa",
            decision="match_existing",
            global_canonical_id="gcn_001",
            decided_by="auto_canonicalize",
            reason="cosine similarity 0.95",
        )
        assert binding.decision == "match_existing"

    def test_create_new(self):
        binding = CanonicalBinding(
            package="pkg_a",
            version="1.0.0",
            local_graph_hash="sha256:abc123",
            local_canonical_id="lcn_bbb",
            decision="create_new",
            global_canonical_id="gcn_new",
            decided_by="auto_canonicalize",
        )
        assert binding.decision == "create_new"
        assert binding.reason is None


class TestGlobalGraph:
    def test_empty_graph(self):
        g = GlobalGraph()
        assert g.knowledge_nodes == []
        assert g.factor_nodes == []
        assert len(g.node_index) == 0

    def test_node_index(self):
        n = GlobalCanonicalNode(
            global_canonical_id="gcn_001",
            knowledge_type="claim",
            representative_content="X",
        )
        g = GlobalGraph(knowledge_nodes=[n])
        assert g.node_index["gcn_001"] is n

    def test_add_node(self):
        g = GlobalGraph()
        n = GlobalCanonicalNode(
            global_canonical_id="gcn_001",
            knowledge_type="claim",
            representative_content="X",
        )
        g.add_node(n)
        assert len(g.knowledge_nodes) == 1
        assert "gcn_001" in g.node_index


class TestGlobalInferenceState:
    def test_create(self):
        state = GlobalInferenceState(
            graph_hash="sha256:abc",
            node_priors={"gcn_001": 0.7},
            factor_parameters={"f_001": FactorParams(conditional_probability=0.9)},
            node_beliefs={"gcn_001": 0.65},
        )
        assert state.node_priors["gcn_001"] == 0.7


class TestCanonicalizationResult:
    def test_create(self):
        result = CanonicalizationResult(
            bindings=[],
            new_global_nodes=[],
            matched_global_nodes=[],
            unresolved_cross_refs=[],
        )
        assert result.bindings == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/global_graph/test_models.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement models**

```python
# libs/global_graph/models.py
"""Global graph models for cross-package canonicalization."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from libs.graph_ir.models import FactorNode, FactorParams, Parameter


class LocalCanonicalRef(BaseModel):
    package: str
    version: str
    local_canonical_id: str


class PackageRef(BaseModel):
    package: str
    version: str


class GlobalCanonicalNode(BaseModel):
    global_canonical_id: str
    knowledge_type: str
    kind: str | None = None
    representative_content: str
    parameters: list[Parameter] = Field(default_factory=list)
    member_local_nodes: list[LocalCanonicalRef] = Field(default_factory=list)
    provenance: list[PackageRef] = Field(default_factory=list)
    metadata: dict | None = None


class CanonicalBinding(BaseModel):
    package: str
    version: str
    local_graph_hash: str
    local_canonical_id: str
    decision: str  # match_existing | create_new
    global_canonical_id: str
    decided_by: str = "auto_canonicalize"
    reason: str | None = None


class GlobalInferenceState(BaseModel):
    graph_hash: str = ""
    node_priors: dict[str, float] = Field(default_factory=dict)
    factor_parameters: dict[str, FactorParams] = Field(default_factory=dict)
    node_beliefs: dict[str, float] = Field(default_factory=dict)
    updated_at: str = ""


class GlobalGraph(BaseModel):
    schema_version: str = "1.0"
    knowledge_nodes: list[GlobalCanonicalNode] = Field(default_factory=list)
    factor_nodes: list[FactorNode] = Field(default_factory=list)
    bindings: list[CanonicalBinding] = Field(default_factory=list)
    inference_state: GlobalInferenceState = Field(default_factory=GlobalInferenceState)

    @property
    def node_index(self) -> dict[str, GlobalCanonicalNode]:
        return {n.global_canonical_id: n for n in self.knowledge_nodes}

    def add_node(self, node: GlobalCanonicalNode) -> None:
        self.knowledge_nodes.append(node)


@dataclass
class CanonicalizationResult:
    bindings: list[CanonicalBinding] = field(default_factory=list)
    new_global_nodes: list[GlobalCanonicalNode] = field(default_factory=list)
    matched_global_nodes: list[str] = field(default_factory=list)
    unresolved_cross_refs: list[str] = field(default_factory=list)
```

```python
# libs/global_graph/__init__.py
"""Global graph: cross-package canonicalization and global inference."""

from .models import (
    CanonicalBinding,
    CanonicalizationResult,
    GlobalCanonicalNode,
    GlobalGraph,
    GlobalInferenceState,
    LocalCanonicalRef,
    PackageRef,
)

__all__ = [
    "CanonicalBinding",
    "CanonicalizationResult",
    "GlobalCanonicalNode",
    "GlobalGraph",
    "GlobalInferenceState",
    "LocalCanonicalRef",
    "PackageRef",
]
```

```python
# tests/libs/global_graph/__init__.py
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/libs/global_graph/test_models.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add libs/global_graph/ tests/libs/global_graph/
git commit -m "feat: add global graph models (GlobalCanonicalNode, CanonicalBinding, GlobalGraph)"
```

---

## Chunk 2: Similarity + Canonicalization Logic

### Task 2: Similarity function

**Files:**
- Create: `libs/global_graph/similarity.py`
- Create: `tests/libs/global_graph/test_similarity.py`

- [ ] **Step 1: Write tests for similarity**

```python
# tests/libs/global_graph/test_similarity.py
"""Tests for content similarity matching."""

from libs.global_graph.models import GlobalCanonicalNode
from libs.global_graph.similarity import find_best_match, compute_similarity

MATCH_THRESHOLD = 0.90


def _node(gcn_id: str, content: str, ktype: str = "claim", kind: str | None = None):
    return GlobalCanonicalNode(
        global_canonical_id=gcn_id,
        knowledge_type=ktype,
        kind=kind,
        representative_content=content,
    )


class TestComputeSimilarity:
    def test_identical_content(self):
        score = compute_similarity("The sky is blue", "The sky is blue")
        assert score > 0.99

    def test_similar_content(self):
        score = compute_similarity(
            "Free fall acceleration is independent of mass",
            "All objects fall at the same rate regardless of weight",
        )
        assert 0.3 < score < 1.0  # similar but not identical

    def test_unrelated_content(self):
        score = compute_similarity(
            "Superconductivity occurs below critical temperature",
            "Photosynthesis converts CO2 to glucose",
        )
        assert score < 0.3


class TestFindBestMatch:
    def test_exact_match_found(self):
        candidates = [
            _node("gcn_1", "The sky is blue"),
            _node("gcn_2", "Water boils at 100 degrees"),
        ]
        match = find_best_match("The sky is blue", "claim", None, candidates, threshold=0.90)
        assert match is not None
        assert match[0] == "gcn_1"
        assert match[1] > 0.90

    def test_no_match_below_threshold(self):
        candidates = [
            _node("gcn_1", "Unrelated topic about chemistry"),
        ]
        match = find_best_match("Free fall acceleration", "claim", None, candidates, threshold=0.90)
        assert match is None

    def test_type_mismatch_rejected(self):
        candidates = [
            _node("gcn_1", "The sky is blue", ktype="setting"),
        ]
        match = find_best_match("The sky is blue", "claim", None, candidates, threshold=0.90)
        assert match is None

    def test_kind_mismatch_rejected_for_action(self):
        candidates = [
            _node("gcn_1", "Apply method X", ktype="action", kind="infer_action"),
        ]
        match = find_best_match(
            "Apply method X", "action", "toolcall_action", candidates, threshold=0.90
        )
        assert match is None

    def test_kind_match_required_for_question(self):
        candidates = [
            _node("gcn_1", "Is X true?", ktype="question", kind="research"),
        ]
        match = find_best_match("Is X true?", "question", "research", candidates, threshold=0.90)
        assert match is not None

    def test_contradiction_never_matched(self):
        candidates = [
            _node("gcn_1", "A contradicts B", ktype="contradiction"),
        ]
        match = find_best_match(
            "A contradicts B", "contradiction", None, candidates, threshold=0.50
        )
        assert match is None

    def test_empty_candidates(self):
        match = find_best_match("anything", "claim", None, [], threshold=0.90)
        assert match is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/global_graph/test_similarity.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement similarity**

```python
# libs/global_graph/similarity.py
"""Content similarity for global canonicalization."""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import GlobalCanonicalNode

# Types that are package-local relations — never match across packages
_RELATION_TYPES = {"contradiction", "equivalence"}
# Types that require kind match
_KIND_REQUIRED_TYPES = {"question", "action"}


def compute_similarity(text_a: str, text_b: str) -> float:
    """Compute TF-IDF cosine similarity between two texts."""
    if not text_a.strip() or not text_b.strip():
        return 0.0
    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform([text_a, text_b])
    sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    return float(sim)


def find_best_match(
    content: str,
    knowledge_type: str,
    kind: str | None,
    candidates: list[GlobalCanonicalNode],
    threshold: float = 0.90,
) -> tuple[str, float] | None:
    """Find the best matching GlobalCanonicalNode for a local node.

    Returns (global_canonical_id, similarity_score) or None if no match.
    """
    if knowledge_type in _RELATION_TYPES:
        return None

    if not candidates or not content.strip():
        return None

    best_id: str | None = None
    best_score: float = 0.0

    for candidate in candidates:
        # Type must match exactly
        if candidate.knowledge_type != knowledge_type:
            continue
        # Kind must match for question and action
        if knowledge_type in _KIND_REQUIRED_TYPES and candidate.kind != kind:
            continue

        score = compute_similarity(content, candidate.representative_content)
        if score > best_score:
            best_score = score
            best_id = candidate.global_canonical_id

    if best_id is not None and best_score >= threshold:
        return (best_id, best_score)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/libs/global_graph/test_similarity.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add libs/global_graph/similarity.py tests/libs/global_graph/test_similarity.py
git commit -m "feat: add TF-IDF cosine similarity for global canonicalization"
```

### Task 3: Canonicalize function

**Files:**
- Create: `libs/global_graph/canonicalize.py`
- Create: `tests/libs/global_graph/test_canonicalize.py`

- [ ] **Step 1: Write tests for canonicalization**

```python
# tests/libs/global_graph/test_canonicalize.py
"""Tests for global canonicalization logic."""

from libs.global_graph.canonicalize import canonicalize_package
from libs.global_graph.models import (
    GlobalCanonicalNode,
    GlobalGraph,
    GlobalInferenceState,
    LocalCanonicalRef,
)
from libs.graph_ir.models import (
    FactorNode,
    FactorParams,
    LocalCanonicalGraph,
    LocalCanonicalNode,
    LocalParameterization,
    SourceRef,
)


def _lcn(lcn_id: str, content: str, ktype: str = "claim", pkg: str = "test_pkg"):
    return LocalCanonicalNode(
        local_canonical_id=lcn_id,
        package=pkg,
        knowledge_type=ktype,
        representative_content=content,
        member_raw_node_ids=[f"raw_{lcn_id[4:]}"],
        source_refs=[SourceRef(package=pkg, version="1.0.0", module="core", knowledge_name=lcn_id)],
    )


def _local_graph(nodes, factors=None, pkg="test_pkg"):
    return LocalCanonicalGraph(
        package=pkg, version="1.0.0",
        knowledge_nodes=nodes,
        factor_nodes=factors or [],
    )


def _local_params(nodes, factors=None):
    priors = {n.local_canonical_id: 0.5 for n in nodes}
    fparams = {}
    for f in (factors or []):
        if f.type == "reasoning":
            fparams[f.factor_id] = FactorParams(conditional_probability=0.9)
    return LocalParameterization(graph_hash="sha256:test", node_priors=priors, factor_parameters=fparams)


class TestCanonicalizeFirstPackage:
    def test_all_create_new_on_empty_global(self):
        nodes = [_lcn("lcn_a", "Claim A"), _lcn("lcn_b", "Claim B")]
        local = _local_graph(nodes)
        params = _local_params(nodes)

        result = canonicalize_package(local, params, GlobalGraph())

        assert len(result.bindings) == 2
        assert all(b.decision == "create_new" for b in result.bindings)
        assert len(result.new_global_nodes) == 2
        assert len(result.matched_global_nodes) == 0

    def test_global_ids_are_assigned(self):
        nodes = [_lcn("lcn_a", "Claim A")]
        local = _local_graph(nodes)
        params = _local_params(nodes)

        result = canonicalize_package(local, params, GlobalGraph())

        gcn = result.new_global_nodes[0]
        assert gcn.global_canonical_id.startswith("gcn_")
        assert gcn.knowledge_type == "claim"
        assert gcn.representative_content == "Claim A"
        assert len(gcn.member_local_nodes) == 1
        assert gcn.member_local_nodes[0].local_canonical_id == "lcn_a"


class TestCanonicalizeWithExistingGlobal:
    def test_match_existing_high_similarity(self):
        existing = GlobalCanonicalNode(
            global_canonical_id="gcn_existing",
            knowledge_type="claim",
            representative_content="Free fall acceleration is independent of mass",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg_old", version="1.0.0", local_canonical_id="lcn_old"),
            ],
        )
        global_graph = GlobalGraph(knowledge_nodes=[existing])

        nodes = [_lcn("lcn_new", "Free fall acceleration is independent of mass")]
        local = _local_graph(nodes)
        params = _local_params(nodes)

        result = canonicalize_package(local, params, global_graph)

        matched = [b for b in result.bindings if b.decision == "match_existing"]
        assert len(matched) == 1
        assert matched[0].global_canonical_id == "gcn_existing"

    def test_create_new_low_similarity(self):
        existing = GlobalCanonicalNode(
            global_canonical_id="gcn_existing",
            knowledge_type="claim",
            representative_content="Superconductivity requires low temperature",
        )
        global_graph = GlobalGraph(knowledge_nodes=[existing])

        nodes = [_lcn("lcn_new", "Photosynthesis produces oxygen")]
        local = _local_graph(nodes)
        params = _local_params(nodes)

        result = canonicalize_package(local, params, global_graph)

        assert all(b.decision == "create_new" for b in result.bindings)


class TestFactorIntegration:
    def test_factors_get_global_ids(self):
        nodes = [
            _lcn("lcn_p", "Premise P"),
            _lcn("lcn_c", "Conclusion C"),
        ]
        factor = FactorNode(
            factor_id="f_test",
            type="reasoning",
            premises=["lcn_p"],
            conclusion="lcn_c",
            metadata={"edge_type": "deduction"},
        )
        local = _local_graph(nodes, [factor])
        params = _local_params(nodes, [factor])

        result = canonicalize_package(local, params, GlobalGraph())

        # Build mapping from bindings
        lcn_to_gcn = {b.local_canonical_id: b.global_canonical_id for b in result.bindings}
        assert "lcn_p" in lcn_to_gcn
        assert "lcn_c" in lcn_to_gcn


class TestInferenceStateInit:
    def test_priors_from_author(self):
        nodes = [_lcn("lcn_a", "Claim A")]
        local = _local_graph(nodes)
        params = LocalParameterization(
            graph_hash="sha256:test",
            node_priors={"lcn_a": 0.75},
            factor_parameters={},
        )

        result = canonicalize_package(local, params, GlobalGraph())

        gcn_id = result.bindings[0].global_canonical_id
        assert result.new_global_nodes[0].global_canonical_id == gcn_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/global_graph/test_canonicalize.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement canonicalize_package**

```python
# libs/global_graph/canonicalize.py
"""Simplified global canonicalization: local node → global node mapping."""

from __future__ import annotations

from hashlib import sha256

from libs.graph_ir.models import LocalCanonicalGraph, LocalParameterization

from .models import (
    CanonicalBinding,
    CanonicalizationResult,
    GlobalCanonicalNode,
    GlobalGraph,
    LocalCanonicalRef,
    PackageRef,
)
from .similarity import find_best_match

MATCH_THRESHOLD = 0.90


def _generate_gcn_id(content: str, knowledge_type: str, counter: int) -> str:
    """Generate a deterministic global canonical ID."""
    payload = f"{knowledge_type}:{content}:{counter}"
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"gcn_{digest[:16]}"


def canonicalize_package(
    local_graph: LocalCanonicalGraph,
    local_params: LocalParameterization,
    global_graph: GlobalGraph,
    threshold: float = MATCH_THRESHOLD,
) -> CanonicalizationResult:
    """Map local canonical nodes to global graph.

    For each LocalCanonicalNode:
    - Search global graph for best match above threshold
    - match_existing: bind to existing GlobalCanonicalNode
    - create_new: create new GlobalCanonicalNode

    Returns CanonicalizationResult with bindings and new/matched nodes.
    """
    bindings: list[CanonicalBinding] = []
    new_global_nodes: list[GlobalCanonicalNode] = []
    matched_global_nodes: list[str] = []

    graph_hash = local_graph.graph_hash()
    existing_nodes = list(global_graph.knowledge_nodes)

    for node in local_graph.knowledge_nodes:
        content = node.representative_content
        match = find_best_match(
            content, node.knowledge_type, node.kind, existing_nodes, threshold
        )

        if match is not None:
            gcn_id, score = match
            bindings.append(
                CanonicalBinding(
                    package=local_graph.package,
                    version=local_graph.version,
                    local_graph_hash=graph_hash,
                    local_canonical_id=node.local_canonical_id,
                    decision="match_existing",
                    global_canonical_id=gcn_id,
                    reason=f"cosine similarity {score:.3f}",
                )
            )
            matched_global_nodes.append(gcn_id)

            # Update existing node's membership
            existing_node = global_graph.node_index.get(gcn_id)
            if existing_node is not None:
                existing_node.member_local_nodes.append(
                    LocalCanonicalRef(
                        package=local_graph.package,
                        version=local_graph.version,
                        local_canonical_id=node.local_canonical_id,
                    )
                )
                pkg_ref = PackageRef(package=local_graph.package, version=local_graph.version)
                if pkg_ref not in existing_node.provenance:
                    existing_node.provenance.append(pkg_ref)
        else:
            gcn_id = _generate_gcn_id(
                content, node.knowledge_type, len(existing_nodes) + len(new_global_nodes)
            )
            gcn = GlobalCanonicalNode(
                global_canonical_id=gcn_id,
                knowledge_type=node.knowledge_type,
                kind=node.kind,
                representative_content=content,
                parameters=node.parameters,
                member_local_nodes=[
                    LocalCanonicalRef(
                        package=local_graph.package,
                        version=local_graph.version,
                        local_canonical_id=node.local_canonical_id,
                    )
                ],
                provenance=[
                    PackageRef(package=local_graph.package, version=local_graph.version)
                ],
                metadata=node.metadata,
            )
            new_global_nodes.append(gcn)
            # Add to existing_nodes so subsequent local nodes can match against it
            existing_nodes.append(gcn)

            bindings.append(
                CanonicalBinding(
                    package=local_graph.package,
                    version=local_graph.version,
                    local_graph_hash=graph_hash,
                    local_canonical_id=node.local_canonical_id,
                    decision="create_new",
                    global_canonical_id=gcn_id,
                )
            )

    return CanonicalizationResult(
        bindings=bindings,
        new_global_nodes=new_global_nodes,
        matched_global_nodes=matched_global_nodes,
        unresolved_cross_refs=[],
    )
```

Update `libs/global_graph/__init__.py` to export the new function:

```python
# libs/global_graph/__init__.py
"""Global graph: cross-package canonicalization and global inference."""

from .canonicalize import canonicalize_package
from .models import (
    CanonicalBinding,
    CanonicalizationResult,
    GlobalCanonicalNode,
    GlobalGraph,
    GlobalInferenceState,
    LocalCanonicalRef,
    PackageRef,
)
from .similarity import compute_similarity, find_best_match

__all__ = [
    "CanonicalBinding",
    "CanonicalizationResult",
    "GlobalCanonicalNode",
    "GlobalGraph",
    "GlobalInferenceState",
    "LocalCanonicalRef",
    "PackageRef",
    "canonicalize_package",
    "compute_similarity",
    "find_best_match",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/libs/global_graph/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add libs/global_graph/ tests/libs/global_graph/
git commit -m "feat: add canonicalize_package with TF-IDF similarity matching"
```

---

## Chunk 3: Serialization + Pipeline Script

### Task 4: Global graph serialization

**Files:**
- Create: `libs/global_graph/serialize.py`
- Modify: `libs/global_graph/__init__.py` (add serialize exports)

- [ ] **Step 1: Implement serialization**

```python
# libs/global_graph/serialize.py
"""JSON serialization for global graph artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from .models import GlobalGraph


def save_global_graph(global_graph: GlobalGraph, output_dir: Path) -> Path:
    """Save global graph to a directory as JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "global_graph.json"
    out_path.write_text(
        json.dumps(
            global_graph.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return out_path


def load_global_graph(path: Path) -> GlobalGraph:
    """Load global graph from a JSON file."""
    if not path.exists():
        return GlobalGraph()
    return GlobalGraph.model_validate_json(path.read_text())
```

- [ ] **Step 2: Commit**

```bash
git add libs/global_graph/serialize.py libs/global_graph/__init__.py
git commit -m "feat: add global graph JSON serialization"
```

### Task 5: Pipeline script

**Files:**
- Create: `scripts/pipeline/canonicalize_global.py`

- [ ] **Step 1: Implement pipeline script**

```python
#!/usr/bin/env python3
"""Canonicalize packages into a shared global graph.

Reads each package's graph_ir/local_canonical_graph.json +
local_parameterization.json, maps local nodes to global nodes,
saves global_graph/global_graph.json.

Usage:
    python scripts/pipeline/canonicalize_global.py \
        tests/fixtures/gaia_language_packages/galileo_falling_bodies \
        tests/fixtures/gaia_language_packages/newton_principia \
        -o tests/fixtures/global_graph
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.global_graph.canonicalize import canonicalize_package
from libs.global_graph.models import GlobalGraph
from libs.global_graph.serialize import load_global_graph, save_global_graph
from libs.graph_ir.models import LocalCanonicalGraph, LocalParameterization


def main():
    parser = argparse.ArgumentParser(description="Canonicalize packages into global graph")
    parser.add_argument("pkg_dirs", type=Path, nargs="+", help="Package directories")
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("global_graph"),
        help="Output directory for global graph (default: global_graph/)",
    )
    args = parser.parse_args()

    # Load existing global graph if present
    global_graph_path = args.output_dir / "global_graph.json"
    global_graph = load_global_graph(global_graph_path)
    print(f"Loaded global graph: {len(global_graph.knowledge_nodes)} existing nodes")

    for pkg_dir in args.pkg_dirs:
        graph_ir_dir = pkg_dir / "graph_ir"
        lcg_path = graph_ir_dir / "local_canonical_graph.json"
        params_path = graph_ir_dir / "local_parameterization.json"

        if not lcg_path.exists():
            print(f"  SKIP {pkg_dir.name}: no local_canonical_graph.json")
            continue
        if not params_path.exists():
            print(f"  SKIP {pkg_dir.name}: no local_parameterization.json")
            continue

        local_graph = LocalCanonicalGraph.model_validate_json(lcg_path.read_text())
        local_params = LocalParameterization.model_validate_json(params_path.read_text())

        print(f"Processing: {pkg_dir.name} ({len(local_graph.knowledge_nodes)} local nodes)")
        result = canonicalize_package(local_graph, local_params, global_graph)

        # Integrate results into global graph
        for gcn in result.new_global_nodes:
            global_graph.add_node(gcn)
        global_graph.bindings.extend(result.bindings)

        created = sum(1 for b in result.bindings if b.decision == "create_new")
        matched = sum(1 for b in result.bindings if b.decision == "match_existing")
        print(f"  → {created} new, {matched} matched")

    save_global_graph(global_graph, args.output_dir)
    print(f"\nGlobal graph: {len(global_graph.knowledge_nodes)} nodes, "
          f"{len(global_graph.bindings)} bindings")
    print(f"Saved to: {args.output_dir / 'global_graph.json'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test the pipeline**

Run:
```bash
python scripts/pipeline/canonicalize_global.py \
    tests/fixtures/gaia_language_packages/galileo_falling_bodies \
    tests/fixtures/gaia_language_packages/newton_principia \
    -o tests/fixtures/global_graph
```

Expected: Creates `tests/fixtures/global_graph/global_graph.json` with ~35 global nodes (19 galileo + some matched from newton's 20).

- [ ] **Step 3: Lint and format**

```bash
ruff check libs/global_graph/ scripts/pipeline/canonicalize_global.py
ruff format libs/global_graph/ scripts/pipeline/canonicalize_global.py
```

- [ ] **Step 4: Commit**

```bash
git add scripts/pipeline/canonicalize_global.py libs/global_graph/
git commit -m "feat: add canonicalize_global.py pipeline script"
```

### Task 6: End-to-end validation with fixtures

- [ ] **Step 1: Run full pipeline on galileo + newton**

```bash
python scripts/pipeline/build_graph_ir.py \
    tests/fixtures/gaia_language_packages/galileo_falling_bodies \
    tests/fixtures/gaia_language_packages/newton_principia

python scripts/pipeline/canonicalize_global.py \
    tests/fixtures/gaia_language_packages/galileo_falling_bodies \
    tests/fixtures/gaia_language_packages/newton_principia \
    -o tests/fixtures/global_graph
```

- [ ] **Step 2: Verify output**

```bash
python -c "
import json
g = json.load(open('tests/fixtures/global_graph/global_graph.json'))
print(f'Nodes: {len(g[\"knowledge_nodes\"])}')
print(f'Bindings: {len(g[\"bindings\"])}')
created = sum(1 for b in g['bindings'] if b['decision'] == 'create_new')
matched = sum(1 for b in g['bindings'] if b['decision'] == 'match_existing')
print(f'Created: {created}, Matched: {matched}')
"
```

- [ ] **Step 3: Run all tests**

```bash
pytest tests/libs/global_graph/ tests/libs/graph_ir/ tests/scripts/ -v
ruff check .
ruff format --check .
```

- [ ] **Step 4: Commit fixture**

```bash
git add tests/fixtures/global_graph/
git commit -m "feat: add global graph fixture from galileo + newton canonicalization"
```
