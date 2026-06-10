"""Proposal artifacts for package-native research actions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

PROPOSAL_SCHEMA_VERSION = 1

VALID_PROPOSAL_KINDS = {
    "research_question",
    "hypothesis",
    "experiment",
    "simulation",
    "proof",
    "benchmark",
    "analysis",
}
VALID_PROPOSAL_STATUSES = {"candidate", "accepted", "deferred"}
VALID_PROPOSAL_PRIORITIES = {"high", "medium", "low"}
STABLE_CLAIM_FIELDS = {"claim", "claims", "stable_claim", "stable_claims"}


class ProposalSchemaError(ValueError):
    """Raised when a research proposal artifact violates the v1 contract."""


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_dict(payload: Any, field: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProposalSchemaError(f"{field} must be an object")
    return payload


def _require_list(payload: Any, field: str) -> list[Any]:
    if not isinstance(payload, list):
        raise ProposalSchemaError(f"{field} must be a list")
    return payload


def _require_non_empty_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ProposalSchemaError(f"{field} must be a non-empty string")
    return value.strip()


def _contains_stable_claim_payload(payload: dict[str, Any]) -> bool:
    if payload.get("kind") in {"claim", "stable_claim"}:
        return True
    return any(field in payload for field in STABLE_CLAIM_FIELDS)


def _validate_ref(ref: Any, field: str) -> None:
    payload = _require_dict(ref, field)
    _require_non_empty_string(payload, "kind")
    has_id = any(
        isinstance(payload.get(key), str) and payload.get(key) for key in ("id", "paper_id")
    )
    if not has_id:
        raise ProposalSchemaError(f"{field} must include id or paper_id")


def _validate_refs(refs: Any, field: str) -> None:
    if refs is None:
        return
    for index, ref in enumerate(_require_list(refs, field)):
        _validate_ref(ref, f"{field}[{index}]")


def validate_proposal_record(proposal: dict[str, Any], *, field: str) -> dict[str, Any]:
    """Validate one open-ended proposal record."""
    if _contains_stable_claim_payload(proposal):
        raise ProposalSchemaError(f"{field} must not contain stable truth claims")
    kind = _require_non_empty_string(proposal, "kind")
    if kind not in VALID_PROPOSAL_KINDS:
        raise ProposalSchemaError(
            f"{field}.kind {kind!r} is invalid; allowed: {sorted(VALID_PROPOSAL_KINDS)}"
        )
    status = _require_non_empty_string(proposal, "status")
    if status not in VALID_PROPOSAL_STATUSES:
        raise ProposalSchemaError(
            f"{field}.status {status!r} is invalid; allowed: {sorted(VALID_PROPOSAL_STATUSES)}"
        )
    priority = _require_non_empty_string(proposal, "priority")
    if priority not in VALID_PROPOSAL_PRIORITIES:
        raise ProposalSchemaError(
            f"{field}.priority {priority!r} is invalid; "
            f"allowed: {sorted(VALID_PROPOSAL_PRIORITIES)}"
        )
    _require_non_empty_string(proposal, "id")
    _require_non_empty_string(proposal, "question")
    _require_non_empty_string(proposal, "rationale")
    _validate_refs(proposal.get("source_refs", []), f"{field}.source_refs")
    return proposal


def _validate_hypothesis(hypothesis: Any, index: int) -> None:
    payload = _require_dict(hypothesis, f"hypotheses[{index}]")
    if _contains_stable_claim_payload(payload):
        raise ProposalSchemaError("hypotheses must not contain stable truth claims")
    _require_non_empty_string(payload, "content")
    _validate_refs(payload.get("source_refs", []), f"hypotheses[{index}].source_refs")


def _validate_obligation(obligation: Any, index: int) -> None:
    payload = _require_dict(obligation, f"candidate_obligations[{index}]")
    _require_non_empty_string(payload, "content")
    _validate_refs(payload.get("source_refs", []), f"candidate_obligations[{index}].source_refs")


def validate_proposal_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate a research proposal artifact dictionary."""
    if artifact.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        raise ProposalSchemaError(
            f"schema_version must be {PROPOSAL_SCHEMA_VERSION}, "
            f"got {artifact.get('schema_version')!r}"
        )
    if artifact.get("kind") != "research_proposal":
        raise ProposalSchemaError("kind must be 'research_proposal'")
    _require_dict(artifact.get("source_assessment"), "source_assessment")
    for index, proposal in enumerate(_require_list(artifact.get("proposals"), "proposals")):
        validate_proposal_record(_require_dict(proposal, f"proposals[{index}]"), field="proposal")
    for index, hypothesis in enumerate(_require_list(artifact.get("hypotheses"), "hypotheses")):
        _validate_hypothesis(hypothesis, index)
    for index, obligation in enumerate(
        _require_list(artifact.get("candidate_obligations"), "candidate_obligations")
    ):
        _validate_obligation(obligation, index)
    for index, note in enumerate(_require_list(artifact.get("notes"), "notes")):
        if not isinstance(note, str) or not note.strip():
            raise ProposalSchemaError(f"notes[{index}] must be a non-empty string")
    return artifact


def _assessment_focus_id(assessment: dict[str, Any]) -> str:
    focus = assessment.get("focus")
    if isinstance(focus, dict):
        value = focus.get("id")
        if isinstance(value, str) and value:
            return value
    return "assessment_focus"


def _source_assessment_payload(assessment: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "assessment",
        "focus_id": _assessment_focus_id(assessment),
        "created_at": assessment.get("created_at"),
    }


def _fallback_proposals(assessment: dict[str, Any]) -> list[dict[str, Any]]:
    review = assessment.get("review")
    next_queries = review.get("next_queries") if isinstance(review, dict) else []
    if not isinstance(next_queries, list):
        next_queries = []
    top_level_next_queries = assessment.get("next_queries")
    if isinstance(top_level_next_queries, list):
        next_queries = [*next_queries, *top_level_next_queries]
    focus_id = _assessment_focus_id(assessment)
    proposals: list[dict[str, Any]] = []
    for index, query in enumerate(next_queries):
        if not isinstance(query, str) or not query.strip():
            continue
        proposals.append(
            {
                "id": f"{focus_id}_proposal_{index}",
                "kind": "research_question",
                "status": "candidate",
                "question": query.strip(),
                "rationale": ("Generated from assessment next_queries as an open-ended follow-up."),
                "priority": "medium",
                "source_refs": [{"kind": "assessment", "id": focus_id}],
            }
        )
    return proposals


def _fallback_obligations(assessment: dict[str, Any]) -> list[dict[str, Any]]:
    obligations = assessment.get("candidate_obligations", [])
    if not isinstance(obligations, list):
        return []
    return [dict(item) for item in obligations if isinstance(item, dict)]


def build_proposal_from_assessment(
    *,
    assessment: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a proposal artifact from an assessment and optional agent analysis."""
    if analysis is None:
        proposals = _fallback_proposals(assessment)
        hypotheses: list[dict[str, Any]] = []
        candidate_obligations = _fallback_obligations(assessment)
        notes = ["No analysis-json was supplied; generated proposals from assessment gaps."]
    else:
        proposals = analysis.get("proposals", [])
        hypotheses = analysis.get("hypotheses", [])
        candidate_obligations = analysis.get("candidate_obligations", [])
        notes = analysis.get("notes", [])
    return {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "kind": "research_proposal",
        "created_at": _utcnow(),
        "source_assessment": _source_assessment_payload(assessment),
        "proposals": [dict(item) for item in proposals if isinstance(item, dict)],
        "hypotheses": [dict(item) for item in hypotheses if isinstance(item, dict)],
        "candidate_obligations": [
            dict(item) for item in candidate_obligations if isinstance(item, dict)
        ],
        "notes": list(notes) if isinstance(notes, list) else [str(notes)],
    }


__all__ = [
    "PROPOSAL_SCHEMA_VERSION",
    "VALID_PROPOSAL_KINDS",
    "VALID_PROPOSAL_PRIORITIES",
    "VALID_PROPOSAL_STATUSES",
    "ProposalSchemaError",
    "build_proposal_from_assessment",
    "validate_proposal_artifact",
    "validate_proposal_record",
]
