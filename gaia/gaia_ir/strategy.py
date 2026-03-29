"""Strategy — reasoning declarations in the Gaia reasoning hypergraph.

Implements docs/foundations/gaia-ir/gaia-ir.md §3.

Three forms (class hierarchy):
- Strategy: leaf reasoning (single ↝)
- CompositeStrategy: contains sub-strategies, supports recursive nesting
- FormalStrategy: contains deterministic Operator expansion (FormalExpr)
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator

from gaia.gaia_ir.operator import Operator


class StrategyType(StrEnum):
    """Strategy types (§3.3). Orthogonal to form (Strategy/Composite/Formal)."""

    INFER = "infer"  # full CPT: 2^k params
    NOISY_AND = "noisy_and"  # ∧ + single param p

    # Named strategies — deterministic (pure FormalStrategy)
    DEDUCTION = "deduction"
    REDUCTIO = "reductio"
    ELIMINATION = "elimination"
    MATHEMATICAL_INDUCTION = "mathematical_induction"
    CASE_ANALYSIS = "case_analysis"

    # Named strategies — non-deterministic (CompositeStrategy with FormalStrategy parts)
    ABDUCTION = "abduction"
    INDUCTION = "induction"
    ANALOGY = "analogy"
    EXTRAPOLATION = "extrapolation"

    # Special
    TOOLCALL = "toolcall"
    PROOF = "proof"


class Step(BaseModel):
    """A single reasoning step (local layer only)."""

    reasoning: str
    premises: list[str] | None = None
    conclusion: str | None = None


class FormalExpr(BaseModel):
    """Deterministic Operator expansion embedded in FormalStrategy.

    Contains only deterministic Operators — no probability parameters.
    Intermediate Knowledge referenced by operators must exist as independent
    Knowledge nodes in the graph (created by compiler/reviewer/agent).
    """

    operators: list[Operator]


def _sha256_hex(data: str, length: int = 16) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:length]


def _compute_strategy_id(scope: str, type_: str, premises: list[str], conclusion: str | None) -> str:
    """Deterministic strategy ID: {lcs_|gcs_}_{sha256(scope + type + sorted(premises) + conclusion)[:16]}."""
    prefix = "lcs_" if scope == "local" else "gcs_"
    payload = f"{scope}|{type_}|{sorted(premises)}|{conclusion}"
    return f"{prefix}{_sha256_hex(payload)}"


class Strategy(BaseModel):
    """Base strategy — leaf reasoning (single ↝).

    Can be instantiated directly for basic strategies (infer, noisy_and, toolcall, proof).
    """

    strategy_id: str | None = None
    scope: str  # "local" | "global"
    type: StrategyType

    # connections
    premises: list[str]  # claim Knowledge IDs
    conclusion: str | None = None  # single output Knowledge (must be claim)
    background: list[str] | None = None  # context Knowledge IDs (any type, not in BP)

    # local layer
    steps: list[Step] | None = None  # reasoning process (local only, None at global)

    # traceability
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _compute_id_and_validate(self) -> Strategy:
        if self.strategy_id is None:
            self.strategy_id = _compute_strategy_id(
                self.scope, self.type, self.premises, self.conclusion
            )
        return self


class CompositeStrategy(Strategy):
    """Strategy with sub-strategies, supporting recursive nesting.

    Used for non-deterministic named strategies (abduction, induction, analogy,
    extrapolation) and for merging duplicate reasoning chains during canonicalization.
    """

    sub_strategies: list[Strategy]

    @model_validator(mode="after")
    def _validate_sub_strategies(self) -> CompositeStrategy:
        if not self.sub_strategies:
            raise ValueError("CompositeStrategy requires at least one sub_strategy")
        return self


class FormalStrategy(Strategy):
    """Strategy with deterministic Operator expansion.

    Used for deterministic named strategies (deduction, reductio, elimination,
    mathematical_induction, case_analysis) and as sub-parts of CompositeStrategy.
    """

    formal_expr: FormalExpr

    @model_validator(mode="after")
    def _validate_formal_expr(self) -> FormalStrategy:
        if not self.formal_expr.operators:
            raise ValueError("FormalStrategy requires at least one operator in formal_expr")
        return self
