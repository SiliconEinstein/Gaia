# Formula Logic Diagnostics API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first reviewer-facing formula logic diagnostics API for Gaia v0.5.

**Architecture:** Add `gaia.engine.ir.logic.diagnostics` as a small, solver-backed API over `LocalCanonicalGraph.formula_graphs`. The API projects propositional `FormulaGraph` shapes to SymPy, emits fatal claim-local diagnostics, emits non-fatal cross-claim warnings/infos, and attaches JSON Boolean conditions for downstream BP probability estimation.

**Tech Stack:** Python, Pydantic, SymPy Boolean logic, pytest, ruff.

---

## File Structure

- Create: `gaia/engine/ir/logic/diagnostics.py`
  - Owns diagnostic Pydantic models.
  - Owns formula graph projection to SymPy.
  - Owns `inspect_formula_graphs`.
  - Does not import BP or review manifest code.
- Modify: `gaia/engine/ir/logic/__init__.py`
  - Re-export the public diagnostics models and entry point.
- Create: `tests/gaia/logic/test_formula_diagnostics.py`
  - Covers model serialization, projection, local diagnostics, pairwise diagnostics, unsupported formulas, and package/review independence.
- Already added spec: `docs/specs/2026-05-17-formula-logic-diagnostics-design.md`
  - Treat as the source of truth for semantics.

## Task 1: Diagnostic Models And Public Export

**Files:**
- Create: `gaia/engine/ir/logic/diagnostics.py`
- Modify: `gaia/engine/ir/logic/__init__.py`
- Test: `tests/gaia/logic/test_formula_diagnostics.py`

- [ ] **Step 1: Write the failing model round-trip test**

Add this new test file:

```python
from gaia.engine.ir.logic.diagnostics import (
    DiagnosticCondition,
    FormulaDiagnostic,
    FormulaDiagnosticReport,
    inspect_formula_graphs,
)


def test_formula_diagnostic_models_round_trip_json():
    condition = DiagnosticCondition(
        kind="joint_incompatibility",
        variables=["t:pkg::left", "t:pkg::right"],
        expression={
            "op": "and",
            "args": [{"var": "t:pkg::left"}, {"var": "t:pkg::right"}],
        },
        confidence_basis="hard_logic",
    )
    diagnostic = FormulaDiagnostic(
        code="cross_claim_incompatibility",
        severity="warning",
        scope="claim_pair",
        logic_strength="hard",
        source_claim="t:pkg::left",
        related_claims=["t:pkg::right"],
        formula_nodes=["fg:left", "fg:right"],
        condition=condition,
        message="Claims cannot both hold.",
    )
    report = FormulaDiagnosticReport(diagnostics=[diagnostic])

    round_tripped = FormulaDiagnosticReport.model_validate_json(report.model_dump_json())

    assert round_tripped == report
    assert round_tripped.has_fatal is False
    assert inspect_formula_graphs is not None
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
python -m pytest tests/gaia/logic/test_formula_diagnostics.py::test_formula_diagnostic_models_round_trip_json -q --no-cov
```

Expected: FAIL with `ModuleNotFoundError: No module named 'gaia.engine.ir.logic.diagnostics'`.

- [ ] **Step 3: Add the diagnostics models and a no-op API**

Create `gaia/engine/ir/logic/diagnostics.py`:

```python
"""Formula-graph logic diagnostics for Gaia IR."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from gaia.engine.ir.graphs import LocalCanonicalGraph

FormulaDiagnosticSeverity = Literal["info", "warning", "fatal"]
FormulaDiagnosticScope = Literal["claim", "claim_pair", "package"]
FormulaLogicStrength = Literal["hard", "soft", "mixed", "unknown"]

DiagnosticConditionKind = Literal[
    "formula_unsat",
    "formula_tautology",
    "joint_incompatibility",
    "entailment_violation",
    "redundant_formula",
]
ConditionConfidenceBasis = Literal["hard_logic", "soft_relation", "projection"]


class DiagnosticCondition(BaseModel):
    """Machine-readable Boolean event associated with a diagnostic."""

    model_config = ConfigDict(extra="forbid")

    kind: DiagnosticConditionKind
    variables: list[str] = Field(default_factory=list)
    expression: dict[str, Any]
    confidence_basis: ConditionConfidenceBasis


class FormulaDiagnostic(BaseModel):
    """One formula-level diagnostic emitted for a compiled graph."""

    model_config = ConfigDict(extra="forbid")

    code: str
    severity: FormulaDiagnosticSeverity
    scope: FormulaDiagnosticScope
    logic_strength: FormulaLogicStrength
    source_claim: str | None = None
    related_claims: list[str] = Field(default_factory=list)
    formula_nodes: list[str] = Field(default_factory=list)
    condition: DiagnosticCondition | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class FormulaDiagnosticReport(BaseModel):
    """Collection of formula diagnostics."""

    model_config = ConfigDict(extra="forbid")

    diagnostics: list[FormulaDiagnostic] = Field(default_factory=list)

    @property
    def has_fatal(self) -> bool:
        """Return whether any diagnostic should block the local claim."""
        return any(diagnostic.severity == "fatal" for diagnostic in self.diagnostics)


def inspect_formula_graphs(
    graph: LocalCanonicalGraph,
    *,
    include_pairwise: bool = True,
) -> FormulaDiagnosticReport:
    """Inspect formula graphs and return reviewer-facing logic diagnostics."""
    del graph, include_pairwise
    return FormulaDiagnosticReport()
```

- [ ] **Step 4: Export the new public API**

Modify `gaia/engine/ir/logic/__init__.py`:

```python
from gaia.engine.ir.logic.diagnostics import (
    DiagnosticCondition,
    FormulaDiagnostic,
    FormulaDiagnosticReport,
    inspect_formula_graphs,
)
```

Add the same names to `__all__`.

- [ ] **Step 5: Run the focused test and verify it passes**

Run:

```bash
python -m pytest tests/gaia/logic/test_formula_diagnostics.py::test_formula_diagnostic_models_round_trip_json -q --no-cov
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add gaia/engine/ir/logic/diagnostics.py gaia/engine/ir/logic/__init__.py tests/gaia/logic/test_formula_diagnostics.py
git commit -m "feat: add formula diagnostic models"
```

## Task 2: FormulaGraph To SymPy Projection

**Files:**
- Modify: `gaia/engine/ir/logic/diagnostics.py`
- Modify: `tests/gaia/logic/test_formula_diagnostics.py`

- [ ] **Step 1: Add projection tests**

Append these tests:

```python
from sympy import And, Implies, Not, Symbol

from gaia.engine.lang import ClaimAtom, claim, forall, land, lnot, implies
from gaia.engine.lang.compiler import compile_package_artifact
from gaia.engine.lang.runtime.package import CollectedPackage
from gaia.engine.lang import Domain, PredicateSymbol, UserPredicate, Variable
from gaia.engine.ir.logic.diagnostics import formula_graph_to_sympy


def _qid(package: str, label: str) -> str:
    return f"t:{package}::{label}"


def _formula_graph_for(artifact, source_claim_id: str):
    return next(
        formula_graph
        for formula_graph in artifact.graph.formula_graphs
        if formula_graph.source_claim == source_claim_id
    )


def test_formula_graph_to_sympy_projects_claim_atom_connectives():
    package = "formula_diag_projection"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        rule = claim(
            "A and not B implies A.",
            formula=implies(land(ClaimAtom(a), lnot(ClaimAtom(b))), ClaimAtom(a)),
        )
        rule.label = "rule"

    artifact = compile_package_artifact(pkg)
    formula_graph = _formula_graph_for(artifact, _qid(package, "rule"))

    expression = formula_graph_to_sympy(formula_graph)

    assert expression == Implies(
        And(Symbol(_qid(package, "a")), Not(Symbol(_qid(package, "b")))),
        Symbol(_qid(package, "a")),
    )


def test_formula_graph_to_sympy_returns_none_for_quantifier_root():
    package = "formula_diag_quantifier"
    with CollectedPackage(package, namespace="t") as pkg:
        domain = Domain(content="Particles", members=["p1"])
        x = Variable(symbol="x", domain=domain)
        stable = PredicateSymbol(name="Stable", arg_domains=(domain,))
        universal = claim("All particles are stable.", formula=forall(x, UserPredicate(stable, (x,))))
        universal.label = "universal"

    artifact = compile_package_artifact(pkg)
    formula_graph = _formula_graph_for(artifact, _qid(package, "universal"))

    assert formula_graph_to_sympy(formula_graph) is None
```

- [ ] **Step 2: Run projection tests and verify they fail**

Run:

```bash
python -m pytest tests/gaia/logic/test_formula_diagnostics.py::test_formula_graph_to_sympy_projects_claim_atom_connectives tests/gaia/logic/test_formula_diagnostics.py::test_formula_graph_to_sympy_returns_none_for_quantifier_root -q --no-cov
```

Expected: FAIL because `formula_graph_to_sympy` is not defined.

- [ ] **Step 3: Implement projection helpers**

Add these imports to `diagnostics.py`:

```python
from dataclasses import dataclass

from sympy import Symbol
from sympy.logic.boolalg import And, Equivalent, Implies, Not, Or

from gaia.engine.ir.formula import FormulaGraph, FormulaNode
```

Add this projection implementation above `inspect_formula_graphs`:

```python
@dataclass(frozen=True)
class _ProjectedFormula:
    source_claim: str
    root: str
    expression: Any
    atom_ids: frozenset[str]


def formula_graph_to_sympy(formula_graph: FormulaGraph) -> Any | None:
    """Project a propositional FormulaGraph into a SymPy Boolean expression."""
    projected = _project_formula_graph(formula_graph)
    if projected is None:
        return None
    return projected.expression


def _project_formula_graph(formula_graph: FormulaGraph) -> _ProjectedFormula | None:
    nodes = {node.id: node for node in formula_graph.nodes}
    atom_ids: set[str] = set()
    expression = _project_node(formula_graph.root, nodes, atom_ids)
    if expression is None:
        return None
    return _ProjectedFormula(
        source_claim=formula_graph.source_claim,
        root=formula_graph.root,
        expression=expression,
        atom_ids=frozenset(atom_ids),
    )


def _project_node(
    node_id: str,
    nodes: dict[str, FormulaNode],
    atom_ids: set[str],
) -> Any | None:
    node = nodes[node_id]
    if node.kind == "atom":
        symbol_name = _atom_symbol_name(node)
        atom_ids.add(symbol_name)
        return Symbol(symbol_name)
    if node.kind != "op":
        return None

    operator = node.descriptor.get("operator")
    children = node.descriptor.get("children", [])
    if not isinstance(operator, str) or not isinstance(children, list):
        return None

    projected_children = [_project_node(child, nodes, atom_ids) for child in children]
    if any(child is None for child in projected_children):
        return None

    if operator == "conjunction":
        return And(*projected_children)
    if operator == "disjunction":
        return Or(*projected_children)
    if operator == "negation" and len(projected_children) == 1:
        return Not(projected_children[0])
    if operator == "implication" and len(projected_children) == 2:
        return Implies(projected_children[0], projected_children[1])
    if operator == "equivalence" and len(projected_children) == 2:
        return Equivalent(projected_children[0], projected_children[1])
    return None


def _atom_symbol_name(node: FormulaNode) -> str:
    descriptor = node.descriptor
    if descriptor.get("kind") == "claim" and isinstance(descriptor.get("qid"), str):
        return descriptor["qid"]
    return node.id
```

- [ ] **Step 4: Run projection tests and verify they pass**

Run:

```bash
python -m pytest tests/gaia/logic/test_formula_diagnostics.py::test_formula_graph_to_sympy_projects_claim_atom_connectives tests/gaia/logic/test_formula_diagnostics.py::test_formula_graph_to_sympy_returns_none_for_quantifier_root -q --no-cov
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gaia/engine/ir/logic/diagnostics.py tests/gaia/logic/test_formula_diagnostics.py
git commit -m "feat: project formula graphs to sympy"
```

## Task 3: Claim-Local Diagnostics

**Files:**
- Modify: `gaia/engine/ir/logic/diagnostics.py`
- Modify: `tests/gaia/logic/test_formula_diagnostics.py`

- [ ] **Step 1: Add claim-local diagnostic tests**

Append these tests:

```python
from gaia.engine.lang import lor


def test_inspect_formula_graphs_reports_claim_local_unsat_as_fatal():
    package = "formula_diag_local_unsat"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        impossible = claim("A and not A.", formula=land(ClaimAtom(a), lnot(ClaimAtom(a))))
        impossible.label = "impossible"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph, include_pairwise=False)

    diagnostic = next(d for d in report.diagnostics if d.code == "formula_unsat")
    assert diagnostic.severity == "fatal"
    assert diagnostic.scope == "claim"
    assert diagnostic.logic_strength == "hard"
    assert diagnostic.source_claim == _qid(package, "impossible")
    assert diagnostic.condition.kind == "formula_unsat"
    assert diagnostic.condition.expression == {"var": _qid(package, "impossible")}
    assert report.has_fatal is True


def test_inspect_formula_graphs_reports_claim_local_tautology_as_warning():
    package = "formula_diag_local_tautology"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        tautology = claim("A or not A.", formula=lor(ClaimAtom(a), lnot(ClaimAtom(a))))
        tautology.label = "tautology"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph, include_pairwise=False)

    diagnostic = next(d for d in report.diagnostics if d.code == "formula_tautology")
    assert diagnostic.severity == "warning"
    assert diagnostic.scope == "claim"
    assert diagnostic.source_claim == _qid(package, "tautology")
    assert report.has_fatal is False


def test_inspect_formula_graphs_reports_redundant_operands_as_info():
    package = "formula_diag_redundant_operand"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        repeated = claim("A and A.", formula=land(ClaimAtom(a), ClaimAtom(a)))
        repeated.label = "repeated"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph, include_pairwise=False)

    diagnostic = next(d for d in report.diagnostics if d.code == "formula_redundant_operand")
    assert diagnostic.severity == "info"
    assert diagnostic.scope == "claim"
    assert diagnostic.source_claim == _qid(package, "repeated")
    assert diagnostic.details["repeated_children"] == [_qid(package, "a")]
```

- [ ] **Step 2: Run local diagnostic tests and verify they fail**

Run:

```bash
python -m pytest tests/gaia/logic/test_formula_diagnostics.py::test_inspect_formula_graphs_reports_claim_local_unsat_as_fatal tests/gaia/logic/test_formula_diagnostics.py::test_inspect_formula_graphs_reports_claim_local_tautology_as_warning tests/gaia/logic/test_formula_diagnostics.py::test_inspect_formula_graphs_reports_redundant_operands_as_info -q --no-cov
```

Expected: FAIL because `inspect_formula_graphs` still returns an empty report.

- [ ] **Step 3: Implement local diagnostics**

Add imports:

```python
from sympy.logic.inference import satisfiable
```

Replace `inspect_formula_graphs` with:

```python
def inspect_formula_graphs(
    graph: LocalCanonicalGraph,
    *,
    include_pairwise: bool = True,
) -> FormulaDiagnosticReport:
    """Inspect formula graphs and return reviewer-facing logic diagnostics."""
    diagnostics: list[FormulaDiagnostic] = []
    projected: list[_ProjectedFormula] = []

    for formula_graph in graph.formula_graphs:
        projection = _project_formula_graph(formula_graph)
        diagnostics.extend(_redundant_operand_diagnostics(formula_graph))
        if projection is None:
            diagnostics.append(_projection_unsupported_diagnostic(formula_graph))
            continue
        projected.append(projection)
        diagnostics.extend(_claim_local_diagnostics(projection))

    if include_pairwise:
        diagnostics.extend(_pairwise_diagnostics(projected))

    return FormulaDiagnosticReport(diagnostics=diagnostics)
```

Add these helpers:

```python
def _claim_local_diagnostics(projection: _ProjectedFormula) -> list[FormulaDiagnostic]:
    diagnostics: list[FormulaDiagnostic] = []
    if satisfiable(projection.expression) is False:
        diagnostics.append(
            FormulaDiagnostic(
                code="formula_unsat",
                severity="fatal",
                scope="claim",
                logic_strength="hard",
                source_claim=projection.source_claim,
                formula_nodes=[projection.root],
                condition=_condition(
                    "formula_unsat",
                    [projection.source_claim],
                    {"var": projection.source_claim},
                    "hard_logic",
                ),
                message=f"Formula for claim {projection.source_claim!r} is unsatisfiable.",
            )
        )
    elif satisfiable(Not(projection.expression)) is False:
        diagnostics.append(
            FormulaDiagnostic(
                code="formula_tautology",
                severity="warning",
                scope="claim",
                logic_strength="hard",
                source_claim=projection.source_claim,
                formula_nodes=[projection.root],
                condition=_condition(
                    "formula_tautology",
                    [projection.source_claim],
                    {"var": projection.source_claim},
                    "hard_logic",
                ),
                message=f"Formula for claim {projection.source_claim!r} is tautological.",
            )
        )
    return diagnostics


def _redundant_operand_diagnostics(formula_graph: FormulaGraph) -> list[FormulaDiagnostic]:
    diagnostics: list[FormulaDiagnostic] = []
    nodes = {node.id: node for node in formula_graph.nodes}
    for node in formula_graph.nodes:
        operator = node.descriptor.get("operator")
        if node.kind != "op" or operator not in {"conjunction", "disjunction"}:
            continue
        children = node.descriptor.get("children", [])
        if not isinstance(children, list):
            continue
        repeated = sorted({child for child in children if children.count(child) > 1})
        if not repeated:
            continue
        diagnostics.append(
            FormulaDiagnostic(
                code="formula_redundant_operand",
                severity="info",
                scope="claim",
                logic_strength="hard",
                source_claim=formula_graph.source_claim,
                formula_nodes=[node.id, *repeated],
                condition=_condition(
                    "redundant_formula",
                    [formula_graph.source_claim],
                    {"var": formula_graph.source_claim},
                    "hard_logic",
                ),
                message=f"Formula for claim {formula_graph.source_claim!r} repeats an operand.",
                details={
                    "operator": operator,
                    "repeated_children": [_condition_var_for_node(nodes[child]) for child in repeated],
                },
            )
        )
    return diagnostics


def _projection_unsupported_diagnostic(formula_graph: FormulaGraph) -> FormulaDiagnostic:
    return FormulaDiagnostic(
        code="formula_projection_unsupported",
        severity="info",
        scope="claim",
        logic_strength="unknown",
        source_claim=formula_graph.source_claim,
        formula_nodes=[formula_graph.root],
        message=(
            f"Formula for claim {formula_graph.source_claim!r} is outside the current "
            "propositional diagnostics subset."
        ),
    )


def _condition(
    kind: DiagnosticConditionKind,
    variables: list[str],
    expression: dict[str, Any],
    confidence_basis: ConditionConfidenceBasis,
) -> DiagnosticCondition:
    return DiagnosticCondition(
        kind=kind,
        variables=variables,
        expression=expression,
        confidence_basis=confidence_basis,
    )


def _condition_var_for_node(node: FormulaNode) -> str:
    if node.kind == "atom":
        return _atom_symbol_name(node)
    return node.id
```

Add a temporary pairwise stub below the helpers so Task 3 is complete:

```python
def _pairwise_diagnostics(projected: list[_ProjectedFormula]) -> list[FormulaDiagnostic]:
    del projected
    return []
```

- [ ] **Step 4: Run local diagnostic tests and verify they pass**

Run:

```bash
python -m pytest tests/gaia/logic/test_formula_diagnostics.py::test_inspect_formula_graphs_reports_claim_local_unsat_as_fatal tests/gaia/logic/test_formula_diagnostics.py::test_inspect_formula_graphs_reports_claim_local_tautology_as_warning tests/gaia/logic/test_formula_diagnostics.py::test_inspect_formula_graphs_reports_redundant_operands_as_info -q --no-cov
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gaia/engine/ir/logic/diagnostics.py tests/gaia/logic/test_formula_diagnostics.py
git commit -m "feat: add claim-local formula diagnostics"
```

## Task 4: Pairwise Cross-Claim Diagnostics

**Files:**
- Modify: `gaia/engine/ir/logic/diagnostics.py`
- Modify: `tests/gaia/logic/test_formula_diagnostics.py`

- [ ] **Step 1: Add pairwise diagnostic tests**

Append these tests:

```python
def test_pairwise_incompatibility_is_warning_with_bp_condition():
    package = "formula_diag_pair_incompat"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        left = claim("A holds.", formula=ClaimAtom(a))
        left.label = "left"
        right = claim("A does not hold.", formula=lnot(ClaimAtom(a)))
        right.label = "right"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph)

    diagnostic = next(d for d in report.diagnostics if d.code == "cross_claim_incompatibility")
    assert diagnostic.severity == "warning"
    assert diagnostic.scope == "claim_pair"
    assert diagnostic.logic_strength == "hard"
    assert diagnostic.source_claim == _qid(package, "left")
    assert diagnostic.related_claims == [_qid(package, "right")]
    assert diagnostic.condition.kind == "joint_incompatibility"
    assert diagnostic.condition.expression == {
        "op": "and",
        "args": [{"var": _qid(package, "left")}, {"var": _qid(package, "right")}],
    }
    assert report.has_fatal is False


def test_pairwise_entailment_is_info_with_violation_condition():
    package = "formula_diag_pair_entailment"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        strong = claim("A and B.", formula=land(ClaimAtom(a), ClaimAtom(b)))
        strong.label = "strong"
        weak = claim("A.", formula=ClaimAtom(a))
        weak.label = "weak"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph)

    diagnostic = next(d for d in report.diagnostics if d.code == "cross_claim_entailment")
    assert diagnostic.severity == "info"
    assert diagnostic.source_claim == _qid(package, "strong")
    assert diagnostic.related_claims == [_qid(package, "weak")]
    assert diagnostic.condition.kind == "entailment_violation"
    assert diagnostic.condition.expression == {
        "op": "and",
        "args": [
            {"var": _qid(package, "strong")},
            {"op": "not", "arg": {"var": _qid(package, "weak")}},
        ],
    }


def test_pairwise_diagnostics_skip_disjoint_formulas():
    package = "formula_diag_pair_disjoint"
    with CollectedPackage(package, namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        left = claim("A holds.", formula=ClaimAtom(a))
        left.label = "left"
        right = claim("B holds.", formula=ClaimAtom(b))
        right.label = "right"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph)

    assert [d for d in report.diagnostics if d.scope == "claim_pair"] == []
```

- [ ] **Step 2: Run pairwise tests and verify they fail**

Run:

```bash
python -m pytest tests/gaia/logic/test_formula_diagnostics.py::test_pairwise_incompatibility_is_warning_with_bp_condition tests/gaia/logic/test_formula_diagnostics.py::test_pairwise_entailment_is_info_with_violation_condition tests/gaia/logic/test_formula_diagnostics.py::test_pairwise_diagnostics_skip_disjoint_formulas -q --no-cov
```

Expected: FAIL because `_pairwise_diagnostics` is still a stub.

- [ ] **Step 3: Implement pairwise diagnostics**

Add import:

```python
from itertools import combinations
```

Replace the pairwise stub:

```python
def _pairwise_diagnostics(projected: list[_ProjectedFormula]) -> list[FormulaDiagnostic]:
    diagnostics: list[FormulaDiagnostic] = []
    for left, right in combinations(projected, 2):
        if left.atom_ids.isdisjoint(right.atom_ids):
            continue

        if satisfiable(And(left.expression, right.expression)) is False:
            diagnostics.append(_cross_claim_incompatibility(left, right))
            continue

        left_entails_right = satisfiable(And(left.expression, Not(right.expression))) is False
        right_entails_left = satisfiable(And(right.expression, Not(left.expression))) is False
        if left_entails_right and right_entails_left:
            diagnostics.append(_cross_claim_equivalence(left, right))
        elif left_entails_right:
            diagnostics.append(_cross_claim_entailment(left, right))
        elif right_entails_left:
            diagnostics.append(_cross_claim_entailment(right, left))
    return diagnostics


def _cross_claim_incompatibility(
    left: _ProjectedFormula,
    right: _ProjectedFormula,
) -> FormulaDiagnostic:
    return FormulaDiagnostic(
        code="cross_claim_incompatibility",
        severity="warning",
        scope="claim_pair",
        logic_strength="hard",
        source_claim=left.source_claim,
        related_claims=[right.source_claim],
        formula_nodes=[left.root, right.root],
        condition=_condition(
            "joint_incompatibility",
            [left.source_claim, right.source_claim],
            _and_event(left.source_claim, right.source_claim),
            "hard_logic",
        ),
        message=(
            f"Formula claims {left.source_claim!r} and {right.source_claim!r} "
            "cannot both hold."
        ),
    )


def _cross_claim_entailment(
    antecedent: _ProjectedFormula,
    consequent: _ProjectedFormula,
) -> FormulaDiagnostic:
    return FormulaDiagnostic(
        code="cross_claim_entailment",
        severity="info",
        scope="claim_pair",
        logic_strength="hard",
        source_claim=antecedent.source_claim,
        related_claims=[consequent.source_claim],
        formula_nodes=[antecedent.root, consequent.root],
        condition=_condition(
            "entailment_violation",
            [antecedent.source_claim, consequent.source_claim],
            {
                "op": "and",
                "args": [
                    {"var": antecedent.source_claim},
                    {"op": "not", "arg": {"var": consequent.source_claim}},
                ],
            },
            "hard_logic",
        ),
        message=(
            f"Formula claim {antecedent.source_claim!r} entails "
            f"{consequent.source_claim!r}."
        ),
    )


def _cross_claim_equivalence(
    left: _ProjectedFormula,
    right: _ProjectedFormula,
) -> FormulaDiagnostic:
    return FormulaDiagnostic(
        code="cross_claim_equivalence",
        severity="info",
        scope="claim_pair",
        logic_strength="hard",
        source_claim=left.source_claim,
        related_claims=[right.source_claim],
        formula_nodes=[left.root, right.root],
        condition=_condition(
            "redundant_formula",
            [left.source_claim, right.source_claim],
            {
                "op": "or",
                "args": [
                    {
                        "op": "and",
                        "args": [
                            {"var": left.source_claim},
                            {"op": "not", "arg": {"var": right.source_claim}},
                        ],
                    },
                    {
                        "op": "and",
                        "args": [
                            {"var": right.source_claim},
                            {"op": "not", "arg": {"var": left.source_claim}},
                        ],
                    },
                ],
            },
            "hard_logic",
        ),
        message=(
            f"Formula claims {left.source_claim!r} and {right.source_claim!r} "
            "are logically equivalent."
        ),
    )


def _and_event(left: str, right: str) -> dict[str, Any]:
    return {"op": "and", "args": [{"var": left}, {"var": right}]}
```

- [ ] **Step 4: Run pairwise tests and verify they pass**

Run:

```bash
python -m pytest tests/gaia/logic/test_formula_diagnostics.py::test_pairwise_incompatibility_is_warning_with_bp_condition tests/gaia/logic/test_formula_diagnostics.py::test_pairwise_entailment_is_info_with_violation_condition tests/gaia/logic/test_formula_diagnostics.py::test_pairwise_diagnostics_skip_disjoint_formulas -q --no-cov
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gaia/engine/ir/logic/diagnostics.py tests/gaia/logic/test_formula_diagnostics.py
git commit -m "feat: add pairwise formula diagnostics"
```

## Task 5: Unsupported Formula Coverage And Final Verification

**Files:**
- Modify: `gaia/engine/ir/logic/diagnostics.py`
- Modify: `tests/gaia/logic/test_formula_diagnostics.py`

- [ ] **Step 1: Add unsupported formula and export tests**

Append these tests:

```python
from gaia.engine.ir.logic import FormulaDiagnosticReport as ExportedFormulaDiagnosticReport
from gaia.engine.ir.logic import inspect_formula_graphs as exported_inspect_formula_graphs


def test_unsupported_quantifier_emits_info_without_crashing():
    package = "formula_diag_unsupported_quantifier"
    with CollectedPackage(package, namespace="t") as pkg:
        domain = Domain(content="Particles", members=["p1"])
        x = Variable(symbol="x", domain=domain)
        stable = PredicateSymbol(name="Stable", arg_domains=(domain,))
        universal = claim("All particles are stable.", formula=forall(x, UserPredicate(stable, (x,))))
        universal.label = "universal"

    report = inspect_formula_graphs(compile_package_artifact(pkg).graph)

    diagnostic = next(d for d in report.diagnostics if d.code == "formula_projection_unsupported")
    assert diagnostic.severity == "info"
    assert diagnostic.logic_strength == "unknown"
    assert diagnostic.source_claim == _qid(package, "universal")


def test_logic_package_exports_formula_diagnostics_api():
    assert ExportedFormulaDiagnosticReport is FormulaDiagnosticReport
    assert exported_inspect_formula_graphs is inspect_formula_graphs
```

- [ ] **Step 2: Run the new tests**

Run:

```bash
python -m pytest tests/gaia/logic/test_formula_diagnostics.py::test_unsupported_quantifier_emits_info_without_crashing tests/gaia/logic/test_formula_diagnostics.py::test_logic_package_exports_formula_diagnostics_api -q --no-cov
```

Expected: PASS. If export assertions fail, update `gaia/engine/ir/logic/__init__.py`.

- [ ] **Step 3: Run focused regression suite**

Run:

```bash
python -m pytest tests/gaia/logic/test_formula_diagnostics.py tests/ir/test_formula_graph.py tests/gaia/logic/test_propositional.py tests/gaia/lang/test_formula_lowering.py -q --no-cov
```

Expected: PASS. Existing deprecation warnings from old formula sugar are acceptable.

- [ ] **Step 4: Run formatting and lint checks**

Run:

```bash
ruff format --check gaia/engine/ir/logic/diagnostics.py tests/gaia/logic/test_formula_diagnostics.py
ruff check gaia/engine/ir/logic/diagnostics.py tests/gaia/logic/test_formula_diagnostics.py gaia/engine/ir/logic/__init__.py
```

Expected: PASS.

- [ ] **Step 5: Commit final polish**

```bash
git add gaia/engine/ir/logic/diagnostics.py gaia/engine/ir/logic/__init__.py tests/gaia/logic/test_formula_diagnostics.py
git commit -m "test: cover formula diagnostics api"
```

## Completion Criteria

- `inspect_formula_graphs(graph)` exists and returns `FormulaDiagnosticReport`.
- Same-claim unsatisfiable formulas produce `fatal`.
- Cross-claim incompatibilities produce `warning`, never `fatal`.
- Soft/hard separation is represented by `logic_strength`, even if phase 1 only emits hard/unknown.
- Every probabilistic warning has a JSON Boolean `DiagnosticCondition`.
- BP is not imported or run by diagnostics.
- `ReviewManifest` is not changed.
- Focused tests and ruff pass.
