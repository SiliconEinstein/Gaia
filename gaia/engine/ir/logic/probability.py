"""Probability scoring for formula diagnostic conditions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from gaia.engine.bp.factor_graph import FactorGraph
from gaia.engine.bp.joint_query import (
    JointDistribution,
    JointDistributionBasis,
    JointQueryMethod,
    JointQueryUnavailable,
    compare_joint_over,
)
from gaia.engine.ir.logic.diagnostics import DiagnosticCondition, FormulaDiagnostic


class ConditionProbabilityEstimate(BaseModel):
    """A method-specific probability for one diagnostic Boolean event."""

    model_config = ConfigDict(extra="forbid")

    variables: list[str]
    method: JointQueryMethod
    probability: float
    is_exact: bool
    basis: JointDistributionBasis
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class DiagnosticProbability(BaseModel):
    """Probability scoring result for a diagnostic condition."""

    model_config = ConfigDict(extra="forbid")

    condition: DiagnosticCondition
    estimates: list[ConditionProbabilityEstimate | JointQueryUnavailable]
    spread: float | None = None
    exact_spread: float | None = None
    diagnostic: FormulaDiagnostic | None = None


def event_probability(expression: dict[str, Any], joint: JointDistribution) -> float:
    """Sum full-joint probability mass satisfying ``expression``.

    The joint table is decoded with Gaia's bit-index convention:
    ``joint.variables[bit]`` has value ``(assignment_index >> bit) & 1``.
    """
    variable_bits = {variable: bit for bit, variable in enumerate(joint.variables)}
    _validate_expression(expression, set(variable_bits))

    probability = 0.0
    for assignment_index, mass in enumerate(joint.probabilities):
        if _evaluate_expression(expression, variable_bits, assignment_index):
            probability += mass
    return float(probability)


def score_condition(
    condition: DiagnosticCondition,
    joint_results: Sequence[JointDistribution | JointQueryUnavailable],
) -> DiagnosticProbability:
    """Score a diagnostic condition against available joint query results."""
    estimates: list[ConditionProbabilityEstimate | JointQueryUnavailable] = []
    probabilities: list[float] = []
    exact_probabilities: list[float] = []

    for result in joint_results:
        if isinstance(result, JointQueryUnavailable):
            estimates.append(result)
            continue

        probability = event_probability(condition.expression, result)
        estimate = ConditionProbabilityEstimate(
            variables=result.variables,
            method=result.method,
            probability=probability,
            is_exact=result.is_exact,
            basis=result.basis,
            diagnostics=result.diagnostics,
        )
        estimates.append(estimate)
        probabilities.append(probability)
        if result.is_exact:
            exact_probabilities.append(probability)

    return DiagnosticProbability(
        condition=condition,
        estimates=estimates,
        spread=_spread(probabilities),
        exact_spread=_spread(exact_probabilities),
    )


def score_diagnostic_conditions(
    graph: FactorGraph,
    diagnostics: Sequence[FormulaDiagnostic],
    *,
    methods: Sequence[JointQueryMethod] = ("exact", "junction_tree", "trw_bp", "mean_field"),
) -> list[DiagnosticProbability]:
    """Score diagnostics that carry machine-readable conditions."""
    scored: list[DiagnosticProbability] = []
    for diagnostic in diagnostics:
        condition = diagnostic.condition
        if condition is None:
            continue
        joint_results = compare_joint_over(graph, condition.variables, methods=methods)
        scored_condition = score_condition(condition, joint_results)
        scored.append(scored_condition.model_copy(update={"diagnostic": diagnostic}))
    return scored


def _spread(probabilities: Sequence[float]) -> float | None:
    if not probabilities:
        return None
    return float(max(probabilities) - min(probabilities))


def _validate_expression(expression: Any, known_variables: set[str]) -> None:
    if not isinstance(expression, dict):
        raise ValueError("diagnostic condition expression must be a mapping.")

    has_var = "var" in expression
    has_op = "op" in expression
    if has_var == has_op:
        raise ValueError(
            "diagnostic condition expression must contain exactly one of 'var' or 'op'."
        )

    if has_var:
        _validate_var_expression(expression, known_variables)
        return

    _validate_operator_expression(expression, known_variables)


def _validate_var_expression(expression: dict[str, Any], known_variables: set[str]) -> None:
    if set(expression) != {"var"}:
        raise ValueError("var expression must contain only 'var'.")
    variable = expression["var"]
    if not isinstance(variable, str) or not variable:
        raise ValueError("diagnostic condition variable must be a non-empty string.")
    if variable not in known_variables:
        raise ValueError(
            f"unknown variable {variable!r} in diagnostic condition expression; "
            f"joint variables are {sorted(known_variables)!r}."
        )


def _validate_operator_expression(expression: dict[str, Any], known_variables: set[str]) -> None:
    operator = expression["op"]
    if not isinstance(operator, str):
        raise ValueError("diagnostic condition operator must be a string.")

    if operator == "not":
        if set(expression) != {"op", "arg"}:
            raise ValueError("not expression requires exactly 'op' and 'arg'.")
        _validate_expression(expression["arg"], known_variables)
        return

    if operator in {"and", "or"}:
        if set(expression) != {"op", "args"}:
            raise ValueError(f"{operator} expression requires exactly 'op' and 'args'.")
        args = expression.get("args")
        if not isinstance(args, list) or not args:
            raise ValueError(f"{operator} expression requires a non-empty 'args' list.")
        for arg in args:
            _validate_expression(arg, known_variables)
        return

    raise ValueError(f"unsupported diagnostic condition operator {operator!r}.")


def _evaluate_expression(
    expression: dict[str, Any],
    variable_bits: dict[str, int],
    assignment_index: int,
) -> bool:
    if "var" in expression:
        bit = variable_bits[expression["var"]]
        return bool((assignment_index >> bit) & 1)

    operator = expression["op"]
    if operator == "not":
        return not _evaluate_expression(expression["arg"], variable_bits, assignment_index)
    if operator == "and":
        return all(
            _evaluate_expression(arg, variable_bits, assignment_index)
            for arg in expression["args"]
        )
    if operator == "or":
        return any(
            _evaluate_expression(arg, variable_bits, assignment_index)
            for arg in expression["args"]
        )

    raise ValueError(f"unsupported diagnostic condition operator {operator!r}.")
