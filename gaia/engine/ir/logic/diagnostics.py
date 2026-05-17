"""Formula-graph logic diagnostics for Gaia IR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sympy import And, Equivalent, Implies, Not, Or, Symbol

from gaia.engine.ir.formula import FormulaGraph, FormulaNode
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


@dataclass(frozen=True)
class _ProjectedFormula:
    source_claim: str
    root: str
    expression: Any
    atom_ids: frozenset[str]


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


def formula_graph_to_sympy(formula_graph: FormulaGraph) -> Any | None:
    """Project a propositional FormulaGraph root to a SymPy Boolean expression."""
    projected = _project_formula_graph(formula_graph)
    if projected is None:
        return None
    return projected.expression


def _project_formula_graph(formula_graph: FormulaGraph) -> _ProjectedFormula | None:
    nodes_by_id = {node.id: node for node in formula_graph.nodes}
    atom_ids: set[str] = set()
    expression = _project_node(formula_graph.root, nodes_by_id, atom_ids)
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
    nodes_by_id: dict[str, FormulaNode],
    atom_ids: set[str],
) -> Any | None:
    node = nodes_by_id.get(node_id)
    if node is None:
        return None

    if node.kind == "atom":
        return _project_atom_node(node, atom_ids)

    if node.kind == "op":
        return _project_op_node(node, nodes_by_id, atom_ids)

    return None


def _project_atom_node(node: FormulaNode, atom_ids: set[str]) -> Any:
    descriptor = node.descriptor
    symbol_name = node.id
    if descriptor.get("kind") == "claim" and isinstance(descriptor.get("qid"), str):
        symbol_name = descriptor["qid"]
    atom_ids.add(symbol_name)
    return Symbol(symbol_name)


def _project_op_node(
    node: FormulaNode,
    nodes_by_id: dict[str, FormulaNode],
    atom_ids: set[str],
) -> Any | None:
    descriptor = node.descriptor
    operator = descriptor.get("operator")
    children = descriptor.get("children")
    if not isinstance(operator, str) or not isinstance(children, list):
        return None
    if not all(isinstance(child_id, str) for child_id in children):
        return None

    child_expressions = [_project_node(child_id, nodes_by_id, atom_ids) for child_id in children]
    if any(child_expression is None for child_expression in child_expressions):
        return None

    return _build_sympy_operation(operator, child_expressions)


def _build_sympy_operation(operator: str, child_expressions: list[Any]) -> Any | None:
    if operator == "conjunction":
        if len(child_expressions) < 2:
            return None
        return And(*child_expressions)
    if operator == "disjunction":
        if len(child_expressions) < 2:
            return None
        return Or(*child_expressions)
    if operator == "negation":
        if len(child_expressions) != 1:
            return None
        return Not(child_expressions[0])
    if operator == "implication":
        if len(child_expressions) != 2:
            return None
        return Implies(child_expressions[0], child_expressions[1])
    if operator == "equivalence":
        if len(child_expressions) != 2:
            return None
        return Equivalent(child_expressions[0], child_expressions[1])

    return None


def inspect_formula_graphs(
    graph: LocalCanonicalGraph,
    *,
    include_pairwise: bool = True,
) -> FormulaDiagnosticReport:
    """Inspect formula graphs and return reviewer-facing logic diagnostics."""
    del graph, include_pairwise
    return FormulaDiagnosticReport()
