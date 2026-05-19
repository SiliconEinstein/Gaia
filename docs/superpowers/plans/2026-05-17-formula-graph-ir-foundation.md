# Formula Graph IR Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement PR 1 from `docs/specs/2026-05-16-formula-graph-ir-design.md`: a canonical, claim-scoped `FormulaGraph` IR spine wired through formula lowering, hashing, and structural validation.

**Architecture:** Add focused IR models in `gaia.engine.ir.formula`; extend `LocalCanonicalGraph` so formula graphs are package content; build formula graphs during `lower_claim_formula` before existing Knowledge/Operator/Strategy lowering; keep BP behavior unchanged. Descriptor JSON is authoritative for formula node identity; edges are a derived traversal view and are checked by validation.

**Tech Stack:** Python 3.12, Pydantic v2 models, existing Gaia IR dataclasses/Pydantic models, pytest, existing `uv run --project .` test workflow.

---

## File Structure

- Create `gaia/engine/ir/formula.py`
  - Owns `FormulaNode`, `FormulaEdge`, `FormulaGraph`, `formula_node_id`, and edge/descriptor validation helpers.
- Modify `gaia/engine/ir/__init__.py`
  - Re-export the formula IR models and helper.
- Modify `gaia/engine/ir/graphs.py`
  - Add `formula_graphs` to `LocalCanonicalGraph`.
  - Include formula graphs in canonical JSON and `ir_hash`.
- Modify `gaia/engine/ir/validator.py`
  - Add structural formula graph validation that reports `ValidationResult` errors.
  - Update stored-hash recomputation to include formula graphs.
- Modify `gaia/engine/lang/compiler/lower_formula.py`
  - Promote canonical descriptor helpers.
  - Add `build_formula_graph`.
  - Extend `FormulaLoweringResult` with `formula_graphs`.
  - Use source-claim-scoped canonical helper ids to avoid duplicate helper claims for repeated formula atoms.
- Modify `gaia/engine/lang/compiler/compile.py`
  - Carry `formula_graphs` through `_FormulaLoweringResult`, `_ActionCompiler` decomposition lowering, and `_build_graph`.
- Create `tests/ir/test_formula_graph.py`
  - Unit tests for node ids, graph roundtrip, structural model checks, and hash participation.
- Modify `tests/ir/test_validator.py`
  - Validator-level tests for malformed formula graph references and id mismatches.
- Modify `tests/gaia/lang/test_formula_lowering.py`
  - Integration tests for repeated atoms, connectives, quantifiers, determinism, and cross-graph atom identity.

---

### Task 1: Add FormulaGraph IR Models

**Files:**
- Create: `gaia/engine/ir/formula.py`
- Modify: `gaia/engine/ir/__init__.py`
- Test: `tests/ir/test_formula_graph.py`

- [x] **Step 1: Write failing tests for formula IR models**

Create `tests/ir/test_formula_graph.py` with:

```python
"""Tests for FormulaGraph IR models."""

import pytest
from pydantic import ValidationError

from gaia.engine.ir import (
    FormulaEdge,
    FormulaGraph,
    FormulaNode,
    Knowledge,
    KnowledgeType,
    LocalCanonicalGraph,
    formula_node_id,
)


def _node(kind: str, descriptor: dict) -> FormulaNode:
    return FormulaNode(id=formula_node_id(descriptor), kind=kind, descriptor=descriptor)


def test_formula_node_id_is_stable_for_descriptor_order():
    left = {"kind": "predicate", "symbol": {"name": "P"}, "args": [{"kind": "constant", "value": 1}]}
    right = {
        "args": [{"value": 1, "kind": "constant"}],
        "symbol": {"name": "P"},
        "kind": "predicate",
    }

    assert formula_node_id(left) == formula_node_id(right)
    assert formula_node_id(left).startswith("fg:")
    assert len(formula_node_id(left)) == len("fg:") + 16


def test_formula_node_rejects_mismatched_id():
    with pytest.raises(ValidationError, match="does not match canonical descriptor hash"):
        FormulaNode(id="fg:0000000000000000", kind="atom", descriptor={"kind": "claim", "qid": "t:p::a"})


def test_formula_graph_round_trips_json():
    atom = _node("atom", {"kind": "claim", "qid": "t:p::a"})
    graph = FormulaGraph(source_claim="t:p::claim", root=atom.id, nodes=[atom])

    roundtripped = FormulaGraph.model_validate_json(graph.model_dump_json())

    assert roundtripped == graph


def test_formula_graph_rejects_dangling_edge():
    atom = _node("atom", {"kind": "claim", "qid": "t:p::a"})

    with pytest.raises(ValidationError, match="edge target 'fg:missing' not found"):
        FormulaGraph(
            source_claim="t:p::claim",
            root=atom.id,
            nodes=[atom],
            edges=[FormulaEdge(source=atom.id, target="fg:missing", role="operand")],
        )


def test_formula_graph_rejects_duplicate_id_with_different_descriptor():
    first = _node("atom", {"kind": "claim", "qid": "t:p::a"})
    second = FormulaNode.model_construct(
        id=first.id,
        kind="atom",
        descriptor={"kind": "claim", "qid": "t:p::b"},
    )

    with pytest.raises(ValidationError, match="appears with different descriptors"):
        FormulaGraph(source_claim="t:p::claim", root=first.id, nodes=[first, second])


def test_formula_graphs_participate_in_ir_hash():
    atom_a = _node("atom", {"kind": "claim", "qid": "t:p::a"})
    atom_b = _node("atom", {"kind": "claim", "qid": "t:p::b"})
    claim = Knowledge(id="t:p::claim", type=KnowledgeType.CLAIM, content="claim")

    graph_a = LocalCanonicalGraph(
        namespace="t",
        package_name="p",
        knowledges=[claim],
        formula_graphs=[FormulaGraph(source_claim="t:p::claim", root=atom_a.id, nodes=[atom_a])],
    )
    graph_b = LocalCanonicalGraph(
        namespace="t",
        package_name="p",
        knowledges=[claim],
        formula_graphs=[FormulaGraph(source_claim="t:p::claim", root=atom_b.id, nodes=[atom_b])],
    )

    assert graph_a.ir_hash != graph_b.ir_hash
```

- [x] **Step 2: Run the new test file and verify imports fail**

Run:

```bash
uv run --project . python -m pytest tests/ir/test_formula_graph.py -q
```

Expected: FAIL with `ImportError: cannot import name 'FormulaEdge'`.

- [x] **Step 3: Add the formula IR model module**

Create `gaia/engine/ir/formula.py`:

```python
"""Formula graph IR models.

FormulaGraph is a claim-scoped canonical view of a Claim.formula payload.
Descriptors are authoritative for identity and hashing; edges are a derived
traversal view for consumers.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, model_validator

FormulaNodeKind = Literal["atom", "op", "quantifier", "term", "variable", "constant"]
FormulaEdgeRole = Literal[
    "operand",
    "antecedent",
    "consequent",
    "left",
    "right",
    "bound_variable",
    "body",
    "arg",
    "function",
]


def _canonical_descriptor_json(descriptor: dict[str, Any]) -> str:
    """Return stable JSON bytes for a formula descriptor."""
    return json.dumps(descriptor, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def formula_node_id(descriptor: dict[str, Any]) -> str:
    """Return the stable formula node id for a canonical descriptor."""
    digest = hashlib.sha256(_canonical_descriptor_json(descriptor).encode()).hexdigest()[:16]
    return f"fg:{digest}"


class FormulaNode(BaseModel):
    """A formula graph node with descriptor-addressed identity."""

    id: str
    kind: FormulaNodeKind
    descriptor: dict[str, Any]

    @model_validator(mode="after")
    def _validate_id(self) -> FormulaNode:
        expected = formula_node_id(self.descriptor)
        if self.id != expected:
            raise ValueError(
                f"FormulaNode '{self.id}' does not match canonical descriptor hash '{expected}'"
            )
        return self


class FormulaEdge(BaseModel):
    """A derived traversal edge between formula nodes."""

    source: str
    target: str
    role: FormulaEdgeRole
    index: int | None = None


class FormulaGraph(BaseModel):
    """Claim-scoped formula graph anchored to a source claim QID."""

    source_claim: str
    root: str
    nodes: list[FormulaNode]
    edges: list[FormulaEdge] = []

    @model_validator(mode="after")
    def _validate_structure(self) -> FormulaGraph:
        descriptors_by_id: dict[str, dict[str, Any]] = {}
        for node in self.nodes:
            existing = descriptors_by_id.get(node.id)
            if existing is not None and existing != node.descriptor:
                raise ValueError(f"FormulaNode id '{node.id}' appears with different descriptors")
            descriptors_by_id[node.id] = node.descriptor

        if self.root not in descriptors_by_id:
            raise ValueError(f"FormulaGraph root '{self.root}' not found in nodes")

        for edge in self.edges:
            if edge.source not in descriptors_by_id:
                raise ValueError(f"FormulaGraph edge source '{edge.source}' not found in nodes")
            if edge.target not in descriptors_by_id:
                raise ValueError(f"FormulaGraph edge target '{edge.target}' not found in nodes")
        return self
```

- [x] **Step 4: Re-export the formula IR models**

Modify `gaia/engine/ir/__init__.py`:

```python
from gaia.engine.ir.formula import FormulaEdge, FormulaGraph, FormulaNode, formula_node_id
```

Add these names to `__all__`:

```python
    "FormulaEdge",  # Formula
    "FormulaGraph",  # Formula
    "FormulaNode",  # Formula
    "formula_node_id",  # Formula
```

- [x] **Step 5: Run the formula model tests**

Run:

```bash
uv run --project . python -m pytest tests/ir/test_formula_graph.py -q
```

Expected: FAIL at `LocalCanonicalGraph(..., formula_graphs=...)` because the graph model does not yet have the field.

- [x] **Step 6: Hold the model slice for the Task 2 commit**

Task 2 wires `formula_graphs` into `LocalCanonicalGraph`; commit the IR model and graph hash slices together after Task 2.

---

### Task 2: Add FormulaGraph To LocalCanonicalGraph And Hashing

**Files:**
- Modify: `gaia/engine/ir/graphs.py`
- Modify: `gaia/engine/ir/validator.py`
- Test: `tests/ir/test_formula_graph.py`

- [x] **Step 1: Update graph canonicalization tests are already failing**

The test `test_formula_graphs_participate_in_ir_hash` from Task 1 is the failing test for this task.

Run:

```bash
uv run --project . python -m pytest tests/ir/test_formula_graph.py::test_formula_graphs_participate_in_ir_hash -q
```

Expected: FAIL because `LocalCanonicalGraph` has no `formula_graphs` field or the field does not affect `ir_hash`.

- [x] **Step 2: Modify `gaia/engine/ir/graphs.py` imports**

Add:

```python
from gaia.engine.ir.formula import FormulaGraph
```

- [x] **Step 3: Add formula graph canonicalization helpers**

Add this helper after `_canonicalize_compose_dump`:

```python
def _canonicalize_formula_graph_dump(data: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(data)
    canonical["nodes"] = sorted(canonical.get("nodes", []), key=_json_sort_key)
    canonical["edges"] = sorted(canonical.get("edges", []), key=_json_sort_key)
    return canonical
```

- [x] **Step 4: Extend `_canonical_json` signature and payload**

Change the signature:

```python
def _canonical_json(
    knowledges: list[Knowledge],
    operators: list[Operator],
    strategies: list[Strategy],
    composes: list[Compose],
    formula_graphs: list[FormulaGraph] | None = None,
) -> str:
```

Add the payload key:

```python
        "formula_graphs": sorted(
            [
                _canonicalize_formula_graph_dump(graph.model_dump(mode="json"))
                for graph in (formula_graphs or [])
            ],
            key=_json_sort_key,
        ),
```

- [x] **Step 5: Add the field to `LocalCanonicalGraph` and hash call**

Add the model field:

```python
    formula_graphs: list[FormulaGraph] = []
```

Update the `_canonical_json` call in `_compute_hash`:

```python
            canonical = _canonical_json(
                self.knowledges,
                self.operators,
                self.strategies,
                self.composes,
                self.formula_graphs,
            )
```

- [x] **Step 6: Update validator hash recomputation**

In `gaia/engine/ir/validator.py`, update the `_canonical_json` call:

```python
        recomputed = _canonical_json(
            graph.knowledges,
            graph.operators,
            graph.strategies,
            graph.composes,
            graph.formula_graphs,
        )
```

- [x] **Step 7: Run the IR formula model tests**

Run:

```bash
uv run --project . python -m pytest tests/ir/test_formula_graph.py -q
```

Expected: PASS.

- [x] **Step 8: Commit Tasks 1 and 2**

Run:

```bash
git add gaia/engine/ir/formula.py gaia/engine/ir/__init__.py gaia/engine/ir/graphs.py gaia/engine/ir/validator.py tests/ir/test_formula_graph.py
git commit -m "feat(ir): add formula graph models"
```

---

### Task 3: Build FormulaGraph During Formula Lowering

**Files:**
- Modify: `gaia/engine/lang/compiler/lower_formula.py`
- Test: `tests/gaia/lang/test_formula_lowering.py`

- [x] **Step 1: Add failing formula graph integration tests**

Append these tests to `tests/gaia/lang/test_formula_lowering.py`:

```python
def _formula_graph_for(artifact, source_claim_id):
    return next(graph for graph in artifact.graph.formula_graphs if graph.source_claim == source_claim_id)


def test_repeated_predicate_formula_builds_one_canonical_atom_node():
    pkg = CollectedPackage(name="formula_repeated_predicate_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        particle = Domain(content="Particles", members=["p1"])
        x = Variable(symbol="x", domain=particle)
        stable = PredicateSymbol(name="Stable", arg_domains=(particle,))
        repeated = claim(
            "Stable(x) and Stable(x).",
            formula=land(UserPredicate(stable, (x,)), UserPredicate(stable, (x,))),
        )
        repeated.label = "repeated"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    graph = _formula_graph_for(artifact, "t:formula_repeated_predicate_pkg::repeated")
    atom_nodes = [
        node for node in graph.nodes
        if node.kind == "atom" and node.descriptor.get("kind") == "predicate"
    ]
    operand_edges = [edge for edge in graph.edges if edge.role == "operand"]

    assert len(atom_nodes) == 1
    assert len(operand_edges) == 2
    assert {edge.target for edge in operand_edges} == {atom_nodes[0].id}


def test_formula_graph_records_nested_connective_shape():
    pkg = CollectedPackage(name="formula_nested_graph_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        c = claim("C.")
        c.label = "c"
        rule = claim(
            "A and B imply C.",
            formula=implies(land(ClaimAtom(a), ClaimAtom(b)), ClaimAtom(c)),
        )
        rule.label = "rule"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    graph = _formula_graph_for(artifact, "t:formula_nested_graph_pkg::rule")
    root = next(node for node in graph.nodes if node.id == graph.root)

    assert root.kind == "op"
    assert root.descriptor["operator"] == "implication"
    assert {edge.role for edge in graph.edges if edge.source == root.id} == {
        "antecedent",
        "consequent",
    }
    antecedent_id = next(edge.target for edge in graph.edges if edge.source == root.id and edge.role == "antecedent")
    antecedent = next(node for node in graph.nodes if node.id == antecedent_id)
    assert antecedent.descriptor["operator"] == "conjunction"


def test_quantifier_formula_graph_preserves_finite_grounding_behavior():
    pkg = CollectedPackage(name="formula_quantifier_graph_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        particle = Domain(content="Particles", members=["p1", "p2"])
        x = Variable(symbol="x", domain=particle)
        stable = PredicateSymbol(name="Stable", arg_domains=(particle,))
        universal = claim(
            "Every particle is stable.",
            formula=Forall(variable=x, body=UserPredicate(stable, (x,))),
            kind=ClaimKind.QUANTIFIED,
            prior=0.9,
        )
        universal.label = "stable_all"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    graph = _formula_graph_for(artifact, "t:formula_quantifier_graph_pkg::stable_all")
    root = next(node for node in graph.nodes if node.id == graph.root)

    assert root.kind == "quantifier"
    assert root.descriptor["quantifier"] == "forall"
    assert {edge.role for edge in graph.edges if edge.source == root.id} == {
        "bound_variable",
        "body",
    }
    assert [
        s
        for s in artifact.graph.strategies
        if (s.metadata or {}).get("formula_lowering") == "forall_grounding"
    ]


def test_cross_graph_same_atom_uses_same_formula_node_id():
    pkg = CollectedPackage(name="formula_cross_graph_identity_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        particle = Domain(content="Particles", members=["p1"])
        x = Variable(symbol="x", domain=particle)
        stable = PredicateSymbol(name="Stable", arg_domains=(particle,))
        first = claim("Stable once.", formula=UserPredicate(stable, (x,)))
        first.label = "first"
        second = claim("Stable twice.", formula=UserPredicate(stable, (x,)))
        second.label = "second"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    first_graph = _formula_graph_for(artifact, "t:formula_cross_graph_identity_pkg::first")
    second_graph = _formula_graph_for(artifact, "t:formula_cross_graph_identity_pkg::second")

    first_atom = next(node for node in first_graph.nodes if node.kind == "atom")
    second_atom = next(node for node in second_graph.nodes if node.kind == "atom")
    assert first_atom.id == second_atom.id
    assert first_graph.source_claim != second_graph.source_claim
```

- [x] **Step 2: Run the new integration tests and verify they fail**

Run:

```bash
uv run --project . python -m pytest tests/gaia/lang/test_formula_lowering.py::test_repeated_predicate_formula_builds_one_canonical_atom_node tests/gaia/lang/test_formula_lowering.py::test_formula_graph_records_nested_connective_shape tests/gaia/lang/test_formula_lowering.py::test_quantifier_formula_graph_preserves_finite_grounding_behavior tests/gaia/lang/test_formula_lowering.py::test_cross_graph_same_atom_uses_same_formula_node_id -q
```

Expected: FAIL because `artifact.graph.formula_graphs` is empty.

- [x] **Step 3: Import formula IR models in `lower_formula.py`**

Add imports:

```python
from gaia.engine.ir.formula import FormulaEdge, FormulaGraph, FormulaNode, formula_node_id
```

- [x] **Step 4: Extend `FormulaLoweringResult`**

Add the field:

```python
    formula_graphs: list[FormulaGraph] = field(default_factory=list)
```

- [x] **Step 5: Rename descriptor helpers to canonical helpers**

Keep the old private names as wrappers so the patch stays small:

```python
def canonical_formula_descriptor(
    formula: Any,
    *,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None = None,
) -> dict[str, Any]:
    return _formula_descriptor(formula, knowledge_map=knowledge_map, bindings=bindings)


def canonical_term_descriptor(
    term: Any,
    *,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None = None,
) -> dict[str, Any]:
    return _term_descriptor(term, knowledge_map=knowledge_map, bindings=bindings)
```

- [x] **Step 6: Add the FormulaGraph builder**

Add this builder after `_FormulaState`:

```python
class _FormulaGraphBuilder:
    def __init__(
        self,
        *,
        source_claim_id: str,
        knowledge_map: dict[int, str],
        bindings: _BindingMap | None = None,
    ):
        self.source_claim_id = source_claim_id
        self.knowledge_map = knowledge_map
        self.bindings = bindings or {}
        self.nodes_by_id: dict[str, FormulaNode] = {}
        self.edges: list[FormulaEdge] = []

    def build(self, formula: Any) -> FormulaGraph:
        root = self.node_for_formula(formula)
        return FormulaGraph(
            source_claim=self.source_claim_id,
            root=root,
            nodes=list(self.nodes_by_id.values()),
            edges=self.edges,
        )

    def node_for_formula(self, formula: Any) -> str:
        if isinstance(formula, ClaimAtom) or _is_atomic_formula(formula):
            return self._atom_node(formula)
        operator_name, children = _connective_operator(formula)
        if operator_name is not None:
            child_ids = [self.node_for_formula(child) for child in children]
            descriptor: dict[str, Any] = {
                "kind": "op",
                "operator": str(operator_name),
                "children": child_ids,
            }
            node_id = self._add_node("op", descriptor)
            self._add_connective_edges(node_id, str(operator_name), child_ids)
            return node_id
        if isinstance(formula, Forall):
            return self._quantifier_node("forall", formula.variable, formula.body)
        if isinstance(formula, Exists):
            return self._quantifier_node("exists", formula.variable, formula.body)
        raise NotImplementedError(f"Unsupported formula graph: {type(formula).__name__}")

    def node_for_term(self, term: Any) -> str:
        descriptor = canonical_term_descriptor(
            term,
            knowledge_map=self.knowledge_map,
            bindings=self.bindings,
        )
        kind = descriptor.get("kind")
        if kind == "variable":
            node_kind = "variable"
        elif kind == "constant":
            node_kind = "constant"
        else:
            node_kind = "term"
        node_id = self._add_node(node_kind, descriptor)
        if isinstance(term, FunctionApp):
            for index, arg in enumerate(term.args):
                self.edges.append(
                    FormulaEdge(
                        source=node_id,
                        target=self.node_for_term(arg),
                        role="arg",
                        index=index,
                    )
                )
        if isinstance(term, ArithOp):
            self.edges.append(
                FormulaEdge(source=node_id, target=self.node_for_term(term.left), role="left")
            )
            self.edges.append(
                FormulaEdge(source=node_id, target=self.node_for_term(term.right), role="right")
            )
        return node_id

    def _atom_node(self, formula: Any) -> str:
        descriptor = canonical_formula_descriptor(
            formula,
            knowledge_map=self.knowledge_map,
            bindings=self.bindings,
        )
        node_id = self._add_node("atom", descriptor)
        if isinstance(formula, UserPredicate):
            for index, arg in enumerate(formula.args):
                self.edges.append(
                    FormulaEdge(
                        source=node_id,
                        target=self.node_for_term(arg),
                        role="arg",
                        index=index,
                    )
                )
        for role, term in _binary_formula_terms(formula):
            self.edges.append(
                FormulaEdge(source=node_id, target=self.node_for_term(term), role=role)
            )
        return node_id

    def _quantifier_node(self, quantifier: str, variable: Variable, body: Any) -> str:
        variable_id = self.node_for_term(variable)
        body_id = self.node_for_formula(body)
        descriptor = {
            "kind": "quantifier",
            "quantifier": quantifier,
            "variable": variable_id,
            "domain": _domain_name(variable.domain),
            "body": body_id,
        }
        node_id = self._add_node("quantifier", descriptor)
        self.edges.append(FormulaEdge(source=node_id, target=variable_id, role="bound_variable"))
        self.edges.append(FormulaEdge(source=node_id, target=body_id, role="body"))
        return node_id

    def _add_connective_edges(self, node_id: str, operator_name: str, child_ids: list[str]) -> None:
        if operator_name == str(OperatorType.IMPLICATION):
            self.edges.append(FormulaEdge(source=node_id, target=child_ids[0], role="antecedent"))
            self.edges.append(FormulaEdge(source=node_id, target=child_ids[1], role="consequent"))
            return
        if operator_name == str(OperatorType.EQUIVALENCE):
            self.edges.append(FormulaEdge(source=node_id, target=child_ids[0], role="left"))
            self.edges.append(FormulaEdge(source=node_id, target=child_ids[1], role="right"))
            return
        for index, child_id in enumerate(child_ids):
            self.edges.append(
                FormulaEdge(source=node_id, target=child_id, role="operand", index=index)
            )

    def _add_node(self, kind: str, descriptor: dict[str, Any]) -> str:
        node_id = formula_node_id(descriptor)
        existing = self.nodes_by_id.get(node_id)
        if existing is None:
            self.nodes_by_id[node_id] = FormulaNode(id=node_id, kind=kind, descriptor=descriptor)
        elif existing.descriptor != descriptor or existing.kind != kind:
            raise ValueError(f"formula node id collision for {node_id}")
        return node_id
```

- [x] **Step 7: Add binary formula term helper**

Add:

```python
def _binary_formula_terms(formula: Any) -> list[tuple[str, Any]]:
    if isinstance(
        formula,
        (
            Equals,
            Greater,
            GreaterEqual,
            Less,
            LessEqual,
            NotEquals,
        ),
    ):
        return [("left", formula.left), ("right", formula.right)]
    return []
```

- [x] **Step 8: Add public builder function**

Add:

```python
def build_formula_graph(
    formula: Any,
    *,
    source_claim_id: str,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None = None,
) -> FormulaGraph:
    """Build a canonical FormulaGraph for a source claim formula."""
    return _FormulaGraphBuilder(
        source_claim_id=source_claim_id,
        knowledge_map=knowledge_map,
        bindings=bindings,
    ).build(formula)
```

- [x] **Step 9: Refactor `lower_claim_formula` so every formula-bearing source emits a graph**

Replace the multiple early returns with this shape:

```python
def lower_claim_formula(
    claim: Claim,
    *,
    claim_id: str,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
) -> FormulaLoweringResult:
    """Lower the formula attached to a Claim, if Milestone B supports it."""
    formula = getattr(claim, "formula", None)
    if formula is None:
        return FormulaLoweringResult()

    formula_graph = build_formula_graph(
        formula,
        source_claim_id=claim_id,
        knowledge_map=knowledge_map,
    )

    if isinstance(formula, Forall):
        result = _lower_forall(
            claim,
            formula,
            claim_id=claim_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
        )
    elif isinstance(formula, Exists):
        result = _lower_exists(
            claim,
            formula,
            claim_id=claim_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
        )
    else:
        operator_name, _ = _connective_operator(formula)
        if operator_name is None and not _is_atomic_formula(formula):
            raise NotImplementedError(f"Unsupported formula lowering: {type(formula).__name__}")
        result = _lower_formula_to_claim(
            formula,
            target_id=claim_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
        )

    return FormulaLoweringResult(
        knowledges=result.knowledges,
        operators=result.operators,
        strategies=result.strategies,
        formula_graphs=[formula_graph],
        metadata_updates=result.metadata_updates,
        parameter_updates=result.parameter_updates,
    )
```

- [x] **Step 10: Run the four formula graph integration tests before compiler wiring**

Run:

```bash
uv run --project . python -m pytest tests/gaia/lang/test_formula_lowering.py::test_repeated_predicate_formula_builds_one_canonical_atom_node tests/gaia/lang/test_formula_lowering.py::test_formula_graph_records_nested_connective_shape tests/gaia/lang/test_formula_lowering.py::test_quantifier_formula_graph_preserves_finite_grounding_behavior tests/gaia/lang/test_formula_lowering.py::test_cross_graph_same_atom_uses_same_formula_node_id -q
```

Expected: FAIL because the compiler does not yet carry `FormulaLoweringResult.formula_graphs` into `LocalCanonicalGraph`.

Task 4 wires the compiler.

---

### Task 4: Wire FormulaGraphs Through Package Compilation

**Files:**
- Modify: `gaia/engine/lang/compiler/compile.py`
- Test: `tests/gaia/lang/test_formula_lowering.py`

- [x] **Step 1: Import `FormulaGraph`**

In `gaia/engine/lang/compiler/compile.py`, add:

```python
from gaia.engine.ir.formula import FormulaGraph
```

- [x] **Step 2: Extend the compiler-side formula result carrier**

Change `_FormulaLoweringResult`:

```python
@dataclass
class _FormulaLoweringResult:
    """Formula-lowering artifacts emitted after action lowering."""

    knowledges: list[IrKnowledge]
    operators: list[IrOperator]
    strategies: list[IrStrategy]
    formula_graphs: list[FormulaGraph]
```

Update its initialization in `_lower_formula_claims`:

```python
    result = _FormulaLoweringResult(
        knowledges=[],
        operators=[],
        strategies=[],
        formula_graphs=[],
    )
```

After `result.strategies.extend(lowered.strategies)`, add:

```python
        result.formula_graphs.extend(lowered.formula_graphs)
```

- [x] **Step 3: Preserve decomposition formula graphs**

Add a field to `_ActionCompiler`:

```python
    formula_graphs: list[FormulaGraph] = field(default_factory=list)
```

In `_emit_decomposition_formula`, after `self.generated_knowledges.extend(lowered.knowledges)`, add:

```python
        self.formula_graphs.extend(lowered.formula_graphs)
```

- [x] **Step 4: Extend `_build_graph`**

Add a parameter:

```python
    action_formula_graphs: list[FormulaGraph],
```

Pass the formula graphs to `LocalCanonicalGraph`:

```python
        formula_graphs=[
            *formula_generated.formula_graphs,
            *action_formula_graphs,
        ],
```

Update the call site in `compile_package_artifact`:

```python
        action_formula_graphs=action_compiler.formula_graphs,
```

- [x] **Step 5: Run the formula graph integration tests**

Run:

```bash
uv run --project . python -m pytest tests/gaia/lang/test_formula_lowering.py::test_repeated_predicate_formula_builds_one_canonical_atom_node tests/gaia/lang/test_formula_lowering.py::test_formula_graph_records_nested_connective_shape tests/gaia/lang/test_formula_lowering.py::test_quantifier_formula_graph_preserves_finite_grounding_behavior tests/gaia/lang/test_formula_lowering.py::test_cross_graph_same_atom_uses_same_formula_node_id -q
```

Expected: PASS.

- [x] **Step 6: Commit Tasks 3 and 4**

Run:

```bash
git add gaia/engine/lang/compiler/lower_formula.py gaia/engine/lang/compiler/compile.py tests/gaia/lang/test_formula_lowering.py
git commit -m "feat(lang): emit formula graphs during lowering"
```

---

### Task 5: Add Structural FormulaGraph Validation

**Files:**
- Modify: `gaia/engine/ir/validator.py`
- Test: `tests/ir/test_validator.py`

- [x] **Step 1: Add validator tests using constructed malformed graphs**

Add imports in `tests/ir/test_validator.py`:

```python
from gaia.engine.ir import FormulaGraph, FormulaNode, formula_node_id
```

Add helpers near `_local_graph`:

```python
def _formula_node(kind: str, descriptor: dict) -> FormulaNode:
    return FormulaNode(id=formula_node_id(descriptor), kind=kind, descriptor=descriptor)
```

Add tests:

```python
class TestFormulaGraphValidation:
    def test_formula_graph_source_claim_must_exist(self):
        atom = _formula_node("atom", {"kind": "claim", "qid": "github:test::a"})
        formula_graph = FormulaGraph(
            source_claim="github:test::missing",
            root=atom.id,
            nodes=[atom],
        )
        g = _local_graph(knowledges=[_claim("github:test::a")], formula_graphs=[formula_graph])

        r = validate_local_graph(g)

        assert not r.valid
        assert any("FormulaGraph source_claim 'github:test::missing' not found" in e for e in r.errors)

    def test_formula_graph_source_claim_must_be_claim(self):
        atom = _formula_node("atom", {"kind": "claim", "qid": "github:test::a"})
        formula_graph = FormulaGraph(
            source_claim="github:test::setting",
            root=atom.id,
            nodes=[atom],
        )
        g = _local_graph(
            knowledges=[_claim("github:test::a"), _setting("github:test::setting")],
            formula_graphs=[formula_graph],
        )

        r = validate_local_graph(g)

        assert not r.valid
        assert any("FormulaGraph source_claim 'github:test::setting' must reference a claim" in e for e in r.errors)

    def test_formula_graph_descriptor_claim_qid_must_exist(self):
        atom = _formula_node("atom", {"kind": "claim", "qid": "github:test::missing"})
        formula_graph = FormulaGraph(
            source_claim="github:test::source",
            root=atom.id,
            nodes=[atom],
        )
        g = _local_graph(knowledges=[_claim("github:test::source")], formula_graphs=[formula_graph])

        r = validate_local_graph(g)

        assert not r.valid
        assert any("FormulaNode" in e and "references missing claim 'github:test::missing'" in e for e in r.errors)

    def test_formula_graph_node_id_mismatch_is_reported(self):
        bad = FormulaNode.model_construct(
            id="fg:0000000000000000",
            kind="atom",
            descriptor={"kind": "claim", "qid": "github:test::a"},
        )
        formula_graph = FormulaGraph.model_construct(
            source_claim="github:test::source",
            root=bad.id,
            nodes=[bad],
            edges=[],
        )
        g = _local_graph(
            knowledges=[_claim("github:test::source"), _claim("github:test::a")],
            formula_graphs=[formula_graph],
        )

        r = validate_local_graph(g)

        assert not r.valid
        assert any("does not match canonical descriptor hash" in e for e in r.errors)
```

- [x] **Step 2: Run the new validator tests and verify failure**

Run:

```bash
uv run --project . python -m pytest tests/ir/test_validator.py::TestFormulaGraphValidation -q
```

Expected: FAIL because `validate_local_graph` does not inspect `formula_graphs`.

- [x] **Step 3: Add formula graph validation helpers**

In `gaia/engine/ir/validator.py`, import:

```python
from gaia.engine.ir.formula import FormulaGraph, FormulaNode, formula_node_id
```

Add these helpers before the Public API section:

```python
def _descriptor_claim_refs(descriptor: object) -> list[str]:
    refs: list[str] = []
    if isinstance(descriptor, dict):
        if descriptor.get("kind") == "claim" and isinstance(descriptor.get("qid"), str):
            refs.append(descriptor["qid"])
        for value in descriptor.values():
            refs.extend(_descriptor_claim_refs(value))
    elif isinstance(descriptor, list):
        for value in descriptor:
            refs.extend(_descriptor_claim_refs(value))
    return refs


def _validate_formula_node(
    graph: FormulaGraph,
    node: FormulaNode,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    expected = formula_node_id(node.descriptor)
    if node.id != expected:
        result.error(
            f"FormulaNode '{node.id}' in FormulaGraph '{graph.source_claim}' "
            f"does not match canonical descriptor hash '{expected}'"
        )
    for ref in _descriptor_claim_refs(node.descriptor):
        if ref not in knowledge_lookup:
            result.error(f"FormulaNode '{node.id}' references missing claim '{ref}'")
        elif knowledge_lookup[ref].type != KnowledgeType.CLAIM:
            result.error(f"FormulaNode '{node.id}' references non-claim knowledge '{ref}'")


def _validate_formula_graphs(
    formula_graphs: list[FormulaGraph],
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    for formula_graph in formula_graphs:
        source = knowledge_lookup.get(formula_graph.source_claim)
        if source is None:
            result.error(f"FormulaGraph source_claim '{formula_graph.source_claim}' not found")
        elif source.type != KnowledgeType.CLAIM:
            result.error(
                f"FormulaGraph source_claim '{formula_graph.source_claim}' must reference a claim"
            )

        descriptors_by_id: dict[str, dict] = {}
        for node in formula_graph.nodes:
            existing = descriptors_by_id.get(node.id)
            if existing is not None and existing != node.descriptor:
                result.error(
                    f"FormulaNode id '{node.id}' appears with different descriptors "
                    f"in FormulaGraph '{formula_graph.source_claim}'"
                )
            descriptors_by_id[node.id] = node.descriptor
            _validate_formula_node(formula_graph, node, knowledge_lookup, result)

        if formula_graph.root not in descriptors_by_id:
            result.error(
                f"FormulaGraph '{formula_graph.source_claim}': root "
                f"'{formula_graph.root}' not found in nodes"
            )

        for edge in formula_graph.edges:
            if edge.source not in descriptors_by_id:
                result.error(
                    f"FormulaGraph '{formula_graph.source_claim}': edge source "
                    f"'{edge.source}' not found in nodes"
                )
            if edge.target not in descriptors_by_id:
                result.error(
                    f"FormulaGraph '{formula_graph.source_claim}': edge target "
                    f"'{edge.target}' not found in nodes"
                )
```

- [x] **Step 4: Call formula graph validation**

In `validate_local_graph`, after `_validate_composes(...)`, add:

```python
    _validate_formula_graphs(graph.formula_graphs, knowledge_lookup, result)
```

- [x] **Step 5: Run validator tests**

Run:

```bash
uv run --project . python -m pytest tests/ir/test_validator.py::TestFormulaGraphValidation -q
```

Expected: PASS.

- [x] **Step 6: Commit validator changes**

Run:

```bash
git add gaia/engine/ir/validator.py tests/ir/test_validator.py
git commit -m "feat(ir): validate formula graph references"
```

---

### Task 6: Stabilize Formula Helper Claim Identity

**Files:**
- Modify: `gaia/engine/lang/compiler/lower_formula.py`
- Test: `tests/gaia/lang/test_formula_lowering.py`

- [x] **Step 1: Add failing helper dedup regression**

Append to `tests/gaia/lang/test_formula_lowering.py`:

```python
def test_repeated_predicate_formula_reuses_generated_atom_helper_claim():
    pkg = CollectedPackage(name="formula_repeated_helper_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        particle = Domain(content="Particles", members=["p1"])
        x = Variable(symbol="x", domain=particle)
        stable = PredicateSymbol(name="Stable", arg_domains=(particle,))
        repeated = claim(
            "Stable(x) and Stable(x).",
            formula=land(UserPredicate(stable, (x,)), UserPredicate(stable, (x,))),
        )
        repeated.label = "repeated"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    generated_atoms = [
        k
        for k in artifact.graph.knowledges
        if (k.metadata or {}).get("generated_kind") == "formula_atom"
    ]

    assert len(generated_atoms) == 1
    assert generated_atoms[0].metadata["source_claim"] == "t:formula_repeated_helper_pkg::repeated"
    assert generated_atoms[0].metadata["formula_node_id"].startswith("fg:")
```

- [x] **Step 2: Run the failing regression**

Run:

```bash
uv run --project . python -m pytest tests/gaia/lang/test_formula_lowering.py::test_repeated_predicate_formula_reuses_generated_atom_helper_claim -q
```

Expected: FAIL because `_generated_claim` still salts every repeated atom with `_helper_counter`.

- [x] **Step 3: Pass `source_claim_id` into `_FormulaState`**

Change `_FormulaState.__init__` signature:

```python
        source_claim_id: str,
```

Set:

```python
        self.source_claim_id = source_claim_id
        self.generated_claims_by_key: dict[tuple[str, str], str] = {}
```

Update the construction in `_lower_formula_to_claim`:

```python
    state = _FormulaState(
        namespace=namespace,
        package_name=package_name,
        source_claim_id=target_id,
        knowledge_map=knowledge_map,
        bindings=bindings,
    )
```

- [x] **Step 4: Replace counter-only generated helper identity**

Replace `_generated_claim` with:

```python
    def _generated_claim(self, role: str, semantic_key: str) -> tuple[str, str, bool]:
        cache_key = (role, semantic_key)
        existing = self.generated_claims_by_key.get(cache_key)
        if existing is not None:
            label = existing.rsplit("::", maxsplit=1)[-1]
            return label, existing, False

        digest = hashlib.sha256(
            f"{self.namespace}|{self.package_name}|{self.source_claim_id}|{role}|{semantic_key}".encode()
        ).hexdigest()[:8]
        label = f"__{_safe_label(role)}_{digest}"
        claim_id = make_qid(self.namespace, self.package_name, label)
        self.generated_claims_by_key[cache_key] = claim_id
        return label, claim_id, True
```

- [x] **Step 5: Update `_atom_claim` to use formula node ids**

Replace the start of `_atom_claim` with:

```python
        descriptor = canonical_formula_descriptor(
            formula,
            knowledge_map=self.knowledge_map,
            bindings=self.bindings,
        )
        node_id = formula_node_id(descriptor)
        label, claim_id, created = self._generated_claim("formula_atom", node_id)
        if not created:
            return claim_id
```

Update metadata construction:

```python
            "formula_atom": descriptor,
            "formula_node_id": node_id,
            "source_claim": self.source_claim_id,
```

- [x] **Step 6: Update `_helper_claim` to use canonical child structure**

Replace the first lines of `_helper_claim` with:

```python
        semantic_key = json.dumps(
            {"operator": str(operator_name), "children": child_ids},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        label, claim_id, created = self._generated_claim(f"{operator_name}_result", semantic_key)
        if not created:
            return claim_id
```

Add to helper metadata:

```python
                    "source_claim": self.source_claim_id,
```

- [x] **Step 7: Run helper identity regression and formula lowering suite**

Run:

```bash
uv run --project . python -m pytest tests/gaia/lang/test_formula_lowering.py -q
```

Expected: PASS.

- [x] **Step 8: Commit helper identity changes**

Run:

```bash
git add gaia/engine/lang/compiler/lower_formula.py tests/gaia/lang/test_formula_lowering.py
git commit -m "fix(lang): canonicalize formula helper identities"
```

---

### Task 7: Full Verification And PR Update

**Files:**
- Verify only unless failures require a narrow fix.

- [x] **Step 1: Run focused test suites**

Run:

```bash
uv run --project . python -m pytest tests/ir/test_formula_graph.py tests/ir/test_validator.py tests/gaia/lang/test_formula_lowering.py -q
```

Expected: PASS.

- [x] **Step 2: Run broader IR and lang tests**

Run:

```bash
uv run --project . python -m pytest tests/ir tests/gaia/lang -q
```

Expected: PASS.

- [x] **Step 3: Run formatting and lint checks**

Run:

```bash
uv run --project . ruff format --check gaia/engine/ir/formula.py gaia/engine/ir/__init__.py gaia/engine/ir/graphs.py gaia/engine/ir/validator.py gaia/engine/lang/compiler/lower_formula.py gaia/engine/lang/compiler/compile.py tests/ir/test_formula_graph.py tests/ir/test_validator.py tests/gaia/lang/test_formula_lowering.py
```

Expected: PASS.

Run:

```bash
uv run --project . ruff check gaia/engine/ir/formula.py gaia/engine/ir/__init__.py gaia/engine/ir/graphs.py gaia/engine/ir/validator.py gaia/engine/lang/compiler/lower_formula.py gaia/engine/lang/compiler/compile.py tests/ir/test_formula_graph.py tests/ir/test_validator.py tests/gaia/lang/test_formula_lowering.py
```

Expected: PASS.

- [x] **Step 4: Inspect final diff**

Run:

```bash
git status --short --branch
git diff --stat origin/v0.5...HEAD
```

Expected: branch contains the implementation commits from Tasks 1-6 and no unstaged changes.

- [ ] **Step 5: Push the implementation branch**

Run:

```bash
git push origin codex/v05-formula-graph-design
```

Expected: branch updates on GitHub.

- [ ] **Step 6: Check PR #632 CI**

Run:

```bash
gh pr checks 632 --watch=false
```

Expected: checks are queued or passing. If a check fails, inspect the named job:

```bash
gh run view <run-id> --log-failed
```

Use the concrete failure output to make one narrow fix commit, then rerun the focused local command that corresponds to the failure.
