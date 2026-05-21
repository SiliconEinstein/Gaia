"""InquiryState rendering for goal-oriented Gaia package review."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from gaia.engine.ir import ReviewManifest

_CANDIDATE_RELATION_EDGE_KIND = "candidate_relation"


@dataclass
class InquiryEdge:
    kind: str
    label: str
    target_id: str | None
    status: str | None
    inputs: list[InquiryNode] = field(default_factory=list)
    conclusion_id: str | None = None
    premise_ids: list[str] = field(default_factory=list)
    background_ids: list[str] = field(default_factory=list)
    rationale: str | None = None


@dataclass
class InquiryNode:
    knowledge_id: str
    label: str
    content: str
    incoming: list[InquiryEdge] = field(default_factory=list)

    @property
    def is_hole(self) -> bool:
        return not any(edge.kind != _CANDIDATE_RELATION_EDGE_KIND for edge in self.incoming)


@dataclass(frozen=True)
class _GoalTreeIndexes:
    """Precomputed lookup tables for goal-tree construction."""

    knowledge_by_id: dict[str, dict[str, Any]]
    strategies_by_conclusion: dict[str, list[dict[str, Any]]]
    operators_by_conclusion: dict[str, list[dict[str, Any]]]
    composes_by_conclusion: dict[str, list[dict[str, Any]]]
    scaffolds_by_conclusion: dict[str, list[dict[str, Any]]]
    candidate_relations_by_claim: dict[str, list[dict[str, Any]]]
    actions_by_warrant: dict[str, list[dict[str, Any]]]


def _knowledge_label(knowledge: dict[str, Any]) -> str:
    label = knowledge.get("label") or str(knowledge.get("id", "")).split("::")[-1]
    return str(label)


def _action_label(metadata: dict[str, Any] | None, fallback: str) -> str:
    label = (metadata or {}).get("action_label") or fallback
    if "::action::" in label:
        return label.split("::action::", 1)[1]
    return label


def _strategy_rationale(strategy: dict[str, Any]) -> str | None:
    parts: list[str] = []
    for step in strategy.get("steps", []) or []:
        if isinstance(step, dict):
            reasoning = step.get("reasoning")
            if isinstance(reasoning, str) and reasoning.strip():
                parts.append(reasoning.strip())
    if parts:
        return "\n\n".join(parts)
    return None


def _review_status(manifest: ReviewManifest, target_id: str | None) -> str | None:
    if target_id is None:
        return None
    status = manifest.latest_status(target_id)
    return status.value if status is not None else None


def _candidate_relation_label(scaffold: dict[str, Any]) -> str:
    label = scaffold.get("label") or scaffold.get("id") or "candidate_relation"
    pattern = scaffold.get("pattern")
    if isinstance(pattern, str) and pattern:
        return f"{label} ({pattern})"
    return str(label)


def _observation_support_entries(knowledge: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = knowledge.get("metadata") or {}
    supported_by = metadata.get("supported_by")
    if not isinstance(supported_by, list):
        return []
    return [
        entry
        for entry in supported_by
        if isinstance(entry, dict) and entry.get("pattern") == "observation"
    ]


def _metadata_warrants(metadata: dict[str, Any] | None) -> list[str]:
    warrants = (metadata or {}).get("warrants")
    return [warrant for warrant in warrants or [] if isinstance(warrant, str) and warrant]


def _exported_claim_ids(ir: dict[str, Any]) -> set[str]:
    return {
        knowledge["id"]
        for knowledge in ir.get("knowledges", [])
        if knowledge.get("id") and knowledge.get("type") == "claim" and knowledge.get("exported")
    }


def _goal_tree_knowledge_index(ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return claim knowledge nodes keyed by id."""
    return {
        knowledge["id"]: knowledge
        for knowledge in ir.get("knowledges", [])
        if knowledge.get("id") and knowledge.get("type") == "claim"
    }


def _goal_tree_strategy_indexes(
    ir: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Build strategy conclusion and warrant indexes."""
    strategies_by_conclusion: dict[str, list[dict[str, Any]]] = {}
    actions_by_warrant: dict[str, list[dict[str, Any]]] = {}
    for strategy in ir.get("strategies", []):
        conclusion = strategy.get("conclusion")
        if conclusion:
            strategies_by_conclusion.setdefault(conclusion, []).append(strategy)
        strategy_id = strategy.get("strategy_id")
        dependencies = [*strategy.get("premises", []), conclusion]
        for warrant in _metadata_warrants(strategy.get("metadata")):
            if warrant != conclusion:
                actions_by_warrant.setdefault(warrant, []).append(
                    {
                        "kind": "strategy",
                        "metadata": strategy.get("metadata"),
                        "target_id": strategy_id,
                        "fallback": strategy_id or "strategy",
                        "dependencies": dependencies,
                    }
                )
    return strategies_by_conclusion, actions_by_warrant


def _goal_tree_operator_indexes(
    ir: dict[str, Any],
    actions_by_warrant: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Build operator conclusion index and append warrant actions."""
    operators_by_conclusion: dict[str, list[dict[str, Any]]] = {}
    for operator in ir.get("operators", []):
        conclusion = operator.get("conclusion")
        if conclusion:
            operators_by_conclusion.setdefault(conclusion, []).append(operator)
        dependencies = [*operator.get("variables", []), conclusion]
        for warrant in _metadata_warrants(operator.get("metadata")):
            if warrant != conclusion:
                actions_by_warrant.setdefault(warrant, []).append(
                    {
                        "kind": "operator",
                        "metadata": operator.get("metadata"),
                        "target_id": operator.get("operator_id"),
                        "fallback": operator.get("operator_id") or "operator",
                        "dependencies": dependencies,
                    }
                )
    return operators_by_conclusion


def _goal_tree_compose_index(ir: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build compose conclusion index."""
    composes_by_conclusion: dict[str, list[dict[str, Any]]] = {}
    for compose in ir.get("composes", []):
        conclusion = compose.get("conclusion")
        if conclusion:
            composes_by_conclusion.setdefault(conclusion, []).append(compose)
    return composes_by_conclusion


def _goal_tree_scaffold_indexes(
    formalization_manifest: dict[str, Any] | None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Index depends_on and candidate-relation scaffold entries."""
    scaffolds_by_conclusion: dict[str, list[dict[str, Any]]] = {}
    candidate_relations_by_claim: dict[str, list[dict[str, Any]]] = {}
    for dependency in (formalization_manifest or {}).get("dependencies", []):
        if not isinstance(dependency, dict):
            continue
        kind = dependency.get("kind")
        if kind == "depends_on":
            conclusion = dependency.get("conclusion")
            if isinstance(conclusion, str) and conclusion:
                scaffolds_by_conclusion.setdefault(conclusion, []).append(dependency)
        elif kind == "candidate_relation":
            claims = dependency.get("claims")
            if not isinstance(claims, list):
                continue
            for claim_id in claims:
                if isinstance(claim_id, str) and claim_id:
                    candidate_relations_by_claim.setdefault(claim_id, []).append(dependency)
    return scaffolds_by_conclusion, candidate_relations_by_claim


def _goal_tree_indexes(
    ir: dict[str, Any],
    formalization_manifest: dict[str, Any] | None,
) -> _GoalTreeIndexes:
    """Build all goal-tree lookup tables."""
    strategies_by_conclusion, actions_by_warrant = _goal_tree_strategy_indexes(ir)
    scaffolds_by_conclusion, candidate_relations_by_claim = _goal_tree_scaffold_indexes(
        formalization_manifest
    )
    return _GoalTreeIndexes(
        knowledge_by_id=_goal_tree_knowledge_index(ir),
        strategies_by_conclusion=strategies_by_conclusion,
        operators_by_conclusion=_goal_tree_operator_indexes(ir, actions_by_warrant),
        composes_by_conclusion=_goal_tree_compose_index(ir),
        scaffolds_by_conclusion=scaffolds_by_conclusion,
        candidate_relations_by_claim=candidate_relations_by_claim,
        actions_by_warrant=actions_by_warrant,
    )


def _append_observation_edges(
    node: InquiryNode,
    knowledge: dict[str, Any],
    review_manifest: ReviewManifest,
) -> None:
    """Append observation support entries attached to a knowledge node."""
    for entry in _observation_support_entries(knowledge):
        action_label = entry.get("action_label")
        target_id = action_label if isinstance(action_label, str) and action_label else None
        node.incoming.append(
            InquiryEdge(
                kind="observe",
                label=_action_label({"action_label": action_label}, "observe"),
                target_id=target_id,
                status=_review_status(review_manifest, target_id),
                inputs=[],
                conclusion_id=knowledge.get("id") if isinstance(knowledge.get("id"), str) else None,
                premise_ids=[],
                background_ids=[],
                rationale=entry.get("rationale")
                if isinstance(entry.get("rationale"), str)
                else None,
            )
        )


def _append_strategy_edges(
    node: InquiryNode,
    knowledge_id: str,
    next_seen: set[str],
    indexes: _GoalTreeIndexes,
    review_manifest: ReviewManifest,
) -> None:
    """Append strategy edges that conclude a node."""
    for strategy in indexes.strategies_by_conclusion.get(knowledge_id, []):
        strategy_id = strategy.get("strategy_id")
        premises = [premise for premise in strategy.get("premises", []) if premise]
        background = [ref for ref in strategy.get("background", []) if ref]
        node.incoming.append(
            InquiryEdge(
                kind="strategy",
                label=_action_label(strategy.get("metadata"), strategy_id or "strategy"),
                target_id=strategy_id,
                status=_review_status(review_manifest, strategy_id),
                inputs=[
                    _build_goal_node(premise, next_seen, indexes, review_manifest)
                    for premise in premises
                ],
                conclusion_id=knowledge_id,
                premise_ids=list(premises),
                background_ids=list(background),
                rationale=_strategy_rationale(strategy),
            )
        )


def _append_operator_edges(
    node: InquiryNode,
    knowledge_id: str,
    next_seen: set[str],
    indexes: _GoalTreeIndexes,
    review_manifest: ReviewManifest,
) -> None:
    """Append operator edges that conclude a node."""
    for operator in indexes.operators_by_conclusion.get(knowledge_id, []):
        operator_id = operator.get("operator_id")
        node.incoming.append(
            InquiryEdge(
                kind="operator",
                label=_action_label(operator.get("metadata"), operator_id or "operator"),
                target_id=operator_id,
                status=_review_status(review_manifest, operator_id),
                inputs=[
                    _build_goal_node(variable, next_seen, indexes, review_manifest)
                    for variable in operator.get("variables", [])
                    if variable
                ],
                conclusion_id=knowledge_id,
                premise_ids=[variable for variable in operator.get("variables", []) if variable],
                background_ids=[],
            )
        )


def _append_compose_edges(
    node: InquiryNode,
    knowledge_id: str,
    next_seen: set[str],
    indexes: _GoalTreeIndexes,
    review_manifest: ReviewManifest,
) -> None:
    """Append compose edges that conclude a node."""
    for compose in indexes.composes_by_conclusion.get(knowledge_id, []):
        compose_id = compose.get("compose_id")
        dependencies = [
            ref for ref in [*compose.get("inputs", []), *compose.get("warrants", [])] if ref
        ]
        node.incoming.append(
            InquiryEdge(
                kind="compose",
                label=_action_label(compose.get("metadata"), compose_id or "compose"),
                target_id=compose_id,
                status=_review_status(review_manifest, compose_id),
                inputs=[
                    _build_goal_node(ref, next_seen, indexes, review_manifest)
                    for ref in dict.fromkeys(dependencies)
                ],
                conclusion_id=knowledge_id,
                premise_ids=list(dict.fromkeys(dependencies)),
                background_ids=[],
            )
        )


def _append_scaffold_edges(
    node: InquiryNode,
    knowledge_id: str,
    seen: set[str],
    next_seen: set[str],
    indexes: _GoalTreeIndexes,
    review_manifest: ReviewManifest,
) -> None:
    """Append formalization scaffold edges."""
    for scaffold in indexes.scaffolds_by_conclusion.get(knowledge_id, []):
        label = scaffold.get("label") or scaffold.get("id") or "depends_on"
        inputs = [ref for ref in scaffold.get("given", []) if isinstance(ref, str) and ref]
        node.incoming.append(
            InquiryEdge(
                kind="scaffold",
                label=str(label),
                target_id=scaffold.get("id") if isinstance(scaffold.get("id"), str) else None,
                status=scaffold.get("status") if isinstance(scaffold.get("status"), str) else None,
                inputs=[
                    _build_goal_node(ref, next_seen, indexes, review_manifest)
                    for ref in dict.fromkeys(inputs)
                ],
                conclusion_id=knowledge_id,
                premise_ids=list(dict.fromkeys(inputs)),
                background_ids=[
                    ref for ref in scaffold.get("background", []) if isinstance(ref, str) and ref
                ],
                rationale=scaffold.get("rationale")
                if isinstance(scaffold.get("rationale"), str)
                else None,
            )
        )

    for scaffold in indexes.candidate_relations_by_claim.get(knowledge_id, []):
        claims = scaffold.get("claims") or []
        inputs = [ref for ref in claims if isinstance(ref, str) and ref and ref != knowledge_id]
        if any(ref in seen for ref in inputs):
            continue
        node.incoming.append(
            InquiryEdge(
                kind=_CANDIDATE_RELATION_EDGE_KIND,
                label=_candidate_relation_label(scaffold),
                target_id=scaffold.get("id") if isinstance(scaffold.get("id"), str) else None,
                status=scaffold.get("status") if isinstance(scaffold.get("status"), str) else None,
                inputs=[
                    _build_goal_node(ref, next_seen, indexes, review_manifest)
                    for ref in dict.fromkeys(inputs)
                ],
                conclusion_id=knowledge_id,
                premise_ids=list(dict.fromkeys(inputs)),
                background_ids=[
                    ref for ref in scaffold.get("background", []) if isinstance(ref, str) and ref
                ],
                rationale=scaffold.get("rationale")
                if isinstance(scaffold.get("rationale"), str)
                else None,
            )
        )


def _append_warrant_edges(
    node: InquiryNode,
    knowledge_id: str,
    next_seen: set[str],
    indexes: _GoalTreeIndexes,
    review_manifest: ReviewManifest,
) -> None:
    """Append metadata warrant edges not already represented by target id."""
    seen_targets = {edge.target_id for edge in node.incoming if edge.target_id}
    for action in indexes.actions_by_warrant.get(knowledge_id, []):
        target_id = action.get("target_id")
        if target_id in seen_targets:
            continue
        dependencies = [
            ref for ref in action.get("dependencies", []) if isinstance(ref, str) and ref
        ]
        node.incoming.append(
            InquiryEdge(
                kind=action.get("kind", "warrant"),
                label=_action_label(action.get("metadata"), action.get("fallback", "warrant")),
                target_id=target_id,
                status=_review_status(review_manifest, target_id),
                inputs=[
                    _build_goal_node(ref, next_seen, indexes, review_manifest)
                    for ref in dict.fromkeys(dependencies)
                ],
                conclusion_id=knowledge_id,
                premise_ids=list(dict.fromkeys(dependencies)),
                background_ids=[],
            )
        )
        if target_id:
            seen_targets.add(target_id)


def _build_goal_node(
    knowledge_id: str,
    seen: set[str],
    indexes: _GoalTreeIndexes,
    review_manifest: ReviewManifest,
) -> InquiryNode:
    """Recursively build one inquiry goal node."""
    knowledge = indexes.knowledge_by_id.get(knowledge_id, {"id": knowledge_id, "content": ""})
    node = InquiryNode(
        knowledge_id=knowledge_id,
        label=_knowledge_label(knowledge),
        content=knowledge.get("content", ""),
    )
    if knowledge_id in seen:
        return node
    next_seen = {*seen, knowledge_id}

    _append_observation_edges(node, knowledge, review_manifest)
    _append_strategy_edges(node, knowledge_id, next_seen, indexes, review_manifest)
    _append_operator_edges(node, knowledge_id, next_seen, indexes, review_manifest)
    _append_compose_edges(node, knowledge_id, next_seen, indexes, review_manifest)
    _append_scaffold_edges(node, knowledge_id, seen, next_seen, indexes, review_manifest)
    _append_warrant_edges(node, knowledge_id, next_seen, indexes, review_manifest)
    return node


def build_goal_trees(
    ir: dict[str, Any],
    review_manifest: ReviewManifest,
    exported_ids: set[str] | None = None,
    formalization_manifest: dict[str, Any] | None = None,
) -> list[InquiryNode]:
    """Build dependency trees by walking backward from exported Claims."""
    goal_ids = exported_ids or _exported_claim_ids(ir)
    indexes = _goal_tree_indexes(ir, formalization_manifest)
    return [
        _build_goal_node(goal_id, set(), indexes, review_manifest)
        for goal_id in sorted(goal_ids)
        if goal_id in indexes.knowledge_by_id
    ]


def _walk(
    node: InquiryNode, *, include_candidate_relations: bool = True
) -> Iterator[InquiryNode | InquiryEdge]:
    yield node
    for edge in node.incoming:
        if not include_candidate_relations and edge.kind == _CANDIDATE_RELATION_EDGE_KIND:
            continue
        yield edge
        for child in edge.inputs:
            yield from _walk(
                child,
                include_candidate_relations=include_candidate_relations,
            )


def _summary(trees: list[InquiryNode]) -> dict[str, int]:
    holes: set[str] = set()
    edge_statuses: dict[str, str] = {}
    for tree in trees:
        for item in _walk(tree, include_candidate_relations=False):
            if isinstance(item, InquiryNode) and item.is_hole:
                holes.add(item.knowledge_id)
            elif isinstance(item, InquiryEdge) and item.target_id and item.status:
                edge_statuses[item.target_id] = item.status
    return {
        "goals": len(trees),
        "accepted": sum(1 for status in edge_statuses.values() if status == "accepted"),
        "unreviewed": sum(1 for status in edge_statuses.values() if status == "unreviewed"),
        "blocked": sum(
            1 for status in edge_statuses.values() if status in {"rejected", "needs_inputs"}
        ),
        "holes": len(holes),
    }


def _render_node(lines: list[str], node: InquiryNode, indent: int) -> None:
    pad = " " * indent
    marker = " [hole]" if node.is_hole else ""
    lines.append(f"{pad}- {node.label}{marker}")
    for edge in node.incoming:
        status = f" [{edge.status}]" if edge.status else ""
        lines.append(f"{pad}  <- {edge.label}{status}")
        for child in edge.inputs:
            _render_node(lines, child, indent + 5)


def render_inquiry(trees: list[InquiryNode]) -> str:
    counts = _summary(trees)
    lines = [
        "Inquiry",
        "Summary:",
        f"  Goals: {counts['goals']}",
        f"  Accepted warrants: {counts['accepted']}",
        f"  Unreviewed: {counts['unreviewed']}",
        f"  Blocked: {counts['blocked']}",
        f"  Structural holes: {counts['holes']}",
        "",
    ]
    for index, tree in enumerate(trees, start=1):
        marker = " [hole]" if tree.is_hole else ""
        lines.append(f"Goal {index}: {tree.label}{marker}")
        for edge in tree.incoming:
            status = f" [{edge.status}]" if edge.status else ""
            lines.append(f"  <- {edge.label}{status}")
            for child in edge.inputs:
                _render_node(lines, child, 5)
        lines.append("")
    return "\n".join(lines).rstrip()
