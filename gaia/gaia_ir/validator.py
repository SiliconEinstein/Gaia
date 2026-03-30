"""Gaia IR validator — structural validation on every IR update.

Implements issue #233. Validates Knowledge, Operator, Strategy, and graph-level
invariants as defined in docs/foundations/gaia-ir/gaia-ir.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gaia.gaia_ir.knowledge import Knowledge, KnowledgeType
from gaia.gaia_ir.operator import Operator
from gaia.gaia_ir.strategy import Strategy, CompositeStrategy, FormalStrategy, StrategyType
from gaia.gaia_ir.graphs import LocalCanonicalGraph, GlobalCanonicalGraph, _canonical_json
from gaia.gaia_ir.parameterization import (
    CROMWELL_EPS,
    PriorRecord,
    StrategyParamRecord,
)
from gaia.gaia_ir.binding import CanonicalBinding


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
                result.error(f"Knowledge '{k.id}': claim must have content or representative_lcn")

        # local-layer shape rules
        if scope == "local":
            if k.content is None:
                result.error(f"Knowledge '{k.id}': local layer requires content")
            if k.representative_lcn is not None:
                result.error(f"Knowledge '{k.id}': local layer must not set representative_lcn")
            if k.local_members is not None:
                result.error(f"Knowledge '{k.id}': local layer must not set local_members")

    return lookup


# ---------------------------------------------------------------------------
# 2. Operator validation
# ---------------------------------------------------------------------------


def _validate_operators(
    operators: list[Operator],
    knowledge_lookup: dict[str, Knowledge],
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate top-level Operators against the knowledge set."""
    for op in operators:
        # operator scope must be compatible with graph scope
        if op.scope is not None and op.scope != scope:
            result.error(
                f"Operator '{op.operator_id}': scope '{op.scope}' incompatible with {scope} graph"
            )

        # reference completeness
        for var_id in op.variables:
            if var_id not in knowledge_lookup:
                result.error(f"Operator '{op.operator_id}': variable '{var_id}' not found in graph")
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
            result.error(f"Strategy '{sid}': conclusion '{strategy.conclusion}' not found in graph")
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

    # scope/prefix checks (applied to nested strategies too, not just top-level)
    prefix = "lcs_" if scope == "local" else "gcs_"
    if strategy.scope != scope:
        result.error(f"Strategy '{sid}': scope '{strategy.scope}' incompatible with {scope} graph")
    if strategy.strategy_id and not strategy.strategy_id.startswith(prefix):
        result.error(f"Strategy '{sid}': expected {prefix} prefix in {scope} graph")

    # form-specific validation
    if isinstance(strategy, CompositeStrategy):
        for sub in strategy.sub_strategies:
            _validate_strategy(sub, knowledge_lookup, scope, result)

    if isinstance(strategy, FormalStrategy):
        _validate_operators(strategy.formal_expr.operators, knowledge_lookup, scope, result)


def _validate_strategies(
    strategies: list[Strategy],
    knowledge_lookup: dict[str, Knowledge],
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate all top-level Strategies."""
    seen_ids: set[str] = set()

    for s in strategies:
        # uniqueness (top-level only)
        if s.strategy_id and s.strategy_id in seen_ids:
            result.error(f"Strategy '{s.strategy_id}': duplicate ID")
        if s.strategy_id:
            seen_ids.add(s.strategy_id)

        # _validate_strategy handles scope, prefix, references, and recursion
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
    _validate_operators(graph.operators, knowledge_lookup, "local", result)
    _validate_strategies(graph.strategies, knowledge_lookup, "local", result)
    _validate_scope_consistency(
        knowledge_lookup, graph.operators, graph.strategies, "local", result
    )

    # hash consistency
    if graph.ir_hash is not None:
        recomputed = _canonical_json(graph.knowledges, graph.operators, graph.strategies)
        import hashlib

        expected = f"sha256:{hashlib.sha256(recomputed.encode()).hexdigest()}"
        if graph.ir_hash != expected:
            result.error(
                f"LocalCanonicalGraph ir_hash mismatch: stored={graph.ir_hash}, computed={expected}"
            )

    return result


def validate_global_graph(graph: GlobalCanonicalGraph) -> ValidationResult:
    """Validate a GlobalCanonicalGraph."""
    result = ValidationResult()

    knowledge_lookup = _validate_knowledges(graph.knowledges, "global", result)
    _validate_operators(graph.operators, knowledge_lookup, "global", result)
    _validate_strategies(graph.strategies, knowledge_lookup, "global", result)
    _validate_scope_consistency(
        knowledge_lookup, graph.operators, graph.strategies, "global", result
    )

    return result


# ---------------------------------------------------------------------------
# 5. Parameterization completeness (pre-BP)
# ---------------------------------------------------------------------------


def validate_parameterization(
    graph: GlobalCanonicalGraph,
    priors: list[PriorRecord],
    strategy_params: list[StrategyParamRecord],
) -> ValidationResult:
    """Validate parameterization completeness before BP run.

    Checks that every claim Knowledge has at least one PriorRecord and every
    Strategy has at least one StrategyParamRecord, and all values are within
    Cromwell bounds.
    """
    result = ValidationResult()

    # collect claim gcn_ids
    claim_ids = {k.id for k in graph.knowledges if k.type == KnowledgeType.CLAIM and k.id}

    # collect strategy ids
    strategy_ids: set[str] = set()
    for s in graph.strategies:
        if s.strategy_id:
            strategy_ids.add(s.strategy_id)

    # check prior coverage
    prior_gcn_ids = {r.gcn_id for r in priors}
    for cid in claim_ids:
        if cid not in prior_gcn_ids:
            result.error(f"Claim '{cid}': missing PriorRecord")

    # check strategy param coverage
    param_strategy_ids = {r.strategy_id for r in strategy_params}
    for sid in strategy_ids:
        if sid not in param_strategy_ids:
            result.error(f"Strategy '{sid}': missing StrategyParamRecord")

    # check conditional_probabilities arity
    strategy_lookup = {s.strategy_id: s for s in graph.strategies if s.strategy_id}
    for r in strategy_params:
        s = strategy_lookup.get(r.strategy_id)
        if s is None:
            continue  # dangling ref handled below
        actual = len(r.conditional_probabilities)
        if s.type == StrategyType.INFER:
            expected = 2 ** len(s.premises)
            if actual != expected:
                result.error(
                    f"StrategyParamRecord '{r.strategy_id}': infer strategy with "
                    f"{len(s.premises)} premises requires 2^{len(s.premises)}={expected} "
                    f"conditional_probabilities, got {actual}"
                )
        elif s.type == StrategyType.NOISY_AND:
            if actual != 1:
                result.error(
                    f"StrategyParamRecord '{r.strategy_id}': noisy_and strategy "
                    f"requires 1 conditional_probability, got {actual}"
                )
        else:
            # named strategies (folded): 1 parameter
            if actual != 1:
                result.error(
                    f"StrategyParamRecord '{r.strategy_id}': {s.type} strategy "
                    f"requires 1 conditional_probability, got {actual}"
                )

    # Cromwell bounds on priors
    for r in priors:
        if r.value < CROMWELL_EPS or r.value > 1 - CROMWELL_EPS:
            result.error(
                f"PriorRecord '{r.gcn_id}': value {r.value} outside Cromwell bounds "
                f"[{CROMWELL_EPS}, {1 - CROMWELL_EPS}]"
            )

    # Cromwell bounds on strategy params
    for r in strategy_params:
        for i, p in enumerate(r.conditional_probabilities):
            if p < CROMWELL_EPS or p > 1 - CROMWELL_EPS:
                result.error(
                    f"StrategyParamRecord '{r.strategy_id}': "
                    f"conditional_probabilities[{i}]={p} outside Cromwell bounds"
                )

    # dangling references: priors for non-existent claims
    all_knowledge_ids = {k.id for k in graph.knowledges if k.id}
    for r in priors:
        if r.gcn_id not in all_knowledge_ids:
            result.warn(f"PriorRecord '{r.gcn_id}': references non-existent Knowledge")

    # dangling references: params for non-existent strategies
    for r in strategy_params:
        if r.strategy_id not in strategy_ids:
            result.warn(f"StrategyParamRecord '{r.strategy_id}': references non-existent Strategy")

    return result


# ---------------------------------------------------------------------------
# 6. CanonicalBinding validation
# ---------------------------------------------------------------------------


def validate_bindings(
    bindings: list[CanonicalBinding],
    local_graph: LocalCanonicalGraph,
    global_graph: GlobalCanonicalGraph,
) -> ValidationResult:
    """Validate CanonicalBindings between local and global graphs.

    Checks completeness (every local Knowledge has exactly one binding) and
    reference validity (both local and global IDs exist).
    """
    result = ValidationResult()

    local_ids = {k.id for k in local_graph.knowledges if k.id}
    global_ids = {k.id for k in global_graph.knowledges if k.id}

    # track which local IDs have bindings
    bound_local_ids: dict[str, int] = {}
    for b in bindings:
        bound_local_ids[b.local_canonical_id] = bound_local_ids.get(b.local_canonical_id, 0) + 1

    # every local Knowledge must have exactly one binding
    for lid in local_ids:
        count = bound_local_ids.get(lid, 0)
        if count == 0:
            result.error(f"Knowledge '{lid}': no CanonicalBinding")
        elif count > 1:
            result.error(f"Knowledge '{lid}': {count} bindings (expected exactly 1)")

    # binding references must be valid
    for b in bindings:
        if b.local_canonical_id not in local_ids:
            result.error(
                f"CanonicalBinding: local_canonical_id '{b.local_canonical_id}' "
                f"not found in local graph"
            )
        if b.global_canonical_id not in global_ids:
            result.error(
                f"CanonicalBinding: global_canonical_id '{b.global_canonical_id}' "
                f"not found in global graph"
            )

    return result
