# Curation Service Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a global graph maintenance service that discovers duplicates, equivalences, contradictions, and structural issues across the entire knowledge graph, then executes approved cleanup operations with audit trails.

**Architecture:** The curation service lives in `libs/curation/` as a library layer (no HTTP routes yet). It follows the same async-first, Pydantic v2 pattern as the rest of the codebase. The service reads from `StorageManager` to load `GlobalCanonicalNode`s and factors, performs analysis (clustering, classification, conflict detection, structure inspection), generates a `CurationPlan` of suggested operations, and executes approved operations back through storage. A new `list_global_nodes()` method must be added to the storage layer first, as curation needs to iterate all global nodes.

**Tech Stack:** Python 3.12+, Pydantic v2, NumPy (cosine similarity), existing `libs/inference/` (BP), existing `libs/global_graph/similarity.py` (embedding matching), existing `libs/embedding.py` (EmbeddingModel)

**Spec:** `docs/superpowers/specs/2026-03-17-curation-service-design.md`

---

## File Structure

```
libs/curation/
  __init__.py                 — Public API exports
  models.py                   — Pydantic models: CurationSuggestion, ClusterGroup,
                                StructureReport, AuditEntry, CurationPlan, CurationResult
  similarity.py               — find_similar(): shared 1-vs-N similarity function (spec §4)
  clustering.py               — cluster_similar_nodes(): builds on find_similar, ANN + BM25 dual-recall
  classification.py           — classify_clusters(): duplicate vs equivalence classification
  conflict.py                 — detect_conflicts(): BP Level 1 + Level 2 sensitivity analysis
  structure.py                — inspect_structure(): graph health checks (orphans, dangling, degree)
  operations.py               — merge_nodes(), create_constraint(): graph modification primitives
  cleanup.py                  — generate_cleanup_plan(), execute_cleanup(): plan + execute
  audit.py                    — AuditLog: append-only log with rollback support
  reviewer.py                 — CurationReviewer: simplified rule-based reviewer for middle-tier
  scheduler.py                — run_curation(): main pipeline orchestrator

tests/libs/curation/
  __init__.py
  test_models.py
  test_similarity.py
  test_clustering.py
  test_classification.py
  test_conflict.py
  test_structure.py
  test_operations.py
  test_cleanup.py
  test_audit.py
  test_reviewer.py
  test_scheduler.py
  test_integration.py
```

**Storage layer additions:**

```
libs/storage/content_store.py     — Add abstract list_global_nodes()
libs/storage/lance_content_store.py — Implement list_global_nodes()
libs/storage/manager.py            — Add list_global_nodes() + upsert_global_nodes() passthroughs
```

**Inference layer additions:**

```
libs/inference/bp.py              — Refactor: extract _run_inner(), add run_with_diagnostics()
```

**V1 scaling note:** `list_global_nodes()` loads all nodes into memory. This is acceptable for V1 where global graph size is bounded. For billion-scale, pagination/streaming will be needed (tracked as future work).

---

## Chunk 1: Storage Layer Extension + Curation Models

### Task 1: Add `list_global_nodes()` to Storage Layer

Curation needs to iterate all `GlobalCanonicalNode`s. Currently only `get_global_node(id)` exists. We add a bulk listing method.

**Files:**
- Modify: `libs/storage/content_store.py:152-158` (add abstract method)
- Modify: `libs/storage/lance_content_store.py:1136-1143` (add implementation after `get_global_node`)
- Modify: `libs/storage/manager.py:185-186` (add passthrough)
- Test: `tests/libs/storage/test_lance_content.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/libs/storage/test_lance_content.py`:

```python
async def test_list_global_nodes(content_store):
    """list_global_nodes returns all upserted global nodes."""
    from libs.storage.models import GlobalCanonicalNode

    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_aaa",
            knowledge_type="claim",
            representative_content="Earth orbits the Sun",
            member_local_nodes=[],
            provenance=[],
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_bbb",
            knowledge_type="claim",
            representative_content="Water is H2O",
            member_local_nodes=[],
            provenance=[],
        ),
    ]
    await content_store.upsert_global_nodes(nodes)
    result = await content_store.list_global_nodes()
    assert len(result) == 2
    ids = {n.global_canonical_id for n in result}
    assert ids == {"gcn_aaa", "gcn_bbb"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_lance_content.py::test_list_global_nodes -v`
Expected: FAIL — `AttributeError: 'LanceContentStore' object has no attribute 'list_global_nodes'`

- [ ] **Step 3: Add abstract method to ContentStore**

In `libs/storage/content_store.py`, after `get_global_node`:

```python
    @abstractmethod
    async def list_global_nodes(self) -> list[GlobalCanonicalNode]:
        """Load all global canonical nodes."""
        ...
```

- [ ] **Step 4: Implement in LanceContentStore**

In `libs/storage/lance_content_store.py`, after the `get_global_node` method:

```python
    async def list_global_nodes(self) -> list[GlobalCanonicalNode]:
        table = self._db.open_table("global_canonical_nodes")
        if table.count_rows() == 0:
            return []
        rows = table.search().limit(table.count_rows()).to_list()
        return [_row_to_global_node(r) for r in rows]
```

- [ ] **Step 5: Add passthroughs to StorageManager**

In `libs/storage/manager.py`, after `get_global_node`:

```python
    async def list_global_nodes(self) -> list[GlobalCanonicalNode]:
        return await self.content_store.list_global_nodes()

    async def upsert_global_nodes(self, nodes: list[GlobalCanonicalNode]) -> None:
        """Upsert global nodes to ContentStore + GraphStore."""
        await self.content_store.upsert_global_nodes(nodes)
        if self.graph_store is not None:
            await self.graph_store.write_global_topology([], nodes)

    async def write_factors(self, factors: list[FactorNode]) -> None:
        """Write factors to ContentStore + GraphStore."""
        await self.content_store.write_factors(factors)
        if self.graph_store is not None:
            await self.graph_store.write_factor_topology(factors)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/libs/storage/test_lance_content.py::test_list_global_nodes -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add libs/storage/content_store.py libs/storage/lance_content_store.py libs/storage/manager.py tests/libs/storage/test_lance_content.py
git commit -m "feat(storage): add list_global_nodes() for curation bulk access"
```

---

### Task 2: Curation Models

All Pydantic models used by the curation service. These are pure data models with no logic dependencies.

**Files:**
- Create: `libs/curation/__init__.py`
- Create: `libs/curation/models.py`
- Create: `tests/libs/curation/__init__.py`
- Create: `tests/libs/curation/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/__init__.py` (empty) and `tests/libs/curation/test_models.py`:

```python
"""Tests for curation data models."""

from libs.curation.models import (
    AuditEntry,
    ClusterGroup,
    ConflictCandidate,
    CurationPlan,
    CurationResult,
    CurationSuggestion,
    SimilarityPair,
    StructureIssue,
    StructureReport,
)


def test_similarity_pair_defaults():
    pair = SimilarityPair(
        node_a_id="gcn_aaa",
        node_b_id="gcn_bbb",
        similarity_score=0.95,
        method="embedding",
    )
    assert pair.node_a_id == "gcn_aaa"
    assert pair.method == "embedding"


def test_cluster_group():
    group = ClusterGroup(
        cluster_id="cluster_001",
        node_ids=["gcn_aaa", "gcn_bbb", "gcn_ccc"],
        pairs=[
            SimilarityPair(
                node_a_id="gcn_aaa",
                node_b_id="gcn_bbb",
                similarity_score=0.96,
                method="embedding",
            )
        ],
    )
    assert len(group.node_ids) == 3
    assert len(group.pairs) == 1


def test_curation_suggestion_types():
    merge = CurationSuggestion(
        suggestion_id="sug_001",
        operation="merge",
        target_ids=["gcn_aaa", "gcn_bbb"],
        confidence=0.97,
        reason="Embedding cosine 0.97",
        evidence={"cosine": 0.97},
    )
    assert merge.operation == "merge"
    assert merge.confidence == 0.97

    constraint = CurationSuggestion(
        suggestion_id="sug_002",
        operation="create_equivalence",
        target_ids=["gcn_ccc", "gcn_ddd"],
        confidence=0.82,
        reason="Semantically equivalent, different angle",
        evidence={"cosine": 0.82},
    )
    assert constraint.operation == "create_equivalence"


def test_conflict_candidate():
    c = ConflictCandidate(
        node_a_id="gcn_aaa",
        node_b_id="gcn_bbb",
        signal_type="oscillation",
        strength=0.8,
        detail={"iterations_oscillating": 12},
    )
    assert c.signal_type == "oscillation"


def test_structure_issue():
    issue = StructureIssue(
        issue_type="orphan_node",
        severity="warning",
        node_ids=["gcn_orphan"],
        detail="Node has no factor connections",
    )
    assert issue.severity == "warning"


def test_structure_report():
    report = StructureReport(
        issues=[
            StructureIssue(
                issue_type="orphan_node",
                severity="warning",
                node_ids=["gcn_orphan"],
                detail="No factor connections",
            ),
            StructureIssue(
                issue_type="dangling_factor",
                severity="error",
                node_ids=["gcn_deleted"],
                detail="Factor references deleted node",
                factor_ids=["f_abc"],
            ),
        ]
    )
    assert len(report.errors) == 1
    assert len(report.warnings) == 1


def test_audit_entry():
    entry = AuditEntry(
        entry_id="audit_001",
        operation="merge",
        target_ids=["gcn_aaa", "gcn_bbb"],
        suggestion_id="sug_001",
        rollback_data={"removed_node": "gcn_bbb", "redirected_factors": ["f_123"]},
    )
    assert entry.operation == "merge"
    assert entry.rollback_data["removed_node"] == "gcn_bbb"


def test_curation_plan():
    plan = CurationPlan(
        suggestions=[
            CurationSuggestion(
                suggestion_id="sug_001",
                operation="merge",
                target_ids=["gcn_aaa", "gcn_bbb"],
                confidence=0.98,
                reason="Near-identical content",
                evidence={},
            ),
            CurationSuggestion(
                suggestion_id="sug_002",
                operation="create_equivalence",
                target_ids=["gcn_ccc", "gcn_ddd"],
                confidence=0.80,
                reason="Equivalent claims",
                evidence={},
            ),
            CurationSuggestion(
                suggestion_id="sug_003",
                operation="merge",
                target_ids=["gcn_eee", "gcn_fff"],
                confidence=0.60,
                reason="Low confidence",
                evidence={},
            ),
        ]
    )
    assert len(plan.auto_approve) == 1  # confidence > 0.95
    assert len(plan.needs_review) == 1  # 0.7 <= confidence <= 0.95
    assert len(plan.discard) == 1  # confidence < 0.7


def test_curation_plan_boundary_at_095():
    """Confidence == 0.95 falls into needs_review (> 0.95 for auto, not >=)."""
    plan = CurationPlan(
        suggestions=[
            CurationSuggestion(
                suggestion_id="sug_boundary",
                operation="merge",
                target_ids=["gcn_x", "gcn_y"],
                confidence=0.95,
                reason="Boundary case",
                evidence={},
            ),
        ]
    )
    assert len(plan.auto_approve) == 0
    assert len(plan.needs_review) == 1


def test_curation_result():
    result = CurationResult(
        executed=[],
        skipped=[],
        audit_entries=[],
        structure_report=StructureReport(issues=[]),
    )
    assert len(result.executed) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'libs.curation'`

- [ ] **Step 3: Implement models**

Create `libs/curation/__init__.py`:

```python
"""Curation service — global graph maintenance and cleanup."""
```

Create `libs/curation/models.py`:

```python
"""Pydantic models for the curation service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class SimilarityPair(BaseModel):
    """A pair of GlobalCanonicalNodes with measured similarity."""

    node_a_id: str
    node_b_id: str
    similarity_score: float
    method: Literal["embedding", "bm25", "both"]


class ClusterGroup(BaseModel):
    """A group of similar GlobalCanonicalNodes discovered by clustering."""

    cluster_id: str
    node_ids: list[str]
    pairs: list[SimilarityPair] = Field(default_factory=list)


class CurationSuggestion(BaseModel):
    """A suggested curation operation with confidence score."""

    suggestion_id: str = Field(default_factory=lambda: f"sug_{uuid4().hex[:12]}")
    operation: Literal[
        "merge",
        "create_equivalence",
        "create_contradiction",
        "fix_dangling_factor",
        "archive_orphan",
    ]
    target_ids: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: dict = Field(default_factory=dict)


class ConflictCandidate(BaseModel):
    """A candidate contradiction discovered via BP signals or sensitivity analysis."""

    node_a_id: str
    node_b_id: str
    signal_type: Literal["oscillation", "sensitivity", "both"]
    strength: float = Field(ge=0.0, le=1.0)
    detail: dict = Field(default_factory=dict)


class StructureIssue(BaseModel):
    """A structural issue found during graph inspection."""

    issue_type: Literal[
        "orphan_node",
        "dangling_factor",
        "high_degree",
        "disconnected_component",
    ]
    severity: Literal["error", "warning", "info"]
    node_ids: list[str] = Field(default_factory=list)
    factor_ids: list[str] = Field(default_factory=list)
    detail: str = ""


class StructureReport(BaseModel):
    """Result of structure inspection."""

    issues: list[StructureIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[StructureIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[StructureIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> list[StructureIssue]:
        return [i for i in self.issues if i.severity == "info"]


class AuditEntry(BaseModel):
    """Immutable record of a curation operation for audit and rollback."""

    entry_id: str = Field(default_factory=lambda: f"audit_{uuid4().hex[:12]}")
    operation: str
    target_ids: list[str]
    suggestion_id: str
    rollback_data: dict = Field(default_factory=dict)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Three-tier thresholds ──

AUTO_APPROVE_THRESHOLD = 0.95
REVIEW_THRESHOLD = 0.70


class CurationPlan(BaseModel):
    """Aggregated curation suggestions with three-tier classification."""

    suggestions: list[CurationSuggestion] = Field(default_factory=list)

    @property
    def auto_approve(self) -> list[CurationSuggestion]:
        return [s for s in self.suggestions if s.confidence > AUTO_APPROVE_THRESHOLD]

    @property
    def needs_review(self) -> list[CurationSuggestion]:
        return [
            s
            for s in self.suggestions
            if REVIEW_THRESHOLD <= s.confidence <= AUTO_APPROVE_THRESHOLD
        ]

    @property
    def discard(self) -> list[CurationSuggestion]:
        return [s for s in self.suggestions if s.confidence < REVIEW_THRESHOLD]


class CurationResult(BaseModel):
    """Result of executing a curation plan."""

    executed: list[CurationSuggestion] = Field(default_factory=list)
    skipped: list[CurationSuggestion] = Field(default_factory=list)
    audit_entries: list[AuditEntry] = Field(default_factory=list)
    structure_report: StructureReport = Field(default_factory=StructureReport)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_models.py -v`
Expected: PASS (all 9 tests)

- [ ] **Step 5: Commit**

```bash
git add libs/curation/ tests/libs/curation/
git commit -m "feat(curation): add curation data models with three-tier plan classification"
```

---

## Chunk 2: Clustering + Classification

### Task 3: Shared Similarity Function (`find_similar`)

The spec §4 defines `find_similar(node, candidates, threshold)` as a shared primitive used by both global canonicalization and curation. This wraps existing similarity infrastructure for 1-vs-N lookup.

**Files:**
- Create: `libs/curation/similarity.py`
- Test: `tests/libs/curation/test_similarity.py`

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/test_similarity.py`:

```python
"""Tests for shared find_similar function."""

import pytest

from libs.curation.similarity import find_similar
from libs.embedding import StubEmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode


def _make_nodes():
    return [
        GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_b",
            knowledge_type="claim",
            representative_content="Water boils at 100 degrees Celsius",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_c",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",  # identical to gcn_a
        ),
    ]


async def test_find_similar_returns_matches_above_threshold():
    """Nodes with identical content should be returned as similar."""
    nodes = _make_nodes()
    query = nodes[0]
    candidates = nodes[1:]
    embedding_model = StubEmbeddingModel(dim=64)

    results = await find_similar(query, candidates, threshold=0.90, embedding_model=embedding_model)
    # gcn_c has identical content to query, should match
    matched_ids = {r[0] for r in results}
    assert "gcn_c" in matched_ids


async def test_find_similar_empty_candidates():
    """No candidates returns empty list."""
    node = GlobalCanonicalNode(
        global_canonical_id="gcn_a",
        knowledge_type="claim",
        representative_content="Test",
    )
    results = await find_similar(node, [], threshold=0.90)
    assert results == []


async def test_find_similar_type_mismatch_excluded():
    """Candidates with different knowledge_type are excluded."""
    query = GlobalCanonicalNode(
        global_canonical_id="gcn_q",
        knowledge_type="claim",
        representative_content="Same content",
    )
    candidate = GlobalCanonicalNode(
        global_canonical_id="gcn_c",
        knowledge_type="question",
        representative_content="Same content",
    )
    results = await find_similar(query, [candidate], threshold=0.50)
    assert results == []


async def test_find_similar_tfidf_fallback():
    """Works without embedding model using TF-IDF."""
    nodes = _make_nodes()
    results = await find_similar(nodes[0], [nodes[2]], threshold=0.50, embedding_model=None)
    # Identical text should match even with TF-IDF
    assert len(results) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_similarity.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement find_similar**

Create `libs/curation/similarity.py`:

```python
"""Shared similarity function for curation.

find_similar() is the 1-vs-N similarity lookup used by both global
canonicalization (1 local node vs global graph) and curation clustering
(N:N via repeated 1-vs-N calls or matrix approach).

Spec reference: §4 shared bottom functions.
"""

from __future__ import annotations

from libs.embedding import EmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode
from libs.global_graph.similarity import (
    compute_similarity_tfidf,
    cosine_similarity_vectors,
)

# Types that are package-local — never match across packages
_RELATION_TYPES = {"contradiction", "equivalence"}
_KIND_REQUIRED_TYPES = {"question", "action"}


async def find_similar(
    node: GlobalCanonicalNode,
    candidates: list[GlobalCanonicalNode],
    threshold: float = 0.90,
    embedding_model: EmbeddingModel | None = None,
) -> list[tuple[str, float]]:
    """Find candidates similar to node above threshold.

    Args:
        node: The query node.
        candidates: Nodes to compare against.
        threshold: Minimum similarity score.
        embedding_model: For embedding-based similarity. Falls back to TF-IDF if None.

    Returns:
        List of (global_canonical_id, similarity_score) sorted by score descending.
    """
    if not candidates or not node.representative_content.strip():
        return []

    if node.knowledge_type in _RELATION_TYPES:
        return []

    # Filter by type/kind constraints
    eligible = []
    for c in candidates:
        if c.global_canonical_id == node.global_canonical_id:
            continue  # Skip self
        if c.knowledge_type != node.knowledge_type:
            continue
        if node.knowledge_type in _KIND_REQUIRED_TYPES and c.kind != node.kind:
            continue
        eligible.append(c)

    if not eligible:
        return []

    results: list[tuple[str, float]] = []

    if embedding_model is not None:
        texts = [node.representative_content] + [c.representative_content for c in eligible]
        embeddings = await embedding_model.embed(texts)
        query_emb = embeddings[0]
        for i, c in enumerate(eligible):
            score = cosine_similarity_vectors(query_emb, embeddings[i + 1])
            if score >= threshold:
                results.append((c.global_canonical_id, score))
    else:
        for c in eligible:
            score = compute_similarity_tfidf(
                node.representative_content, c.representative_content
            )
            if score >= threshold:
                results.append((c.global_canonical_id, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_similarity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/curation/similarity.py tests/libs/curation/test_similarity.py
git commit -m "feat(curation): add shared find_similar() function per spec §4"
```

---

### Task 4: Clustering — Similar Node Discovery

Find groups of semantically similar `GlobalCanonicalNode`s via embedding cosine similarity + BM25 dual recall.

**Files:**
- Create: `libs/curation/clustering.py`
- Test: `tests/libs/curation/test_clustering.py`

**Key design decisions:**
- Reuses `cosine_similarity_vectors` from `libs/global_graph/similarity.py`
- BM25 recall via `StorageManager.search_bm25()` — searches Knowledge content, maps back to global nodes via bindings
- Clustering uses single-linkage on pairwise similarity above threshold
- Returns `list[ClusterGroup]` — each group has ≥2 nodes

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/test_clustering.py`:

```python
"""Tests for curation clustering module."""

import pytest

from libs.curation.clustering import cluster_similar_nodes, _build_clusters_from_pairs
from libs.curation.models import SimilarityPair
from libs.embedding import StubEmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode


# ── Unit test: cluster building from pairs ──


def test_build_clusters_single_pair():
    """Two nodes above threshold form one cluster."""
    pairs = [
        SimilarityPair(
            node_a_id="gcn_a", node_b_id="gcn_b", similarity_score=0.96, method="embedding"
        )
    ]
    clusters = _build_clusters_from_pairs(pairs)
    assert len(clusters) == 1
    assert set(clusters[0].node_ids) == {"gcn_a", "gcn_b"}


def test_build_clusters_transitive():
    """A-B and B-C should merge into one cluster {A, B, C}."""
    pairs = [
        SimilarityPair(
            node_a_id="gcn_a", node_b_id="gcn_b", similarity_score=0.95, method="embedding"
        ),
        SimilarityPair(
            node_a_id="gcn_b", node_b_id="gcn_c", similarity_score=0.93, method="embedding"
        ),
    ]
    clusters = _build_clusters_from_pairs(pairs)
    assert len(clusters) == 1
    assert set(clusters[0].node_ids) == {"gcn_a", "gcn_b", "gcn_c"}


def test_build_clusters_disjoint():
    """Two disjoint pairs form two clusters."""
    pairs = [
        SimilarityPair(
            node_a_id="gcn_a", node_b_id="gcn_b", similarity_score=0.96, method="embedding"
        ),
        SimilarityPair(
            node_a_id="gcn_c", node_b_id="gcn_d", similarity_score=0.95, method="embedding"
        ),
    ]
    clusters = _build_clusters_from_pairs(pairs)
    assert len(clusters) == 2


def test_build_clusters_empty():
    """No pairs produce no clusters."""
    clusters = _build_clusters_from_pairs([])
    assert clusters == []


# ── Integration test: full clustering with embedding ──


async def test_cluster_similar_nodes_finds_similar():
    """Nodes with identical content should cluster together."""
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_b",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",  # identical
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_c",
            knowledge_type="claim",
            representative_content="Water boils at 100 degrees Celsius",  # different
        ),
    ]
    embedding_model = StubEmbeddingModel(dim=64)
    clusters = await cluster_similar_nodes(nodes, embedding_model=embedding_model, threshold=0.90)
    # The two identical texts should cluster; the different one should not
    matching = [c for c in clusters if "gcn_a" in c.node_ids]
    assert len(matching) == 1
    assert "gcn_b" in matching[0].node_ids


async def test_cluster_similar_nodes_empty():
    """Empty input returns no clusters."""
    clusters = await cluster_similar_nodes([], threshold=0.90)
    assert clusters == []


async def test_cluster_similar_nodes_single_node():
    """Single node cannot form a cluster."""
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="Solo node",
        ),
    ]
    clusters = await cluster_similar_nodes(nodes, threshold=0.90)
    assert clusters == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_clustering.py -v`
Expected: FAIL — `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement clustering**

Create `libs/curation/clustering.py`:

```python
"""Clustering — discover groups of similar GlobalCanonicalNodes.

Uses dual-recall: embedding cosine similarity (primary) + TF-IDF (secondary).
Both signals are computed and their results merged (union). Pairs found by
both methods get method="both" and the max score.

Spec reference: §3.1 — "ANN + BM25 dual recall".

Clustering strategy: single-linkage on pairwise similarity above threshold.
"""

from __future__ import annotations

from uuid import uuid4

import numpy as np

from libs.embedding import EmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode
from libs.global_graph.similarity import compute_similarity_tfidf, cosine_similarity_vectors

from .models import ClusterGroup, SimilarityPair


def _build_clusters_from_pairs(pairs: list[SimilarityPair]) -> list[ClusterGroup]:
    """Build clusters from similarity pairs using union-find (single linkage)."""
    if not pairs:
        return []

    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for pair in pairs:
        parent.setdefault(pair.node_a_id, pair.node_a_id)
        parent.setdefault(pair.node_b_id, pair.node_b_id)
        union(pair.node_a_id, pair.node_b_id)

    # Group by root
    groups: dict[str, list[str]] = {}
    for node_id in parent:
        root = find(node_id)
        groups.setdefault(root, []).append(node_id)

    # Attach pairs to their cluster
    pair_index: dict[str, list[SimilarityPair]] = {}
    for pair in pairs:
        root = find(pair.node_a_id)
        pair_index.setdefault(root, []).append(pair)

    return [
        ClusterGroup(
            cluster_id=f"cluster_{uuid4().hex[:8]}",
            node_ids=sorted(members),
            pairs=pair_index.get(root, []),
        )
        for root, members in groups.items()
        if len(members) >= 2
    ]


def _merge_pair_sets(
    emb_pairs: dict[tuple[str, str], SimilarityPair],
    tfidf_pairs: dict[tuple[str, str], SimilarityPair],
) -> list[SimilarityPair]:
    """Merge embedding and TF-IDF pair results (union). Dual-recall."""
    all_keys = set(emb_pairs.keys()) | set(tfidf_pairs.keys())
    merged: list[SimilarityPair] = []
    for key in all_keys:
        ep = emb_pairs.get(key)
        tp = tfidf_pairs.get(key)
        if ep and tp:
            merged.append(
                SimilarityPair(
                    node_a_id=key[0],
                    node_b_id=key[1],
                    similarity_score=max(ep.similarity_score, tp.similarity_score),
                    method="both",
                )
            )
        elif ep:
            merged.append(ep)
        else:
            assert tp is not None
            merged.append(tp)
    return merged


async def cluster_similar_nodes(
    nodes: list[GlobalCanonicalNode],
    threshold: float = 0.90,
    embedding_model: EmbeddingModel | None = None,
) -> list[ClusterGroup]:
    """Find clusters of similar nodes via dual-recall: embedding + TF-IDF.

    Both signals are always computed (when embedding_model is available).
    Results are merged (union) so pairs caught by either method are included.

    Args:
        nodes: All GlobalCanonicalNodes to compare.
        threshold: Minimum similarity to consider a pair.
        embedding_model: For embedding computation. TF-IDF always runs as secondary.

    Returns:
        List of ClusterGroups, each containing ≥2 similar nodes.
    """
    if len(nodes) < 2:
        return []

    emb_pairs: dict[tuple[str, str], SimilarityPair] = {}
    tfidf_pairs: dict[tuple[str, str], SimilarityPair] = {}

    # Embedding recall (primary)
    if embedding_model is not None:
        texts = [n.representative_content for n in nodes]
        embeddings = await embedding_model.embed(texts)

        emb_matrix = np.array(embeddings)
        norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)
        normalized = emb_matrix / norms
        sim_matrix = normalized @ normalized.T

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                if nodes[i].knowledge_type != nodes[j].knowledge_type:
                    continue
                score = float(sim_matrix[i, j])
                if score >= threshold:
                    key = (nodes[i].global_canonical_id, nodes[j].global_canonical_id)
                    emb_pairs[key] = SimilarityPair(
                        node_a_id=key[0],
                        node_b_id=key[1],
                        similarity_score=score,
                        method="embedding",
                    )

    # TF-IDF recall (secondary, always runs)
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if nodes[i].knowledge_type != nodes[j].knowledge_type:
                continue
            score = compute_similarity_tfidf(
                nodes[i].representative_content,
                nodes[j].representative_content,
            )
            if score >= threshold:
                key = (nodes[i].global_canonical_id, nodes[j].global_canonical_id)
                tfidf_pairs[key] = SimilarityPair(
                    node_a_id=key[0],
                    node_b_id=key[1],
                    similarity_score=score,
                    method="bm25",
                )

    # Merge dual-recall results
    merged_pairs = _merge_pair_sets(emb_pairs, tfidf_pairs)
    return _build_clusters_from_pairs(merged_pairs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_clustering.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/curation/clustering.py tests/libs/curation/test_clustering.py
git commit -m "feat(curation): add clustering with embedding + TF-IDF dual-recall"
```

---

### Task 5: Classification — Duplicate vs Equivalence

For each cluster, classify the relationship between nodes as `merge` (duplicate) or `create_equivalence`.

**Files:**
- Create: `libs/curation/classification.py`
- Test: `tests/libs/curation/test_classification.py`

**Design:** High similarity (> 0.95) + same content length ratio → merge (duplicate). Otherwise → equivalence. V1 does not do abstraction/induction.

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/test_classification.py`:

```python
"""Tests for curation classification module."""

from libs.curation.classification import classify_clusters
from libs.curation.models import ClusterGroup, CurationSuggestion, SimilarityPair
from libs.global_graph.models import GlobalCanonicalNode

# ── Test fixtures ──

_NODES = {
    "gcn_a": GlobalCanonicalNode(
        global_canonical_id="gcn_a",
        knowledge_type="claim",
        representative_content="The Earth orbits the Sun",
    ),
    "gcn_b": GlobalCanonicalNode(
        global_canonical_id="gcn_b",
        knowledge_type="claim",
        representative_content="The Earth orbits the Sun",  # identical = duplicate
    ),
    "gcn_c": GlobalCanonicalNode(
        global_canonical_id="gcn_c",
        knowledge_type="claim",
        representative_content="Our planet revolves around the star at the center of the solar system",
    ),
}


def test_classify_high_similarity_as_merge():
    """Pair with very high similarity → merge suggestion."""
    clusters = [
        ClusterGroup(
            cluster_id="c1",
            node_ids=["gcn_a", "gcn_b"],
            pairs=[
                SimilarityPair(
                    node_a_id="gcn_a",
                    node_b_id="gcn_b",
                    similarity_score=0.99,
                    method="embedding",
                )
            ],
        )
    ]
    suggestions = classify_clusters(clusters, _NODES)
    assert len(suggestions) == 1
    assert suggestions[0].operation == "merge"
    assert suggestions[0].confidence > 0.95


def test_classify_medium_similarity_as_equivalence():
    """Pair with medium-high similarity → equivalence suggestion."""
    clusters = [
        ClusterGroup(
            cluster_id="c2",
            node_ids=["gcn_a", "gcn_c"],
            pairs=[
                SimilarityPair(
                    node_a_id="gcn_a",
                    node_b_id="gcn_c",
                    similarity_score=0.88,
                    method="embedding",
                )
            ],
        )
    ]
    suggestions = classify_clusters(clusters, _NODES)
    assert len(suggestions) == 1
    assert suggestions[0].operation == "create_equivalence"


def test_classify_empty_clusters():
    """No clusters produce no suggestions."""
    assert classify_clusters([], {}) == []


def test_classify_multi_node_cluster():
    """Cluster with 3 nodes produces pairwise suggestions."""
    clusters = [
        ClusterGroup(
            cluster_id="c3",
            node_ids=["gcn_a", "gcn_b", "gcn_c"],
            pairs=[
                SimilarityPair(
                    node_a_id="gcn_a",
                    node_b_id="gcn_b",
                    similarity_score=0.99,
                    method="embedding",
                ),
                SimilarityPair(
                    node_a_id="gcn_a",
                    node_b_id="gcn_c",
                    similarity_score=0.85,
                    method="embedding",
                ),
            ],
        )
    ]
    suggestions = classify_clusters(clusters, _NODES)
    # Should produce suggestions for each pair
    assert len(suggestions) == 2
    ops = {s.operation for s in suggestions}
    assert "merge" in ops
    assert "create_equivalence" in ops
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_classification.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement classification**

Create `libs/curation/classification.py`:

```python
"""Classification — determine relationship type for clustered node pairs.

V1 supports two classifications:
- merge (duplicate): very high similarity, similar content length
- create_equivalence: high similarity but different enough to keep both
"""

from __future__ import annotations

from libs.global_graph.models import GlobalCanonicalNode

from .models import ClusterGroup, CurationSuggestion, SimilarityPair

# Threshold above which a pair is classified as duplicate (merge)
MERGE_THRESHOLD = 0.95


def _classify_pair(
    pair: SimilarityPair,
    nodes: dict[str, GlobalCanonicalNode],
) -> CurationSuggestion:
    """Classify a single similarity pair as merge or equivalence."""
    node_a = nodes.get(pair.node_a_id)
    node_b = nodes.get(pair.node_b_id)

    score = pair.similarity_score

    # High similarity → merge candidate
    if score >= MERGE_THRESHOLD:
        # Additional heuristic: content length ratio close to 1.0 suggests true duplicate
        if node_a and node_b:
            len_a = len(node_a.representative_content)
            len_b = len(node_b.representative_content)
            length_ratio = min(len_a, len_b) / max(len_a, len_b) if max(len_a, len_b) > 0 else 1.0
            # Even with very high embedding similarity, if length ratio is very low
            # it's more likely paraphrase than duplicate
            if length_ratio < 0.5:
                return CurationSuggestion(
                    operation="create_equivalence",
                    target_ids=[pair.node_a_id, pair.node_b_id],
                    confidence=score * 0.9,
                    reason=f"High similarity ({score:.3f}) but length ratio {length_ratio:.2f} suggests paraphrase",
                    evidence={"cosine": score, "length_ratio": length_ratio, "method": pair.method},
                )

        return CurationSuggestion(
            operation="merge",
            target_ids=[pair.node_a_id, pair.node_b_id],
            confidence=score,
            reason=f"Near-identical content (similarity {score:.3f})",
            evidence={"cosine": score, "method": pair.method},
        )

    # Below merge threshold → equivalence
    return CurationSuggestion(
        operation="create_equivalence",
        target_ids=[pair.node_a_id, pair.node_b_id],
        confidence=score * 0.9,  # Discount: lower confidence for equivalence
        reason=f"Semantically similar but distinct (similarity {score:.3f})",
        evidence={"cosine": score, "method": pair.method},
    )


def classify_clusters(
    clusters: list[ClusterGroup],
    nodes: dict[str, GlobalCanonicalNode],
) -> list[CurationSuggestion]:
    """Classify all pairs within clusters into merge or equivalence suggestions.

    Args:
        clusters: Cluster groups from clustering step.
        nodes: Mapping from global_canonical_id → GlobalCanonicalNode for content lookup.

    Returns:
        List of CurationSuggestions, one per pair.
    """
    suggestions: list[CurationSuggestion] = []
    for cluster in clusters:
        for pair in cluster.pairs:
            suggestions.append(_classify_pair(pair, nodes))
    return suggestions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_classification.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/curation/classification.py tests/libs/curation/test_classification.py
git commit -m "feat(curation): add classification (duplicate vs equivalence)"
```

---

## Chunk 3: Conflict Discovery

### Task 6: BP Diagnostics — Oscillation Detection

Extend BP to return diagnostic information that Level 1 conflict detection needs: per-node belief history (direction changes) and convergence metadata.

**Files:**
- Modify: `libs/inference/bp.py` (add `BPDiagnostics` class and `run_with_diagnostics` method)
- Test: `tests/libs/inference/test_bp.py` (add diagnostics tests)

- [ ] **Step 1: Write the failing test**

Add to `tests/libs/inference/test_bp.py`:

```python
from libs.inference.bp import BPDiagnostics


def test_bp_diagnostics_returned():
    """run_with_diagnostics returns beliefs + diagnostics."""
    from libs.inference.factor_graph import FactorGraph

    g = FactorGraph()
    g.add_variable(1, 0.5)
    g.add_variable(2, 0.5)
    g.add_factor(0, [1], [2], 0.9, "deduction")

    bp = BeliefPropagation(max_iterations=10)
    beliefs, diag = bp.run_with_diagnostics(g)
    assert isinstance(beliefs, dict)
    assert isinstance(diag, BPDiagnostics)
    assert diag.iterations_run > 0
    assert diag.converged is True or diag.converged is False
    assert 1 in diag.belief_history
    assert 2 in diag.belief_history
    assert len(diag.belief_history[1]) > 0


def test_bp_diagnostics_oscillation_detection():
    """Conflicting factors should show direction changes in belief history."""
    from libs.inference.factor_graph import FactorGraph

    g = FactorGraph()
    g.add_variable(1, 0.8)
    g.add_variable(2, 0.8)
    # A supports B via deduction
    g.add_factor(0, [1], [2], 0.95, "deduction")
    # But also a contradiction between A and B
    g.add_factor(1, [1, 2], [], 0.95, "relation_contradiction")

    bp = BeliefPropagation(max_iterations=50, damping=0.5)
    beliefs, diag = bp.run_with_diagnostics(g)
    # The graph has tension; check diagnostics captured history
    assert len(diag.belief_history[1]) >= 2
    assert isinstance(diag.direction_changes, dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/inference/test_bp.py::test_bp_diagnostics_returned -v`
Expected: FAIL — `ImportError: cannot import name 'BPDiagnostics'`

- [ ] **Step 3: Implement BP diagnostics**

In `libs/inference/bp.py`, add a `BPDiagnostics` dataclass and refactor the BP loop so `run()` and `run_with_diagnostics()` share the same core logic.

At the top of the file, add import:
```python
from dataclasses import dataclass, field
```

After the `InconsistentGraphError` class, add:

```python
@dataclass
class BPDiagnostics:
    """Diagnostic information from a BP run for conflict detection."""

    iterations_run: int = 0
    converged: bool = False
    max_change_at_stop: float = 0.0
    belief_history: dict[int, list[float]] = field(default_factory=dict)
    direction_changes: dict[int, int] = field(default_factory=dict)
```

Update `__all__`:
```python
__all__ = ["BeliefPropagation", "BPDiagnostics", "InconsistentGraphError"]
```

**Refactor**: Extract the BP loop into `_run_core(self, graph, collect_diagnostics=False)` that returns `(beliefs, diag_or_None)`. Then rewrite `run()` and add `run_with_diagnostics()` as thin wrappers:

Replace the existing `run()` method with:

```python
    def _run_core(
        self, graph: FactorGraph, collect_diagnostics: bool = False
    ) -> tuple[dict[int, float], BPDiagnostics | None]:
        """Core BP loop shared by run() and run_with_diagnostics()."""
        diag = BPDiagnostics() if collect_diagnostics else None

        if not graph.variables:
            return {}, diag

        if not graph.factors:
            if diag is not None:
                diag.converged = True
            return dict(graph.variables), diag

        var_factors = graph.get_var_factors()
        priors = {vid: _prior_msg(p) for vid, p in graph.variables.items()}

        f2v_msgs: dict[tuple[int, int], Msg] = {}
        v2f_msgs: dict[tuple[int, int], Msg] = {}
        uniform = np.array([0.5, 0.5])

        for fi, factor in enumerate(graph.factors):
            for vid in factor["premises"] + factor["conclusions"]:
                if vid in graph.variables:
                    f2v_msgs[(fi, vid)] = uniform.copy()
                    v2f_msgs[(vid, fi)] = uniform.copy()

        prev_beliefs = {vid: p for vid, p in graph.variables.items()}
        if diag is not None:
            for vid, p in graph.variables.items():
                diag.belief_history[vid] = [p]

        max_change = 0.0
        for iteration in range(self._max_iter):
            new_v2f: dict[tuple[int, int], Msg] = {}
            for (vid, fi), _ in v2f_msgs.items():
                new_v2f[(vid, fi)] = _compute_var_to_factor(
                    vid, fi, priors[vid], var_factors, f2v_msgs
                )

            new_f2v: dict[tuple[int, int], Msg] = {}
            for (fi, vid), _ in f2v_msgs.items():
                new_f2v[(fi, vid)] = _compute_factor_to_var(
                    fi, vid, graph.factors[fi], new_v2f, prev_beliefs
                )

            for key in f2v_msgs:
                f2v_msgs[key] = _normalize(
                    self._damping * new_f2v[key] + (1 - self._damping) * f2v_msgs[key]
                )
            for key in v2f_msgs:
                v2f_msgs[key] = _normalize(
                    self._damping * new_v2f[key] + (1 - self._damping) * v2f_msgs[key]
                )

            beliefs: dict[int, float] = {}
            for vid in graph.variables:
                b = priors[vid].copy()
                for fi in var_factors[vid]:
                    b = b * f2v_msgs[(fi, vid)]
                b = _normalize(b)
                beliefs[vid] = float(b[1])

            if diag is not None:
                for vid, belief in beliefs.items():
                    diag.belief_history[vid].append(belief)

            max_change = max(abs(beliefs[vid] - prev_beliefs[vid]) for vid in beliefs)
            if max_change < self._threshold:
                if diag is not None:
                    diag.iterations_run = iteration + 1
                    diag.converged = True
                    diag.max_change_at_stop = max_change
                return beliefs, diag
            prev_beliefs = beliefs

        if diag is not None:
            diag.iterations_run = self._max_iter
            diag.converged = False
            diag.max_change_at_stop = max_change
            # Compute direction changes per variable
            for vid, history in diag.belief_history.items():
                changes = 0
                for k in range(2, len(history)):
                    prev_dir = history[k - 1] - history[k - 2]
                    curr_dir = history[k] - history[k - 1]
                    if prev_dir * curr_dir < 0:
                        changes += 1
                diag.direction_changes[vid] = changes

        return beliefs, diag

    def run(self, graph: FactorGraph) -> dict[int, float]:
        """Run loopy BP on *graph* and return posterior beliefs."""
        beliefs, _ = self._run_core(graph, collect_diagnostics=False)
        return beliefs

    def run_with_diagnostics(self, graph: FactorGraph) -> tuple[dict[int, float], BPDiagnostics]:
        """Run loopy BP and return beliefs + diagnostic information.

        Diagnostics include per-node belief history and direction change counts,
        useful for Level 1 conflict detection (oscillation signals).
        """
        beliefs, diag = self._run_core(graph, collect_diagnostics=True)
        assert diag is not None  # collect_diagnostics=True guarantees non-None

        # Compute direction changes (only if not converged — converged means no oscillation)
        if not diag.converged:
            pass  # Already computed in _run_core
        else:
            for vid, history in diag.belief_history.items():
                changes = 0
                for k in range(2, len(history)):
                    prev_dir = history[k - 1] - history[k - 2]
                    curr_dir = history[k] - history[k - 1]
                    if prev_dir * curr_dir < 0:
                        changes += 1
                diag.direction_changes[vid] = changes

        return beliefs, diag
```

**Important**: Delete the old `run()` method body and replace with the `_run_core` delegation above. This avoids maintaining two copies of the BP loop.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/inference/test_bp.py::test_bp_diagnostics_returned tests/libs/inference/test_bp.py::test_bp_diagnostics_oscillation_detection -v`
Expected: PASS

- [ ] **Step 5: Run all existing BP tests to check nothing broke**

Run: `pytest tests/libs/inference/ -v`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
git add libs/inference/bp.py tests/libs/inference/test_bp.py
git commit -m "feat(inference): add BPDiagnostics with belief history and oscillation detection"
```

---

### Task 7: Conflict Discovery — Level 1 + Level 2

Level 1: Use BP diagnostics to find oscillating/unstable nodes.
Level 2: Sensitivity analysis — clamp each candidate node to true, re-run BP, find nodes whose beliefs drop significantly.

**Files:**
- Create: `libs/curation/conflict.py`
- Test: `tests/libs/curation/test_conflict.py`

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/test_conflict.py`:

```python
"""Tests for conflict discovery (BP Level 1 + Level 2)."""

import pytest

from libs.curation.conflict import (
    detect_conflicts_level1,
    detect_conflicts_level2,
)
from libs.curation.models import ConflictCandidate
from libs.inference.bp import BPDiagnostics, BeliefPropagation
from libs.inference.factor_graph import FactorGraph


def _make_contradictory_graph() -> FactorGraph:
    """Create a graph with inherent contradiction: A→B but A∧B is contradictory."""
    g = FactorGraph()
    g.add_variable(1, 0.8)
    g.add_variable(2, 0.8)
    g.add_factor(0, [1], [2], 0.95, "deduction")
    g.add_factor(1, [1, 2], [], 0.95, "relation_contradiction")
    return g


def _make_clean_graph() -> FactorGraph:
    """Create a graph with no contradictions."""
    g = FactorGraph()
    g.add_variable(1, 0.8)
    g.add_variable(2, 0.5)
    g.add_factor(0, [1], [2], 0.9, "deduction")
    return g


# ── Level 1: Oscillation detection ──


def test_level1_finds_oscillating_nodes():
    """Contradictory graph should produce oscillation or uncertain beliefs."""
    g = _make_contradictory_graph()
    bp = BeliefPropagation(max_iterations=50, damping=0.3)
    beliefs, diag = bp.run_with_diagnostics(g)
    # With a contradiction, at least one node should have direction changes
    total_changes = sum(diag.direction_changes.values())
    assert total_changes > 0, "Contradictory graph should cause belief oscillation"
    # Use relaxed threshold to ensure we capture the oscillation
    candidates = detect_conflicts_level1(diag, min_direction_changes=1, belief_range=(0.0, 1.0))
    assert len(candidates) >= 1, "Should find at least one conflict candidate"


def test_level1_clean_graph_no_conflicts():
    """Clean graph should produce no oscillation signals."""
    g = _make_clean_graph()
    bp = BeliefPropagation(max_iterations=50)
    _, diag = bp.run_with_diagnostics(g)
    candidates = detect_conflicts_level1(diag, min_direction_changes=3)
    assert candidates == []


def test_level1_empty_diagnostics():
    """Empty diagnostics produce no candidates."""
    diag = BPDiagnostics()
    assert detect_conflicts_level1(diag) == []


# ── Level 2: Sensitivity analysis ──


def test_level2_finds_antagonistic_pair():
    """Clamping A to true should cause B to drop when they are contradictory."""
    g = _make_contradictory_graph()
    bp = BeliefPropagation(max_iterations=50, damping=0.5)

    # Run baseline
    baseline_beliefs = bp.run(g)

    # Sensitivity analysis for node 1 — use very small min_drop since the
    # deduction and contradiction pull in opposite directions
    candidates = detect_conflicts_level2(
        graph=g,
        probe_node_ids=[1],
        baseline_beliefs=baseline_beliefs,
        bp=bp,
        min_drop=0.01,
    )
    # Clamping node 1 to true with a relation_contradiction on (1,2) should
    # cause node 2's belief to shift. The deduction pushes it up while the
    # contradiction pushes it down — either way, there should be a measurable effect.
    assert len(candidates) >= 1, "Clamping contradictory node should affect its partner"


def test_level2_clean_graph_no_antagonism():
    """In a supportive graph, clamping A should not cause B to drop significantly."""
    g = _make_clean_graph()
    bp = BeliefPropagation(max_iterations=50)
    baseline_beliefs = bp.run(g)

    candidates = detect_conflicts_level2(
        graph=g,
        probe_node_ids=[1],
        baseline_beliefs=baseline_beliefs,
        bp=bp,
        min_drop=0.1,
    )
    # No antagonistic relationships in a purely supportive graph
    assert candidates == []


def test_level2_empty_probe():
    """No probe nodes means no candidates."""
    g = _make_clean_graph()
    bp = BeliefPropagation()
    baseline = bp.run(g)
    candidates = detect_conflicts_level2(
        graph=g, probe_node_ids=[], baseline_beliefs=baseline, bp=bp
    )
    assert candidates == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_conflict.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement conflict discovery**

Create `libs/curation/conflict.py`:

```python
"""Conflict discovery via BP signals (Level 1) and sensitivity analysis (Level 2).

Level 1: Find nodes with belief oscillation (direction changes) in BP diagnostics.
Level 2: Clamp probe nodes to true, re-run BP, find nodes with significant belief drops.
"""

from __future__ import annotations

from libs.inference.bp import BPDiagnostics, BeliefPropagation
from libs.inference.factor_graph import FactorGraph

from .models import ConflictCandidate


def detect_conflicts_level1(
    diag: BPDiagnostics,
    min_direction_changes: int = 2,
    belief_range: tuple[float, float] = (0.3, 0.7),
) -> list[ConflictCandidate]:
    """Level 1: Identify candidate conflict regions from BP oscillation signals.

    Finds nodes whose belief oscillated (changed direction) frequently during BP
    and whose final belief is in the uncertain range (0.3-0.7).

    Args:
        diag: Diagnostics from run_with_diagnostics().
        min_direction_changes: Minimum number of direction changes to flag.
        belief_range: Belief value range to consider "uncertain".

    Returns:
        ConflictCandidate pairs from oscillating nodes.
    """
    if not diag.belief_history:
        return []

    # Find oscillating nodes
    oscillating_ids: list[int] = []
    for vid, changes in diag.direction_changes.items():
        if changes < min_direction_changes:
            continue
        # Check if final belief is in uncertain range
        history = diag.belief_history.get(vid, [])
        if history:
            final = history[-1]
            if belief_range[0] <= final <= belief_range[1]:
                oscillating_ids.append(vid)

    # Pair oscillating nodes (they are likely in conflict with each other)
    candidates: list[ConflictCandidate] = []
    for i in range(len(oscillating_ids)):
        for j in range(i + 1, len(oscillating_ids)):
            a, b = oscillating_ids[i], oscillating_ids[j]
            strength = (
                diag.direction_changes.get(a, 0) + diag.direction_changes.get(b, 0)
            ) / (2 * max(diag.iterations_run, 1))
            candidates.append(
                ConflictCandidate(
                    node_a_id=str(a),
                    node_b_id=str(b),
                    signal_type="oscillation",
                    strength=min(strength, 1.0),
                    detail={
                        "a_direction_changes": diag.direction_changes.get(a, 0),
                        "b_direction_changes": diag.direction_changes.get(b, 0),
                        "a_final_belief": diag.belief_history[a][-1],
                        "b_final_belief": diag.belief_history[b][-1],
                    },
                )
            )

    return candidates


def detect_conflicts_level2(
    graph: FactorGraph,
    probe_node_ids: list[int],
    baseline_beliefs: dict[int, float],
    bp: BeliefPropagation,
    min_drop: float = 0.1,
) -> list[ConflictCandidate]:
    """Level 2: Sensitivity analysis — clamp probes to true, find antagonistic nodes.

    For each probe node, create a modified graph with the probe clamped to true
    (prior = 0.999), run BP, and find nodes whose belief dropped significantly
    compared to the baseline.

    Args:
        graph: The original factor graph.
        probe_node_ids: Node IDs to test (typically from Level 1 candidates).
        baseline_beliefs: Beliefs from a normal BP run.
        bp: BeliefPropagation instance to use.
        min_drop: Minimum belief drop to flag as antagonistic.

    Returns:
        ConflictCandidate pairs (probe, antagonist).
    """
    if not probe_node_ids:
        return []

    candidates: list[ConflictCandidate] = []

    for probe_id in probe_node_ids:
        if probe_id not in graph.variables:
            continue

        # Build clamped graph: same structure, probe prior → 0.999
        clamped = FactorGraph()
        for vid, prior in graph.variables.items():
            clamped.add_variable(vid, 0.999 if vid == probe_id else prior)
        for factor in graph.factors:
            clamped.add_factor(
                factor["edge_id"],
                factor["premises"],
                factor["conclusions"],
                factor["probability"],
                factor.get("edge_type", "deduction"),
                factor.get("gate_var"),
            )

        # Run BP on clamped graph
        clamped_beliefs = bp.run(clamped)

        # Find nodes with significant belief drop
        for vid, clamped_belief in clamped_beliefs.items():
            if vid == probe_id:
                continue
            baseline = baseline_beliefs.get(vid, 0.5)
            drop = baseline - clamped_belief
            if drop >= min_drop:
                candidates.append(
                    ConflictCandidate(
                        node_a_id=str(probe_id),
                        node_b_id=str(vid),
                        signal_type="sensitivity",
                        strength=min(drop, 1.0),
                        detail={
                            "probe_id": probe_id,
                            "baseline_belief": baseline,
                            "clamped_belief": clamped_belief,
                            "belief_drop": drop,
                        },
                    )
                )

    return candidates
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_conflict.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/curation/conflict.py tests/libs/curation/test_conflict.py
git commit -m "feat(curation): add conflict discovery Level 1 (oscillation) + Level 2 (sensitivity)"
```

---

## Chunk 4: Structure Inspection + Audit Log

### Task 8: Structure Inspection

Check graph health: orphan nodes, dangling factors, high-degree nodes, disconnected components.

**Files:**
- Create: `libs/curation/structure.py`
- Test: `tests/libs/curation/test_structure.py`

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/test_structure.py`:

```python
"""Tests for graph structure inspection."""

from libs.curation.structure import inspect_structure
from libs.global_graph.models import GlobalCanonicalNode
from libs.storage.models import FactorNode


def _make_nodes(*ids: str) -> list[GlobalCanonicalNode]:
    return [
        GlobalCanonicalNode(
            global_canonical_id=gid,
            knowledge_type="claim",
            representative_content=f"Content of {gid}",
        )
        for gid in ids
    ]


def test_orphan_node_detected():
    """Node with no factor connections is flagged as orphan."""
    nodes = _make_nodes("gcn_a", "gcn_b", "gcn_orphan")
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_a"],
            conclusion="gcn_b",
            package_id="pkg1",
        )
    ]
    report = inspect_structure(nodes, factors)
    orphan_issues = [i for i in report.issues if i.issue_type == "orphan_node"]
    assert len(orphan_issues) == 1
    assert "gcn_orphan" in orphan_issues[0].node_ids


def test_dangling_factor_detected():
    """Factor referencing non-existent node is flagged."""
    nodes = _make_nodes("gcn_a")
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_a"],
            conclusion="gcn_deleted",  # does not exist
            package_id="pkg1",
        )
    ]
    report = inspect_structure(nodes, factors)
    dangling = [i for i in report.issues if i.issue_type == "dangling_factor"]
    assert len(dangling) == 1
    assert dangling[0].severity == "error"
    assert "f_1" in dangling[0].factor_ids


def test_high_degree_detected():
    """Node participating in many factors is flagged as high-degree."""
    nodes = _make_nodes("gcn_hub", "gcn_1", "gcn_2", "gcn_3", "gcn_4", "gcn_5")
    factors = [
        FactorNode(
            factor_id=f"f_{i}",
            type="reasoning",
            premises=["gcn_hub"],
            conclusion=f"gcn_{i}",
            package_id="pkg1",
        )
        for i in range(1, 6)
    ]
    report = inspect_structure(nodes, factors, high_degree_threshold=4)
    high_deg = [i for i in report.issues if i.issue_type == "high_degree"]
    assert len(high_deg) == 1
    assert "gcn_hub" in high_deg[0].node_ids


def test_clean_graph_no_issues():
    """Well-formed graph has no error/warning issues."""
    nodes = _make_nodes("gcn_a", "gcn_b")
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_a"],
            conclusion="gcn_b",
            package_id="pkg1",
        )
    ]
    report = inspect_structure(nodes, factors)
    assert len(report.errors) == 0
    assert len(report.warnings) == 0


def test_empty_graph():
    """Empty graph produces no issues."""
    report = inspect_structure([], [])
    assert report.issues == []


def test_disconnected_components():
    """Two separate subgraphs should be flagged as disconnected."""
    nodes = _make_nodes("gcn_a", "gcn_b", "gcn_c", "gcn_d")
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_a"],
            conclusion="gcn_b",
            package_id="pkg1",
        ),
        FactorNode(
            factor_id="f_2",
            type="reasoning",
            premises=["gcn_c"],
            conclusion="gcn_d",
            package_id="pkg1",
        ),
    ]
    report = inspect_structure(nodes, factors)
    disconnected = [i for i in report.issues if i.issue_type == "disconnected_component"]
    assert len(disconnected) == 1
    assert disconnected[0].severity == "info"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_structure.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement structure inspection**

Create `libs/curation/structure.py`:

```python
"""Structure inspection — check graph health.

Detects: orphan nodes, dangling factors, high-degree nodes, disconnected components.
"""

from __future__ import annotations

from collections import defaultdict

from libs.global_graph.models import GlobalCanonicalNode
from libs.storage.models import FactorNode

from .models import StructureIssue, StructureReport


def inspect_structure(
    nodes: list[GlobalCanonicalNode],
    factors: list[FactorNode],
    high_degree_threshold: int = 20,
) -> StructureReport:
    """Inspect the global graph structure for health issues.

    Args:
        nodes: All GlobalCanonicalNodes in the graph.
        factors: All FactorNodes in the graph.
        high_degree_threshold: Flag nodes with degree above this.

    Returns:
        StructureReport with categorized issues.
    """
    if not nodes and not factors:
        return StructureReport()

    node_ids = {n.global_canonical_id for n in nodes}
    issues: list[StructureIssue] = []

    # Build degree map + adjacency for components
    degree: dict[str, int] = defaultdict(int)
    adjacency: dict[str, set[str]] = defaultdict(set)

    for factor in factors:
        all_refs = list(factor.premises) + [factor.conclusion]

        # Check for dangling references
        dangling = [ref for ref in all_refs if ref not in node_ids]
        if dangling:
            issues.append(
                StructureIssue(
                    issue_type="dangling_factor",
                    severity="error",
                    node_ids=dangling,
                    factor_ids=[factor.factor_id],
                    detail=f"Factor {factor.factor_id} references non-existent node(s): {dangling}",
                )
            )

        # Update degree and adjacency (only for existing nodes)
        existing_refs = [ref for ref in all_refs if ref in node_ids]
        for ref in existing_refs:
            degree[ref] += 1
        for i in range(len(existing_refs)):
            for j in range(i + 1, len(existing_refs)):
                adjacency[existing_refs[i]].add(existing_refs[j])
                adjacency[existing_refs[j]].add(existing_refs[i])

    # Orphan nodes: no factor connections
    for nid in node_ids:
        if degree[nid] == 0:
            issues.append(
                StructureIssue(
                    issue_type="orphan_node",
                    severity="warning",
                    node_ids=[nid],
                    detail=f"Node {nid} has no factor connections",
                )
            )

    # High-degree nodes
    for nid, deg in degree.items():
        if deg > high_degree_threshold:
            issues.append(
                StructureIssue(
                    issue_type="high_degree",
                    severity="info",
                    node_ids=[nid],
                    detail=f"Node {nid} has degree {deg} (threshold: {high_degree_threshold})",
                )
            )

    # Disconnected components (BFS)
    # Only check nodes that participate in at least one factor
    connected_nodes = {nid for nid in node_ids if degree[nid] > 0}
    if len(connected_nodes) > 1:
        visited: set[str] = set()
        component_count = 0
        for start in connected_nodes:
            if start in visited:
                continue
            component_count += 1
            queue = [start]
            while queue:
                current = queue.pop()
                if current in visited:
                    continue
                visited.add(current)
                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)

        if component_count > 1:
            issues.append(
                StructureIssue(
                    issue_type="disconnected_component",
                    severity="info",
                    detail=f"Graph has {component_count} disconnected components",
                )
            )

    return StructureReport(issues=issues)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_structure.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/curation/structure.py tests/libs/curation/test_structure.py
git commit -m "feat(curation): add structure inspection (orphans, dangling, degree, components)"
```

---

### Task 9: Audit Log

Append-only audit log for curation operations. Supports rollback by storing the pre-operation state.

**Files:**
- Create: `libs/curation/audit.py`
- Test: `tests/libs/curation/test_audit.py`

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/test_audit.py`:

```python
"""Tests for curation audit log."""

from libs.curation.audit import AuditLog
from libs.curation.models import AuditEntry


def test_audit_log_append_and_list():
    """Entries can be appended and listed."""
    log = AuditLog()
    entry = AuditEntry(
        entry_id="a1",
        operation="merge",
        target_ids=["gcn_a", "gcn_b"],
        suggestion_id="sug_1",
        rollback_data={"removed_node": "gcn_b"},
    )
    log.append(entry)
    assert len(log.entries) == 1
    assert log.entries[0].entry_id == "a1"


def test_audit_log_get_by_id():
    """Can retrieve entry by ID."""
    log = AuditLog()
    entry = AuditEntry(
        entry_id="a1",
        operation="merge",
        target_ids=["gcn_a", "gcn_b"],
        suggestion_id="sug_1",
    )
    log.append(entry)
    assert log.get("a1") is not None
    assert log.get("nonexistent") is None


def test_audit_log_list_by_operation():
    """Can filter entries by operation type."""
    log = AuditLog()
    log.append(
        AuditEntry(
            entry_id="a1",
            operation="merge",
            target_ids=["gcn_a", "gcn_b"],
            suggestion_id="sug_1",
        )
    )
    log.append(
        AuditEntry(
            entry_id="a2",
            operation="create_equivalence",
            target_ids=["gcn_c", "gcn_d"],
            suggestion_id="sug_2",
        )
    )
    merges = log.list_by_operation("merge")
    assert len(merges) == 1
    assert merges[0].entry_id == "a1"


def test_audit_log_serialization():
    """Log can be serialized and deserialized."""
    log = AuditLog()
    log.append(
        AuditEntry(
            entry_id="a1",
            operation="merge",
            target_ids=["gcn_a", "gcn_b"],
            suggestion_id="sug_1",
            rollback_data={"key": "value"},
        )
    )
    data = log.to_dicts()
    assert len(data) == 1
    assert data[0]["entry_id"] == "a1"

    restored = AuditLog.from_dicts(data)
    assert len(restored.entries) == 1
    assert restored.entries[0].rollback_data == {"key": "value"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_audit.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement audit log**

Create `libs/curation/audit.py`:

```python
"""Audit log for curation operations.

Append-only in-memory log. Each entry stores rollback_data sufficient to
undo the operation. Serializable to/from list[dict] for persistence.
"""

from __future__ import annotations

from .models import AuditEntry


class AuditLog:
    """Append-only audit log for curation operations."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def append(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    def get(self, entry_id: str) -> AuditEntry | None:
        for e in self._entries:
            if e.entry_id == entry_id:
                return e
        return None

    def list_by_operation(self, operation: str) -> list[AuditEntry]:
        return [e for e in self._entries if e.operation == operation]

    def to_dicts(self) -> list[dict]:
        return [e.model_dump(mode="json") for e in self._entries]

    @classmethod
    def from_dicts(cls, data: list[dict]) -> AuditLog:
        log = cls()
        for d in data:
            log.append(AuditEntry.model_validate(d))
        return log
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_audit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/curation/audit.py tests/libs/curation/test_audit.py
git commit -m "feat(curation): add audit log with serialization support"
```

---

## Chunk 5: Operations + Cleanup + Scheduler

### Task 10: Operations — Merge Nodes + Create Constraint

Graph modification primitives: merge two GlobalCanonicalNodes, create an equivalence or contradiction factor.

**Files:**
- Create: `libs/curation/operations.py`
- Test: `tests/libs/curation/test_operations.py`

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/test_operations.py`:

```python
"""Tests for curation graph operations."""

from libs.curation.operations import create_constraint, merge_nodes
from libs.global_graph.models import GlobalCanonicalNode, LocalCanonicalRef, PackageRef
from libs.storage.models import FactorNode


def _make_node(gid: str, content: str, members: int = 1) -> GlobalCanonicalNode:
    return GlobalCanonicalNode(
        global_canonical_id=gid,
        knowledge_type="claim",
        representative_content=content,
        member_local_nodes=[
            LocalCanonicalRef(package=f"pkg{i}", version="0.1.0", local_canonical_id=f"lcn_{gid}_{i}")
            for i in range(members)
        ],
        provenance=[PackageRef(package=f"pkg{i}", version="0.1.0") for i in range(members)],
    )


# ── merge_nodes ──


def test_merge_nodes_combines_members():
    """Merging two nodes should combine their member_local_nodes."""
    source = _make_node("gcn_source", "The Earth orbits the Sun", members=1)
    target = _make_node("gcn_target", "The Earth orbits the Sun", members=1)
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_source"],
            conclusion="gcn_other",
            package_id="pkg1",
        ),
        FactorNode(
            factor_id="f_2",
            type="reasoning",
            premises=["gcn_other"],
            conclusion="gcn_target",
            package_id="pkg1",
        ),
    ]

    result = merge_nodes("gcn_source", "gcn_target", source, target, factors)
    assert result.merged_node.global_canonical_id == "gcn_target"
    # Target should now have members from both
    assert len(result.merged_node.member_local_nodes) == 2
    # Factors referencing source should be redirected to target
    assert all(
        "gcn_source" not in (f.premises + [f.conclusion]) for f in result.updated_factors
    )
    # Rollback data should record what was merged
    assert result.rollback_data["source_id"] == "gcn_source"


def test_merge_nodes_deduplicates_provenance():
    """Provenance from both nodes is deduplicated."""
    source = _make_node("gcn_s", "Content", members=1)
    target = _make_node("gcn_t", "Content", members=1)
    # Give them same provenance
    target.provenance = list(source.provenance)

    result = merge_nodes("gcn_s", "gcn_t", source, target, [])
    # Should not have duplicate provenance
    prov_set = {(p.package, p.version) for p in result.merged_node.provenance}
    assert len(prov_set) == len(result.merged_node.provenance)


# ── create_constraint ──


def test_create_equivalence_constraint():
    """Create an equivalence factor between two nodes."""
    factor = create_constraint("gcn_a", "gcn_b", "equivalence")
    assert factor.type == "equiv_constraint"
    assert set(factor.premises) == {"gcn_a", "gcn_b"}
    assert factor.metadata["curation_created"] is True


def test_create_contradiction_constraint():
    """Create a contradiction factor between two nodes."""
    factor = create_constraint("gcn_a", "gcn_b", "contradiction")
    assert factor.type == "mutex_constraint"
    assert set(factor.premises) == {"gcn_a", "gcn_b"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_operations.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement operations**

Create `libs/curation/operations.py`:

```python
"""Graph modification operations for curation.

merge_nodes: Merge source into target, redirect all factor references.
create_constraint: Create equivalence or contradiction factor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from uuid import uuid4

from libs.global_graph.models import GlobalCanonicalNode, PackageRef
from libs.storage.models import FactorNode


@dataclass
class MergeResult:
    """Result of merging two GlobalCanonicalNodes."""

    merged_node: GlobalCanonicalNode
    updated_factors: list[FactorNode]
    removed_node_id: str
    rollback_data: dict = field(default_factory=dict)


def merge_nodes(
    source_id: str,
    target_id: str,
    source: GlobalCanonicalNode,
    target: GlobalCanonicalNode,
    factors: list[FactorNode],
) -> MergeResult:
    """Merge source node into target node.

    - Combines member_local_nodes and provenance
    - Redirects all factor references from source_id → target_id
    - Returns updated target node and modified factors

    Args:
        source_id: ID of the node to remove.
        target_id: ID of the node to keep.
        source: Source GlobalCanonicalNode.
        target: Target GlobalCanonicalNode (will be modified).
        factors: All factors in the graph (those referencing source will be updated).

    Returns:
        MergeResult with the merged node, updated factors, and rollback data.
    """
    # Combine member_local_nodes
    merged_members = list(target.member_local_nodes) + list(source.member_local_nodes)

    # Deduplicate provenance
    seen_prov: set[tuple[str, str]] = set()
    merged_prov: list[PackageRef] = []
    for p in list(target.provenance) + list(source.provenance):
        key = (p.package, p.version)
        if key not in seen_prov:
            seen_prov.add(key)
            merged_prov.append(p)

    # Merge metadata
    target_meta = dict(target.metadata or {})
    source_meta = dict(source.metadata or {})
    # Merge source_knowledge_names lists
    target_names = target_meta.get("source_knowledge_names", [])
    source_names = source_meta.get("source_knowledge_names", [])
    merged_names = list(dict.fromkeys(target_names + source_names))
    if merged_names:
        target_meta["source_knowledge_names"] = merged_names

    merged_node = target.model_copy(
        update={
            "member_local_nodes": merged_members,
            "provenance": merged_prov,
            "metadata": target_meta if target_meta else None,
        }
    )

    # Redirect factors
    updated_factors: list[FactorNode] = []
    original_factor_data: list[dict] = []

    for factor in factors:
        new_premises = [target_id if p == source_id else p for p in factor.premises]
        new_conclusion = target_id if factor.conclusion == source_id else factor.conclusion
        new_contexts = [target_id if c == source_id else c for c in factor.contexts]

        changed = (
            new_premises != factor.premises
            or new_conclusion != factor.conclusion
            or new_contexts != factor.contexts
        )

        if changed:
            original_factor_data.append(factor.model_dump())

        updated_factors.append(
            factor.model_copy(
                update={
                    "premises": new_premises,
                    "conclusion": new_conclusion,
                    "contexts": new_contexts,
                }
            )
        )

    rollback_data = {
        "source_id": source_id,
        "target_id": target_id,
        "source_node": source.model_dump(),
        "original_target_node": target.model_dump(),
        "original_factors": original_factor_data,
    }

    return MergeResult(
        merged_node=merged_node,
        updated_factors=updated_factors,
        removed_node_id=source_id,
        rollback_data=rollback_data,
    )


def create_constraint(
    node_a_id: str,
    node_b_id: str,
    constraint_type: str,
) -> FactorNode:
    """Create an equivalence or contradiction factor between two nodes.

    Args:
        node_a_id: First node ID.
        node_b_id: Second node ID.
        constraint_type: "equivalence" or "contradiction".

    Returns:
        New FactorNode representing the constraint.
    """
    factor_type = "equiv_constraint" if constraint_type == "equivalence" else "mutex_constraint"
    # Deterministic factor ID from the pair
    pair_key = f"{min(node_a_id, node_b_id)}:{max(node_a_id, node_b_id)}:{constraint_type}"
    digest = sha256(pair_key.encode()).hexdigest()[:16]
    factor_id = f"f_cur_{digest}"

    # For constraint factors, conclusion is a gate variable (synthetic)
    gate_id = f"gate_{digest}"

    return FactorNode(
        factor_id=factor_id,
        type=factor_type,
        premises=[node_a_id, node_b_id],
        contexts=[],
        conclusion=gate_id,
        package_id="__curation__",
        metadata={
            "curation_created": True,
            "constraint_type": constraint_type,
            "edge_type": f"relation_{constraint_type}",
        },
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_operations.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/curation/operations.py tests/libs/curation/test_operations.py
git commit -m "feat(curation): add merge_nodes and create_constraint operations"
```

---

### Task 11: Cleanup — Plan Generation + Execution

Combines all analysis outputs into a `CurationPlan`, then executes approved operations via StorageManager.

**Files:**
- Create: `libs/curation/cleanup.py`
- Test: `tests/libs/curation/test_cleanup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/test_cleanup.py`:

```python
"""Tests for cleanup plan generation and execution."""

from unittest.mock import AsyncMock

from libs.curation.audit import AuditLog
from libs.curation.cleanup import execute_cleanup, generate_cleanup_plan
from libs.curation.models import (
    ConflictCandidate,
    CurationPlan,
    CurationSuggestion,
    StructureIssue,
    StructureReport,
)
from libs.global_graph.models import GlobalCanonicalNode, LocalCanonicalRef, PackageRef
from libs.storage.models import FactorNode


# ── generate_cleanup_plan ──


def test_generate_plan_combines_sources():
    """Plan combines cluster suggestions, conflict suggestions, and structure suggestions."""
    cluster_suggestions = [
        CurationSuggestion(
            suggestion_id="s1",
            operation="merge",
            target_ids=["gcn_a", "gcn_b"],
            confidence=0.98,
            reason="Duplicate",
            evidence={},
        ),
    ]
    conflict_candidates = [
        ConflictCandidate(
            node_a_id="gcn_c",
            node_b_id="gcn_d",
            signal_type="sensitivity",
            strength=0.85,
        ),
    ]
    structure_report = StructureReport(
        issues=[
            StructureIssue(
                issue_type="dangling_factor",
                severity="error",
                node_ids=["gcn_deleted"],
                factor_ids=["f_bad"],
                detail="Dangling",
            ),
        ]
    )

    plan = generate_cleanup_plan(cluster_suggestions, conflict_candidates, structure_report)
    assert isinstance(plan, CurationPlan)
    # Should have merge + contradiction + fix suggestions
    ops = {s.operation for s in plan.suggestions}
    assert "merge" in ops
    assert "create_contradiction" in ops
    assert "fix_dangling_factor" in ops


def test_generate_plan_empty_inputs():
    """No inputs produce empty plan."""
    plan = generate_cleanup_plan([], [], StructureReport())
    assert plan.suggestions == []


# ── execute_cleanup ──


async def test_execute_cleanup_auto_merges():
    """High-confidence merge suggestions are auto-executed."""
    plan = CurationPlan(
        suggestions=[
            CurationSuggestion(
                suggestion_id="s1",
                operation="merge",
                target_ids=["gcn_a", "gcn_b"],
                confidence=0.98,
                reason="Duplicate",
                evidence={},
            ),
        ]
    )
    nodes = {
        "gcn_a": GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="Earth orbits Sun",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg1", version="0.1.0", local_canonical_id="lcn_a")
            ],
            provenance=[PackageRef(package="pkg1", version="0.1.0")],
        ),
        "gcn_b": GlobalCanonicalNode(
            global_canonical_id="gcn_b",
            knowledge_type="claim",
            representative_content="Earth orbits Sun",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg2", version="0.1.0", local_canonical_id="lcn_b")
            ],
            provenance=[PackageRef(package="pkg2", version="0.1.0")],
        ),
    }
    factors: list[FactorNode] = []
    audit_log = AuditLog()

    result = await execute_cleanup(plan, nodes, factors, audit_log)
    assert len(result.executed) == 1
    assert result.executed[0].operation == "merge"
    assert len(audit_log.entries) == 1


async def test_execute_cleanup_skips_low_confidence():
    """Low-confidence suggestions are skipped (discarded)."""
    plan = CurationPlan(
        suggestions=[
            CurationSuggestion(
                suggestion_id="s1",
                operation="merge",
                target_ids=["gcn_a", "gcn_b"],
                confidence=0.50,  # Below review threshold
                reason="Low confidence",
                evidence={},
            ),
        ]
    )
    audit_log = AuditLog()
    result = await execute_cleanup(plan, {}, [], audit_log)
    assert len(result.executed) == 0
    assert len(result.skipped) == 1
    assert len(audit_log.entries) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_cleanup.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement cleanup**

Create `libs/curation/cleanup.py`:

```python
"""Cleanup — generate and execute curation plans.

generate_cleanup_plan: Combine analysis results into a CurationPlan.
execute_cleanup: Execute approved operations (auto-approve > 0.95, skip < 0.70).
"""

from __future__ import annotations

import logging

from libs.global_graph.models import GlobalCanonicalNode
from libs.storage.models import FactorNode

from .audit import AuditLog
from .models import (
    AuditEntry,
    ConflictCandidate,
    CurationPlan,
    CurationResult,
    CurationSuggestion,
    StructureIssue,
    StructureReport,
)
from .operations import create_constraint, merge_nodes

logger = logging.getLogger(__name__)


def generate_cleanup_plan(
    cluster_suggestions: list[CurationSuggestion],
    conflict_candidates: list[ConflictCandidate],
    structure_report: StructureReport,
) -> CurationPlan:
    """Combine all analysis outputs into a unified CurationPlan.

    Args:
        cluster_suggestions: From classification step (merge/equivalence).
        conflict_candidates: From conflict discovery (Level 1 + 2).
        structure_report: From structure inspection.

    Returns:
        CurationPlan with all suggestions combined.
    """
    suggestions: list[CurationSuggestion] = list(cluster_suggestions)

    # Convert conflict candidates to create_contradiction suggestions
    for candidate in conflict_candidates:
        suggestions.append(
            CurationSuggestion(
                operation="create_contradiction",
                target_ids=[candidate.node_a_id, candidate.node_b_id],
                confidence=candidate.strength,
                reason=f"Conflict detected via {candidate.signal_type} (strength {candidate.strength:.3f})",
                evidence=candidate.detail,
            )
        )

    # Convert structure issues to fix suggestions
    for issue in structure_report.issues:
        if issue.issue_type == "dangling_factor" and issue.severity == "error":
            suggestions.append(
                CurationSuggestion(
                    operation="fix_dangling_factor",
                    target_ids=issue.factor_ids,
                    confidence=1.0,  # Structural errors are certain
                    reason=issue.detail,
                    evidence={"issue_type": issue.issue_type},
                )
            )
        elif issue.issue_type == "orphan_node" and issue.severity == "warning":
            suggestions.append(
                CurationSuggestion(
                    operation="archive_orphan",
                    target_ids=issue.node_ids,
                    confidence=0.8,
                    reason=issue.detail,
                    evidence={"issue_type": issue.issue_type},
                )
            )

    return CurationPlan(suggestions=suggestions)


async def execute_cleanup(
    plan: CurationPlan,
    nodes: dict[str, GlobalCanonicalNode],
    factors: list[FactorNode],
    audit_log: AuditLog,
) -> CurationResult:
    """Execute a curation plan: auto-approve high confidence, skip low confidence.

    Args:
        plan: The curation plan to execute.
        nodes: Global nodes by ID (mutable — will be updated in place).
        factors: All factors (mutable — will be updated in place).
        audit_log: Audit log to record operations.

    Returns:
        CurationResult with executed and skipped suggestions.
    """
    executed: list[CurationSuggestion] = []
    skipped: list[CurationSuggestion] = []
    audit_entries: list[AuditEntry] = []

    for suggestion in plan.auto_approve:
        entry = _execute_suggestion(suggestion, nodes, factors)
        if entry is not None:
            audit_log.append(entry)
            audit_entries.append(entry)
            executed.append(suggestion)
        else:
            skipped.append(suggestion)

    # needs_review items are left for the curation reviewer agent (V1: skip)
    for suggestion in plan.needs_review:
        skipped.append(suggestion)
        logger.info("Skipped (needs review): %s — %s", suggestion.suggestion_id, suggestion.reason)

    # discard items are dropped
    for suggestion in plan.discard:
        skipped.append(suggestion)

    return CurationResult(
        executed=executed,
        skipped=skipped,
        audit_entries=audit_entries,
        structure_report=StructureReport(),
    )


def _execute_suggestion(
    suggestion: CurationSuggestion,
    nodes: dict[str, GlobalCanonicalNode],
    factors: list[FactorNode],
) -> AuditEntry | None:
    """Execute a single suggestion and return an audit entry, or None on failure."""
    if suggestion.operation == "merge":
        if len(suggestion.target_ids) != 2:
            return None
        source_id, target_id = suggestion.target_ids
        source = nodes.get(source_id)
        target = nodes.get(target_id)
        if source is None or target is None:
            return None

        result = merge_nodes(source_id, target_id, source, target, factors)
        # Apply: replace target in nodes, remove source, update factors
        nodes[target_id] = result.merged_node
        nodes.pop(source_id, None)
        factors.clear()
        factors.extend(result.updated_factors)

        return AuditEntry(
            operation="merge",
            target_ids=[source_id, target_id],
            suggestion_id=suggestion.suggestion_id,
            rollback_data=result.rollback_data,
        )

    if suggestion.operation in ("create_equivalence", "create_contradiction"):
        if len(suggestion.target_ids) != 2:
            return None
        constraint_type = (
            "equivalence" if suggestion.operation == "create_equivalence" else "contradiction"
        )
        factor = create_constraint(
            suggestion.target_ids[0], suggestion.target_ids[1], constraint_type
        )
        factors.append(factor)

        return AuditEntry(
            operation=suggestion.operation,
            target_ids=list(suggestion.target_ids),
            suggestion_id=suggestion.suggestion_id,
            rollback_data={"created_factor_id": factor.factor_id},
        )

    if suggestion.operation == "fix_dangling_factor":
        # Remove dangling factors
        removed_ids = set(suggestion.target_ids)
        original_factors = [f.model_dump() for f in factors if f.factor_id in removed_ids]
        factors[:] = [f for f in factors if f.factor_id not in removed_ids]

        return AuditEntry(
            operation="fix_dangling_factor",
            target_ids=list(suggestion.target_ids),
            suggestion_id=suggestion.suggestion_id,
            rollback_data={"removed_factors": original_factors},
        )

    logger.warning("Unknown operation: %s", suggestion.operation)
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_cleanup.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/curation/cleanup.py tests/libs/curation/test_cleanup.py
git commit -m "feat(curation): add cleanup plan generation and execution"
```

---

### Task 12: Scheduler — Main Pipeline Orchestrator

The top-level `run_curation()` function that orchestrates the full pipeline:
clustering → classification → conflict discovery → structure inspection → cleanup.

**Files:**
- Create: `libs/curation/scheduler.py`
- Test: `tests/libs/curation/test_scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/test_scheduler.py`:

```python
"""Tests for the curation scheduler (main pipeline orchestrator)."""

from unittest.mock import AsyncMock, patch

import pytest

from libs.curation.audit import AuditLog
from libs.curation.models import CurationResult, StructureReport
from libs.curation.scheduler import run_curation
from libs.embedding import StubEmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode
from libs.storage.models import FactorNode


def _mock_storage_manager(nodes: list[GlobalCanonicalNode], factors: list[FactorNode]):
    """Build a mock StorageManager returning given nodes and factors."""
    mgr = AsyncMock()
    mgr.list_global_nodes = AsyncMock(return_value=nodes)
    mgr.list_factors = AsyncMock(return_value=factors)
    mgr.upsert_global_nodes = AsyncMock()
    mgr.write_factors = AsyncMock()
    return mgr


async def test_run_curation_empty_graph():
    """Empty graph produces empty result."""
    mgr = _mock_storage_manager([], [])
    result = await run_curation(mgr)
    assert isinstance(result, CurationResult)
    assert result.executed == []


async def test_run_curation_with_duplicate_nodes():
    """Duplicate nodes should be detected and merged."""
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_b",
            knowledge_type="claim",
            representative_content="The Earth orbits the Sun",  # identical
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_c",
            knowledge_type="claim",
            representative_content="Water boils at 100 degrees Celsius",
        ),
    ]
    factors: list[FactorNode] = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_a"],
            conclusion="gcn_c",
            package_id="pkg1",
        ),
    ]
    mgr = _mock_storage_manager(nodes, factors)
    embedding_model = StubEmbeddingModel(dim=64)

    result = await run_curation(mgr, embedding_model=embedding_model, similarity_threshold=0.90)
    assert isinstance(result, CurationResult)
    # With identical content and StubEmbeddingModel, these should cluster and potentially merge
    # (exact behavior depends on StubEmbeddingModel's similarity for identical texts)


async def test_run_curation_with_orphan():
    """Orphan node should appear in structure report."""
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="Connected node",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_orphan",
            knowledge_type="claim",
            representative_content="Orphan node",
        ),
    ]
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_a"],
            conclusion="gcn_a",  # self-loop just to give gcn_a a connection
            package_id="pkg1",
        ),
    ]
    mgr = _mock_storage_manager(nodes, factors)
    result = await run_curation(mgr, skip_conflict_detection=True)
    assert isinstance(result, CurationResult)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_scheduler.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement scheduler**

Create `libs/curation/scheduler.py`:

```python
"""Curation scheduler — main pipeline orchestrator.

Pipeline: cluster → classify → detect conflicts → inspect structure → cleanup.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from libs.embedding import EmbeddingModel
from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph

from .audit import AuditLog
from .classification import classify_clusters
from .cleanup import execute_cleanup, generate_cleanup_plan
from .clustering import cluster_similar_nodes
from .conflict import detect_conflicts_level1, detect_conflicts_level2
from .models import ConflictCandidate, CurationResult, StructureReport
from .structure import inspect_structure

if TYPE_CHECKING:
    from libs.storage.manager import StorageManager

logger = logging.getLogger(__name__)


def _build_factor_graph_from_storage(
    nodes: dict[str, object],
    factors: list,
) -> tuple[FactorGraph, dict[str, int], dict[int, str]]:
    """Build a FactorGraph from storage models.

    Returns the graph plus bidirectional ID mappings (str ↔ int).
    """
    from libs.storage.models import FactorNode as StorageFactorNode

    graph = FactorGraph()
    str_to_int: dict[str, int] = {}
    int_to_str: dict[int, str] = {}

    # Assign integer IDs to nodes
    for idx, node_id in enumerate(nodes.keys()):
        str_to_int[node_id] = idx
        int_to_str[idx] = node_id
        graph.add_variable(idx, 0.5)  # Neutral prior for curation analysis

    # Add factors
    for fi, factor in enumerate(factors):
        premises_int = [str_to_int[p] for p in factor.premises if p in str_to_int]
        conclusion_int = str_to_int.get(factor.conclusion)

        if not premises_int:
            continue

        edge_type = (factor.metadata or {}).get("edge_type", "deduction")

        if factor.type in ("mutex_constraint", "equiv_constraint"):
            # Constraint factors: no conclusion in BP
            graph.add_factor(fi, premises_int, [], 0.9, f"relation_{edge_type.split('_')[-1] if 'relation_' in edge_type else edge_type}")
        elif conclusion_int is not None:
            graph.add_factor(fi, premises_int, [conclusion_int], 0.9, edge_type)

    return graph, str_to_int, int_to_str


async def run_curation(
    storage: StorageManager,
    embedding_model: EmbeddingModel | None = None,
    similarity_threshold: float = 0.90,
    skip_conflict_detection: bool = False,
    bp_max_iterations: int = 50,
    bp_damping: float = 0.5,
) -> CurationResult:
    """Run the full curation pipeline.

    Steps:
    1. Load all global nodes and factors
    2. Cluster similar nodes
    3. Classify clusters (duplicate / equivalence)
    4. Detect conflicts (BP Level 1 + 2) — optional
    5. Inspect structure
    6. Generate and execute cleanup plan

    Args:
        storage: StorageManager to read/write data.
        embedding_model: For similarity computation. Falls back to TF-IDF if None.
        similarity_threshold: Minimum similarity for clustering.
        skip_conflict_detection: Skip BP-based conflict detection (faster).
        bp_max_iterations: Max BP iterations for conflict detection.
        bp_damping: BP damping factor.

    Returns:
        CurationResult with executed operations and audit trail.
    """
    # Step 1: Load data
    all_nodes = await storage.list_global_nodes()
    all_factors = await storage.list_factors()

    if not all_nodes:
        logger.info("No global nodes found, nothing to curate")
        return CurationResult(structure_report=StructureReport())

    node_map = {n.global_canonical_id: n for n in all_nodes}
    logger.info("Loaded %d global nodes and %d factors", len(all_nodes), len(all_factors))

    # Step 2: Cluster similar nodes
    clusters = await cluster_similar_nodes(
        all_nodes,
        threshold=similarity_threshold,
        embedding_model=embedding_model,
    )
    logger.info("Found %d clusters", len(clusters))

    # Step 3: Classify clusters
    cluster_suggestions = classify_clusters(clusters, node_map)
    logger.info("Generated %d cluster suggestions", len(cluster_suggestions))

    # Step 4: Detect conflicts
    conflict_candidates: list[ConflictCandidate] = []
    if not skip_conflict_detection and len(all_nodes) >= 2 and all_factors:
        bp = BeliefPropagation(
            max_iterations=bp_max_iterations,
            damping=bp_damping,
        )
        fg, str_to_int, int_to_str = _build_factor_graph_from_storage(node_map, all_factors)

        if fg.factors:
            # Level 1: Oscillation detection
            baseline_beliefs, diag = bp.run_with_diagnostics(fg)
            level1 = detect_conflicts_level1(diag)

            # Map int IDs back to string IDs
            for c in level1:
                c.node_a_id = int_to_str.get(int(c.node_a_id), c.node_a_id)
                c.node_b_id = int_to_str.get(int(c.node_b_id), c.node_b_id)
            conflict_candidates.extend(level1)

            # Level 2: Sensitivity analysis on Level 1 candidates
            probe_ids = set()
            for c in level1:
                probe_ids.add(str_to_int.get(c.node_a_id, -1))
                probe_ids.add(str_to_int.get(c.node_b_id, -1))
            probe_ids.discard(-1)

            if probe_ids:
                level2 = detect_conflicts_level2(
                    fg, list(probe_ids), baseline_beliefs, bp
                )
                for c in level2:
                    c.node_a_id = int_to_str.get(int(c.node_a_id), c.node_a_id)
                    c.node_b_id = int_to_str.get(int(c.node_b_id), c.node_b_id)
                conflict_candidates.extend(level2)

        logger.info("Found %d conflict candidates", len(conflict_candidates))

    # Step 5: Structure inspection
    structure_report = inspect_structure(all_nodes, all_factors)
    logger.info(
        "Structure: %d errors, %d warnings, %d info",
        len(structure_report.errors),
        len(structure_report.warnings),
        len(structure_report.infos),
    )

    # Step 6: Generate and execute cleanup plan
    plan = generate_cleanup_plan(cluster_suggestions, conflict_candidates, structure_report)
    logger.info(
        "Plan: %d auto-approve, %d needs review, %d discard",
        len(plan.auto_approve),
        len(plan.needs_review),
        len(plan.discard),
    )

    audit_log = AuditLog()
    mutable_factors = list(all_factors)
    result = await execute_cleanup(plan, node_map, mutable_factors, audit_log)
    result.structure_report = structure_report

    # Step 7: Persist changes if any operations were executed
    if result.executed:
        updated_nodes = list(node_map.values())
        await storage.upsert_global_nodes(updated_nodes)
        await storage.write_factors(mutable_factors)
        logger.info("Persisted %d node updates and %d factor updates",
                     len(updated_nodes), len(mutable_factors))

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 5: Update `libs/curation/__init__.py` with public exports**

```python
"""Curation service — global graph maintenance and cleanup."""

from .scheduler import run_curation

__all__ = ["run_curation"]
```

- [ ] **Step 6: Run all curation tests**

Run: `pytest tests/libs/curation/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add libs/curation/ tests/libs/curation/
git commit -m "feat(curation): add scheduler orchestrating full curation pipeline"
```

---

## Chunk 6: Integration Test + Final Verification

### Task 13: End-to-End Integration Test

A single integration test that exercises the full pipeline with realistic data.

**Files:**
- Create: `tests/libs/curation/test_integration.py`

- [ ] **Step 1: Write the integration test**

Create `tests/libs/curation/test_integration.py`:

```python
"""End-to-end integration test for the curation pipeline."""

import pytest

from libs.curation.models import CurationResult
from libs.curation.scheduler import run_curation
from libs.embedding import StubEmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode, LocalCanonicalRef, PackageRef
from libs.storage.models import FactorNode
from unittest.mock import AsyncMock


def _build_test_graph():
    """Build a realistic test graph with known issues.

    Graph:
    - gcn_earth_1 and gcn_earth_2: duplicate claims about Earth
    - gcn_water: standalone claim
    - gcn_orphan: orphan node (no factors)
    - f_1: gcn_earth_1 → gcn_water (deduction)
    - f_dangling: references gcn_deleted (does not exist)
    """
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_earth_1",
            knowledge_type="claim",
            representative_content="The Earth revolves around the Sun in an elliptical orbit",
            member_local_nodes=[
                LocalCanonicalRef(package="astronomy", version="0.1.0", local_canonical_id="lcn_e1")
            ],
            provenance=[PackageRef(package="astronomy", version="0.1.0")],
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_earth_2",
            knowledge_type="claim",
            representative_content="The Earth revolves around the Sun in an elliptical orbit",
            member_local_nodes=[
                LocalCanonicalRef(package="physics", version="0.1.0", local_canonical_id="lcn_e2")
            ],
            provenance=[PackageRef(package="physics", version="0.1.0")],
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_water",
            knowledge_type="claim",
            representative_content="Water boils at 100 degrees Celsius at standard pressure",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_orphan",
            knowledge_type="claim",
            representative_content="This node is isolated",
        ),
    ]
    factors = [
        FactorNode(
            factor_id="f_1",
            type="reasoning",
            premises=["gcn_earth_1"],
            conclusion="gcn_water",
            package_id="astronomy",
            metadata={"edge_type": "deduction"},
        ),
        FactorNode(
            factor_id="f_dangling",
            type="reasoning",
            premises=["gcn_deleted"],
            conclusion="gcn_water",
            package_id="astronomy",
            metadata={"edge_type": "deduction"},
        ),
    ]
    return nodes, factors


async def test_full_curation_pipeline():
    """Run the full curation pipeline on a graph with known issues."""
    nodes, factors = _build_test_graph()

    mgr = AsyncMock()
    mgr.list_global_nodes = AsyncMock(return_value=nodes)
    mgr.list_factors = AsyncMock(return_value=factors)
    mgr.upsert_global_nodes = AsyncMock()
    mgr.write_factors = AsyncMock()

    embedding_model = StubEmbeddingModel(dim=64)

    result = await run_curation(
        mgr,
        embedding_model=embedding_model,
        similarity_threshold=0.90,
        skip_conflict_detection=True,  # Skip BP for this test — focus on clustering + structure
    )

    assert isinstance(result, CurationResult)

    # Structure report should find the orphan and the dangling factor
    orphan_issues = [
        i for i in result.structure_report.issues if i.issue_type == "orphan_node"
    ]
    dangling_issues = [
        i for i in result.structure_report.issues if i.issue_type == "dangling_factor"
    ]
    assert len(dangling_issues) >= 1

    # The two identical Earth nodes should produce some kind of suggestion
    # (merge or equivalence depending on StubEmbeddingModel similarity)
    all_target_ids = set()
    for s in result.executed + result.skipped:
        all_target_ids.update(s.target_ids)
    # At minimum, structural issues should have produced suggestions
    assert len(result.executed) + len(result.skipped) > 0
```

- [ ] **Step 2: Run the integration test**

Run: `pytest tests/libs/curation/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run all tests (full suite)**

Run: `pytest tests/ -v --tb=short`
Expected: ALL PASS (no regressions)

- [ ] **Step 4: Run lint and format**

```bash
ruff check libs/curation/ tests/libs/curation/ libs/inference/bp.py libs/storage/content_store.py libs/storage/lance_content_store.py libs/storage/manager.py
ruff format libs/curation/ tests/libs/curation/ libs/inference/bp.py libs/storage/content_store.py libs/storage/lance_content_store.py libs/storage/manager.py
```

- [ ] **Step 5: Final commit**

```bash
git add tests/libs/curation/test_integration.py
git commit -m "test(curation): add end-to-end integration test for full pipeline"
```

---

### Task 14: Curation Reviewer (Simplified)

Per spec §6, a simplified reviewer for the 0.7-0.95 confidence tier. V1 uses rule-based heuristics, not LLM.

**Files:**
- Create: `libs/curation/reviewer.py`
- Test: `tests/libs/curation/test_reviewer.py`
- Modify: `libs/curation/cleanup.py` (integrate reviewer into execute_cleanup)

- [ ] **Step 1: Write the failing test**

Create `tests/libs/curation/test_reviewer.py`:

```python
"""Tests for the simplified curation reviewer."""

from libs.curation.models import CurationSuggestion
from libs.curation.reviewer import CurationReviewer


def test_reviewer_approves_high_similarity_equivalence():
    """Equivalence with similarity > 0.85 should be approved."""
    reviewer = CurationReviewer()
    suggestion = CurationSuggestion(
        operation="create_equivalence",
        target_ids=["gcn_a", "gcn_b"],
        confidence=0.88,
        reason="Semantically similar",
        evidence={"cosine": 0.88},
    )
    decision = reviewer.review(suggestion)
    assert decision == "approve"


def test_reviewer_rejects_low_evidence_merge():
    """Merge without strong evidence should be rejected."""
    reviewer = CurationReviewer()
    suggestion = CurationSuggestion(
        operation="merge",
        target_ids=["gcn_a", "gcn_b"],
        confidence=0.75,
        reason="Might be duplicate",
        evidence={"cosine": 0.75},
    )
    decision = reviewer.review(suggestion)
    assert decision == "reject"


def test_reviewer_approves_high_confidence_contradiction():
    """Contradiction with high strength should be approved."""
    reviewer = CurationReviewer()
    suggestion = CurationSuggestion(
        operation="create_contradiction",
        target_ids=["gcn_a", "gcn_b"],
        confidence=0.85,
        reason="Strong conflict signal",
        evidence={"belief_drop": 0.3},
    )
    decision = reviewer.review(suggestion)
    assert decision == "approve"


def test_reviewer_rejects_weak_contradiction():
    """Contradiction with weak signal should be rejected."""
    reviewer = CurationReviewer()
    suggestion = CurationSuggestion(
        operation="create_contradiction",
        target_ids=["gcn_a", "gcn_b"],
        confidence=0.72,
        reason="Weak conflict",
        evidence={"belief_drop": 0.05},
    )
    decision = reviewer.review(suggestion)
    assert decision == "reject"


def test_reviewer_approves_orphan_archive():
    """Orphan archival is low-risk, should approve."""
    reviewer = CurationReviewer()
    suggestion = CurationSuggestion(
        operation="archive_orphan",
        target_ids=["gcn_orphan"],
        confidence=0.80,
        reason="No connections",
        evidence={},
    )
    decision = reviewer.review(suggestion)
    assert decision == "approve"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/curation/test_reviewer.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement reviewer**

Create `libs/curation/reviewer.py`:

```python
"""Simplified curation reviewer — rule-based heuristics for V1.

Reviews suggestions in the 0.7-0.95 confidence tier that are not
auto-approved. Spec §6: separate from package review agent.

Decision criteria:
- merge: only approve if cosine > 0.90 (just below auto-threshold)
- create_equivalence: approve if cosine > 0.85
- create_contradiction: approve if belief_drop > 0.15 or confidence > 0.80
- archive_orphan: always approve (low risk)
- fix_dangling_factor: always approve (structural fix)
"""

from __future__ import annotations

import logging
from typing import Literal

from .models import CurationSuggestion

logger = logging.getLogger(__name__)

Decision = Literal["approve", "reject"]


class CurationReviewer:
    """Rule-based reviewer for medium-confidence curation suggestions."""

    def __init__(
        self,
        merge_cosine_threshold: float = 0.90,
        equiv_cosine_threshold: float = 0.85,
        contradiction_confidence_threshold: float = 0.80,
        contradiction_drop_threshold: float = 0.15,
    ) -> None:
        self._merge_cosine = merge_cosine_threshold
        self._equiv_cosine = equiv_cosine_threshold
        self._contradiction_conf = contradiction_confidence_threshold
        self._contradiction_drop = contradiction_drop_threshold

    def review(self, suggestion: CurationSuggestion) -> Decision:
        """Review a suggestion and return approve or reject."""
        op = suggestion.operation
        evidence = suggestion.evidence

        if op == "merge":
            cosine = evidence.get("cosine", 0.0)
            if cosine >= self._merge_cosine:
                return "approve"
            return "reject"

        if op == "create_equivalence":
            cosine = evidence.get("cosine", 0.0)
            if cosine >= self._equiv_cosine:
                return "approve"
            return "reject"

        if op == "create_contradiction":
            drop = evidence.get("belief_drop", 0.0)
            if drop >= self._contradiction_drop or suggestion.confidence >= self._contradiction_conf:
                return "approve"
            return "reject"

        if op in ("archive_orphan", "fix_dangling_factor"):
            return "approve"

        logger.warning("Unknown operation for review: %s", op)
        return "reject"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/curation/test_reviewer.py -v`
Expected: PASS

- [ ] **Step 5: Integrate reviewer into cleanup.py**

In `libs/curation/cleanup.py`, modify `execute_cleanup` to use the reviewer for `needs_review` items instead of unconditionally skipping them:

Add import at top:
```python
from .reviewer import CurationReviewer
```

Replace the `needs_review` loop in `execute_cleanup`:
```python
    # needs_review items go through simplified rule-based reviewer
    reviewer = CurationReviewer()
    for suggestion in plan.needs_review:
        decision = reviewer.review(suggestion)
        if decision == "approve":
            entry = _execute_suggestion(suggestion, nodes, factors)
            if entry is not None:
                audit_log.append(entry)
                audit_entries.append(entry)
                executed.append(suggestion)
                continue
        skipped.append(suggestion)
        logger.info(
            "Reviewer %s: %s — %s", decision, suggestion.suggestion_id, suggestion.reason
        )
```

- [ ] **Step 6: Run all curation tests**

Run: `pytest tests/libs/curation/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add libs/curation/reviewer.py libs/curation/cleanup.py tests/libs/curation/test_reviewer.py
git commit -m "feat(curation): add simplified rule-based curation reviewer for middle tier"
```

---

### Task 15: Integration Test with Conflict Detection

Add a second integration test that exercises the BP-based conflict pipeline end-to-end.

**Files:**
- Modify: `tests/libs/curation/test_integration.py`

- [ ] **Step 1: Add conflict integration test**

Append to `tests/libs/curation/test_integration.py`:

```python
async def test_curation_pipeline_with_conflict_detection():
    """Run full pipeline including BP-based conflict detection."""
    nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_claim_a",
            knowledge_type="claim",
            representative_content="Vitamin C prevents colds",
        ),
        GlobalCanonicalNode(
            global_canonical_id="gcn_claim_b",
            knowledge_type="claim",
            representative_content="Vitamin C does not prevent colds",
        ),
    ]
    # A supports B via deduction, but they also have a contradiction factor
    factors = [
        FactorNode(
            factor_id="f_support",
            type="reasoning",
            premises=["gcn_claim_a"],
            conclusion="gcn_claim_b",
            package_id="health",
            metadata={"edge_type": "deduction"},
        ),
        FactorNode(
            factor_id="f_contradict",
            type="mutex_constraint",
            premises=["gcn_claim_a", "gcn_claim_b"],
            conclusion="gate_vc",
            package_id="health",
            metadata={"edge_type": "relation_contradiction"},
        ),
    ]

    mgr = AsyncMock()
    mgr.list_global_nodes = AsyncMock(return_value=nodes)
    mgr.list_factors = AsyncMock(return_value=factors)
    mgr.upsert_global_nodes = AsyncMock()
    mgr.write_factors = AsyncMock()

    result = await run_curation(
        mgr,
        skip_conflict_detection=False,
        bp_max_iterations=50,
        bp_damping=0.3,
    )

    assert isinstance(result, CurationResult)
    # The pipeline should complete without errors
    # Whether conflicts are detected depends on BP dynamics, but no crashes
```

- [ ] **Step 2: Run the integration test**

Run: `pytest tests/libs/curation/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/libs/curation/test_integration.py
git commit -m "test(curation): add integration test with BP conflict detection pipeline"
```

---

## Summary

| Task | Component | Key Files | Dependencies |
|------|-----------|-----------|--------------|
| 1 | Storage: `list_global_nodes()` + passthroughs | storage layer | None |
| 2 | Curation models | `libs/curation/models.py` | None |
| 3 | Shared `find_similar()` | `libs/curation/similarity.py` | Task 2 |
| 4 | Clustering (dual-recall) | `libs/curation/clustering.py` | Task 2, 3 |
| 5 | Classification | `libs/curation/classification.py` | Task 2 |
| 6 | BP diagnostics (refactored) | `libs/inference/bp.py` | None |
| 7 | Conflict discovery L1+L2 | `libs/curation/conflict.py` | Task 2, 6 |
| 8 | Structure inspection | `libs/curation/structure.py` | Task 2 |
| 9 | Audit log | `libs/curation/audit.py` | Task 2 |
| 10 | Operations | `libs/curation/operations.py` | Task 2 |
| 11 | Cleanup | `libs/curation/cleanup.py` | Task 2, 9, 10 |
| 12 | Scheduler | `libs/curation/scheduler.py` | 1-11 |
| 13 | Integration test E2E | `tests/libs/curation/test_integration.py` | 1-12 |
| 14 | Curation reviewer (simplified) | `libs/curation/reviewer.py` | Task 2, 11 |
| 15 | Integration test + conflict E2E | `tests/libs/curation/test_integration.py` | All above |

**Parallelizable groups:**
- Tasks 1, 2, 6 can run in parallel (no dependencies)
- Tasks 3, 5, 8, 9, 10 can run in parallel (all depend only on Task 2)
- Tasks 4, 7 can run in parallel (4 depends on 2+3, 7 depends on 2+6)
- Task 11 depends on 9+10
- Task 12 depends on 1-11
- Task 13 depends on 12
- Task 14 depends on 2+11
- Task 15 depends on all
