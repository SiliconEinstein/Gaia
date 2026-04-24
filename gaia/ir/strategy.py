"""Strategy — reasoning declarations in the Gaia reasoning hypergraph.

Implements docs/foundations/gaia-ir/gaia-ir.md §3.

Three forms (class hierarchy):
- Strategy: leaf reasoning (single ↝)
- CompositeStrategy: contains sub-strategies (by reference), supports recursive nesting
- FormalStrategy: contains deterministic Operator expansion (FormalExpr)
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, model_validator

from gaia.ir.operator import Operator, OperatorType

if TYPE_CHECKING:
    from gaia.ir.formalize import FormalizationResult


class StrategyType(StrEnum):
    """Strategy types (§3.3). Orthogonal to form (Strategy/Composite/Formal)."""

    INFER = "infer"  # full CPT: 2^k params
    ASSOCIATE = "associate"  # symmetric pairwise association
    NOISY_AND = "noisy_and"  # ∧ + single param p

    # Named strategies — deterministic (pure FormalStrategy)
    DEDUCTION = "deduction"
    REDUCTIO = "reductio"
    ELIMINATION = "elimination"
    MATHEMATICAL_INDUCTION = "mathematical_induction"
    CASE_ANALYSIS = "case_analysis"

    # Named strategies — non-deterministic (FormalStrategy)
    ABDUCTION = "abduction"
    ANALOGY = "analogy"
    EXTRAPOLATION = "extrapolation"
    SUPPORT = "support"  # forward implication with a soft warrant
    COMPARE = "compare"  # prediction comparison via matching + inferential ordering

    # Composite strategies — non-atomic
    INDUCTION = "induction"  # CompositeStrategy wrapping shared-conclusion abductions


class Step(BaseModel):
    """A single reasoning step (local layer only)."""

    reasoning: str
    premises: list[str] | None = None


class FormalExpr(BaseModel):
    """Deterministic Operator expansion embedded in FormalStrategy.

    Contains only deterministic Operators — no probability parameters.
    Intermediate Knowledge referenced by operators must exist as independent
    Knowledge nodes in the graph (created by compiler/reviewer/agent).
    """

    operators: list[Operator]


def _sha256_hex(data: str, length: int = 16) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:length]


def _compute_strategy_id(
    scope: str,
    type_: str,
    premises: list[str],
    conclusion: str | None,
    structure_hash: str = "",
) -> str:
    """Deterministic strategy ID: lcs_{sha256(scope + type + sorted(premises) + conclusion + structure_hash)[:16]}."""
    prefix = "lcs_"
    payload = f"{scope}|{type_}|{sorted(premises)}|{conclusion}|{structure_hash}"
    return f"{prefix}{_sha256_hex(payload)}"


def _probability(value: float, field_name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise ValueError(f"{field_name} must be a probability in [0, 1], got {value!r}")
    return parsed


def _probability_list(values: list[float], field_name: str) -> list[float]:
    return [_probability(value, f"{field_name}[{i}]") for i, value in enumerate(values)]


_FORMAL_STRATEGY_TYPES = frozenset(
    {
        StrategyType.DEDUCTION,
        StrategyType.ELIMINATION,
        StrategyType.MATHEMATICAL_INDUCTION,
        StrategyType.CASE_ANALYSIS,
        StrategyType.ABDUCTION,
        StrategyType.ANALOGY,
        StrategyType.EXTRAPOLATION,
        StrategyType.SUPPORT,
        StrategyType.COMPARE,
    }
)


_SYMMETRIC_OPS = frozenset(
    {
        OperatorType.EQUIVALENCE,
        OperatorType.CONTRADICTION,
        OperatorType.COMPLEMENT,
        OperatorType.DISJUNCTION,
        OperatorType.CONJUNCTION,
    }
)


def _canonical_formal_expr(formal_expr: FormalExpr) -> str:
    """Canonical JSON representation of a FormalExpr for hashing.

    Operators are sorted by their JSON representation to ensure
    order-independent deterministic serialization (spec §3.2).
    Variables are sorted only for symmetric operators; implication
    preserves input order (A→B ≠ B→A).
    """
    ops = []
    for op in formal_expr.operators:
        variables = sorted(op.variables) if op.operator in _SYMMETRIC_OPS else list(op.variables)
        ops.append(
            {
                "operator": op.operator.value,
                "variables": variables,
                "conclusion": op.conclusion,
            }
        )
    ops.sort(key=lambda x: json.dumps(x, sort_keys=True))
    return json.dumps(ops, sort_keys=True, separators=(",", ":"))


class Strategy(BaseModel):
    """Base strategy — leaf reasoning (single ↝).

    Can be instantiated directly for basic strategies (infer, noisy_and).
    """

    strategy_id: str | None = None
    scope: str  # "local"
    type: StrategyType

    # connections
    premises: list[str]  # claim Knowledge IDs
    conclusion: str | None = None  # single output Knowledge (must be claim)
    background: list[str] | None = None  # context Knowledge IDs (any type, not in BP)

    # local layer
    steps: list[Step] | None = None  # reasoning process (local only, None at global)
    conditional_probabilities: list[float] | None = None  # infer/noisy_and CPT parameters
    prior_hypothesis: float | None = None
    prior_evidence: float | None = None
    p_a_given_b: float | None = None
    p_b_given_a: float | None = None
    prior_a: float | None = None
    prior_b: float | None = None

    # traceability
    metadata: dict[str, Any] | None = None

    def _structure_hash(self) -> str:
        """Compute the structure hash component for strategy ID.

        Leaf strategies have empty structure hash.
        """
        return ""

    def formalize(
        self, *, namespace: str | None = None, package_name: str | None = None
    ) -> FormalizationResult:
        """Expand a named leaf Strategy into generated intermediates + FormalStrategy.

        For local scope, ``namespace`` and ``package_name`` are required so that
        generated intermediate Knowledge IDs use QID format.
        """
        from gaia.ir.formalize import formalize_named_strategy

        if isinstance(self, CompositeStrategy):
            raise TypeError("CompositeStrategy cannot be directly formalized")
        if isinstance(self, FormalStrategy):
            raise TypeError("FormalStrategy is already formalized")
        if self.conclusion is None:
            raise ValueError("formalize() requires the strategy to set a conclusion")

        return formalize_named_strategy(
            scope=self.scope,
            type_=self.type,
            premises=self.premises,
            conclusion=self.conclusion,
            namespace=namespace,
            package_name=package_name,
            background=self.background,
            steps=self.steps,
            metadata=self.metadata,
        )

    @model_validator(mode="after")
    def _compute_id_and_validate(self) -> Strategy:
        if self.scope != "local":
            raise ValueError("scope must be 'local'")

        if self.strategy_id is not None:
            if not self.strategy_id.startswith("lcs_"):
                raise ValueError("local strategies must use a strategy_id with lcs_ prefix")

        if self.strategy_id is None:
            self.strategy_id = _compute_strategy_id(
                self.scope,
                self.type,
                self.premises,
                self.conclusion,
                structure_hash=self._structure_hash(),
            )
        if self.conditional_probabilities is not None:
            probabilities = _probability_list(
                self.conditional_probabilities,
                "conditional_probabilities",
            )
            if self.type == StrategyType.INFER:
                expected = 1 << len(self.premises)
                if len(probabilities) != expected:
                    raise ValueError(
                        f"infer strategy with {len(self.premises)} premises requires "
                        f"{expected} conditional_probabilities, got {len(probabilities)}"
                    )
            elif self.type == StrategyType.NOISY_AND:
                if len(probabilities) != 1:
                    raise ValueError(
                        f"noisy_and strategy requires 1 conditional_probability, got {len(probabilities)}"
                    )
            object.__setattr__(self, "conditional_probabilities", probabilities)
        if self.type == StrategyType.INFER and self.__class__.__name__ != "CompositeStrategy":
            if self.prior_hypothesis is not None:
                object.__setattr__(
                    self,
                    "prior_hypothesis",
                    _probability(self.prior_hypothesis, "prior_hypothesis"),
                )
            if self.prior_evidence is not None:
                object.__setattr__(
                    self,
                    "prior_evidence",
                    _probability(self.prior_evidence, "prior_evidence"),
                )
        if self.type == StrategyType.ASSOCIATE and self.__class__.__name__ != "CompositeStrategy":
            if len(self.premises) != 2:
                raise ValueError("associate strategy requires exactly 2 premises")
            if self.conclusion is None:
                raise ValueError("associate strategy requires a helper conclusion")
            if self.p_a_given_b is None or self.p_b_given_a is None:
                raise ValueError("associate strategy requires p_a_given_b and p_b_given_a")
            object.__setattr__(
                self,
                "p_a_given_b",
                _probability(self.p_a_given_b, "p_a_given_b"),
            )
            object.__setattr__(
                self,
                "p_b_given_a",
                _probability(self.p_b_given_a, "p_b_given_a"),
            )
            if self.prior_a is not None:
                object.__setattr__(self, "prior_a", _probability(self.prior_a, "prior_a"))
            if self.prior_b is not None:
                object.__setattr__(self, "prior_b", _probability(self.prior_b, "prior_b"))
        return self

    # No leaf type restriction — per §3.5.1, named strategies (deduction, abduction,
    # etc.) can exist as leaf Strategy before being formalized into FormalStrategy.


class CompositeStrategy(Strategy):
    """Strategy with sub-strategies (by reference), supporting recursive nesting.

    Generic container — any StrategyType is allowed. Sub-strategies are
    referenced by strategy_id strings, not embedded objects.
    """

    sub_strategies: list[str]  # strategy_id references

    def _structure_hash(self) -> str:
        """SHA-256 of sorted sub_strategy IDs."""
        payload = str(sorted(self.sub_strategies))
        return _sha256_hex(payload)

    @model_validator(mode="after")
    def _validate_sub_strategies(self) -> CompositeStrategy:
        if not self.sub_strategies:
            raise ValueError("CompositeStrategy requires at least one sub_strategy")
        return self


class FormalStrategy(Strategy):
    """Strategy with deterministic Operator expansion.

    Used for named strategies (deduction, elimination,
    mathematical_induction, case_analysis, abduction, analogy,
    extrapolation) and as sub-parts of CompositeStrategy.
    """

    formal_expr: FormalExpr

    def _structure_hash(self) -> str:
        """SHA-256 of canonical formal expression."""
        return _sha256_hex(_canonical_formal_expr(self.formal_expr))

    @model_validator(mode="after")
    def _validate_formal_expr(self) -> FormalStrategy:
        if not self.formal_expr.operators:
            raise ValueError("FormalStrategy requires at least one operator in formal_expr")
        if self.type not in _FORMAL_STRATEGY_TYPES:
            allowed = ", ".join(sorted(t.value for t in _FORMAL_STRATEGY_TYPES))
            raise ValueError(
                f"FormalStrategy form only allows types: {allowed}; got {self.type.value}"
            )
        return self
