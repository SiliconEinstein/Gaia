"""Gaia IR validator — structural validation on every IR update.

Implements issue #233. Validates Knowledge, Operator, Strategy, and graph-level
invariants as defined in docs/foundations/gaia-ir/gaia-ir.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from gaia.ir.graphs import LocalCanonicalGraph, _canonical_json
from gaia.ir.knowledge import (
    Knowledge,
    KnowledgeType,
    is_qid,
    is_structural_expression_helper,
)
from gaia.ir.operator import Operator, OperatorType
from gaia.ir.parameterization import (
    CROMWELL_EPS,
    PriorRecord,
    StrategyParamRecord,
)
from gaia.ir.strategy import CompositeStrategy, FormalStrategy, Strategy, StrategyType


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
    OperatorType.NEGATION,
    OperatorType.DISJUNCTION,
    OperatorType.EQUIVALENCE,
    OperatorType.CONTRADICTION,
    OperatorType.COMPLEMENT,
    OperatorType.IMPLICATION,
}


@dataclass
class ValidationResult:
    """Accumulated structural validation result for Gaia IR objects."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        """Record a validation error and mark the result invalid."""
        self.errors.append(msg)
        self.valid = False

    def warn(self, msg: str) -> None:
        """Record a non-fatal validation warning."""
        self.warnings.append(msg)

    def merge(self, other: ValidationResult) -> None:
        """Merge another validation result into this accumulator."""
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
    del graph_namespace, graph_package_name
    lookup: dict[str, Knowledge] = {}

    for k in knowledges:
        # ID format check
        if scope == "local" and k.id and not is_qid(k.id):
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

        metadata = k.metadata or {}
        if "prior" in metadata:
            prior = metadata["prior"]
            if isinstance(prior, bool) or not isinstance(prior, (int, float)):
                result.error(
                    f"Knowledge '{k.id}': metadata prior must be a number, "
                    f"got {type(prior).__name__}"
                )
            else:
                prior_value = float(prior)
                if not math.isfinite(prior_value):
                    result.error(f"Knowledge '{k.id}': metadata prior must be finite")
                elif prior_value < CROMWELL_EPS or prior_value > 1 - CROMWELL_EPS:
                    result.error(
                        f"Knowledge '{k.id}': metadata prior {prior_value} outside Cromwell bounds "
                        f"[{CROMWELL_EPS}, {1 - CROMWELL_EPS}]"
                    )

        # local-layer shape rules
        if scope == "local" and k.content is None:
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

        if top_level and op.operator_id is not None and not op.operator_id.startswith("lco_"):
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
        else:
            conclusion = knowledge_lookup[op.conclusion]
            metadata = conclusion.metadata or {}
            if is_structural_expression_helper(conclusion) and "prior" in metadata:
                result.error(
                    f"Knowledge '{op.conclusion}': structural helper claim "
                    "must not have metadata prior"
                )

        # conclusion must NOT be in variables (belt-and-suspenders, Pydantic also checks)
        if op.conclusion in op.variables:
            result.error(
                f"Operator '{op.operator_id}': conclusion '{op.conclusion}' "
                "must not be in variables"
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
                f"Strategy '{sid}': premise '{pid}' is "
                f"'{knowledge_lookup[pid].type}', must be claim"
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
                f"CompositeStrategy '{sid}': sub_strategy '{sub_id}' "
                "not found as top-level strategy"
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
    color: dict[str, int] = dict.fromkeys(adj, WHITE)

    def dfs(node: str) -> bool:
        """Returns True if cycle found."""
        color[node] = GRAY
        for nb in adj.get(node, []):
            if nb not in color:
                continue  # non-composite, leaf — no cycle through it
            if color[nb] == GRAY:
                result.error(f"CompositeStrategy cycle detected involving '{node}' -> '{nb}'")
                return True
            if color[nb] == WHITE and dfs(nb):
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
    del knowledge_lookup
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
    color: dict[str, int] = dict.fromkeys(conclusion_to_deps, WHITE)

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
    del knowledge_lookup

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
# 5. Compose validation
# ---------------------------------------------------------------------------


def _validate_composes(
    graph: LocalCanonicalGraph,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    target_ids = set(knowledge_lookup)
    target_ids.update(op.operator_id for op in graph.operators if op.operator_id)
    target_ids.update(strategy.strategy_id for strategy in graph.strategies if strategy.strategy_id)
    compose_ids = {compose.compose_id for compose in graph.composes}
    target_ids.update(compose_ids)
    compose_edges: dict[str, list[str]] = {compose_id: [] for compose_id in compose_ids}

    for compose in graph.composes:
        if not compose.compose_id.startswith("lcm_"):
            result.error(f"Compose '{compose.compose_id}': expected lcm_ prefix in local graph")

        for field_name in ("inputs", "background", "warrants"):
            for ref in getattr(compose, field_name):
                if ref not in knowledge_lookup:
                    result.error(
                        f"Compose '{compose.compose_id}': {field_name} reference "
                        f"'{ref}' not found in graph"
                    )

        if compose.conclusion not in knowledge_lookup:
            result.error(
                f"Compose '{compose.compose_id}': conclusion '{compose.conclusion}' "
                "not found in graph"
            )
        elif knowledge_lookup[compose.conclusion].type != KnowledgeType.CLAIM:
            result.error(
                f"Compose '{compose.compose_id}': conclusion '{compose.conclusion}' is "
                f"'{knowledge_lookup[compose.conclusion].type}', must be claim"
            )

        for action_ref in compose.actions:
            if action_ref not in target_ids:
                result.error(
                    f"Compose '{compose.compose_id}': action target '{action_ref}' "
                    "not found in graph"
                )
                continue
            if action_ref == compose.compose_id:
                result.error(
                    f"Compose '{compose.compose_id}': cannot reference itself as an action"
                )
                continue
            if action_ref in compose_ids:
                compose_edges[compose.compose_id].append(action_ref)

    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def visit(compose_id: str) -> None:
        if compose_id in visited:
            return
        if compose_id in visiting:
            cycle_start = path.index(compose_id)
            cycle = [*path[cycle_start:], compose_id]
            result.error(f"Compose DAG contains cycle: {' -> '.join(cycle)}")
            return

        visiting.add(compose_id)
        path.append(compose_id)
        for child_id in compose_edges.get(compose_id, []):
            visit(child_id)
        path.pop()
        visiting.remove(compose_id)
        visited.add(compose_id)

    for compose_id in compose_ids:
        visit(compose_id)


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
    _validate_composes(graph, knowledge_lookup, result)

    # hash consistency
    if graph.ir_hash is not None:
        recomputed = _canonical_json(
            graph.knowledges,
            graph.operators,
            graph.strategies,
            graph.composes,
        )
        import hashlib

        expected = f"sha256:{hashlib.sha256(recomputed.encode()).hexdigest()}"
        if graph.ir_hash != expected:
            result.error(
                f"LocalCanonicalGraph ir_hash mismatch: stored={graph.ir_hash}, computed={expected}"
            )

    return result


# ---------------------------------------------------------------------------
# 6. Parameterization completeness (pre-BP)
# ---------------------------------------------------------------------------


def _claims_without_prior_requirement(graph: LocalCanonicalGraph) -> tuple[set[str], set[str]]:
    """Return prohibited-prior claims and all prior-exempt claims."""
    no_prior_allowed: set[str] = set()
    for operator in graph.operators:
        if operator.operator in _STRUCTURAL_HELPER_OPERATOR_TYPES:
            no_prior_allowed.add(operator.conclusion)

    for strategy in graph.strategies:
        if not isinstance(strategy, FormalStrategy):
            continue
        own_interface: set[str] = set(strategy.premises)
        if strategy.conclusion is not None:
            own_interface.add(strategy.conclusion)
        for operator in strategy.formal_expr.operators:
            if operator.conclusion not in own_interface:
                no_prior_allowed.add(operator.conclusion)

    strategy_conclusions = {
        strategy.conclusion for strategy in graph.strategies if strategy.conclusion is not None
    }
    return no_prior_allowed, no_prior_allowed | strategy_conclusions


def _parameterized_strategy_ids(graph: LocalCanonicalGraph) -> tuple[set[str], set[str]]:
    """Return all strategy ids and the subset that require parameter records."""
    parameterized_ids: set[str] = set()
    all_strategy_ids: set[str] = set()
    for strategy in graph.strategies:
        if not strategy.strategy_id:
            continue
        all_strategy_ids.add(strategy.strategy_id)
        if isinstance(strategy, CompositeStrategy):
            continue
        if strategy.type in _PARAMETERIZED_TYPES:
            parameterized_ids.add(strategy.strategy_id)
    return all_strategy_ids, parameterized_ids


def _validate_prior_coverage(
    result: ValidationResult,
    *,
    claim_ids: set[str],
    prior_exempt: set[str],
    priors: list[PriorRecord],
) -> None:
    """Validate that independent claims have PriorRecord coverage."""
    prior_knowledge_ids = {record.knowledge_id for record in priors}
    for cid in claim_ids:
        if cid in prior_exempt:
            continue
        if cid not in prior_knowledge_ids:
            result.error(f"Claim '{cid}': missing PriorRecord")


def _validate_prohibited_priors(
    result: ValidationResult,
    *,
    priors: list[PriorRecord],
    no_prior_allowed: set[str],
) -> None:
    """Reject PriorRecords on private or structural helper claims."""
    for prior_record in priors:
        if prior_record.knowledge_id in no_prior_allowed:
            result.error(
                f"PriorRecord '{prior_record.knowledge_id}': private or structural helper claim "
                f"must not have independent PriorRecord"
            )


def _validate_strategy_param_coverage(
    result: ValidationResult,
    *,
    strategy_params: list[StrategyParamRecord],
    all_strategy_ids: set[str],
    parameterized_ids: set[str],
) -> None:
    """Validate StrategyParamRecord coverage and unnecessary records."""
    param_strategy_ids = {record.strategy_id for record in strategy_params}
    for strategy_id in parameterized_ids:
        if strategy_id not in param_strategy_ids:
            result.error(f"Strategy '{strategy_id}': missing StrategyParamRecord")

    for record in strategy_params:
        if record.strategy_id in all_strategy_ids - parameterized_ids:
            result.warn(
                f"StrategyParamRecord '{record.strategy_id}': strategy type is not parameterized "
                f"(only infer/noisy_and need params)"
            )


def _validate_strategy_param_arity(
    result: ValidationResult,
    graph: LocalCanonicalGraph,
    strategy_params: list[StrategyParamRecord],
) -> None:
    """Validate conditional-probability arity for parameterized strategies."""
    strategy_lookup = {
        strategy.strategy_id: strategy for strategy in graph.strategies if strategy.strategy_id
    }
    for strategy_param in strategy_params:
        strategy = strategy_lookup.get(strategy_param.strategy_id)
        if strategy is None or strategy.type not in _PARAMETERIZED_TYPES:
            continue
        actual = len(strategy_param.conditional_probabilities)
        if strategy.type == StrategyType.INFER:
            expected = 2 ** len(strategy.premises)
            if actual != expected:
                result.error(
                    f"StrategyParamRecord '{strategy_param.strategy_id}': infer strategy with "
                    f"{len(strategy.premises)} premises requires "
                    f"2^{len(strategy.premises)}={expected} "
                    f"conditional_probabilities, got {actual}"
                )
        elif strategy.type == StrategyType.NOISY_AND and actual != 1:
            result.error(
                f"StrategyParamRecord '{strategy_param.strategy_id}': noisy_and strategy "
                f"requires 1 conditional_probability, got {actual}"
            )


def _validate_cromwell_bounds(
    result: ValidationResult,
    *,
    priors: list[PriorRecord],
    strategy_params: list[StrategyParamRecord],
) -> None:
    """Validate Cromwell bounds for priors and strategy parameters."""
    for prior_record in priors:
        if prior_record.value < CROMWELL_EPS or prior_record.value > 1 - CROMWELL_EPS:
            result.error(
                f"PriorRecord '{prior_record.knowledge_id}': value {prior_record.value} "
                f"outside Cromwell bounds "
                f"[{CROMWELL_EPS}, {1 - CROMWELL_EPS}]"
            )

    for strategy_param in strategy_params:
        for index, probability in enumerate(strategy_param.conditional_probabilities):
            if probability < CROMWELL_EPS or probability > 1 - CROMWELL_EPS:
                result.error(
                    f"StrategyParamRecord '{strategy_param.strategy_id}': "
                    f"conditional_probabilities[{index}]={probability} outside Cromwell bounds"
                )


def _validate_parameterization_dangling_refs(
    result: ValidationResult,
    *,
    graph: LocalCanonicalGraph,
    priors: list[PriorRecord],
    strategy_params: list[StrategyParamRecord],
    all_strategy_ids: set[str],
) -> None:
    """Warn about parameterization records that reference missing IR objects."""
    all_knowledge_ids = {knowledge.id for knowledge in graph.knowledges if knowledge.id}
    for prior_record in priors:
        if prior_record.knowledge_id not in all_knowledge_ids:
            result.warn(
                f"PriorRecord '{prior_record.knowledge_id}': references non-existent Knowledge"
            )

    for strategy_param in strategy_params:
        if strategy_param.strategy_id not in all_strategy_ids:
            result.warn(
                f"StrategyParamRecord '{strategy_param.strategy_id}': "
                "references non-existent Strategy"
            )


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

    claim_ids = {k.id for k in graph.knowledges if k.type == KnowledgeType.CLAIM and k.id}
    no_prior_allowed, prior_exempt = _claims_without_prior_requirement(graph)
    all_strategy_ids, parameterized_ids = _parameterized_strategy_ids(graph)

    _validate_prior_coverage(result, claim_ids=claim_ids, prior_exempt=prior_exempt, priors=priors)
    _validate_prohibited_priors(result, priors=priors, no_prior_allowed=no_prior_allowed)
    _validate_strategy_param_coverage(
        result,
        strategy_params=strategy_params,
        all_strategy_ids=all_strategy_ids,
        parameterized_ids=parameterized_ids,
    )
    _validate_strategy_param_arity(result, graph, strategy_params)
    _validate_cromwell_bounds(result, priors=priors, strategy_params=strategy_params)
    _validate_parameterization_dangling_refs(
        result,
        graph=graph,
        priors=priors,
        strategy_params=strategy_params,
        all_strategy_ids=all_strategy_ids,
    )

    return result
