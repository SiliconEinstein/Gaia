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
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from gaia.ir.operator import Operator, OperatorType

if TYPE_CHECKING:
    from gaia.ir.formalize import FormalizationResult


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

    # Named strategies — non-deterministic (FormalStrategy)
    ABDUCTION = "abduction"
    ANALOGY = "analogy"
    EXTRAPOLATION = "extrapolation"
    SUPPORT = "support"  # forward implication with a soft warrant
    COMPARE = "compare"  # prediction comparison via matching + inferential ordering

    # Composite strategies — non-atomic
    INDUCTION = "induction"  # CompositeStrategy wrapping shared-conclusion abductions

    # v6 Strategy methods — carriers only in the first implementation phase.
    LIKELIHOOD = "likelihood"
    COMPUTE = "compute"
    OPAQUE_CONDITIONAL = "opaque_conditional"


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


class DeductionMethod(BaseModel):
    """v6 deduction method marker."""

    kind: Literal["deduction"] = "deduction"


class ModuleUseMethod(BaseModel):
    """v6 module instantiation payload, used by likelihood strategies."""

    kind: Literal["module_use"] = "module_use"
    module_ref: str
    input_bindings: dict[str, str]
    output_bindings: dict[str, str]
    premise_bindings: dict[str, str] = {}


class ComputeMethod(BaseModel):
    """v6 deterministic computation payload."""

    kind: Literal["compute"] = "compute"
    function_ref: str
    input_bindings: dict[str, str]
    output: str
    output_binding: dict[str, str] | None = None
    code_hash: str | None = None


class OpaqueConditionalMethod(BaseModel):
    """Legacy escape hatch for opaque conditional probability tables."""

    kind: Literal["opaque_conditional"] = "opaque_conditional"
    parameter_ref: str | None = None
    metadata: dict[str, Any] | None = None


StrategyMethod = Annotated[
    DeductionMethod | ModuleUseMethod | ComputeMethod | OpaqueConditionalMethod,
    Field(discriminator="kind"),
]


class LikelihoodModuleSpec(BaseModel):
    """Machine-readable specification for a standard likelihood module."""

    module_ref: str
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    premise_schema: dict[str, str]
    target_role: str
    score_role: str
    score_value_path: str = "value"
    score_type: Literal["log_lr", "bayes_factor", "likelihood_table", "custom"]
    effect: Literal["add_log_odds", "multiply_odds", "likelihood_table_update"]


class LikelihoodScoreRecord(BaseModel):
    """Model/data-derived likelihood strength consumed by a likelihood Strategy."""

    score_id: str
    module_ref: str
    target: str
    score_type: Literal["log_lr", "bayes_factor", "likelihood_table", "custom"]
    value: Any
    query: str | dict[str, Any] | None = None
    rationale: str | None = None


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


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _v6_strategy_payload_hash(
    method: StrategyMethod | None,
    assertions: list[str],
) -> str:
    payload: dict[str, Any] = {}
    if method is not None:
        payload["method"] = method.model_dump(mode="json", exclude_none=True)
    if assertions:
        payload["assertions"] = sorted(assertions)
    if not payload:
        return ""
    return _sha256_hex(_canonical_json(payload))


def _combine_structure_hashes(*parts: str) -> str:
    non_empty = [p for p in parts if p]
    if not non_empty:
        return ""
    if len(non_empty) == 1:
        return non_empty[0]
    return _sha256_hex(_canonical_json(non_empty))


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
    method: StrategyMethod | None = None
    reason: str | None = None
    assertions: list[str] = []

    # local layer
    steps: list[Step] | None = None  # reasoning process (local only, None at global)

    # traceability
    metadata: dict[str, Any] | None = None

    def _structure_hash(self) -> str:
        """Compute the structure hash component for strategy ID.

        Leaf strategies have empty structure hash unless they use v6 method or assertions.
        """
        return _v6_strategy_payload_hash(self.method, self.assertions)

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
        return _combine_structure_hashes(
            _sha256_hex(payload),
            _v6_strategy_payload_hash(self.method, self.assertions),
        )

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
        return _combine_structure_hashes(
            _sha256_hex(_canonical_formal_expr(self.formal_expr)),
            _v6_strategy_payload_hash(self.method, self.assertions),
        )

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
