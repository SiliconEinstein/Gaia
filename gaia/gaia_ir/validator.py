"""Gaia IR validator — structural validation on every IR update.

Implements issue #233. Validates Knowledge, Operator, Strategy, and graph-level
invariants as defined in docs/foundations/gaia-ir/gaia-ir.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gaia.gaia_ir.knowledge import Knowledge, KnowledgeType
from gaia.gaia_ir.operator import Operator, OperatorType
from gaia.gaia_ir.strategy import Strategy, CompositeStrategy, FormalStrategy, StrategyType
from gaia.gaia_ir.graphs import LocalCanonicalGraph, GlobalCanonicalGraph, _canonical_json
from gaia.gaia_ir.parameterization import (
    CROMWELL_EPS,
    PriorRecord,
    StrategyParamRecord,
)
from gaia.gaia_ir.binding import CanonicalBinding


_PARAMETERIZED_TYPES = {StrategyType.INFER, StrategyType.NOISY_AND}
_STRUCTURAL_HELPER_OPERATOR_TYPES = {
    OperatorType.CONJUNCTION,
    OperatorType.DISJUNCTION,
    OperatorType.EQUIVALENCE,
    OperatorType.CONTRADICTION,
    OperatorType.COMPLEMENT,
}


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
    *,
    top_level: bool,
) -> None:
    """Validate top-level Operators against the knowledge set."""
    for op in operators:
        if top_level and (op.operator_id is None or op.scope is None):
            result.error(
                "Top-level Operator must set both operator_id and scope "
                "(embedded FormalExpr operators may omit them)"
            )

        # operator scope must be compatible with graph scope
        if op.scope is not None and op.scope != scope:
            result.error(
                f"Operator '{op.operator_id}': scope '{op.scope}' incompatible with {scope} graph"
            )

        # reference completeness — variables (inputs only)
        for var_id in op.variables:
            if var_id not in knowledge_lookup:
                result.error(f"Operator '{op.operator_id}': variable '{var_id}' not found in graph")
            elif knowledge_lookup[var_id].type != KnowledgeType.CLAIM:
                result.error(
                    f"Operator '{op.operator_id}': variable '{var_id}' is "
                    f"'{knowledge_lookup[var_id].type}', must be claim"
                )

        # conclusion reference completeness (required str, always present)
        if op.conclusion not in knowledge_lookup:
            result.error(
                f"Operator '{op.operator_id}': conclusion '{op.conclusion}' not found in graph"
            )
        elif knowledge_lookup[op.conclusion].type != KnowledgeType.CLAIM:
            result.error(
                f"Operator '{op.operator_id}': conclusion '{op.conclusion}' is "
                f"'{knowledge_lookup[op.conclusion].type}', must be claim"
            )

        # conclusion must NOT be in variables (belt-and-suspenders, Pydantic also checks)
        if op.conclusion in op.variables:
            result.error(
                f"Operator '{op.operator_id}': conclusion '{op.conclusion}' must not be in variables"
            )


# ---------------------------------------------------------------------------
# 3. Strategy validation
# ---------------------------------------------------------------------------


def _validate_strategy(
    strategy: Strategy,
    knowledge_lookup: dict[str, Knowledge],
    scope: str,
    result: ValidationResult,
    strategy_lookup: dict[str, Strategy] | None = None,
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

    # scope/prefix checks
    prefix = "lcs_" if scope == "local" else "gcs_"
    if strategy.scope != scope:
        result.error(f"Strategy '{sid}': scope '{strategy.scope}' incompatible with {scope} graph")
    if strategy.strategy_id and not strategy.strategy_id.startswith(prefix):
        result.error(f"Strategy '{sid}': expected {prefix} prefix in {scope} graph")

    # form-specific validation
    if isinstance(strategy, CompositeStrategy):
        _validate_composite_sub_strategies(strategy, strategy_lookup, result)

    if isinstance(strategy, FormalStrategy):
        _validate_operators(
            strategy.formal_expr.operators,
            knowledge_lookup,
            scope,
            result,
            top_level=False,
        )
        _validate_formal_expr_closure(strategy, knowledge_lookup, result)


def _validate_composite_sub_strategies(
    strategy: CompositeStrategy,
    strategy_lookup: dict[str, Strategy] | None,
    result: ValidationResult,
) -> None:
    """Validate CompositeStrategy sub_strategy references exist."""
    sid = strategy.strategy_id or "<no-id>"
    if strategy_lookup is None:
        return
    for sub_id in strategy.sub_strategies:
        if sub_id not in strategy_lookup:
            result.error(
                f"CompositeStrategy '{sid}': sub_strategy '{sub_id}' not found as top-level strategy"
            )


def _validate_composite_dag(
    strategies: list[Strategy],
    result: ValidationResult,
) -> None:
    """Check that CompositeStrategy sub_strategy references form a DAG (no cycles)."""
    # Build adjacency: composite strategy_id -> list of sub_strategy_ids
    adj: dict[str, list[str]] = {}
    composite_ids: set[str] = set()
    for s in strategies:
        if isinstance(s, CompositeStrategy) and s.strategy_id:
            adj[s.strategy_id] = list(s.sub_strategies)
            composite_ids.add(s.strategy_id)

    # DFS cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {sid: WHITE for sid in adj}

    def dfs(node: str) -> bool:
        """Returns True if cycle found."""
        color[node] = GRAY
        for nb in adj.get(node, []):
            if nb not in color:
                continue  # non-composite, leaf — no cycle through it
            if color[nb] == GRAY:
                result.error(f"CompositeStrategy cycle detected involving '{node}' -> '{nb}'")
                return True
            if color[nb] == WHITE:
                if dfs(nb):
                    return True
        color[node] = BLACK
        return False

    for sid in adj:
        if color[sid] == WHITE:
            dfs(sid)


def _validate_formal_expr_closure(
    strategy: FormalStrategy,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate FormalExpr reference closure and DAG (§5 of 08-validation.md).

    Each Operator's variables/conclusion must reference one of:
    - The FormalStrategy's premises (interface input)
    - The FormalStrategy's conclusion (interface output)
    - Another Operator's conclusion in the same FormalExpr (internal intermediate)

    Operator conclusion dependencies must form a DAG (no cycles).
    """
    sid = strategy.strategy_id or "<no-id>"
    allowed: set[str] = set(strategy.premises)
    if strategy.conclusion is not None:
        allowed.add(strategy.conclusion)

    # Collect all operator conclusions in this FormalExpr as internal intermediates
    operator_conclusions: set[str] = set()
    for op in strategy.formal_expr.operators:
        operator_conclusions.add(op.conclusion)

    full_allowed = allowed | operator_conclusions

    for op in strategy.formal_expr.operators:
        for var_id in op.variables:
            if var_id not in full_allowed:
                result.error(
                    f"FormalStrategy '{sid}': operator variable '{var_id}' not in "
                    f"strategy premises/conclusion or operator conclusions (reference closure)"
                )
        if op.conclusion not in full_allowed:
            result.error(
                f"FormalStrategy '{sid}': operator conclusion '{op.conclusion}' not in "
                f"strategy premises/conclusion or operator conclusions (reference closure)"
            )

    # DAG check: operator conclusion dependencies must not cycle (§5.3)
    # Build adjacency: conclusion -> set of conclusions it depends on (via variables)
    conclusion_to_deps: dict[str, set[str]] = {}
    for op in strategy.formal_expr.operators:
        deps = {v for v in op.variables if v in operator_conclusions}
        conclusion_to_deps[op.conclusion] = deps

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {c: WHITE for c in conclusion_to_deps}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for dep in conclusion_to_deps.get(node, set()):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                result.error(
                    f"FormalStrategy '{sid}': FormalExpr cycle detected "
                    f"involving '{node}' -> '{dep}'"
                )
                return True
            if color[dep] == WHITE and dfs(dep):
                return True
        color[node] = BLACK
        return False

    for c in conclusion_to_deps:
        if color[c] == WHITE:
            dfs(c)


def _validate_private_node_isolation(
    strategies: list[Strategy],
    operators: list[Operator],
    result: ValidationResult,
) -> None:
    """Validate that internal FormalExpr nodes are not referenced externally.

    A 'private' node is an operator conclusion in a FormalExpr that is NOT in
    the owning FormalStrategy's own premises/conclusion interface. Such nodes
    must not be referenced by any other top-level strategy or top-level operator.
    """
    # Collect private nodes per FormalStrategy: operator conclusions that are NOT
    # in the owning strategy's premises or conclusion
    private_nodes: dict[str, str] = {}  # node_id -> owning strategy_id
    for s in strategies:
        if isinstance(s, FormalStrategy):
            sid = s.strategy_id or "<no-id>"
            own_interface: set[str] = set(s.premises)
            if s.conclusion is not None:
                own_interface.add(s.conclusion)
            for op in s.formal_expr.operators:
                if op.conclusion not in own_interface:
                    private_nodes[op.conclusion] = sid

    # Check: no other strategy references a private node
    for s in strategies:
        sid = s.strategy_id or "<no-id>"
        for pid in s.premises:
            if pid in private_nodes and private_nodes[pid] != sid:
                result.error(
                    f"Strategy '{sid}': premise '{pid}' is a private internal node "
                    f"of FormalStrategy '{private_nodes[pid]}'"
                )
        if s.conclusion is not None and s.conclusion in private_nodes:
            owner = private_nodes[s.conclusion]
            if owner != sid:
                result.error(
                    f"Strategy '{sid}': conclusion '{s.conclusion}' is a private internal node "
                    f"of FormalStrategy '{owner}'"
                )

    # Check: no top-level operator references a private node
    for op in operators:
        oid = op.operator_id or "<no-id>"
        for var_id in op.variables:
            if var_id in private_nodes:
                result.error(
                    f"Operator '{oid}': variable '{var_id}' is a private internal node "
                    f"of FormalStrategy '{private_nodes[var_id]}'"
                )
        if op.conclusion in private_nodes:
            result.error(
                f"Operator '{oid}': conclusion '{op.conclusion}' is a private internal node "
                f"of FormalStrategy '{private_nodes[op.conclusion]}'"
            )


def _validate_strategies(
    strategies: list[Strategy],
    operators: list[Operator],
    knowledge_lookup: dict[str, Knowledge],
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate all top-level Strategies."""
    seen_ids: set[str] = set()
    strategy_lookup: dict[str, Strategy] = {}

    for s in strategies:
        if s.strategy_id:
            strategy_lookup[s.strategy_id] = s

    for s in strategies:
        # uniqueness (top-level only)
        if s.strategy_id and s.strategy_id in seen_ids:
            result.error(f"Strategy '{s.strategy_id}': duplicate ID")
        if s.strategy_id:
            seen_ids.add(s.strategy_id)

        _validate_strategy(s, knowledge_lookup, scope, result, strategy_lookup)

    # DAG check for CompositeStrategy references
    _validate_composite_dag(strategies, result)

    # Private node isolation check (includes top-level operators)
    _validate_private_node_isolation(strategies, operators, result)


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

    def _check_operator_prefix(op: Operator, context: str) -> None:
        for var_id in op.variables:
            if var_id and not var_id.startswith(prefix):
                result.error(
                    f"{context} '{op.operator_id}': variable '{var_id}' has wrong prefix for {scope} graph"
                )
        if op.conclusion and not op.conclusion.startswith(prefix):
            result.error(
                f"{context} '{op.operator_id}': conclusion '{op.conclusion}' has wrong prefix for {scope} graph"
            )

    for op in operators:
        _check_operator_prefix(op, "Operator")

    # Also check FormalExpr-embedded operators
    for s in strategies:
        if isinstance(s, FormalStrategy):
            for op in s.formal_expr.operators:
                _check_operator_prefix(op, f"FormalStrategy '{s.strategy_id}' operator")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_local_graph(graph: LocalCanonicalGraph) -> ValidationResult:
    """Validate a LocalCanonicalGraph."""
    result = ValidationResult()

    knowledge_lookup = _validate_knowledges(graph.knowledges, "local", result)
    _validate_operators(graph.operators, knowledge_lookup, "local", result, top_level=True)
    _validate_strategies(graph.strategies, graph.operators, knowledge_lookup, "local", result)
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
    _validate_operators(graph.operators, knowledge_lookup, "global", result, top_level=True)
    _validate_strategies(graph.strategies, graph.operators, knowledge_lookup, "global", result)
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

    Checks that every non-private claim Knowledge has at least one PriorRecord
    and every parameterized Strategy (infer/noisy_and) has a StrategyParamRecord.
    FormalStrategy types derive behavior from FormalExpr — no params needed.

    Two categories of claims are excluded from PriorRecord requirements and
    PROHIBITED from having independent PriorRecords:
    1. Top-level structural helper claims — conclusions of top-level Operators
       with structural types (conjunction/disjunction/equivalence/contradiction/
       complement). Their truth value is fully determined by the Operator.
    2. FormalExpr private nodes — ANY operator conclusion inside a FormalExpr
       that is NOT in the owning FormalStrategy's premises/conclusion interface.
       Per spec §4 of 04-helper-claims.md, private nodes must not carry
       independent PriorRecord regardless of the operator type.

    Generated public interface claims (e.g. abduction's AlternativeExplanationForObs)
    are part of the strategy interface, so they remain ordinary claim inputs and
    still require PriorRecord.
    """
    result = ValidationResult()

    # collect claim gcn_ids
    claim_ids = {k.id for k in graph.knowledges if k.type == KnowledgeType.CLAIM and k.id}

    # identify claims that must not have independent PriorRecords:

    # (a) top-level structural helper claims — conclusions of structural operators
    no_prior_ids: set[str] = set()
    for op in graph.operators:
        if op.operator in _STRUCTURAL_HELPER_OPERATOR_TYPES:
            no_prior_ids.add(op.conclusion)

    # (b) FormalExpr private nodes — ALL operator conclusions inside FormalExpr
    #     that are NOT in the owning strategy's premises/conclusion interface
    for s in graph.strategies:
        if isinstance(s, FormalStrategy):
            own_interface: set[str] = set(s.premises)
            if s.conclusion is not None:
                own_interface.add(s.conclusion)
            for op in s.formal_expr.operators:
                if op.conclusion not in own_interface:
                    no_prior_ids.add(op.conclusion)

    # collect strategy ids, split by parameterized vs not
    parameterized_ids: set[str] = set()
    all_strategy_ids: set[str] = set()
    for s in graph.strategies:
        if s.strategy_id:
            all_strategy_ids.add(s.strategy_id)
            if s.type in _PARAMETERIZED_TYPES:
                parameterized_ids.add(s.strategy_id)

    # check prior coverage (exclude private/helper claims)
    prior_gcn_ids = {r.gcn_id for r in priors}
    for cid in claim_ids:
        if cid in no_prior_ids:
            continue  # private or structural helper — no prior needed
        if cid not in prior_gcn_ids:
            result.error(f"Claim '{cid}': missing PriorRecord")

    # private/helper claims must NOT have PriorRecords (spec §4 of 04-helper-claims.md)
    for r_prior in priors:
        if r_prior.gcn_id in no_prior_ids:
            result.error(
                f"PriorRecord '{r_prior.gcn_id}': private or structural helper claim "
                f"must not have independent PriorRecord"
            )

    # check strategy param coverage — only for parameterized types
    param_strategy_ids = {r.strategy_id for r in strategy_params}
    for sid in parameterized_ids:
        if sid not in param_strategy_ids:
            result.error(f"Strategy '{sid}': missing StrategyParamRecord")

    # warn if StrategyParamRecord exists for non-parameterized type
    non_parameterized_ids = all_strategy_ids - parameterized_ids
    for r in strategy_params:
        if r.strategy_id in non_parameterized_ids:
            result.warn(
                f"StrategyParamRecord '{r.strategy_id}': strategy type is not parameterized "
                f"(only infer/noisy_and need params)"
            )

    # check conditional_probabilities arity — only for infer/noisy_and
    strategy_lookup = {s.strategy_id: s for s in graph.strategies if s.strategy_id}
    for r in strategy_params:
        s = strategy_lookup.get(r.strategy_id)
        if s is None:
            continue  # dangling ref handled below
        if s.type not in _PARAMETERIZED_TYPES:
            continue  # non-parameterized, already warned
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
        if r.strategy_id not in all_strategy_ids:
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
