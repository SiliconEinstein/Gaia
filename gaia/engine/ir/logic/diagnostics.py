"""Formula-graph logic diagnostics for Gaia IR."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sympy import And, Equivalent, Implies, Not, Or, Symbol
from sympy.logic.inference import satisfiable

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
    symbol_name = _atom_symbol_name(node)
    atom_ids.add(symbol_name)
    return Symbol(symbol_name)


def _atom_symbol_name(node: FormulaNode) -> str:
    descriptor = node.descriptor
    qid = descriptor.get("qid")
    if descriptor.get("kind") == "claim" and isinstance(qid, str):
        return qid
    return node.id


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
    for child_id in children:
        if child_id not in nodes_by_id:
            raise ValueError(f"FormulaGraph '{node.id}' references missing child node '{child_id}'")

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
    diagnostics: list[FormulaDiagnostic] = []
    projected: list[_ProjectedFormula] = []

    for formula_graph in graph.formula_graphs:
        diagnostics.extend(_redundant_operand_diagnostics(formula_graph))
        try:
            projection = _project_formula_graph(formula_graph)
        except ValueError as error:
            diagnostics.append(_projection_malformed_diagnostic(formula_graph, error))
            continue
        if projection is None:
            diagnostics.append(_projection_unsupported_diagnostic(formula_graph))
            continue
        local_diagnostics = _claim_local_diagnostics(projection)
        diagnostics.extend(local_diagnostics)
        if _is_pairwise_candidate(local_diagnostics):
            projected.append(projection)

    if include_pairwise:
        diagnostics.extend(_pairwise_diagnostics(projected))

    return FormulaDiagnosticReport(diagnostics=diagnostics)


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
    nodes_by_id = {node.id: node for node in formula_graph.nodes}
    for node in formula_graph.nodes:
        operator = node.descriptor.get("operator")
        if node.kind != "op" or operator not in {"conjunction", "disjunction"}:
            continue
        children = node.descriptor.get("children", [])
        if not isinstance(children, list):
            continue
        repeated = sorted(
            {child for child in children if isinstance(child, str) and children.count(child) > 1}
        )
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
                    "repeated_children": [
                        _condition_var_for_node(nodes_by_id[child])
                        for child in repeated
                        if child in nodes_by_id
                    ],
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


def _projection_malformed_diagnostic(
    formula_graph: FormulaGraph,
    error: ValueError,
) -> FormulaDiagnostic:
    return FormulaDiagnostic(
        code="formula_projection_malformed",
        severity="warning",
        scope="claim",
        logic_strength="unknown",
        source_claim=formula_graph.source_claim,
        formula_nodes=[formula_graph.root],
        message=f"Formula for claim {formula_graph.source_claim!r} is malformed.",
        details={"error": str(error)},
    )


def _is_pairwise_candidate(local_diagnostics: list[FormulaDiagnostic]) -> bool:
    """Exclude locally degenerate formulas from pairwise scans.

    Unsatisfiable formulas would look incompatible with every overlapping
    formula, and tautologies would be entailed by every overlap. Those cases are
    already reported as claim-local diagnostics, so pairwise would only add
    noise.
    """
    excluded_codes = {"formula_unsat", "formula_tautology"}
    return not any(diagnostic.code in excluded_codes for diagnostic in local_diagnostics)


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
            f"Formula claims {left.source_claim!r} and {right.source_claim!r} cannot both hold."
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
        message=(f"Formula claim {antecedent.source_claim!r} entails {consequent.source_claim!r}."),
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
