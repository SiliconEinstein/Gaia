"""Gaia IR validator — structural validation on every IR update.

Implements issue #233. Validates Knowledge, Operator, Strategy, and graph-level
invariants as defined in docs/foundations/gaia-ir/gaia-ir.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gaia.gaia_ir.knowledge import Knowledge, KnowledgeType
from gaia.gaia_ir.operator import Operator, OperatorType
from gaia.gaia_ir.strategy import Strategy, CompositeStrategy, FormalStrategy
from gaia.gaia_ir.graphs import LocalCanonicalGraph, GlobalCanonicalGraph, _canonical_json


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def merge(self, other: ValidationResult) -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.valid:
            self.valid = False


# ---------------------------------------------------------------------------
# 1. Knowledge validation
# ---------------------------------------------------------------------------


def _validate_knowledges(
    knowledges: list[Knowledge],
    scope: str,
    result: ValidationResult,
) -> dict[str, Knowledge]:
    """Validate Knowledge nodes and return id→Knowledge lookup."""
    prefix = "lcn_" if scope == "local" else "gcn_"
    lookup: dict[str, Knowledge] = {}

    for k in knowledges:
        # ID prefix
        if k.id and not k.id.startswith(prefix):
            result.error(f"Knowledge '{k.id}': expected {prefix} prefix in {scope} graph")

        # uniqueness
        if k.id in lookup:
            result.error(f"Knowledge '{k.id}': duplicate ID")
        if k.id:
            lookup[k.id] = k

        # type
        if k.type not in set(KnowledgeType):
            result.error(f"Knowledge '{k.id}': invalid type '{k.type}'")

        # claim content completeness
        if k.type == KnowledgeType.CLAIM:
            if k.content is None and k.representative_lcn is None:
                result.error(
                    f"Knowledge '{k.id}': claim must have content or representative_lcn"
                )

    return lookup


# ---------------------------------------------------------------------------
# 2. Operator validation
# ---------------------------------------------------------------------------


def _validate_operators(
    operators: list[Operator],
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate top-level Operators against the knowledge set."""
    for op in operators:
        # reference completeness
        for var_id in op.variables:
            if var_id not in knowledge_lookup:
                result.error(
                    f"Operator '{op.operator_id}': variable '{var_id}' not found in graph"
                )
            elif knowledge_lookup[var_id].type != KnowledgeType.CLAIM:
                result.error(
                    f"Operator '{op.operator_id}': variable '{var_id}' is "
                    f"'{knowledge_lookup[var_id].type}', must be claim"
                )

        # conclusion in variables (Pydantic also checks this, but belt-and-suspenders at graph level)
        if op.conclusion is not None and op.conclusion not in op.variables:
            result.error(
                f"Operator '{op.operator_id}': conclusion '{op.conclusion}' not in variables"
            )


# ---------------------------------------------------------------------------
# 3. Strategy validation
# ---------------------------------------------------------------------------


def _validate_strategy(
    strategy: Strategy,
    knowledge_lookup: dict[str, Knowledge],
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate a single Strategy (any form) against the knowledge set."""
    sid = strategy.strategy_id or "<no-id>"

    # premise reference + type
    for pid in strategy.premises:
        if pid not in knowledge_lookup:
            result.error(f"Strategy '{sid}': premise '{pid}' not found in graph")
        elif knowledge_lookup[pid].type != KnowledgeType.CLAIM:
            result.error(
                f"Strategy '{sid}': premise '{pid}' is '{knowledge_lookup[pid].type}', must be claim"
            )

    # conclusion reference + type
    if strategy.conclusion is not None:
        if strategy.conclusion not in knowledge_lookup:
            result.error(
                f"Strategy '{sid}': conclusion '{strategy.conclusion}' not found in graph"
            )
        elif knowledge_lookup[strategy.conclusion].type != KnowledgeType.CLAIM:
            result.error(
                f"Strategy '{sid}': conclusion '{strategy.conclusion}' is "
                f"'{knowledge_lookup[strategy.conclusion].type}', must be claim"
            )

    # no self-loop
    if strategy.conclusion is not None and strategy.conclusion in strategy.premises:
        result.error(f"Strategy '{sid}': conclusion in premises (self-loop)")

    # background reference (any type OK, just must exist)
    if strategy.background:
        for bid in strategy.background:
            if bid not in knowledge_lookup:
                result.warn(f"Strategy '{sid}': background '{bid}' not found in graph")

    # global strategies must not have steps
    if scope == "global" and strategy.steps is not None:
        result.error(f"Strategy '{sid}': global strategy must not have steps")

    # form-specific validation
    if isinstance(strategy, CompositeStrategy):
        for sub in strategy.sub_strategies:
            _validate_strategy(sub, knowledge_lookup, scope, result)

    if isinstance(strategy, FormalStrategy):
        _validate_operators(strategy.formal_expr.operators, knowledge_lookup, result)


def _validate_strategies(
    strategies: list[Strategy],
    knowledge_lookup: dict[str, Knowledge],
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate all top-level Strategies."""
    prefix = "lcs_" if scope == "local" else "gcs_"
    seen_ids: set[str] = set()

    for s in strategies:
        # ID prefix
        if s.strategy_id and not s.strategy_id.startswith(prefix):
            result.error(
                f"Strategy '{s.strategy_id}': expected {prefix} prefix in {scope} graph"
            )

        # uniqueness
        if s.strategy_id and s.strategy_id in seen_ids:
            result.error(f"Strategy '{s.strategy_id}': duplicate ID")
        if s.strategy_id:
            seen_ids.add(s.strategy_id)

        _validate_strategy(s, knowledge_lookup, scope, result)


# ---------------------------------------------------------------------------
# 4. Graph-level validation
# ---------------------------------------------------------------------------


def _validate_scope_consistency(
    knowledge_lookup: dict[str, Knowledge],
    operators: list[Operator],
    strategies: list[Strategy],
    scope: str,
    result: ValidationResult,
) -> None:
    """Ensure all references use the correct ID prefix for the scope."""
    prefix = "lcn_" if scope == "local" else "gcn_"

    for s in strategies:
        for pid in s.premises:
            if pid and not pid.startswith(prefix):
                result.error(
                    f"Strategy '{s.strategy_id}': premise '{pid}' has wrong prefix for {scope} graph"
                )
        if s.conclusion and not s.conclusion.startswith(prefix):
            result.error(
                f"Strategy '{s.strategy_id}': conclusion '{s.conclusion}' has wrong prefix for {scope} graph"
            )

    for op in operators:
        for var_id in op.variables:
            if var_id and not var_id.startswith(prefix):
                result.error(
                    f"Operator '{op.operator_id}': variable '{var_id}' has wrong prefix for {scope} graph"
                )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_local_graph(graph: LocalCanonicalGraph) -> ValidationResult:
    """Validate a LocalCanonicalGraph."""
    result = ValidationResult()

    knowledge_lookup = _validate_knowledges(graph.knowledges, "local", result)
    _validate_operators(graph.operators, knowledge_lookup, result)
    _validate_strategies(graph.strategies, knowledge_lookup, "local", result)
    _validate_scope_consistency(knowledge_lookup, graph.operators, graph.strategies, "local", result)

    # hash consistency
    if graph.ir_hash is not None:
        recomputed = _canonical_json(graph.knowledges, graph.operators, graph.strategies)
        import hashlib
        expected = f"sha256:{hashlib.sha256(recomputed.encode()).hexdigest()}"
        if graph.ir_hash != expected:
            result.error(f"LocalCanonicalGraph ir_hash mismatch: stored={graph.ir_hash}, computed={expected}")

    return result


def validate_global_graph(graph: GlobalCanonicalGraph) -> ValidationResult:
    """Validate a GlobalCanonicalGraph."""
    result = ValidationResult()

    knowledge_lookup = _validate_knowledges(graph.knowledges, "global", result)
    _validate_operators(graph.operators, knowledge_lookup, result)
    _validate_strategies(graph.strategies, knowledge_lookup, "global", result)
    _validate_scope_consistency(knowledge_lookup, graph.operators, graph.strategies, "global", result)

    return result
