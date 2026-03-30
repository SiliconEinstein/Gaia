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
    EQUIVALENCE = "equivalence"  # A=B
    CONTRADICTION = "contradiction"  # ¬(A=1 ∧ B=1)
    COMPLEMENT = "complement"  # A≠B (XOR)
    DISJUNCTION = "disjunction"  # ¬(all Aᵢ=0)
    CONJUNCTION = "conjunction"  # M = A₁ ∧ ... ∧ Aₖ


class Operator(BaseModel):
    """Deterministic logical constraint between Knowledge nodes.

    Operators have no probability parameters — they encode logical structure.
    They can appear standalone (top-level operators array) or embedded in FormalExpr.
    """

    operator_id: str | None = None  # lco_ or gco_ prefix
    scope: str | None = None  # "local" | "global" (None when embedded in FormalExpr)

    operator: OperatorType
    variables: list[str]  # ordered input Knowledge IDs (conclusion never appears here)
    conclusion: str  # output Knowledge ID (separate from variables for all types)

    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_invariants(self) -> Operator:
        if self.scope not in (None, "local", "global"):
            raise ValueError("scope must be one of: None, 'local', 'global'")

        if (
            self.scope == "local"
            and self.operator_id is not None
            and not self.operator_id.startswith("lco_")
        ):
            raise ValueError("local operators must use an operator_id with lco_ prefix")

        if (
            self.scope == "global"
            and self.operator_id is not None
            and not self.operator_id.startswith("gco_")
        ):
            raise ValueError("global operators must use an operator_id with gco_ prefix")

        # §2.4: conclusion must NEVER appear in variables (inputs-only separation)
        if self.conclusion in self.variables:
            raise ValueError(
                f"conclusion '{self.conclusion}' must not appear in variables "
                f"(variables are inputs only)"
            )

        # §2.4: arity constraints per operator type
        if self.operator == OperatorType.IMPLICATION:
            if len(self.variables) != 1:
                raise ValueError("operator=implication requires exactly 1 variable (input)")

        elif self.operator == OperatorType.CONJUNCTION:
            if len(self.variables) < 2:
                raise ValueError("operator=conjunction requires at least 2 variables (inputs)")

        elif self.operator in (
            OperatorType.EQUIVALENCE,
            OperatorType.CONTRADICTION,
            OperatorType.COMPLEMENT,
        ):
            if len(self.variables) != 2:
                raise ValueError(f"operator={self.operator} requires exactly 2 variables")

        elif self.operator == OperatorType.DISJUNCTION:
            if len(self.variables) < 2:
                raise ValueError("operator=disjunction requires at least 2 variables")

        return self
