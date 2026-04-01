# QID (Qualified Node ID) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace content-addressed `lcn_{hash}` Knowledge IDs with name-addressed QIDs (`{namespace}:{package_name}::{label}`) per the design in `docs/plans/2026-03-31-cross-package-identity-design.md`.

**Architecture:** Knowledge nodes gain a `label` field. Local IDs become QIDs composed from `LocalCanonicalGraph.(namespace, package_name)` + `Knowledge.label`. Global IDs (`gcn_*`) are unchanged. Strategy/Operator hash-based IDs are unchanged but their Knowledge references switch from `lcn_*` to QIDs.

**Tech Stack:** Python 3.12, Pydantic v2, pytest

**Scope:** `gaia/gaia_ir/` and `tests/gaia_ir/` only. The `libs/graph_ir/` build pipeline is a separate follow-up.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `gaia/gaia_ir/knowledge.py` | Modify | Add `label`, remove `package_id`, add `make_qid()`, remove `_compute_knowledge_id()` |
| `gaia/gaia_ir/graphs.py` | Modify | Add `namespace`, `package_name` to `LocalCanonicalGraph` |
| `gaia/gaia_ir/formalize.py` | Modify | Accept `namespace`+`package_name`, generate QID-based IDs for intermediates |
| `gaia/gaia_ir/validator.py` | Modify | Replace `lcn_` prefix checks with QID format validation, add label uniqueness |
| `gaia/gaia_ir/__init__.py` | Modify | Export `make_qid` |
| `tests/gaia_ir/test_knowledge.py` | Modify | Update all tests for QID identity |
| `tests/gaia_ir/test_graphs.py` | Modify | Update fixtures to use QID, test namespace/package_name |
| `tests/gaia_ir/test_formalize.py` | Modify | Update for QID-based generated IDs |
| `tests/gaia_ir/test_strategy.py` | Modify | Replace `lcn_*` fixtures with QIDs |
| `tests/gaia_ir/test_validator.py` | Modify | Replace 188 `lcn_*` refs, update prefix assertions to QID format |
| `tests/gaia_ir/test_binding.py` | Modify | Replace 3 `lcn_*` refs |
| `tests/gaia_ir/test_operator.py` | No change | No `lcn_` refs (uses plain strings like `"a"`, `"b"`) |

---

## Conventions

**QID format:** `{namespace}:{package_name}::{label}`
- Regex: `^[a-z][a-z0-9_]*:[a-z][a-z0-9_\-]*::[a-z][a-z0-9_]*$`
- Example: `reg:galileo_falling_bodies::vacuum_prediction`

**Generated label format:** `__{role}_{hash8}` (double underscore prefix signals auto-generated)
- Example: `reg:my_pkg::__conjunction_result_a1b2c3d4`

**Test default:** All test QIDs use namespace=`reg`, package_name=`test`
- `"lcn_a"` → `"reg:test::a"`, `"lcn_b"` → `"reg:test::b"`, etc.

**Global IDs:** Unchanged — `gcn_*` prefix, no QID.

---

## Chunk 1: Core Model Changes

### Task 1: Knowledge model — add `label`, `make_qid()`, remove `package_id`

**Files:**
- Modify: `gaia/gaia_ir/knowledge.py`
- Test: `tests/gaia_ir/test_knowledge.py`

- [ ] **Step 1: Write failing tests for the new QID identity model**

Replace the entire test file. Key behavioral changes:
- `Knowledge(label="x", type="claim", content="...")` is valid (id assigned later by graph)
- `Knowledge(id="reg:pkg::x", type="claim", content="...", label="x")` is valid (explicit QID)
- `Knowledge(id="gcn_abc", type="claim")` still works (global layer unchanged)
- `package_id` field no longer exists
- `make_qid("reg", "pkg", "label")` → `"reg:pkg::label"`
- Content hash unchanged: `SHA-256(type + content + sorted(params))`

```python
# tests/gaia_ir/test_knowledge.py
"""Tests for Knowledge data model."""

import pytest
from gaia.gaia_ir import Knowledge, KnowledgeType, Parameter, LocalCanonicalRef, PackageRef
from gaia.gaia_ir.knowledge import make_qid


class TestMakeQid:
    def test_basic(self):
        assert make_qid("reg", "my_pkg", "my_label") == "reg:my_pkg::my_label"

    def test_paper_namespace(self):
        assert make_qid("paper", "10.1038_abc", "cmb_spectrum") == "paper:10.1038_abc::cmb_spectrum"


class TestKnowledgeType:
    def test_three_types(self):
        assert set(KnowledgeType) == {"claim", "setting", "question"}

    def test_no_template(self):
        with pytest.raises(ValueError):
            KnowledgeType("template")


class TestKnowledgeCreation:
    def test_explicit_qid(self):
        k = Knowledge(id="reg:pkg::x", type=KnowledgeType.CLAIM, content="test", label="x")
        assert k.id == "reg:pkg::x"
        assert k.label == "x"

    def test_explicit_global_id(self):
        k = Knowledge(id="gcn_abc123", type=KnowledgeType.CLAIM)
        assert k.id == "gcn_abc123"

    def test_label_only_defers_id(self):
        """Knowledge with label but no id — id assigned later by graph."""
        k = Knowledge(label="x", type=KnowledgeType.CLAIM, content="test")
        assert k.id is None
        assert k.label == "x"

    def test_no_id_no_label_raises(self):
        with pytest.raises(ValueError, match="id.*label"):
            Knowledge(type=KnowledgeType.CLAIM, content="test")

    def test_content_hash_auto_computed(self):
        k = Knowledge(id="reg:pkg::x", type="claim", content="test", label="x")
        assert k.content_hash is not None
        assert len(k.content_hash) == 64

    def test_same_content_same_hash(self):
        k1 = Knowledge(id="reg:pkg_a::x", type="claim", content="test", label="x")
        k2 = Knowledge(id="reg:pkg_b::y", type="claim", content="test", label="y")
        assert k1.content_hash == k2.content_hash

    def test_explicit_wrong_content_hash_rejected(self):
        with pytest.raises(ValueError, match="content_hash"):
            Knowledge(
                id="reg:pkg::x", type="claim", content="test", label="x",
                content_hash="0" * 64,
            )

    def test_different_content_different_hash(self):
        k1 = Knowledge(id="reg:pkg::a", type="claim", content="A", label="a")
        k2 = Knowledge(id="reg:pkg::b", type="claim", content="B", label="b")
        assert k1.content_hash != k2.content_hash

    def test_different_type_different_hash(self):
        k1 = Knowledge(id="reg:pkg::a", type="claim", content="X", label="a")
        k2 = Knowledge(id="reg:pkg::b", type="setting", content="X", label="b")
        assert k1.content_hash != k2.content_hash


class TestKnowledgeParameters:
    def test_closed_claim_empty_params(self):
        k = Knowledge(id="gcn_1", type="claim", parameters=[])
        assert k.parameters == []

    def test_universal_claim_with_params(self):
        k = Knowledge(
            id="gcn_2", type="claim",
            parameters=[Parameter(name="x", type="material")],
        )
        assert len(k.parameters) == 1

    def test_params_affect_content_hash(self):
        k1 = Knowledge(id="reg:pkg::a", type="claim", content="P({x})", label="a")
        k2 = Knowledge(
            id="reg:pkg::b", type="claim", content="P({x})", label="b",
            parameters=[Parameter(name="x", type="T")],
        )
        assert k1.content_hash != k2.content_hash


class TestKnowledgeLocalGlobal:
    def test_local_with_qid(self):
        k = Knowledge(
            id="reg:pkg::vacuum_prediction", type="claim",
            content="In vacuum all bodies fall equally fast",
            label="vacuum_prediction",
            provenance=[PackageRef(package_id="pkg", version="1.0")],
        )
        assert k.id == "reg:pkg::vacuum_prediction"
        assert k.label == "vacuum_prediction"
        assert k.representative_lcn is None

    def test_global_knowledge(self):
        k = Knowledge(
            id="gcn_abc123", type="claim",
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="reg:pkg::x", package_id="pkg", version="1.0",
            ),
        )
        assert k.content is None
        assert k.representative_lcn.local_canonical_id == "reg:pkg::x"

    def test_global_with_explicit_content_hash(self):
        k = Knowledge(id="gcn_abc123", type="claim", content_hash="abcd1234" * 8)
        assert k.content_hash == "abcd1234" * 8

    def test_global_with_direct_content(self):
        k = Knowledge(id="gcn_direct", type="claim", content="conjunction result")
        assert k.content == "conjunction result"


class TestKnowledgeMetadata:
    def test_metadata_refs(self):
        k = Knowledge(
            id="gcn_1", type="claim",
            metadata={"refs": ["gcn_2", "gcn_3"]},
        )
        assert k.metadata["refs"] == ["gcn_2", "gcn_3"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia_ir/test_knowledge.py -v`
Expected: FAIL (make_qid not defined, package_id still exists, etc.)

- [ ] **Step 3: Implement Knowledge model changes**

```python
# gaia/gaia_ir/knowledge.py
"""Knowledge — propositions in the Gaia reasoning hypergraph.

Implements docs/foundations/gaia-ir/02-gaia-ir.md §1.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator


# QID format: {namespace}:{package_name}::{label}
_QID_RE = re.compile(r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_\-]*::[a-z][a-z0-9_]*$")


def make_qid(namespace: str, package_name: str, label: str) -> str:
    """Compose a Qualified Node ID: {namespace}:{package_name}::{label}."""
    return f"{namespace}:{package_name}::{label}"


def is_qid(id_: str) -> bool:
    """Check if an ID string matches QID format."""
    return bool(_QID_RE.match(id_))


class KnowledgeType(StrEnum):
    """Knowledge types (§1.2)."""

    CLAIM = "claim"
    SETTING = "setting"
    QUESTION = "question"


class Parameter(BaseModel):
    """Quantified variable in a universal claim."""

    name: str
    type: str


class LocalCanonicalRef(BaseModel):
    """Reference to a local canonical Knowledge."""

    local_canonical_id: str
    package_id: str
    version: str


class PackageRef(BaseModel):
    """Reference to a package version."""

    package_id: str
    version: str


def _sha256_hex(data: str, length: int = 16) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:length]


def _compute_content_hash(type_: str, content: str, parameters: list[Parameter]) -> str:
    """Content fingerprint: SHA-256(type + content + sorted(parameters)), no package info.

    Same content in different packages produces the same content_hash.
    Used for canonicalization fast-path (exact match) and curation dedup.
    """
    sorted_params = sorted((p.name, p.type) for p in parameters)
    payload = f"{type_}|{content}|{sorted_params}"
    return _sha256_hex(payload, length=64)


class Knowledge(BaseModel):
    """Knowledge node — unified data class for local and global layers.

    Local layer: id is a QID ({namespace}:{package_name}::{label}), or None
    if the graph will assign it from its own namespace/package_name + this
    node's label.
    Global layer: id has gcn_ prefix, assigned by the registry.
    """

    id: str | None = None
    label: str | None = None
    type: KnowledgeType
    content: str | None = None
    content_hash: str | None = None
    parameters: list[Parameter] = []
    metadata: dict[str, Any] | None = None

    # provenance
    provenance: list[PackageRef] | None = None

    # global layer
    representative_lcn: LocalCanonicalRef | None = None
    local_members: list[LocalCanonicalRef] | None = None

    @model_validator(mode="after")
    def _compute_derived_fields(self) -> Knowledge:
        # Must have at least id or label
        if self.id is None and self.label is None:
            raise ValueError(
                "Knowledge requires either an explicit `id` or a `label` "
                "(id will be assigned by the owning graph)"
            )

        # Content hash is a derived fingerprint — auto-compute and verify
        if self.content is not None:
            expected = _compute_content_hash(self.type, self.content, self.parameters)
            if self.content_hash is not None and self.content_hash != expected:
                raise ValueError(
                    "content_hash must match the derived content fingerprint"
                )
            self.content_hash = expected

        return self
```

- [ ] **Step 4: Update `__init__.py` to export `make_qid`**

Add to imports in `gaia/gaia_ir/__init__.py`:

```python
from gaia.gaia_ir.knowledge import ..., make_qid
```

And add `"make_qid"` to `__all__`.

- [ ] **Step 5: Run knowledge tests**

Run: `pytest tests/gaia_ir/test_knowledge.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add gaia/gaia_ir/knowledge.py gaia/gaia_ir/__init__.py tests/gaia_ir/test_knowledge.py
git commit -m "feat(gaia-ir): replace content-addressed Knowledge ID with QID and label"
```

---

### Task 2: LocalCanonicalGraph — add `namespace`, `package_name`, auto-assign QIDs

**Files:**
- Modify: `gaia/gaia_ir/graphs.py`
- Test: `tests/gaia_ir/test_graphs.py`

- [ ] **Step 1: Write failing tests**

Key behaviors:
- `LocalCanonicalGraph(namespace="reg", package_name="my_pkg", knowledges=[...])` is valid
- Knowledge nodes with `label` but no `id` get QID auto-assigned from graph context
- Knowledge nodes with explicit `id` are left as-is
- `namespace` and `package_name` are required for LocalCanonicalGraph

```python
# tests/gaia_ir/test_graphs.py — key new/changed tests

def test_local_graph_requires_namespace_and_package():
    """LocalCanonicalGraph must have namespace and package_name."""
    with pytest.raises(ValidationError):
        LocalCanonicalGraph(knowledges=[])  # missing namespace, package_name


def test_local_graph_auto_assigns_qid():
    """Knowledge with label but no id gets QID from graph context."""
    k = Knowledge(label="x", type="claim", content="test")
    assert k.id is None
    g = LocalCanonicalGraph(
        namespace="reg", package_name="my_pkg",
        knowledges=[k],
    )
    assert g.knowledges[0].id == "reg:my_pkg::x"


def test_local_graph_preserves_explicit_id():
    """Knowledge with explicit id is not overwritten."""
    k = Knowledge(id="reg:other::x", type="claim", content="test", label="x")
    g = LocalCanonicalGraph(
        namespace="reg", package_name="my_pkg",
        knowledges=[k],
    )
    assert g.knowledges[0].id == "reg:other::x"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia_ir/test_graphs.py -v`
Expected: FAIL

- [ ] **Step 3: Implement LocalCanonicalGraph changes**

In `gaia/gaia_ir/graphs.py`, update `LocalCanonicalGraph`:

```python
class LocalCanonicalGraph(BaseModel):
    """Local canonical graph — single package."""

    scope: str = "local"
    namespace: str
    package_name: str
    ir_hash: str | None = None
    knowledges: list[Knowledge]
    operators: list[Operator] = []
    strategies: list[Strategy] = []

    @model_validator(mode="after")
    def _assign_qids_and_hash(self) -> LocalCanonicalGraph:
        # Auto-assign QIDs to Knowledge nodes that have label but no id
        for k in self.knowledges:
            if k.id is None and k.label is not None:
                k.id = make_qid(self.namespace, self.package_name, k.label)

        # Compute ir_hash if not set
        if self.ir_hash is None:
            canonical = _canonical_json(self.knowledges, self.operators, self.strategies)
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            self.ir_hash = f"sha256:{digest}"
        return self
```

- [ ] **Step 4: Update all test_graphs.py fixtures to use QID**

Replace all `lcn_*` IDs with QIDs (e.g. `"reg:test::a"`). All `LocalCanonicalGraph(...)` calls add `namespace="reg", package_name="test"`.

- [ ] **Step 5: Run tests**

Run: `pytest tests/gaia_ir/test_graphs.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add gaia/gaia_ir/graphs.py tests/gaia_ir/test_graphs.py
git commit -m "feat(gaia-ir): add namespace/package_name to LocalCanonicalGraph, auto-assign QIDs"
```

---

## Chunk 2: Formalization & Validation

### Task 3: formalize.py — QID-based generated intermediates

**Files:**
- Modify: `gaia/gaia_ir/formalize.py`
- Test: `tests/gaia_ir/test_formalize.py`

- [ ] **Step 1: Update `formalize_named_strategy()` signature**

Add `namespace` and `package_name` parameters. Generated intermediate Knowledge nodes get QID labels with `__` prefix:
- `_generated_claim_id()` → `make_qid(ns, pkg, f"__{role}_{hash8}")`
- `_generated_interface_claim_id()` → same pattern

The `scope` parameter is removed (local/global inferred from whether namespace/package_name are provided vs `gcn_` prefix).

Wait — global formalization also exists (`scope="global"`). For global scope, generated IDs keep `gcn_` prefix. So `scope` stays, and namespace/package_name are only needed for local scope.

- [ ] **Step 2: Write failing tests**

Update `tests/gaia_ir/test_formalize.py`:
- All `lcn_*` IDs → `"reg:test::*"` QIDs
- `formalize_named_strategy(scope="local", ...)` → add `namespace="reg", package_name="test"`
- Assert generated Knowledge IDs match QID format with `__` prefix labels
- Global scope tests (`scope="global"`) keep `gcn_*` IDs unchanged

- [ ] **Step 3: Implement formalize.py changes**

Key changes to `formalize.py`:
1. Add `namespace: str | None = None` and `package_name: str | None = None` to `formalize_named_strategy()`
2. Update `_TemplateBuilder` to accept namespace/package_name
3. Update `_generated_claim_id()` and `_generated_interface_claim_id()`:
   - Local scope: `make_qid(namespace, package_name, f"__{role}_{hash8}")`
   - Global scope: `f"gcn_{hash16}"` (unchanged)
4. Update `Strategy.formalize()` to pass through namespace/package_name

- [ ] **Step 4: Run tests**

Run: `pytest tests/gaia_ir/test_formalize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/gaia_ir/formalize.py gaia/gaia_ir/strategy.py tests/gaia_ir/test_formalize.py
git commit -m "feat(gaia-ir): formalize.py generates QID-based intermediate Knowledge IDs"
```

---

### Task 4: validator.py — QID format validation

**Files:**
- Modify: `gaia/gaia_ir/validator.py`
- Test: `tests/gaia_ir/test_validator.py`

- [ ] **Step 1: Design validation rule changes**

Current rules → New rules:
1. `_validate_knowledges()`: `prefix = "lcn_"` check → QID format check for local scope; `gcn_` for global (unchanged)
2. `_validate_scope_consistency()`: same pattern — local Knowledge/Strategy/Operator references must be QID format
3. **New rule**: label uniqueness within a LocalCanonicalGraph
4. **New rule**: QID namespace must be `reg` or `paper`
5. Strategy/Operator `lcs_`/`gcs_`/`lco_`/`gco_` prefix checks: **unchanged** (they don't use QID)

- [ ] **Step 2: Write failing tests**

Update `tests/gaia_ir/test_validator.py`:
- Replace all 188 `lcn_*` occurrences with `reg:test::*` QIDs
- All `_local_graph(...)` calls add `namespace="reg", package_name="test"`
- Update assertions checking "prefix" errors → "QID format" errors
- Add new tests:
  - `test_local_knowledge_must_have_qid_format` — non-QID local ID is rejected
  - `test_duplicate_label_rejected` — two Knowledge with same label in local graph
  - `test_invalid_namespace_rejected` — namespace not in `{reg, paper}`

- [ ] **Step 3: Implement validator changes**

In `_validate_knowledges()`:
```python
if scope == "local":
    if k.id and not is_qid(k.id):
        result.error(f"Knowledge '{k.id}': local ID must be QID format ({{ns}}:{{pkg}}::{{label}})")
```

In `_validate_scope_consistency()`:
```python
if scope == "local":
    # Knowledge IDs must be QID format
    # Strategy references (premises, conclusion) must be QID format
    # Operator references (variables, conclusion) must be QID format
```

Add `_validate_label_uniqueness()` and `_validate_namespace()`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/gaia_ir/test_validator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/gaia_ir/validator.py tests/gaia_ir/test_validator.py
git commit -m "feat(gaia-ir): validator enforces QID format for local Knowledge IDs"
```

---

## Chunk 3: Remaining Test Updates

### Task 5: Update test_strategy.py

**Files:**
- Test: `tests/gaia_ir/test_strategy.py`

- [ ] **Step 1: Replace all 19 `lcn_*` refs with QIDs**

Pattern: `"lcn_a"` → `"reg:test::a"`, etc. Also update `Strategy.formalize()` calls to pass `namespace`/`package_name` if the method signature changes.

- [ ] **Step 2: Run tests**

Run: `pytest tests/gaia_ir/test_strategy.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gaia_ir/test_strategy.py
git commit -m "test(gaia-ir): update strategy tests for QID Knowledge references"
```

---

### Task 6: Update test_binding.py

**Files:**
- Test: `tests/gaia_ir/test_binding.py`

- [ ] **Step 1: Replace 3 `lcn_*` refs with QIDs**

- [ ] **Step 2: Run tests**

Run: `pytest tests/gaia_ir/test_binding.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gaia_ir/test_binding.py
git commit -m "test(gaia-ir): update binding tests for QID Knowledge references"
```

---

### Task 7: Full test suite green check

- [ ] **Step 1: Run full gaia_ir test suite**

Run: `pytest tests/gaia_ir -v`
Expected: ALL PASS

- [ ] **Step 2: Run ruff**

Run: `ruff check gaia/gaia_ir/ tests/gaia_ir/ && ruff format --check gaia/gaia_ir/ tests/gaia_ir/`
Expected: All checks passed

- [ ] **Step 3: Final commit if any remaining fixes**

---

## Notes

### What's NOT in scope
- `libs/graph_ir/` build pipeline (separate PR — needs compiler changes to pass labels)
- `libs/storage/` storage layer (separate concern)
- Gaia Lang compiler changes (upstream of IR)
- Global canonicalization flow (gcn_ IDs unchanged)

### Breaking changes
- `Knowledge.package_id` field removed
- `_compute_knowledge_id()` function removed
- Local Knowledge IDs change format (`lcn_*` → QID)
- `LocalCanonicalGraph` now requires `namespace` and `package_name`
- `formalize_named_strategy()` gains `namespace`/`package_name` params (local scope)
- `ir_hash` values change (Knowledge IDs changed)

### Migration
No data migration needed — `gaia/gaia_ir/` is a pure model layer with no persisted state. Downstream consumers (`libs/graph_ir/`, `libs/storage/`) will adapt in follow-up PRs.
