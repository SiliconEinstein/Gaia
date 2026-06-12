"""Field-map artifacts for autonomous review-style research runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

FIELD_MAP_SCHEMA_VERSION = 1


class FieldMapSchemaError(ValueError):
    """Raised when a field-map artifact violates the v1 contract."""


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_dict(payload: Any, field: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise FieldMapSchemaError(f"{field} must be an object")
    return payload


def _require_list(payload: Any, field: str) -> list[Any]:
    if not isinstance(payload, list):
        raise FieldMapSchemaError(f"{field} must be a list")
    return payload


def _require_non_empty_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FieldMapSchemaError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_ref(ref: Any, field: str) -> None:
    payload = _require_dict(ref, field)
    _require_non_empty_string(payload, "kind")
    if not any(
        isinstance(payload.get(key), str | int) and str(payload.get(key))
        for key in ("id", "paper_id", "query_index")
    ):
        raise FieldMapSchemaError(f"{field} must include one of id, paper_id, or query_index")


def _validate_query_list(value: Any, field: str) -> None:
    for index, query in enumerate(_require_list(value, field)):
        if not isinstance(query, str) or not query.strip():
            raise FieldMapSchemaError(f"{field}[{index}] must be a non-empty string")


def _validate_bucket(bucket: Any, index: int) -> None:
    payload = _require_dict(bucket, f"buckets[{index}]")
    _require_non_empty_string(payload, "id")
    _require_non_empty_string(payload, "title")
    _require_non_empty_string(payload, "role")
    _require_non_empty_string(payload, "coverage_status")
    if "required_for_review" in payload and not isinstance(payload["required_for_review"], bool):
        raise FieldMapSchemaError(f"buckets[{index}].required_for_review must be a bool")

    refs = payload.get("evidence_refs", [])
    for ref_index, ref in enumerate(_require_list(refs, f"buckets[{index}].evidence_refs")):
        _validate_ref(ref, f"buckets[{index}].evidence_refs[{ref_index}]")
    _validate_query_list(
        payload.get("recommended_queries", []),
        f"buckets[{index}].recommended_queries",
    )


def _validate_gap(gap: Any, index: int) -> None:
    payload = _require_dict(gap, f"coverage_gaps[{index}]")
    _require_non_empty_string(payload, "kind")
    _require_non_empty_string(payload, "description")
    _validate_query_list(
        payload.get("recommended_queries", []),
        f"coverage_gaps[{index}].recommended_queries",
    )


def _validate_string_list(value: Any, field: str) -> None:
    for index, item in enumerate(_require_list(value, field)):
        if not isinstance(item, str) or not item.strip():
            raise FieldMapSchemaError(f"{field}[{index}] must be a non-empty string")


def validate_field_map_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate a field-map artifact dictionary."""
    if artifact.get("schema_version") != FIELD_MAP_SCHEMA_VERSION:
        raise FieldMapSchemaError(
            f"schema_version must be {FIELD_MAP_SCHEMA_VERSION}, "
            f"got {artifact.get('schema_version')!r}"
        )
    if artifact.get("kind") != "field_map":
        raise FieldMapSchemaError("kind must be 'field_map'")
    _require_non_empty_string(artifact, "topic")
    _require_non_empty_string(artifact, "language")
    _require_list(artifact.get("source_landscapes"), "source_landscapes")
    _require_non_empty_string(artifact, "domain_thesis")

    buckets = _require_list(artifact.get("buckets"), "buckets")
    if not buckets:
        raise FieldMapSchemaError("buckets must not be empty")
    for index, bucket in enumerate(buckets):
        _validate_bucket(bucket, index)

    _validate_string_list(artifact.get("controversy_axes", []), "controversy_axes")
    for index, gap in enumerate(_require_list(artifact.get("coverage_gaps", []), "coverage_gaps")):
        _validate_gap(gap, index)
    _validate_query_list(artifact.get("recommended_expansions", []), "recommended_expansions")
    _validate_string_list(artifact.get("synthesis_notes", []), "synthesis_notes")
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


def build_field_map_artifact(
    *,
    topic: str,
    landscapes: list[dict[str, Any]],
    analysis: dict[str, Any],
    language: str = "zh",
) -> dict[str, Any]:
    """Build a field-map artifact from broad landscapes and LLM analysis."""
    artifact = {
        "schema_version": FIELD_MAP_SCHEMA_VERSION,
        "kind": "field_map",
        "created_at": _utcnow(),
        "topic": topic,
        "language": language,
        "source_landscapes": _landscape_refs(landscapes),
        "domain_thesis": str(analysis.get("domain_thesis") or "").strip(),
        "buckets": [
            dict(bucket) for bucket in analysis.get("buckets", []) if isinstance(bucket, dict)
        ],
        "controversy_axes": list(analysis.get("controversy_axes", [])),
        "coverage_gaps": [
            dict(gap) for gap in analysis.get("coverage_gaps", []) if isinstance(gap, dict)
        ],
        "recommended_expansions": list(analysis.get("recommended_expansions", [])),
        "synthesis_notes": list(analysis.get("synthesis_notes", [])),
    }
    return validate_field_map_artifact(artifact)


__all__ = [
    "FIELD_MAP_SCHEMA_VERSION",
    "FieldMapSchemaError",
    "build_field_map_artifact",
    "validate_field_map_artifact",
]
