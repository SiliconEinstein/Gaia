"""Gaia IR validator — structural validation on every IR update.

Implements issue #233. Validates Knowledge, Operator, Strategy, and graph-level
invariants as defined in docs/foundations/gaia-ir/gaia-ir.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from gaia.engine.ir.compose import Compose
from gaia.engine.ir.formula import FormulaGraph, formula_node_id
from gaia.engine.ir.graphs import LocalCanonicalGraph, _canonical_json
from gaia.engine.ir.knowledge import (
    Knowledge,
    KnowledgeType,
    is_qid,
    is_structural_expression_helper,
)
from gaia.engine.ir.operator import Operator, OperatorType
from gaia.engine.ir.parameterization import (
    CROMWELL_EPS,
    PriorRecord,
)
from gaia.engine.ir.strategy import CompositeStrategy, FormalStrategy, Strategy


def _parse_qid(qid: str) -> tuple[str, str, str] | None:
    """Parse QID into (namespace, package_name, label). Returns None if not valid QID."""
    parts = qid.split("::", 1)
    if len(parts) != 2:
        return None
    prefix_parts = parts[0].split(":", 1)
    if len(prefix_parts) != 2:
        return None
    return (prefix_parts[0], prefix_parts[1], parts[1])


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


def _validate_knowledge_id_and_uniqueness(
    knowledge: Knowledge,
    scope: str,
    lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate QID shape and duplicate Knowledge IDs."""
    if scope == "local" and knowledge.id and not is_qid(knowledge.id):
        result.error(
            f"Knowledge '{knowledge.id}': expected QID format "
            f"(namespace:package_name::label) in local graph"
        )

    if knowledge.id in lookup:
        result.error(f"Knowledge '{knowledge.id}': duplicate ID")
    if knowledge.id:
        lookup[knowledge.id] = knowledge


def _validate_metadata_prior(knowledge: Knowledge, result: ValidationResult) -> None:
    """Validate legacy metadata prior shape and Cromwell bounds."""
    metadata = knowledge.metadata or {}
    if "prior" not in metadata:
        return

    prior = metadata["prior"]
    if isinstance(prior, bool) or not isinstance(prior, (int, float)):
        result.error(
            f"Knowledge '{knowledge.id}': metadata prior must be a number, "
            f"got {type(prior).__name__}"
        )
        return

    prior_value = float(prior)
    if not math.isfinite(prior_value):
        result.error(f"Knowledge '{knowledge.id}': metadata prior must be finite")
    elif prior_value < CROMWELL_EPS or prior_value > 1 - CROMWELL_EPS:
        result.error(
            f"Knowledge '{knowledge.id}': metadata prior {prior_value} outside Cromwell bounds "
            f"[{CROMWELL_EPS}, {1 - CROMWELL_EPS}]"
        )


def _validate_knowledge_node(
    knowledge: Knowledge,
    scope: str,
    lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate one Knowledge node and update the ID lookup."""
    _validate_knowledge_id_and_uniqueness(knowledge, scope, lookup, result)

    if knowledge.type not in set(KnowledgeType):
        result.error(f"Knowledge '{knowledge.id}': invalid type '{knowledge.type}'")

    _validate_metadata_prior(knowledge, result)

    if scope == "local" and knowledge.content is None:
        result.error(f"Knowledge '{knowledge.id}': local layer requires content")


def _validate_local_label_uniqueness(
    knowledges: list[Knowledge],
    result: ValidationResult,
) -> None:
    """Validate local graph label uniqueness."""
    labels = [knowledge.label for knowledge in knowledges if knowledge.label]
    if len(labels) == len(set(labels)):
        return

    seen: set[str] = set()
    for label in labels:
        if label in seen:
            result.error(f"Knowledge label '{label}': duplicate in local graph")
        seen.add(label)


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

    for knowledge in knowledges:
        _validate_knowledge_node(knowledge, scope, lookup, result)

    # label uniqueness check for local scope
    if scope == "local":
        _validate_local_label_uniqueness(knowledges, result)

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


def _validate_strategy_premises(
    strategy: Strategy,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate Strategy premise references and claim types."""
    sid = strategy.strategy_id or "<no-id>"
    for pid in strategy.premises:
        if pid not in knowledge_lookup:
            result.error(f"Strategy '{sid}': premise '{pid}' not found in graph")
        elif knowledge_lookup[pid].type != KnowledgeType.CLAIM:
            result.error(
                f"Strategy '{sid}': premise '{pid}' is "
                f"'{knowledge_lookup[pid].type}', must be claim"
            )


def _validate_strategy_conclusion(
    strategy: Strategy,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate Strategy conclusion reference, type, and self-loop."""
    sid = strategy.strategy_id or "<no-id>"
    if strategy.conclusion is not None:
        if strategy.conclusion not in knowledge_lookup:
            result.error(f"Strategy '{sid}': conclusion '{strategy.conclusion}' not found in graph")
        elif knowledge_lookup[strategy.conclusion].type != KnowledgeType.CLAIM:
            result.error(
                f"Strategy '{sid}': conclusion '{strategy.conclusion}' is "
                f"'{knowledge_lookup[strategy.conclusion].type}', must be claim"
            )

    if strategy.conclusion is not None and strategy.conclusion in strategy.premises:
        result.error(f"Strategy '{sid}': conclusion in premises (self-loop)")


def _validate_strategy_background_refs(
    strategy: Strategy,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate Strategy background references when present."""
    if not strategy.background:
        return
    sid = strategy.strategy_id or "<no-id>"
    for bid in strategy.background:
        if bid not in knowledge_lookup:
            result.warn(f"Strategy '{sid}': background '{bid}' not found in graph")


def _validate_strategy_scope_and_prefix(
    strategy: Strategy,
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate Strategy scope compatibility and local ID prefix."""
    sid = strategy.strategy_id or "<no-id>"
    if strategy.scope != scope:
        result.error(f"Strategy '{sid}': scope '{strategy.scope}' incompatible with {scope} graph")
    if strategy.strategy_id and not strategy.strategy_id.startswith("lcs_"):
        result.error(f"Strategy '{sid}': expected lcs_ prefix in {scope} graph")


def _validate_form_strategy_operators(
    strategy: FormalStrategy,
    knowledge_lookup: dict[str, Knowledge],
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate FormalStrategy embedded operators and closure."""
    _validate_operators(
        strategy.formal_expr.operators,
        knowledge_lookup,
        scope,
        result,
        top_level=False,
    )
    _validate_formal_expr_closure(strategy, knowledge_lookup, result)


def _validate_strategy(
    strategy: Strategy,
    knowledge_lookup: dict[str, Knowledge],
    scope: str,
    result: ValidationResult,
    strategy_lookup: dict[str, Strategy] | None = None,
) -> None:
    """Validate a single Strategy (any form) against the knowledge set."""
    _validate_strategy_premises(strategy, knowledge_lookup, result)
    _validate_strategy_conclusion(strategy, knowledge_lookup, result)
    _validate_strategy_background_refs(strategy, knowledge_lookup, result)
    _validate_strategy_scope_and_prefix(strategy, scope, result)

    # form-specific validation
    if isinstance(strategy, CompositeStrategy):
        _validate_composite_sub_strategies(strategy, strategy_lookup, result)

    if isinstance(strategy, FormalStrategy):
        _validate_form_strategy_operators(strategy, knowledge_lookup, scope, result)


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


def _formal_expr_reference_sets(strategy: FormalStrategy) -> tuple[set[str], set[str]]:
    """Return full allowed refs and operator conclusions for a FormalExpr."""
    allowed: set[str] = set(strategy.premises)
    if strategy.conclusion is not None:
        allowed.add(strategy.conclusion)

    operator_conclusions = {op.conclusion for op in strategy.formal_expr.operators}
    return allowed | operator_conclusions, operator_conclusions


def _validate_formal_expr_references(
    strategy: FormalStrategy,
    full_allowed: set[str],
    result: ValidationResult,
) -> None:
    """Validate FormalExpr variables and conclusions are reference-closed."""
    sid = strategy.strategy_id or "<no-id>"
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


def _validate_formal_expr_dag(
    strategy: FormalStrategy,
    operator_conclusions: set[str],
    result: ValidationResult,
) -> None:
    """Validate that FormalExpr operator conclusion dependencies form a DAG."""
    sid = strategy.strategy_id or "<no-id>"
    conclusion_to_deps: dict[str, set[str]] = {}
    for op in strategy.formal_expr.operators:
        conclusion_to_deps[op.conclusion] = {v for v in op.variables if v in operator_conclusions}

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

    for conclusion in conclusion_to_deps:
        if color[conclusion] == WHITE:
            dfs(conclusion)


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
    full_allowed, operator_conclusions = _formal_expr_reference_sets(strategy)
    _validate_formal_expr_references(strategy, full_allowed, result)
    _validate_formal_expr_dag(strategy, operator_conclusions, result)


def _collect_private_formal_nodes(strategies: list[Strategy]) -> dict[str, str]:
    """Map private FormalExpr node IDs to their owning strategy IDs."""
    private_nodes: dict[str, str] = {}
    for strategy in strategies:
        if not isinstance(strategy, FormalStrategy):
            continue
        sid = strategy.strategy_id or "<no-id>"
        own_interface: set[str] = set(strategy.premises)
        if strategy.conclusion is not None:
            own_interface.add(strategy.conclusion)
        for op in strategy.formal_expr.operators:
            if op.conclusion not in own_interface:
                private_nodes[op.conclusion] = sid
    return private_nodes


def _validate_strategy_private_refs(
    strategy: Strategy,
    private_nodes: dict[str, str],
    result: ValidationResult,
) -> None:
    """Validate one Strategy does not reference another strategy's private nodes."""
    sid = strategy.strategy_id or "<no-id>"
    for pid in strategy.premises:
        if pid in private_nodes and private_nodes[pid] != sid:
            result.error(
                f"Strategy '{sid}': premise '{pid}' is a private internal node "
                f"of FormalStrategy '{private_nodes[pid]}'"
            )
    if strategy.conclusion is not None and strategy.conclusion in private_nodes:
        owner = private_nodes[strategy.conclusion]
        if owner != sid:
            result.error(
                f"Strategy '{sid}': conclusion '{strategy.conclusion}' is a private internal node "
                f"of FormalStrategy '{owner}'"
            )


def _validate_operator_private_refs(
    operator: Operator,
    private_nodes: dict[str, str],
    result: ValidationResult,
) -> None:
    """Validate one top-level Operator does not reference private FormalExpr nodes."""
    oid = operator.operator_id or "<no-id>"
    for var_id in operator.variables:
        if var_id in private_nodes:
            result.error(
                f"Operator '{oid}': variable '{var_id}' is a private internal node "
                f"of FormalStrategy '{private_nodes[var_id]}'"
            )
    if operator.conclusion in private_nodes:
        result.error(
            f"Operator '{oid}': conclusion '{operator.conclusion}' is a private internal node "
            f"of FormalStrategy '{private_nodes[operator.conclusion]}'"
        )


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
    private_nodes = _collect_private_formal_nodes(strategies)

    # Check: no other strategy references a private node
    for strategy in strategies:
        _validate_strategy_private_refs(strategy, private_nodes, result)

    # Check: no top-level operator references a private node
    for operator in operators:
        _validate_operator_private_refs(operator, private_nodes, result)


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


def _check_local_id_format(id_: str, context: str, scope: str, result: ValidationResult) -> None:
    """Validate a local graph reference uses QID format."""
    if id_ and not is_qid(id_):
        result.error(
            f"{context} has wrong format for {scope} graph (expected QID namespace:package::label)"
        )


def _validate_strategy_id_formats(
    strategies: list[Strategy],
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate Strategy premise and conclusion ID formats."""
    for strategy in strategies:
        for pid in strategy.premises:
            _check_local_id_format(
                pid,
                f"Strategy '{strategy.strategy_id}': premise '{pid}'",
                scope,
                result,
            )
        if strategy.conclusion:
            _check_local_id_format(
                strategy.conclusion,
                f"Strategy '{strategy.strategy_id}': conclusion '{strategy.conclusion}'",
                scope,
                result,
            )


def _validate_operator_id_formats(
    operator: Operator,
    context: str,
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate one Operator's variable and conclusion ID formats."""
    for var_id in operator.variables:
        _check_local_id_format(
            var_id,
            f"{context} '{operator.operator_id}': variable '{var_id}'",
            scope,
            result,
        )
    if operator.conclusion:
        _check_local_id_format(
            operator.conclusion,
            f"{context} '{operator.operator_id}': conclusion '{operator.conclusion}'",
            scope,
            result,
        )


def _validate_formal_expr_id_formats(
    strategies: list[Strategy],
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate ID formats for FormalExpr-embedded operators."""
    for strategy in strategies:
        if not isinstance(strategy, FormalStrategy):
            continue
        for operator in strategy.formal_expr.operators:
            _validate_operator_id_formats(
                operator,
                f"FormalStrategy '{strategy.strategy_id}' operator",
                scope,
                result,
            )


def _validate_scope_consistency(
    knowledge_lookup: dict[str, Knowledge],
    operators: list[Operator],
    strategies: list[Strategy],
    scope: str,
    result: ValidationResult,
) -> None:
    """Ensure all references use the correct ID format for the scope."""
    del knowledge_lookup

    _validate_strategy_id_formats(strategies, scope, result)
    for operator in operators:
        _validate_operator_id_formats(operator, "Operator", scope, result)
    _validate_formal_expr_id_formats(strategies, scope, result)


# ---------------------------------------------------------------------------
# 5. Compose validation
# ---------------------------------------------------------------------------


def _compose_validation_indexes(
    graph: LocalCanonicalGraph,
    knowledge_lookup: dict[str, Knowledge],
) -> tuple[set[str], set[str], dict[str, list[str]]]:
    """Build valid compose action targets and compose adjacency indexes."""
    target_ids = set(knowledge_lookup)
    target_ids.update(op.operator_id for op in graph.operators if op.operator_id)
    target_ids.update(strategy.strategy_id for strategy in graph.strategies if strategy.strategy_id)
    compose_ids = {compose.compose_id for compose in graph.composes}
    target_ids.update(compose_ids)
    compose_edges: dict[str, list[str]] = {compose_id: [] for compose_id in compose_ids}
    return target_ids, compose_ids, compose_edges


def _validate_compose_reference_fields(
    compose: Compose,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate compose inputs/background/warrants reference Knowledge nodes."""
    for field_name in ("inputs", "background", "warrants"):
        for ref in getattr(compose, field_name):
            if ref not in knowledge_lookup:
                result.error(
                    f"Compose '{compose.compose_id}': {field_name} reference "
                    f"'{ref}' not found in graph"
                )


def _validate_compose_conclusion(
    compose: Compose,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate compose conclusion exists and references a claim."""
    if compose.conclusion not in knowledge_lookup:
        result.error(
            f"Compose '{compose.compose_id}': conclusion '{compose.conclusion}' not found in graph"
        )
    elif knowledge_lookup[compose.conclusion].type != KnowledgeType.CLAIM:
        result.error(
            f"Compose '{compose.compose_id}': conclusion '{compose.conclusion}' is "
            f"'{knowledge_lookup[compose.conclusion].type}', must be claim"
        )


def _validate_compose_action_ref(
    compose: Compose,
    action_ref: str,
    target_ids: set[str],
    compose_ids: set[str],
    compose_edges: dict[str, list[str]],
    result: ValidationResult,
) -> None:
    """Validate one compose action target and record compose-to-compose edges."""
    if action_ref not in target_ids:
        result.error(
            f"Compose '{compose.compose_id}': action target '{action_ref}' not found in graph"
        )
        return
    if action_ref == compose.compose_id:
        result.error(f"Compose '{compose.compose_id}': cannot reference itself as an action")
        return
    if action_ref in compose_ids:
        compose_edges[compose.compose_id].append(action_ref)


def _validate_one_compose(
    compose: Compose,
    knowledge_lookup: dict[str, Knowledge],
    target_ids: set[str],
    compose_ids: set[str],
    compose_edges: dict[str, list[str]],
    result: ValidationResult,
) -> None:
    """Validate one Compose record and collect nested compose edges."""
    if not compose.compose_id.startswith("lcm_"):
        result.error(f"Compose '{compose.compose_id}': expected lcm_ prefix in local graph")

    _validate_compose_reference_fields(compose, knowledge_lookup, result)
    _validate_compose_conclusion(compose, knowledge_lookup, result)
    for action_ref in compose.actions:
        _validate_compose_action_ref(
            compose,
            action_ref,
            target_ids,
            compose_ids,
            compose_edges,
            result,
        )


def _validate_compose_dag(
    compose_ids: set[str],
    compose_edges: dict[str, list[str]],
    result: ValidationResult,
) -> None:
    """Validate compose-to-compose action references form a DAG."""
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


def _validate_composes(
    graph: LocalCanonicalGraph,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate Compose records, references, and nested compose DAGs."""
    target_ids, compose_ids, compose_edges = _compose_validation_indexes(graph, knowledge_lookup)

    for compose in graph.composes:
        _validate_one_compose(
            compose,
            knowledge_lookup,
            target_ids,
            compose_ids,
            compose_edges,
            result,
        )

    _validate_compose_dag(compose_ids, compose_edges, result)


# ---------------------------------------------------------------------------
# 6. Formula graph validation
# ---------------------------------------------------------------------------


def _formula_graph_label(formula_graph: FormulaGraph) -> str:
    source_claim = getattr(formula_graph, "source_claim", None)
    if isinstance(source_claim, str) and source_claim:
        return source_claim
    return "<invalid-source-claim>"


def _validate_formula_descriptor_qids(
    value: Any,
    *,
    formula_graph: FormulaGraph,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    if isinstance(value, dict):
        kind = value.get("kind")
        qid = value.get("qid")
        if kind in {"claim", "knowledge"}:
            if not isinstance(qid, str):
                result.error(
                    f"FormulaGraph '{_formula_graph_label(formula_graph)}': "
                    "descriptor qid must be a string"
                )
            else:
                knowledge = knowledge_lookup.get(qid)
                if knowledge is None:
                    result.error(
                        f"FormulaGraph '{_formula_graph_label(formula_graph)}': "
                        f"descriptor qid '{qid}' not found in graph"
                    )
                elif knowledge.type != KnowledgeType.CLAIM:
                    result.error(
                        f"FormulaGraph '{_formula_graph_label(formula_graph)}': "
                        f"descriptor qid '{qid}' must reference a claim"
                    )
        for child in value.values():
            _validate_formula_descriptor_qids(
                child,
                formula_graph=formula_graph,
                knowledge_lookup=knowledge_lookup,
                result=result,
            )
        return

    if isinstance(value, list):
        for child in value:
            _validate_formula_descriptor_qids(
                child,
                formula_graph=formula_graph,
                knowledge_lookup=knowledge_lookup,
                result=result,
            )


def _formula_graph_sequence(
    value: Any,
    *,
    label: str,
    field_name: str,
    result: ValidationResult,
) -> list[Any]:
    if isinstance(value, list):
        return value
    result.error(f"FormulaGraph '{label}': {field_name} must be a list")
    return []


def _validate_formula_graph_source(
    formula_graph: FormulaGraph,
    *,
    label: str,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    source_claim_id = getattr(formula_graph, "source_claim", None)
    if not isinstance(source_claim_id, str):
        result.error(f"FormulaGraph '{label}': source_claim must be a string")
        return

    source_claim = knowledge_lookup.get(source_claim_id)
    if source_claim is None:
        result.error(f"FormulaGraph '{label}': source_claim '{source_claim_id}' not found in graph")
    elif source_claim.type != KnowledgeType.CLAIM:
        result.error(
            f"FormulaGraph '{label}': source_claim "
            f"'{source_claim_id}' is '{source_claim.type}', must be claim"
        )


def _validate_formula_node_hash(
    *,
    node_id: str | None,
    descriptor: dict[str, Any],
    result: ValidationResult,
) -> None:
    display_id = node_id or "<missing-id>"
    try:
        expected = formula_node_id(descriptor)
    except (TypeError, ValueError) as exc:
        result.error(
            f"FormulaNode '{display_id}': descriptor is not canonical JSON serializable: {exc}"
        )
        return

    if node_id != expected:
        result.error(
            f"FormulaNode '{node_id}' does not match canonical descriptor hash '{expected}'"
        )


def _validate_formula_node(
    node: Any,
    *,
    formula_graph: FormulaGraph,
    label: str,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> tuple[str, tuple[str, dict[str, Any]]] | None:
    node_id = getattr(node, "id", None)
    if not isinstance(node_id, str):
        result.error(f"FormulaGraph '{label}': FormulaNode id must be a string")

    kind = getattr(node, "kind", None)
    if not isinstance(kind, str):
        result.error(f"FormulaGraph '{label}': FormulaNode kind must be a string")

    descriptor = getattr(node, "descriptor", None)
    if not isinstance(descriptor, dict):
        result.error(f"FormulaNode '{node_id or '<missing-id>'}': descriptor must be a dict")
        return None

    _validate_formula_node_hash(
        node_id=node_id if isinstance(node_id, str) else None,
        descriptor=descriptor,
        result=result,
    )
    _validate_formula_descriptor_qids(
        descriptor,
        formula_graph=formula_graph,
        knowledge_lookup=knowledge_lookup,
        result=result,
    )

    if not isinstance(node_id, str) or not isinstance(kind, str):
        return None

    return node_id, (kind, descriptor)


def _validate_formula_graph_nodes(
    formula_graph: FormulaGraph,
    *,
    label: str,
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> dict[str, tuple[str, dict[str, Any]]]:
    node_signatures: dict[str, tuple[str, dict[str, Any]]] = {}
    nodes = _formula_graph_sequence(
        getattr(formula_graph, "nodes", None),
        label=label,
        field_name="nodes",
        result=result,
    )
    for node in nodes:
        signature_entry = _validate_formula_node(
            node,
            formula_graph=formula_graph,
            label=label,
            knowledge_lookup=knowledge_lookup,
            result=result,
        )
        if signature_entry is None:
            continue
        node_id, signature = signature_entry
        existing = node_signatures.get(node_id)
        if existing is not None and existing != signature:
            result.error(
                f"FormulaGraph '{label}': FormulaNode id '{node_id}' appears with "
                "different kind or descriptor"
            )
        node_signatures[node_id] = signature
    return node_signatures


def _validate_formula_graph_root(
    formula_graph: FormulaGraph,
    *,
    label: str,
    node_ids: set[str],
    result: ValidationResult,
) -> None:
    root = getattr(formula_graph, "root", None)
    if not isinstance(root, str):
        result.error(f"FormulaGraph '{label}': root must be a string")
    elif root not in node_ids:
        result.error(f"FormulaGraph '{label}': root '{root}' not found in nodes")


def _validate_formula_graph_edges(
    formula_graph: FormulaGraph,
    *,
    label: str,
    node_ids: set[str],
    result: ValidationResult,
) -> None:
    edges = _formula_graph_sequence(
        getattr(formula_graph, "edges", None),
        label=label,
        field_name="edges",
        result=result,
    )
    for edge in edges:
        edge_source = getattr(edge, "source", None)
        edge_target = getattr(edge, "target", None)
        if not isinstance(edge_source, str):
            result.error(f"FormulaGraph '{label}': edge source is missing")
        elif edge_source not in node_ids:
            result.error(f"FormulaGraph '{label}': edge source '{edge_source}' not found in nodes")
        if not isinstance(edge_target, str):
            result.error(f"FormulaGraph '{label}': edge target is missing")
        elif edge_target not in node_ids:
            result.error(f"FormulaGraph '{label}': edge target '{edge_target}' not found in nodes")


def _validate_formula_graphs(
    formula_graphs: list[FormulaGraph],
    knowledge_lookup: dict[str, Knowledge],
    result: ValidationResult,
) -> None:
    """Validate FormulaGraph structure independent of Pydantic construction."""
    if not isinstance(formula_graphs, list):
        result.error("LocalCanonicalGraph formula_graphs must be a list")
        return

    for formula_graph in formula_graphs:
        label = _formula_graph_label(formula_graph)
        _validate_formula_graph_source(
            formula_graph,
            label=label,
            knowledge_lookup=knowledge_lookup,
            result=result,
        )
        node_signatures = _validate_formula_graph_nodes(
            formula_graph,
            label=label,
            knowledge_lookup=knowledge_lookup,
            result=result,
        )
        node_ids = set(node_signatures)
        _validate_formula_graph_root(
            formula_graph,
            label=label,
            node_ids=node_ids,
            result=result,
        )
        _validate_formula_graph_edges(
            formula_graph,
            label=label,
            node_ids=node_ids,
            result=result,
        )


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
    _validate_formula_graphs(graph.formula_graphs, knowledge_lookup, result)

    # hash consistency
    if graph.ir_hash is not None:
        recomputed = _canonical_json(
            graph.knowledges,
            graph.operators,
            graph.strategies,
            graph.composes,
            graph.formula_graphs,
        )
        import hashlib

        expected = f"sha256:{hashlib.sha256(recomputed.encode()).hexdigest()}"
        if graph.ir_hash != expected:
            result.error(
                f"LocalCanonicalGraph ir_hash mismatch: stored={graph.ir_hash}, computed={expected}"
            )

    return result


# ---------------------------------------------------------------------------
# 7. Parameterization completeness (pre-BP)
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


def _validate_cromwell_bounds(
    result: ValidationResult,
    *,
    priors: list[PriorRecord],
) -> None:
    """Validate Cromwell bounds for prior records."""
    for prior_record in priors:
        if prior_record.value < CROMWELL_EPS or prior_record.value > 1 - CROMWELL_EPS:
            result.error(
                f"PriorRecord '{prior_record.knowledge_id}': value {prior_record.value} "
                f"outside Cromwell bounds "
                f"[{CROMWELL_EPS}, {1 - CROMWELL_EPS}]"
            )


def _validate_parameterization_dangling_refs(
    result: ValidationResult,
    *,
    graph: LocalCanonicalGraph,
    priors: list[PriorRecord],
) -> None:
    """Warn about prior records that reference missing IR objects."""
    all_knowledge_ids = {knowledge.id for knowledge in graph.knowledges if knowledge.id}
    for prior_record in priors:
        if prior_record.knowledge_id not in all_knowledge_ids:
            result.warn(
                f"PriorRecord '{prior_record.knowledge_id}': references non-existent Knowledge"
            )


def validate_parameterization(
    graph: LocalCanonicalGraph,
    priors: list[PriorRecord],
) -> ValidationResult:
    """Validate parameterization completeness before BP run.

    Checks that every independent claim Knowledge has at least one PriorRecord.
    Strategy probability parameters are part of the Strategy IR itself in the
    v0.5 contract; this validator does not maintain a separate strategy
    parameterization layer.

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

    _validate_prior_coverage(result, claim_ids=claim_ids, prior_exempt=prior_exempt, priors=priors)
    _validate_prohibited_priors(result, priors=priors, no_prior_allowed=no_prior_allowed)
    _validate_cromwell_bounds(result, priors=priors)
    _validate_parameterization_dangling_refs(
        result,
        graph=graph,
        priors=priors,
    )

    return result
