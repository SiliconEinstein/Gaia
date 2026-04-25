"""Quality gate checks for Gaia packages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gaia.cli._packages import GaiaCliError
from gaia.cli.commands._inquiry import InquiryEdge, InquiryNode, build_goal_trees
from gaia.cli.commands._review_manifest import latest_reviews
from gaia.ir import ReviewManifest, ReviewStatus


@dataclass
class QualityConfig:
    min_posterior: float | None = None
    allow_holes: bool = False
    allow_unformalized_dependencies: bool = False


def load_quality_config(tool_gaia_quality: dict[str, Any] | None) -> QualityConfig:
    config = tool_gaia_quality or {}
    min_posterior = config.get("min_posterior")
    return QualityConfig(
        min_posterior=float(min_posterior) if min_posterior is not None else None,
        allow_holes=bool(config.get("allow_holes", False)),
        allow_unformalized_dependencies=bool(
            config.get("allow_unformalized_dependencies", False)
        ),
    )


def load_beliefs(pkg_path: str | Path) -> dict[str, Any] | None:
    path = Path(pkg_path) / ".gaia" / "beliefs.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise GaiaCliError(f"Error: {path} is not valid JSON: {exc}") from exc


def _exported_claim_ids(ir: dict[str, Any]) -> set[str]:
    return {
        knowledge["id"]
        for knowledge in ir.get("knowledges", [])
        if knowledge.get("id") and knowledge.get("type") == "claim" and knowledge.get("exported")
    }


def _walk(node: InquiryNode):
    yield node
    for edge in node.incoming:
        yield edge
        for child in edge.inputs:
            yield from _walk(child)


def _structural_holes(trees: list[InquiryNode]) -> list[InquiryNode]:
    holes: dict[str, InquiryNode] = {}
    for tree in trees:
        for item in _walk(tree):
            if isinstance(item, InquiryNode) and item.is_hole:
                holes[item.knowledge_id] = item
    return sorted(holes.values(), key=lambda node: node.label)


def _reachable_review_targets(trees: list[InquiryNode]) -> set[str]:
    targets: set[str] = set()
    for tree in trees:
        for item in _walk(tree):
            if isinstance(item, InquiryEdge) and item.target_id:
                targets.add(item.target_id)
    return targets


def _unformalized_dependencies(trees: list[InquiryNode]) -> list[InquiryEdge]:
    edges: dict[str, InquiryEdge] = {}
    for tree in trees:
        for item in _walk(tree):
            if (
                isinstance(item, InquiryEdge)
                and item.kind == "scaffold"
                and item.status == "unformalized"
            ):
                key = item.target_id or item.label
                edges[key] = item
    return sorted(edges.values(), key=lambda edge: edge.label)


def check_quality_gate(
    ir: dict[str, Any],
    beliefs: dict[str, Any] | None,
    review_manifest: ReviewManifest,
    config: QualityConfig,
    exported_ids: set[str] | None = None,
    formalization_manifest: dict[str, Any] | None = None,
) -> list[str]:
    failures: list[str] = []
    goals = exported_ids or _exported_claim_ids(ir)
    trees = build_goal_trees(ir, review_manifest, goals, formalization_manifest)
    reachable_targets = _reachable_review_targets(trees)

    if not config.allow_holes:
        for hole in _structural_holes(trees):
            failures.append(f"Structural hole: {hole.label} has no warrant chain")

    if not config.allow_unformalized_dependencies:
        for edge in _unformalized_dependencies(trees):
            failures.append(f"Unformalized dependency: {edge.label}")

    for review in latest_reviews(review_manifest):
        if review.target_id not in reachable_targets:
            continue
        if review.status != ReviewStatus.ACCEPTED:
            failures.append(
                f"Unreviewed/rejected: {review.action_label} (status={review.status.value})"
            )

    if config.min_posterior is not None:
        if beliefs is None:
            failures.append("Missing beliefs: run `gaia infer` before using min_posterior")
        else:
            belief_by_id = {
                entry.get("knowledge_id"): float(entry.get("belief"))
                for entry in beliefs.get("beliefs", [])
                if isinstance(entry, dict)
                and isinstance(entry.get("knowledge_id"), str)
                and isinstance(entry.get("belief"), int | float)
            }
            for knowledge_id in sorted(goals):
                belief = belief_by_id.get(knowledge_id)
                if belief is None:
                    failures.append(f"Missing belief: {knowledge_id}")
                elif belief < config.min_posterior:
                    failures.append(
                        f"Low posterior: {knowledge_id} = {belief:.3f} < {config.min_posterior}"
                    )

    return failures
