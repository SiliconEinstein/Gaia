"""InquiryState rendering for goal-oriented Gaia package review."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gaia.ir import ReviewManifest


@dataclass
class InquiryEdge:
    kind: str
    label: str
    target_id: str | None
    status: str | None
    inputs: list["InquiryNode"] = field(default_factory=list)


@dataclass
class InquiryNode:
    knowledge_id: str
    label: str
    content: str
    incoming: list[InquiryEdge] = field(default_factory=list)

    @property
    def is_hole(self) -> bool:
        return not self.incoming


def _knowledge_label(knowledge: dict[str, Any]) -> str:
    return knowledge.get("label") or knowledge.get("id", "").split("::")[-1]


def _action_label(metadata: dict[str, Any] | None, fallback: str) -> str:
    label = (metadata or {}).get("action_label") or fallback
    if "::action::" in label:
        return label.split("::action::", 1)[1]
    return label


def _review_status(manifest: ReviewManifest, target_id: str | None) -> str | None:
    if target_id is None:
        return None
    status = manifest.latest_status(target_id)
    return status.value if status is not None else None


def _grounding_action_label(knowledge: dict[str, Any]) -> str | None:
    metadata = knowledge.get("metadata") or {}
    grounding = metadata.get("grounding")
    if not isinstance(grounding, dict):
        return None
    action_label = grounding.get("action_label")
    return action_label if isinstance(action_label, str) and action_label else None


def _has_grounding(knowledge: dict[str, Any]) -> bool:
    metadata = knowledge.get("metadata") or {}
    return isinstance(metadata.get("grounding"), dict)


def _metadata_warrants(metadata: dict[str, Any] | None) -> list[str]:
    warrants = (metadata or {}).get("warrants")
    return [warrant for warrant in warrants or [] if isinstance(warrant, str) and warrant]


def _exported_claim_ids(ir: dict[str, Any]) -> set[str]:
    return {
        knowledge["id"]
        for knowledge in ir.get("knowledges", [])
        if knowledge.get("id") and knowledge.get("type") == "claim" and knowledge.get("exported")
    }


def build_goal_trees(
    ir: dict[str, Any],
    review_manifest: ReviewManifest,
    exported_ids: set[str] | None = None,
) -> list[InquiryNode]:
    """Build dependency trees by walking backward from exported Claims."""

    goal_ids = exported_ids or _exported_claim_ids(ir)
    knowledge_by_id = {
        knowledge["id"]: knowledge
        for knowledge in ir.get("knowledges", [])
        if knowledge.get("id") and knowledge.get("type") == "claim"
    }

    strategies_by_conclusion: dict[str, list[dict[str, Any]]] = {}
    for strategy in ir.get("strategies", []):
        conclusion = strategy.get("conclusion")
        if conclusion:
            strategies_by_conclusion.setdefault(conclusion, []).append(strategy)

    actions_by_warrant: dict[str, list[dict[str, Any]]] = {}
    for strategy in ir.get("strategies", []):
        strategy_id = strategy.get("strategy_id")
        conclusion = strategy.get("conclusion")
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

    composes_by_conclusion: dict[str, list[dict[str, Any]]] = {}
    for compose in ir.get("composes", []):
        conclusion = compose.get("conclusion")
        if conclusion:
            composes_by_conclusion.setdefault(conclusion, []).append(compose)

    def build_node(knowledge_id: str, seen: set[str]) -> InquiryNode:
        knowledge = knowledge_by_id.get(knowledge_id, {"id": knowledge_id, "content": ""})
        node = InquiryNode(
            knowledge_id=knowledge_id,
            label=_knowledge_label(knowledge),
            content=knowledge.get("content", ""),
        )
        if knowledge_id in seen:
            return node
        next_seen = {*seen, knowledge_id}

        if _has_grounding(knowledge):
            action_label = _grounding_action_label(knowledge)
            target_id = knowledge_id if action_label else None
            node.incoming.append(
                InquiryEdge(
                    kind="grounding",
                    label=_action_label({"action_label": action_label}, "grounding"),
                    target_id=target_id,
                    status=_review_status(review_manifest, target_id),
                    inputs=[],
                )
            )

        for strategy in strategies_by_conclusion.get(knowledge_id, []):
            strategy_id = strategy.get("strategy_id")
            edge = InquiryEdge(
                kind="strategy",
                label=_action_label(strategy.get("metadata"), strategy_id or "strategy"),
                target_id=strategy_id,
                status=_review_status(review_manifest, strategy_id),
                inputs=[
                    build_node(premise, next_seen)
                    for premise in strategy.get("premises", [])
                    if premise
                ],
            )
            node.incoming.append(edge)

        for operator in operators_by_conclusion.get(knowledge_id, []):
            operator_id = operator.get("operator_id")
            edge = InquiryEdge(
                kind="operator",
                label=_action_label(operator.get("metadata"), operator_id or "operator"),
                target_id=operator_id,
                status=_review_status(review_manifest, operator_id),
                inputs=[
                    build_node(variable, next_seen)
                    for variable in operator.get("variables", [])
                    if variable
                ],
            )
            node.incoming.append(edge)

        for compose in composes_by_conclusion.get(knowledge_id, []):
            compose_id = compose.get("compose_id")
            dependencies = [
                ref for ref in [*compose.get("inputs", []), *compose.get("warrants", [])] if ref
            ]
            edge = InquiryEdge(
                kind="compose",
                label=_action_label(compose.get("metadata"), compose_id or "compose"),
                target_id=compose_id,
                status=_review_status(review_manifest, compose_id),
                inputs=[build_node(ref, next_seen) for ref in dict.fromkeys(dependencies)],
            )
            node.incoming.append(edge)

        seen_targets = {edge.target_id for edge in node.incoming if edge.target_id}
        for action in actions_by_warrant.get(knowledge_id, []):
            target_id = action.get("target_id")
            if target_id in seen_targets:
                continue
            dependencies = [
                ref for ref in action.get("dependencies", []) if isinstance(ref, str) and ref
            ]
            edge = InquiryEdge(
                kind=action.get("kind", "warrant"),
                label=_action_label(action.get("metadata"), action.get("fallback", "warrant")),
                target_id=target_id,
                status=_review_status(review_manifest, target_id),
                inputs=[build_node(ref, next_seen) for ref in dict.fromkeys(dependencies)],
            )
            node.incoming.append(edge)
            if target_id:
                seen_targets.add(target_id)

        return node

    return [
        build_node(goal_id, set()) for goal_id in sorted(goal_ids) if goal_id in knowledge_by_id
    ]


def _walk(node: InquiryNode):
    yield node
    for edge in node.incoming:
        yield edge
        for child in edge.inputs:
            yield from _walk(child)


def _summary(trees: list[InquiryNode]) -> dict[str, int]:
    holes: set[str] = set()
    edge_statuses: dict[str, str] = {}
    for tree in trees:
        for item in _walk(tree):
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
