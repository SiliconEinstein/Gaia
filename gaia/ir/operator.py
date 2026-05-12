"""Operator — deterministic logical constraints between Knowledge.

Implements docs/foundations/gaia-ir/gaia-ir.md §2.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator


class OperatorType(StrEnum):
    """Operator types (§2.2). All are deterministic (ψ ∈ {0,1}, no free parameters)."""

    IMPLICATION = "implication"  # A=1 → B must =1
    NEGATION = "negation"  # H = ¬A
    EQUIVALENCE = "equivalence"  # A=B
    CONTRADICTION = "contradiction"  # ¬(A=1 ∧ B=1)
    COMPLEMENT = "complement"  # A≠B (XOR)
    DISJUNCTION = "disjunction"  # ¬(all Aᵢ=0)
    CONJUNCTION = "conjunction"  # M = A₁ ∧ ... ∧ Aₖ


_BINARY_OPERATOR_TYPES = frozenset(
    {
        OperatorType.EQUIVALENCE,
        OperatorType.CONTRADICTION,
        OperatorType.COMPLEMENT,
    }
)


def _validate_scope_and_id(operator: Operator) -> None:
    """Validate Operator scope and local ID prefix invariants."""
    if operator.scope not in (None, "local"):
        raise ValueError("scope must be one of: None, 'local'")

    if (
        operator.scope == "local"
        and operator.operator_id is not None
        and not operator.operator_id.startswith("lco_")
    ):
        raise ValueError("local operators must use an operator_id with lco_ prefix")


def _validate_operator_arity(operator: Operator) -> None:
    """Validate §2.4 arity constraints for an Operator."""
    variable_count = len(operator.variables)
    if operator.operator == OperatorType.IMPLICATION:
        if variable_count != 2:
            raise ValueError("operator=implication requires exactly 2 variables (inputs)")
        return

    if operator.operator == OperatorType.NEGATION:
        if variable_count != 1:
            raise ValueError("operator=negation requires exactly 1 variable (input)")
        return

    if operator.operator == OperatorType.CONJUNCTION:
        if variable_count < 2:
            raise ValueError("operator=conjunction requires at least 2 variables (inputs)")
        return

    if operator.operator in _BINARY_OPERATOR_TYPES:
        if variable_count != 2:
            raise ValueError(f"operator={operator.operator} requires exactly 2 variables")
        return

    if operator.operator == OperatorType.DISJUNCTION and variable_count < 2:
        raise ValueError("operator=disjunction requires at least 2 variables")


class Operator(BaseModel):
    """Deterministic logical constraint between Knowledge nodes.

    Operators have no probability parameters — they encode logical structure.
    They can appear standalone (top-level operators array) or embedded in FormalExpr.
    """

    operator_id: str | None = None  # lco_ prefix
    scope: str | None = None  # "local" (None when embedded in FormalExpr)

    operator: OperatorType
    variables: list[str]  # ordered input Knowledge IDs (conclusion never appears here)
    conclusion: str  # output Knowledge ID (separate from variables for all types)

    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_invariants(self) -> Operator:
        _validate_scope_and_id(self)

        # §2.4: conclusion must NEVER appear in variables (inputs-only separation)
        if self.conclusion in self.variables:
            raise ValueError(
                f"conclusion '{self.conclusion}' must not appear in variables "
                f"(variables are inputs only)"
            )

        _validate_operator_arity(self)

        return self
