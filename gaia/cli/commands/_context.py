"""Context packet builder for gaia inquiry context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from gaia.cli.commands._inquiry import InquiryEdge, InquiryNode, build_goal_trees
from gaia.engine.inquiry.focus import FocusBinding, resolve_focus_target
from gaia.engine.inquiry.review_manifest import load_or_generate_review_manifest
from gaia.engine.inquiry.state import InquiryState, load_state
from gaia.engine.packaging import (
    apply_package_priors,
    compile_loaded_package_artifact,
    ensure_package_env,
    load_gaia_package,
)

TrajectorySelector = Literal["most_uncertain", "shortest"]
RenderOrder = Literal["backward", "forward"]


@dataclass(frozen=True)
class ContextRouteStep:
    edge_kind: str
    target_id: str | None
    label: str
    status: str | None
    conclusion_id: str
    premise_ids: list[str]
    background_ids: list[str]
    rationale: str | None


@dataclass(frozen=True)
class ContextPacket:
    focus: FocusBinding
    trajectory: TrajectorySelector
    order: RenderOrder
    route: list[ContextRouteStep]
    ir: dict[str, Any]
    source_ir: dict[str, Any]
    state: InquiryState


def build_context_packet(
    path: str | Path,
    *,
    focus_override: str | None,
    trajectory: TrajectorySelector,
    order: RenderOrder,
) -> ContextPacket:
    pkg_path = Path(path).resolve()
    state = _load_state_read_only(pkg_path)
    focus_raw = focus_override if focus_override is not None else state.focus
    if focus_raw is None:
        raise ValueError("No inquiry focus set; pass --focus or run gaia inquiry focus <claim>.")

    ensure_package_env(pkg_path)
    loaded = load_gaia_package(str(pkg_path))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    graph = compiled.graph
    review_manifest = load_or_generate_review_manifest(loaded.pkg_path, compiled)

    focus = resolve_focus_target(focus_raw, graph)
    if focus.resolved_id is None or focus.kind != "claim":
        raise ValueError(f"Focus {focus_raw!r} did not resolve to a claim.")

    source_ir = compiled.to_json()
    trees = build_goal_trees(
        source_ir,
        review_manifest,
        exported_ids={focus.resolved_id},
        formalization_manifest=compiled.formalization_manifest,
    )
    if not trees:
        route: list[ContextRouteStep] = []
    else:
        routes = _enumerate_routes(trees[0])
        route = _select_route(routes, trajectory, state, source_ir)

    return ContextPacket(
        focus=focus,
        trajectory=trajectory,
        order=order,
        route=route,
        ir=_build_ir_slice(source_ir, route, focus.resolved_id),
        source_ir=source_ir,
        state=state,
    )


def _load_state_read_only(pkg_path: Path) -> InquiryState:
    state_path = pkg_path / ".gaia" / "inquiry" / "state.json"
    if not state_path.exists():
        return InquiryState()
    return load_state(pkg_path)


def _route_step(edge: InquiryEdge, conclusion_id: str) -> ContextRouteStep:
    return ContextRouteStep(
        edge_kind=edge.kind,
        target_id=edge.target_id,
        label=edge.label,
        status=edge.status,
        conclusion_id=edge.conclusion_id or conclusion_id,
        premise_ids=list(edge.premise_ids),
        background_ids=list(edge.background_ids),
        rationale=edge.rationale,
    )


def _enumerate_routes(node: InquiryNode) -> list[list[ContextRouteStep]]:
    if not node.incoming:
        return [[]]
    routes: list[list[ContextRouteStep]] = []
    for edge in node.incoming:
        step = _route_step(edge, node.knowledge_id)
        if not edge.inputs:
            routes.append([step])
            continue
        for child in edge.inputs:
            for child_route in _enumerate_routes(child):
                routes.append([step, *child_route])
    return routes


def _select_route(
    routes: list[list[ContextRouteStep]],
    trajectory: TrajectorySelector,
    state: InquiryState,
    ir: dict[str, Any],
) -> list[ContextRouteStep]:
    if not routes:
        return []
    if trajectory == "shortest":
        return min(routes, key=lambda route: (len(route), _route_key(route)))
    return sorted(
        routes,
        key=lambda route: (-_uncertainty_score(route, state, ir), len(route), _route_key(route)),
    )[0]


def _route_key(route: list[ContextRouteStep]) -> tuple[str, ...]:
    return tuple(step.target_id or step.label for step in route)


def _known_knowledge_ids(ir: dict[str, Any]) -> set[str]:
    return {item["id"] for item in ir.get("knowledges", []) if item.get("id")}


def _uncertainty_score(
    route: list[ContextRouteStep],
    state: InquiryState,
    ir: dict[str, Any],
) -> int:
    known = _known_knowledge_ids(ir)
    obligation_targets = {item.target_qid for item in state.synthetic_obligations}
    rejected_targets = {item.target_strategy for item in state.synthetic_rejections}
    score = 0
    for step in route:
        step_targets = {target for target in (step.target_id, step.label) if target}
        if step_targets & rejected_targets:
            score += 6
        if step_targets & obligation_targets or step.conclusion_id in obligation_targets:
            score += 4
        if step.status == "rejected":
            score += 6
        elif step.status == "needs_inputs":
            score += 5
        elif step.status == "unreviewed":
            score += 2
        if not step.rationale:
            score += 2
        for ref in [*step.premise_ids, *step.background_ids, step.conclusion_id]:
            if ref and ref not in known:
                score += 5
    if route:
        last_premises = route[-1].premise_ids
        if last_premises and any(ref in known for ref in last_premises):
            score += 1
    return score


def _build_ir_slice(
    ir: dict[str, Any],
    route: list[ContextRouteStep],
    focus_id: str,
) -> dict[str, Any]:
    knowledge_ids = {focus_id}
    strategy_ids: set[str] = set()
    operator_ids: set[str] = set()
    compose_ids: set[str] = set()
    for step in route:
        knowledge_ids.add(step.conclusion_id)
        knowledge_ids.update(step.premise_ids)
        knowledge_ids.update(step.background_ids)
        if step.edge_kind == "strategy" and step.target_id:
            strategy_ids.add(step.target_id)
        elif step.edge_kind == "operator" and step.target_id:
            operator_ids.add(step.target_id)
        elif step.edge_kind == "compose" and step.target_id:
            compose_ids.add(step.target_id)

    knowledges = [item for item in ir.get("knowledges", []) if item.get("id") in knowledge_ids]
    strategies = [
        item for item in ir.get("strategies", []) if item.get("strategy_id") in strategy_ids
    ]
    operators = [
        item for item in ir.get("operators", []) if item.get("operator_id") in operator_ids
    ]
    composes = [item for item in ir.get("composes", []) if item.get("compose_id") in compose_ids]

    return {
        "namespace": ir.get("namespace"),
        "package_name": ir.get("package_name"),
        "scope": ir.get("scope", "local"),
        "knowledges": knowledges,
        "strategies": strategies,
        "operators": operators,
        "composes": composes,
        "formula_graphs": [],
    }


def _knowledge_by_id(ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in ir.get("knowledges", []) if item.get("id")}


def _display_label(knowledge: dict[str, Any] | None, qid: str) -> str:
    if knowledge is not None and knowledge.get("label"):
        return str(knowledge["label"])
    tail = qid.rsplit("::", 1)[-1]
    return tail or qid


def _content(knowledge: dict[str, Any] | None) -> str:
    if knowledge is None:
        return ""
    return str(knowledge.get("content") or "")


def _preview(text: str, limit: int = 96) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _ordered_steps(packet: ContextPacket) -> list[ContextRouteStep]:
    if packet.order == "forward":
        return list(reversed(packet.route))
    return list(packet.route)


def render_context_markdown(packet: ContextPacket) -> str:
    k_by_id = _knowledge_by_id(packet.ir)
    focus_id = packet.focus.resolved_id or ""
    focus_k = k_by_id.get(focus_id)
    focus_label = packet.focus.resolved_label or _display_label(focus_k, focus_id)
    lines: list[str] = [
        "## Focus",
        "",
        f"### `{focus_label}`",
        "",
        _content(focus_k),
        "",
        "## Why This Claim",
        "",
    ]

    references: list[str] = []
    seen_refs: set[str] = set()

    if not packet.route:
        lines.extend(["No supporting trajectory was found.", ""])
    else:
        for step in _ordered_steps(packet):
            conclusion = k_by_id.get(step.conclusion_id)
            conclusion_label = _display_label(conclusion, step.conclusion_id)
            lines.extend(
                [
                    f"### Why `{conclusion_label}`?",
                    "",
                    "**Claim**",
                    _content(conclusion),
                    "",
                ]
            )
            if step.rationale:
                lines.extend(["**Because**", step.rationale, ""])
            if step.premise_ids:
                lines.append("**Given**")
                for premise_id in step.premise_ids:
                    premise = k_by_id.get(premise_id)
                    label = _display_label(premise, premise_id)
                    lines.append(f"- `{label}`: {_preview(_content(premise))}")
                    if premise_id not in seen_refs:
                        references.append(premise_id)
                        seen_refs.add(premise_id)
                lines.append("")
            if step.background_ids:
                lines.append("**Background**")
                for background_id in step.background_ids:
                    background = k_by_id.get(background_id)
                    label = _display_label(background, background_id)
                    title = background.get("title") if isinstance(background, dict) else None
                    suffix = f": {title}" if title else ""
                    lines.append(f"- `{label}`{suffix}")
                    if background_id not in seen_refs:
                        references.append(background_id)
                        seen_refs.add(background_id)
                lines.append("")

    if references:
        lines.extend(["## References", ""])
        for ref in references:
            item = k_by_id.get(ref)
            label = _display_label(item, ref)
            lines.extend([f"### `{label}`", _content(item), ""])

    return "\n".join(lines).rstrip() + "\n"


def context_to_json_dict(packet: ContextPacket) -> dict[str, Any]:
    return {
        "context_schema_version": 1,
        "focus": {
            "id": packet.focus.resolved_id,
            "label": packet.focus.resolved_label,
        },
        "selection": {
            "trajectory": packet.trajectory,
            "order": packet.order,
        },
        "why_route": [
            {
                "edge_kind": step.edge_kind,
                "target_id": step.target_id,
                "label": step.label,
                "status": step.status,
                "conclusion": step.conclusion_id,
                "premises": list(step.premise_ids),
                "background": list(step.background_ids),
                "rationale": step.rationale,
            }
            for step in _ordered_steps(packet)
        ],
        "ir": packet.ir,
    }
