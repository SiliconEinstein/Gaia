"""Heuristic stop criteria for package-native research loops."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

STOP_SCHEMA_VERSION = 1


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _list(payload: object) -> list[Any]:
    return payload if isinstance(payload, list) else []


def _dict(payload: object) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _paper_ids(landscapes: list[dict[str, Any]]) -> set[str]:
    paper_ids: set[str] = set()
    for landscape in landscapes:
        for lead in _list(landscape.get("paper_leads")):
            if not isinstance(lead, dict):
                continue
            paper_id = lead.get("paper_id")
            if isinstance(paper_id, str) and paper_id:
                paper_ids.add(paper_id)
    return paper_ids


def _paper_ids_by_variable(landscapes: list[dict[str, Any]]) -> dict[str, str]:
    paper_by_variable: dict[str, str] = {}
    for landscape in landscapes:
        for item in _list(landscape.get("items")):
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            source = item.get("source")
            source_paper_id = source.get("paper_id") if isinstance(source, dict) else None
            paper_id = item.get("paper_id") or source_paper_id
            if isinstance(item_id, str) and item_id and isinstance(paper_id, str) and paper_id:
                paper_by_variable[item_id] = paper_id
    return paper_by_variable


def _assessment_variable_ids(assessment: dict[str, Any] | None) -> set[str]:
    if assessment is None:
        return set()
    variable_ids: set[str] = set()
    payloads = [
        *_list(assessment.get("relations")),
        *_list(assessment.get("candidate_obligations")),
    ]
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for ref in _list(payload.get("source_refs")):
            if isinstance(ref, dict) and ref.get("kind") == "variable":
                ref_id = ref.get("id")
                if isinstance(ref_id, str) and ref_id:
                    variable_ids.add(ref_id)
    return variable_ids


def _relation_type_counts(assessment: dict[str, Any] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    if assessment is None:
        return counts
    for relation in _list(assessment.get("relations")):
        if not isinstance(relation, dict):
            continue
        relation_type = relation.get("type")
        if isinstance(relation_type, str) and relation_type:
            counts[relation_type] = counts.get(relation_type, 0) + 1
    return counts


def _dimension(status: str, score: float | None, reason: str) -> dict[str, Any]:
    return {"status": status, "score": score, "reason": reason}


def _coverage_dimension(focus_artifact: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if focus_artifact is None:
        return (
            _dimension("missing", 0.0, "No focus artifact is available yet."),
            "continue_broad_scan",
        )

    focuses = _list(focus_artifact.get("focuses"))
    gaps = _list(focus_artifact.get("coverage_gaps"))
    ready = [
        focus
        for focus in focuses
        if isinstance(focus, dict) and focus.get("readiness") == "ready_for_assess"
    ]
    needs_expand = [
        focus
        for focus in focuses
        if isinstance(focus, dict) and focus.get("readiness") == "needs_expand"
    ]
    score = len(ready) / max(len(focuses), 1)

    if ready and not gaps:
        return (
            _dimension(
                "sufficient",
                score,
                f"{len(ready)} of {len(focuses)} focus(es) are ready for assessment.",
            ),
            "ready_for_assess",
        )
    if gaps or needs_expand:
        return (
            _dimension(
                "weak",
                score,
                (
                    f"{len(gaps)} coverage gap(s) and {len(needs_expand)} "
                    "focus(es) needing expansion remain."
                ),
            ),
            "expand_focus",
        )
    return (
        _dimension("weak", score, "No focus is marked ready_for_assess."),
        "continue_broad_scan",
    )


def _relation_mix_dimension(assessment: dict[str, Any] | None) -> dict[str, Any]:
    if assessment is None:
        return _dimension("missing", None, "No assessment artifact is available yet.")
    counts = _relation_type_counts(assessment)
    positive = counts.get("supports", 0)
    tension = counts.get("opposes", 0) + counts.get("qualifies", 0) + counts.get("undercuts", 0)
    relation_total = sum(counts.values())
    if positive >= 1 and tension >= 1:
        return _dimension(
            "sufficient",
            min((positive + tension) / max(relation_total, 1), 1.0),
            "Assessment has both supportive and opposing/qualifying/undercutting evidence.",
        )
    if relation_total == 0:
        return _dimension("weak", 0.0, "Assessment contains no evidence relations.")
    return _dimension(
        "weak",
        min((positive + tension) / max(relation_total, 1), 1.0),
        "Relation mix is one-sided; targeted expansion or human review is needed.",
    )


def _obligation_dimension(
    assessment: dict[str, Any] | None,
    *,
    max_open_obligations: int,
) -> dict[str, Any]:
    if assessment is None:
        return _dimension("missing", None, "No assessment artifact is available yet.")
    obligations = _list(assessment.get("candidate_obligations"))
    count = len(obligations)
    if count <= max_open_obligations:
        return _dimension(
            "sufficient",
            1.0,
            f"{count} unresolved obligation(s), within threshold {max_open_obligations}.",
        )
    return _dimension(
        "weak",
        max(max_open_obligations / max(count, 1), 0.0),
        f"{count} unresolved obligation(s) exceed threshold {max_open_obligations}.",
    )


def _query_novelty_dimension(
    landscapes: list[dict[str, Any]],
    previous_landscapes: list[dict[str, Any]],
    *,
    assessment: dict[str, Any] | None,
    min_new_lead_ratio: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_ids = _paper_ids(landscapes)
    previous_ids = _paper_ids(previous_landscapes)
    new_ids = current_ids - previous_ids
    ratio = len(new_ids) / max(len(current_ids), 1)
    cited_paper_ids = {
        paper_id
        for variable_id, paper_id in _paper_ids_by_variable(landscapes).items()
        if variable_id in _assessment_variable_ids(assessment)
    }
    grounding_ratio = len(cited_paper_ids) / max(len(current_ids), 1)
    metrics = {
        "current_paper_leads": len(current_ids),
        "previous_paper_leads": len(previous_ids),
        "new_paper_leads": len(new_ids),
        "new_paper_lead_ratio": round(ratio, 4),
        "assessment_grounded_paper_leads": len(cited_paper_ids),
        "assessment_grounded_paper_lead_ratio": round(grounding_ratio, 4),
    }
    if not landscapes or not previous_landscapes:
        return (
            _dimension(
                "unknown",
                None,
                "Need both current and previous landscapes to estimate query novelty.",
            ),
            metrics,
        )
    if not current_ids:
        return (_dimension("weak", 0.0, "Latest landscape has no paper leads."), metrics)
    if ratio < min_new_lead_ratio:
        return (
            _dimension(
                "weak",
                ratio,
                (
                    "Latest landscape adds too few new paper leads "
                    f"({ratio:.2f} < {min_new_lead_ratio:.2f})."
                ),
            ),
            metrics,
        )
    if assessment is not None and grounding_ratio < min_new_lead_ratio:
        return (
            _dimension(
                "weak",
                grounding_ratio,
                (
                    "Latest landscape adds novel paper leads, but too few are grounded "
                    "in the assessment "
                    f"({grounding_ratio:.2f} < {min_new_lead_ratio:.2f})."
                ),
            ),
            metrics,
        )
    return (
        _dimension(
            "sufficient",
            ratio,
            (
                "Latest landscape still adds novel paper leads "
                f"({ratio:.2f} >= {min_new_lead_ratio:.2f})."
            ),
        ),
        metrics,
    )


def _choose_recommendation(
    *,
    coverage_action: str,
    dimensions: dict[str, dict[str, Any]],
    has_assessment: bool,
) -> str:
    coverage_status = str(dimensions["coverage"]["status"])
    relation_status = str(dimensions["relation_mix"]["status"])
    obligation_status = str(dimensions["unresolved_obligations"]["status"])
    novelty_status = str(dimensions["query_novelty"]["status"])

    if coverage_status in {"missing", "weak"}:
        return "ready_for_human_review" if novelty_status == "weak" else coverage_action
    if not has_assessment:
        return "ready_for_assess"
    if relation_status != "sufficient" or obligation_status == "weak":
        return "ready_for_human_review" if novelty_status == "weak" else "expand_focus"
    return "ready_for_human_review"


def evaluate_research_stop(
    *,
    focus_artifact: dict[str, Any] | None = None,
    assessment: dict[str, Any] | None = None,
    landscapes: list[dict[str, Any]] | None = None,
    previous_landscapes: list[dict[str, Any]] | None = None,
    max_open_obligations: int = 2,
    min_new_lead_ratio: float = 0.2,
) -> dict[str, Any]:
    """Evaluate heuristic stop criteria for one research-loop state."""
    current_landscapes = list(landscapes or [])
    prior_landscapes = list(previous_landscapes or [])
    coverage, coverage_action = _coverage_dimension(focus_artifact)
    query_novelty, novelty_metrics = _query_novelty_dimension(
        current_landscapes,
        prior_landscapes,
        assessment=assessment,
        min_new_lead_ratio=min_new_lead_ratio,
    )
    dimensions = {
        "coverage": coverage,
        "relation_mix": _relation_mix_dimension(assessment),
        "unresolved_obligations": _obligation_dimension(
            assessment,
            max_open_obligations=max_open_obligations,
        ),
        "query_novelty": query_novelty,
    }
    recommendation = _choose_recommendation(
        coverage_action=coverage_action,
        dimensions=dimensions,
        has_assessment=assessment is not None,
    )
    reasons = [f"{name}: {dimension['reason']}" for name, dimension in sorted(dimensions.items())]
    metrics = {
        **novelty_metrics,
        "focuses": len(_list(_dict(focus_artifact).get("focuses"))),
        "coverage_gaps": len(_list(_dict(focus_artifact).get("coverage_gaps"))),
        "relations": sum(_relation_type_counts(assessment).values()),
        "candidate_obligations": len(_list(_dict(assessment).get("candidate_obligations"))),
    }
    return {
        "schema_version": STOP_SCHEMA_VERSION,
        "kind": "research_stop",
        "created_at": _utcnow(),
        "recommendation": recommendation,
        "should_stop": recommendation in {"ready_for_assess", "ready_for_human_review"},
        "dimensions": dimensions,
        "metrics": metrics,
        "reasons": reasons,
        "thresholds": {
            "max_open_obligations": max_open_obligations,
            "min_new_lead_ratio": min_new_lead_ratio,
        },
    }


__all__ = ["STOP_SCHEMA_VERSION", "evaluate_research_stop"]
