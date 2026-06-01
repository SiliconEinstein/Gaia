"""Assessment artifact schema helpers for package-native research actions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

ASSESSMENT_SCHEMA_VERSION = 1

RELATION_PROMOTION_HINTS: dict[str, set[str]] = {
    "supports": {"derive", "infer", "depends_on", "none"},
    "opposes": {"contradict", "infer", "none"},
    "qualifies": {"derive", "question", "obligation", "none"},
    "undercuts": {"obligation", "question", "none"},
    "background_for": {"none"},
    "needs_more_evidence": {"obligation", "none"},
}

VALID_RELATIONS = set(RELATION_PROMOTION_HINTS)
VALID_PROMOTION_HINTS = {
    hint for allowed_hints in RELATION_PROMOTION_HINTS.values() for hint in allowed_hints
}


class AssessmentSchemaError(ValueError):
    """Raised when a research assessment artifact violates the v1 contract."""


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_assessment_artifact(
    *,
    focus: dict[str, Any],
    evidence_packet: dict[str, Any],
    relations: list[dict[str, Any]],
    candidate_obligations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a v1 assessment artifact dictionary without writing source."""
    return {
        "schema_version": ASSESSMENT_SCHEMA_VERSION,
        "kind": "assessment",
        "created_at": _utcnow(),
        "focus": dict(focus),
        "evidence_packet": dict(evidence_packet),
        "relations": [dict(relation) for relation in relations],
        "candidate_obligations": [dict(item) for item in candidate_obligations or []],
    }


def _require_dict(payload: Any, field: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AssessmentSchemaError(f"{field} must be an object")
    return payload


def _require_non_empty_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise AssessmentSchemaError(f"{field} must be a non-empty string")
    return value


def _validate_source_refs(source_refs: Any) -> None:
    if not isinstance(source_refs, list) or not source_refs:
        raise AssessmentSchemaError("relation source_refs must contain at least one source ref")
    for index, ref in enumerate(source_refs):
        ref_payload = _require_dict(ref, f"source_refs[{index}]")
        _require_non_empty_string(ref_payload, "kind")
        _require_non_empty_string(ref_payload, "id")


def validate_assessment_relation(relation: dict[str, Any]) -> dict[str, Any]:
    """Validate one v1 assessment relation record."""
    relation_type = _require_non_empty_string(relation, "type")
    if relation_type not in VALID_RELATIONS:
        raise AssessmentSchemaError(
            f"relation type {relation_type!r} is invalid; allowed: {sorted(VALID_RELATIONS)}"
        )

    _require_non_empty_string(relation, "epistemic_status")
    _validate_source_refs(relation.get("source_refs"))

    hint = relation.get("promotion_hint", "none")
    if not isinstance(hint, str) or not hint:
        raise AssessmentSchemaError("promotion_hint must be a non-empty string")
    allowed_hints = RELATION_PROMOTION_HINTS[relation_type]
    if hint not in allowed_hints:
        raise AssessmentSchemaError(
            f"promotion_hint {hint!r} is not allowed for relation {relation_type!r}; "
            f"allowed: {sorted(allowed_hints)}"
        )
    return relation


def validate_assessment_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate a v1 assessment artifact dictionary."""
    if artifact.get("schema_version") != ASSESSMENT_SCHEMA_VERSION:
        raise AssessmentSchemaError(
            f"schema_version must be {ASSESSMENT_SCHEMA_VERSION}, "
            f"got {artifact.get('schema_version')!r}"
        )
    if artifact.get("kind") != "assessment":
        raise AssessmentSchemaError("kind must be 'assessment'")
    _require_dict(artifact.get("focus"), "focus")
    _require_dict(artifact.get("evidence_packet"), "evidence_packet")

    relations = artifact.get("relations")
    if not isinstance(relations, list):
        raise AssessmentSchemaError("relations must be a list")
    for index, relation in enumerate(relations):
        validate_assessment_relation(_require_dict(relation, f"relations[{index}]"))

    candidate_obligations = artifact.get("candidate_obligations")
    if not isinstance(candidate_obligations, list):
        raise AssessmentSchemaError("candidate_obligations must be a list")
    for index, obligation in enumerate(candidate_obligations):
        _require_dict(obligation, f"candidate_obligations[{index}]")

    return artifact


__all__ = [
    "ASSESSMENT_SCHEMA_VERSION",
    "RELATION_PROMOTION_HINTS",
    "VALID_PROMOTION_HINTS",
    "VALID_RELATIONS",
    "AssessmentSchemaError",
    "build_assessment_artifact",
    "validate_assessment_artifact",
    "validate_assessment_relation",
]
