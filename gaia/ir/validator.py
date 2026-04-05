"""Gaia IR validator — structural validation on every IR update.

Implements issue #233. Validates Knowledge, Operator, Strategy, and graph-level
invariants as defined in docs/foundations/gaia-ir/gaia-ir.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gaia.ir.knowledge import Knowledge, KnowledgeType, is_qid
from gaia.ir.operator import Operator, OperatorType
from gaia.ir.strategy import Strategy, CompositeStrategy, FormalStrategy, StrategyType
from gaia.ir.graphs import LocalCanonicalGraph, _canonical_json
from gaia.ir.parameterization import (
    CROMWELL_EPS,
    PriorRecord,
    StrategyParamRecord,
)


def _parse_qid(qid: str) -> tuple[str, str, str] | None:
    """Parse QID into (namespace, package_name, label). Returns None if not valid QID."""
    parts = qid.split("::", 1)
    if len(parts) != 2:
        return None
    prefix_parts = parts[0].split(":", 1)
    if len(prefix_parts) != 2:
        return None
    return (prefix_parts[0], prefix_parts[1], parts[1])


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
    *,
    graph_namespace: str | None = None,
    graph_package_name: str | None = None,
) -> dict[str, Knowledge]:
    """Validate Knowledge nodes and return id→Knowledge lookup."""
    lookup: dict[str, Knowledge] = {}

    for k in knowledges:
        # ID format check
        if scope == "local":
            if k.id and not is_qid(k.id):
                result.error(
                    f"Knowledge '{k.id}': expected QID format "
                    f"(namespace:package_name::label) in local graph"
                )

        # uniqueness
        if k.id in lookup:
            result.error(f"Knowledge '{k.id}': duplicate ID")
        if k.id:
            lookup[k.id] = k

        # type
        if k.type not in set(KnowledgeType):
            result.error(f"Knowledge '{k.id}': invalid type '{k.type}'")

        # local-layer shape rules
        if scope == "local":
            if k.content is None:
                result.error(f"Knowledge '{k.id}': local layer requires content")

    # label uniqueness check for local scope
    if scope == "local":
        labels = [k.label for k in knowledges if k.label]
        if len(labels) != len(set(labels)):
            seen: set[str] = set()
            for label in labels:
                if label in seen:
                    result.error(f"Knowledge label '{label}': duplicate in local graph")
                seen.add(label)

    # graph namespace is a free-form string (e.g. "github", "paper", "dp")
    # — no validation constraint on allowed values.

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

        if top_level and op.operator_id is not None:
            if not op.operator_id.startswith("lco_"):
                result.error(f"Operator '{op.operator_id}': expected lco_ prefix in {scope} graph")

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

    # scope/prefix checks
    if strategy.scope != scope:
        result.error(f"Strategy '{sid}': scope '{strategy.scope}' incompatible with {scope} graph")
    if strategy.strategy_id and not strategy.strategy_id.startswith("lcs_"):
        result.error(f"Strategy '{sid}': expected lcs_ prefix in {scope} graph")

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
    """Ensure all references use the correct ID format for the scope."""

    def _check_id_format(id_: str, context: str) -> None:
        if id_ and not is_qid(id_):
            result.error(
                f"{context} has wrong format for {scope} graph "
                f"(expected QID namespace:package::label)"
            )

    for s in strategies:
        for pid in s.premises:
            _check_id_format(pid, f"Strategy '{s.strategy_id}': premise '{pid}'")
        if s.conclusion:
            _check_id_format(
                s.conclusion, f"Strategy '{s.strategy_id}': conclusion '{s.conclusion}'"
            )

    def _check_operator_ids(op: Operator, context: str) -> None:
        for var_id in op.variables:
            _check_id_format(var_id, f"{context} '{op.operator_id}': variable '{var_id}'")
        if op.conclusion:
            _check_id_format(
                op.conclusion, f"{context} '{op.operator_id}': conclusion '{op.conclusion}'"
            )

    for op in operators:
        _check_operator_ids(op, "Operator")

    # Also check FormalExpr-embedded operators
    for s in strategies:
        if isinstance(s, FormalStrategy):
            for op in s.formal_expr.operators:
                _check_operator_ids(op, f"FormalStrategy '{s.strategy_id}' operator")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_local_graph(graph: LocalCanonicalGraph) -> ValidationResult:
    """Validate a LocalCanonicalGraph."""
    result = ValidationResult()

    knowledge_lookup = _validate_knowledges(
        graph.knowledges,
        "local",
        result,
        graph_namespace=graph.namespace,
        graph_package_name=graph.package_name,
    )
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


# ---------------------------------------------------------------------------
# 5. Parameterization completeness (pre-BP)
# ---------------------------------------------------------------------------


def validate_parameterization(
    graph: LocalCanonicalGraph,
    priors: list[PriorRecord],
    strategy_params: list[StrategyParamRecord],
) -> ValidationResult:
    """Validate parameterization completeness before BP run.

    Checks that every independent claim Knowledge has at least one PriorRecord
    and every parameterized Strategy (infer/noisy_and) has a StrategyParamRecord.
    FormalStrategy types derive behavior from FormalExpr — no params needed.

    Three categories of claims are excluded from PriorRecord requirements:

    1. **Strategy conclusions** — claims that appear as the conclusion of any
       Strategy. Their belief is derived from premises via BP; they do not need
       independent priors (but may optionally have them).
    2. **Top-level structural helper claims** — conclusions of top-level Operators
       with structural types (conjunction/disjunction/equivalence/contradiction/
       complement). Their truth value is fully determined by the Operator.
       These are PROHIBITED from having independent PriorRecords.
    3. **FormalExpr private nodes** — ANY operator conclusion inside a FormalExpr
       that is NOT in the owning FormalStrategy's premises/conclusion interface.
       Per spec §4 of 04-helper-claims.md, private nodes must not carry
       independent PriorRecord regardless of the operator type.
       These are PROHIBITED from having independent PriorRecords.

    Generated public interface claims (e.g. abduction's AlternativeExplanationForObs)
    are part of the strategy interface, so they remain ordinary claim inputs and
    still require PriorRecord.
    """
    result = ValidationResult()

    # collect claim knowledge_ids
    claim_ids = {k.id for k in graph.knowledges if k.type == KnowledgeType.CLAIM and k.id}

    # --- Identify claims exempt from PriorRecord requirements ---

    # (a) Claims that MUST NOT have PriorRecords (prohibited)
    no_prior_allowed: set[str] = set()

    # Top-level structural helper claims — conclusions of structural operators
    for op in graph.operators:
        if op.operator in _STRUCTURAL_HELPER_OPERATOR_TYPES:
            no_prior_allowed.add(op.conclusion)

    # FormalExpr private nodes — operator conclusions inside FormalExpr
    # that are NOT in the owning strategy's premises/conclusion interface
    for s in graph.strategies:
        if isinstance(s, FormalStrategy):
            own_interface: set[str] = set(s.premises)
            if s.conclusion is not None:
                own_interface.add(s.conclusion)
            for op in s.formal_expr.operators:
                if op.conclusion not in own_interface:
                    no_prior_allowed.add(op.conclusion)

    # (b) Claims that don't NEED PriorRecords but may optionally have them
    # Strategy conclusions — their belief derives from premises via BP
    strategy_conclusions: set[str] = set()
    for s in graph.strategies:
        if s.conclusion is not None:
            strategy_conclusions.add(s.conclusion)

    # Combined: all claims exempt from the "must have prior" check
    prior_exempt = no_prior_allowed | strategy_conclusions

    # collect strategy ids, split by parameterized vs not
    parameterized_ids: set[str] = set()
    all_strategy_ids: set[str] = set()
    for s in graph.strategies:
        if s.strategy_id:
            all_strategy_ids.add(s.strategy_id)
            if isinstance(s, CompositeStrategy):
                continue  # composite delegates to sub-strategies, no own params
            if s.type in _PARAMETERIZED_TYPES:
                parameterized_ids.add(s.strategy_id)

    # check prior coverage (exclude exempt claims)
    prior_knowledge_ids = {r.knowledge_id for r in priors}
    for cid in claim_ids:
        if cid in prior_exempt:
            continue  # derived or structural — no prior needed
        if cid not in prior_knowledge_ids:
            result.error(f"Claim '{cid}': missing PriorRecord")

    # prohibited claims must NOT have PriorRecords (spec §4 of 04-helper-claims.md)
    for r_prior in priors:
        if r_prior.knowledge_id in no_prior_allowed:
            result.error(
                f"PriorRecord '{r_prior.knowledge_id}': private or structural helper claim "
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
                f"PriorRecord '{r.knowledge_id}': value {r.value} outside Cromwell bounds "
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
        if r.knowledge_id not in all_knowledge_ids:
            result.warn(f"PriorRecord '{r.knowledge_id}': references non-existent Knowledge")

    # dangling references: params for non-existent strategies
    for r in strategy_params:
        if r.strategy_id not in all_strategy_ids:
            result.warn(f"StrategyParamRecord '{r.strategy_id}': references non-existent Strategy")

    return result
