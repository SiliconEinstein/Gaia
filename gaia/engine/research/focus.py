"""Focus synthesis artifacts for package-native research actions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

FOCUS_SYNTHESIS_SCHEMA_VERSION = 1

VALID_FOCUS_STATUSES = {"candidate", "accepted", "deferred"}
VALID_FOCUS_PRIORITIES = {"high", "medium", "low"}
VALID_FOCUS_READINESS = {"ready_for_assess", "needs_expand", "needs_human_review", "defer"}


class FocusSynthesisSchemaError(ValueError):
    """Raised when a focus synthesis artifact violates the v1 contract."""


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_dict(payload: Any, field: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise FocusSynthesisSchemaError(f"{field} must be an object")
    return payload


def _require_list(payload: Any, field: str) -> list[Any]:
    if not isinstance(payload, list):
        raise FocusSynthesisSchemaError(f"{field} must be a list")
    return payload


def _require_non_empty_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FocusSynthesisSchemaError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_ref(ref: Any, field: str) -> None:
    payload = _require_dict(ref, field)
    _require_non_empty_string(payload, "kind")
    if not any(
        isinstance(payload.get(key), str | int) and str(payload.get(key))
        for key in ("id", "paper_id", "query_index")
    ):
        raise FocusSynthesisSchemaError(f"{field} must include one of id, paper_id, or query_index")


def _validate_focus(focus: Any, index: int) -> None:
    payload = _require_dict(focus, f"focuses[{index}]")
    _require_non_empty_string(payload, "id")
    _require_non_empty_string(payload, "kind")
    _require_non_empty_string(payload, "question")
    _require_non_empty_string(payload, "rationale")

    status = _require_non_empty_string(payload, "status")
    if status not in VALID_FOCUS_STATUSES:
        raise FocusSynthesisSchemaError(
            f"focuses[{index}].status {status!r} is invalid; "
            f"allowed: {sorted(VALID_FOCUS_STATUSES)}"
        )

    priority = _require_non_empty_string(payload, "priority")
    if priority not in VALID_FOCUS_PRIORITIES:
        raise FocusSynthesisSchemaError(
            f"focuses[{index}].priority {priority!r} is invalid; "
            f"allowed: {sorted(VALID_FOCUS_PRIORITIES)}"
        )

    readiness = _require_non_empty_string(payload, "readiness")
    if readiness not in VALID_FOCUS_READINESS:
        raise FocusSynthesisSchemaError(
            f"focuses[{index}].readiness {readiness!r} is invalid; "
            f"allowed: {sorted(VALID_FOCUS_READINESS)}"
        )

    _require_dict(payload.get("scope"), f"focuses[{index}].scope")
    _require_dict(payload.get("coverage"), f"focuses[{index}].coverage")
    evidence_refs = _require_list(payload.get("evidence_refs"), f"focuses[{index}].evidence_refs")
    if not evidence_refs:
        raise FocusSynthesisSchemaError(f"focuses[{index}].evidence_refs must not be empty")
    for ref_index, ref in enumerate(evidence_refs):
        _validate_ref(ref, f"focuses[{index}].evidence_refs[{ref_index}]")

    suggested_queries = _require_list(
        payload.get("suggested_queries"), f"focuses[{index}].suggested_queries"
    )
    for query_index, query in enumerate(suggested_queries):
        if not isinstance(query, str) or not query.strip():
            raise FocusSynthesisSchemaError(
                f"focuses[{index}].suggested_queries[{query_index}] must be a non-empty string"
            )


def _validate_gap(gap: Any, index: int) -> None:
    payload = _require_dict(gap, f"coverage_gaps[{index}]")
    _require_non_empty_string(payload, "kind")
    _require_non_empty_string(payload, "description")
    refs = payload.get("evidence_refs", [])
    if refs is None:
        refs = []
    for ref_index, ref in enumerate(_require_list(refs, f"coverage_gaps[{index}].evidence_refs")):
        _validate_ref(ref, f"coverage_gaps[{index}].evidence_refs[{ref_index}]")


def validate_focus_synthesis_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate a focus synthesis artifact dictionary."""
    if artifact.get("schema_version") != FOCUS_SYNTHESIS_SCHEMA_VERSION:
        raise FocusSynthesisSchemaError(
            f"schema_version must be {FOCUS_SYNTHESIS_SCHEMA_VERSION}, "
            f"got {artifact.get('schema_version')!r}"
        )
    if artifact.get("kind") != "focus_synthesis":
        raise FocusSynthesisSchemaError("kind must be 'focus_synthesis'")
    _require_non_empty_string(artifact, "language")
    _require_list(artifact.get("source_landscapes"), "source_landscapes")

    focuses = _require_list(artifact.get("focuses"), "focuses")
    for index, focus in enumerate(focuses):
        _validate_focus(focus, index)

    gaps = _require_list(artifact.get("coverage_gaps"), "coverage_gaps")
    for index, gap in enumerate(gaps):
        _validate_gap(gap, index)

    notes = artifact.get("notes", [])
    for index, note in enumerate(_require_list(notes, "notes")):
        if not isinstance(note, str) or not note.strip():
            raise FocusSynthesisSchemaError(f"notes[{index}] must be a non-empty string")
    return artifact


def _landscape_refs(landscapes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for index, landscape in enumerate(landscapes):
        refs.append(
            {
                "index": index,
                "kind": landscape.get("kind"),
                "action": landscape.get("action"),
                "target": landscape.get("target"),
                "stats": landscape.get("stats", {}),
            }
        )
    return refs


def _fallback_focuses(landscapes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    focuses: list[dict[str, Any]] = []
    for landscape_index, landscape in enumerate(landscapes):
        candidates = landscape.get("candidate_focuses", [])
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            candidate_id = candidate.get("id") or (
                f"landscape_{landscape_index}_focus_{len(focuses)}"
            )
            question = candidate.get("question") or "Review the retrieved evidence tension."
            evidence_refs = candidate.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs:
                evidence_refs = [{"kind": "research_landscape", "id": str(landscape_index)}]
            focuses.append(
                {
                    "id": str(candidate_id),
                    "kind": "research_focus",
                    "status": "candidate",
                    "question": str(question),
                    "rationale": (
                        "Deterministic fallback focus generated from landscape candidate_focuses. "
                        "Use LLM synthesis for semantic clustering and prioritization."
                    ),
                    "priority": "medium",
                    "readiness": "needs_expand",
                    "scope": {
                        "source": "landscape_candidate_focus",
                        "landscape_index": landscape_index,
                    },
                    "coverage": {
                        "status": "unknown",
                        "raw_results": landscape.get("stats", {}).get("raw_results"),
                        "paper_leads": landscape.get("stats", {}).get("paper_leads"),
                    },
                    "evidence_refs": list(evidence_refs),
                    "suggested_queries": [],
                }
            )
    return focuses


def build_focus_synthesis_artifact(
    *,
    landscapes: list[dict[str, Any]],
    analysis: dict[str, Any] | None = None,
    language: str = "zh",
) -> dict[str, Any]:
    """Build a focus synthesis artifact from landscapes and optional LLM analysis."""
    if analysis is not None:
        focuses = analysis.get("focuses", [])
        coverage_gaps = analysis.get("coverage_gaps", [])
        notes = analysis.get("notes", [])
    else:
        focuses = _fallback_focuses(landscapes)
        coverage_gaps = []
        notes = [
            "No analysis-json was supplied; generated deterministic fallback focuses.",
            "LLM focus synthesis should cluster snippets and paper leads before assessment.",
        ]

    artifact = {
        "schema_version": FOCUS_SYNTHESIS_SCHEMA_VERSION,
        "kind": "focus_synthesis",
        "created_at": _utcnow(),
        "language": language,
        "source_landscapes": _landscape_refs(landscapes),
        "focuses": [dict(focus) for focus in focuses if isinstance(focus, dict)],
        "coverage_gaps": [dict(gap) for gap in coverage_gaps if isinstance(gap, dict)],
        "notes": list(notes) if isinstance(notes, list) else [str(notes)],
    }
    validate_focus_synthesis_artifact(artifact)
    return artifact


__all__ = [
    "FOCUS_SYNTHESIS_SCHEMA_VERSION",
    "VALID_FOCUS_PRIORITIES",
    "VALID_FOCUS_READINESS",
    "VALID_FOCUS_STATUSES",
    "FocusSynthesisSchemaError",
    "build_focus_synthesis_artifact",
    "validate_focus_synthesis_artifact",
]
