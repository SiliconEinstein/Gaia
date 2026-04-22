"""Generate ReviewManifest records from compiled v6 action targets."""

from __future__ import annotations

import hashlib
from typing import Any

from gaia.ir import Review, ReviewManifest, ReviewStatus
from gaia.lang.review.templates import generate_audit_question


def _review_id(target_kind: str, target_id: str) -> str:
    digest = hashlib.sha256(f"{target_kind}|{target_id}".encode()).hexdigest()[:12]
    return f"rev_{digest}"


def _labels_by_id(compiled: Any) -> dict[str, str]:
    labels: dict[str, str] = {}
    for knowledge in compiled.graph.knowledges:
        if not knowledge.id:
            continue
        if knowledge.label:
            labels[knowledge.id] = knowledge.label
        else:
            labels[knowledge.id] = knowledge.id.split("::")[-1]
    return labels


def _strategy_action_type(strategy: Any) -> str:
    pattern = (strategy.metadata or {}).get("pattern")
    if pattern == "observation":
        return "observe"
    if pattern == "computation":
        return "compute"
    if pattern == "inference":
        return "infer"
    return "derive"


def _operator_action_type(operator: Any) -> str:
    if operator.operator == "equivalence":
        return "equal"
    if operator.operator == "contradiction":
        return "contradict"
    return str(operator.operator)


def _strategy_question(strategy: Any, action_type: str, labels: dict[str, str]) -> str:
    if action_type == "infer":
        hypothesis = strategy.premises[0] if strategy.premises else ""
        return generate_audit_question(
            "infer",
            hypothesis_label=labels.get(hypothesis, hypothesis),
            evidence_label=labels.get(strategy.conclusion, strategy.conclusion or "?"),
        )
    return generate_audit_question(
        action_type,
        conclusion_label=labels.get(strategy.conclusion, strategy.conclusion or "?"),
    )


def _operator_question(operator: Any, action_type: str, labels: dict[str, str]) -> str:
    a = operator.variables[0] if operator.variables else ""
    b = operator.variables[1] if len(operator.variables) > 1 else ""
    return generate_audit_question(
        action_type,
        a_label=labels.get(a, a),
        b_label=labels.get(b, b),
    )


def generate_review_manifest(compiled: Any) -> ReviewManifest:
    """Generate unreviewed Review records for each v6 action target."""
    labels = _labels_by_id(compiled)
    reviews: list[Review] = []

    for strategy in compiled.graph.strategies:
        metadata = strategy.metadata or {}
        action_label = metadata.get("action_label")
        if not action_label or not strategy.strategy_id:
            continue
        action_type = _strategy_action_type(strategy)
        reviews.append(
            Review(
                review_id=_review_id("strategy", strategy.strategy_id),
                action_label=action_label,
                target_kind="strategy",
                target_id=strategy.strategy_id,
                status=ReviewStatus.UNREVIEWED,
                audit_question=_strategy_question(strategy, action_type, labels),
                round=1,
            )
        )

    for operator in compiled.graph.operators:
        metadata = operator.metadata or {}
        action_label = metadata.get("action_label")
        if not action_label or not operator.operator_id:
            continue
        action_type = _operator_action_type(operator)
        reviews.append(
            Review(
                review_id=_review_id("operator", operator.operator_id),
                action_label=action_label,
                target_kind="operator",
                target_id=operator.operator_id,
                status=ReviewStatus.UNREVIEWED,
                audit_question=_operator_question(operator, action_type, labels),
                round=1,
            )
        )

    return ReviewManifest(reviews=reviews)
