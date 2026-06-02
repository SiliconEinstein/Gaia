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
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a v1 assessment artifact dictionary without writing source."""
    relation_payloads = [dict(relation) for relation in relations]
    obligation_payloads = [dict(item) for item in candidate_obligations or []]
    artifact = {
        "schema_version": ASSESSMENT_SCHEMA_VERSION,
        "kind": "assessment",
        "created_at": _utcnow(),
        "focus": dict(focus),
        "evidence_packet": dict(evidence_packet),
        "citations": _citations_from_refs(
            evidence_packet,
            relations=relation_payloads,
            candidate_obligations=obligation_payloads,
        ),
        "relations": relation_payloads,
        "candidate_obligations": obligation_payloads,
    }
    if review is not None:
        artifact["review"] = dict(review)
    return artifact


def _iter_source_refs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for record in records:
        source_refs = record.get("source_refs")
        if not isinstance(source_refs, list):
            continue
        for ref in source_refs:
            if isinstance(ref, dict):
                refs.append(ref)
    return refs


def _source_ref_id(ref: dict[str, Any]) -> str | None:
    ref_id = ref.get("id") or ref.get("paper_id")
    if isinstance(ref_id, str) and ref_id:
        return ref_id
    if isinstance(ref_id, int):
        return str(ref_id)
    return None


def _cited_ref_ids(
    *,
    relations: list[dict[str, Any]],
    candidate_obligations: list[dict[str, Any]],
) -> dict[str, set[str]]:
    cited: dict[str, set[str]] = {
        "item": set(),
        "variable": set(),
        "factor": set(),
        "chain": set(),
        "package": set(),
        "paper": set(),
    }
    for ref in _iter_source_refs([*relations, *candidate_obligations]):
        kind = ref.get("kind")
        ref_id = _source_ref_id(ref)
        if isinstance(kind, str) and kind in cited and ref_id:
            cited[kind].add(ref_id)
    return cited


def _append_unique(values: list[str], value: Any) -> None:
    if isinstance(value, str) and value and value not in values:
        values.append(value)


def _item_matches_cited_refs(item: dict[str, Any], cited: dict[str, set[str]]) -> bool:
    item_id = item.get("item_id")
    kind = item.get("kind")
    source_id = item.get("id")
    source = item.get("source")
    paper_id = source.get("paper_id") if isinstance(source, dict) else None
    return (
        (isinstance(item_id, str) and item_id in cited["item"])
        or (
            isinstance(kind, str)
            and kind in cited
            and isinstance(source_id, str)
            and source_id in cited[kind]
        )
        or (isinstance(paper_id, str) and paper_id in cited["paper"])
    )


def _citation_key(item: dict[str, Any]) -> tuple[str, str] | None:
    source = item.get("source")
    source_payload = source if isinstance(source, dict) else {}
    paper_id = source_payload.get("paper_id")
    if isinstance(paper_id, str) and paper_id:
        return ("paper", paper_id)
    kind = item.get("kind")
    source_id = item.get("id")
    if isinstance(kind, str) and kind and isinstance(source_id, str) and source_id:
        return (kind, source_id)
    item_id = item.get("item_id")
    if isinstance(item_id, str) and item_id:
        return ("item", item_id)
    return None


def _new_citation(item: dict[str, Any], citation_id: str) -> dict[str, Any]:
    source = item.get("source")
    source_payload = source if isinstance(source, dict) else {}
    paper_id = source_payload.get("paper_id")
    source_kind = (
        "paper" if isinstance(paper_id, str) and paper_id else str(item.get("kind") or "item")
    )
    citation: dict[str, Any] = {
        "id": citation_id,
        "source_kind": source_kind,
        "title": source_payload.get("paper_title") or item.get("title"),
        "doi": source_payload.get("doi"),
        "item_ids": [],
        "variable_ids": [],
    }
    if isinstance(paper_id, str) and paper_id:
        citation["paper_id"] = paper_id
    else:
        citation["source_id"] = item.get("id")
    return citation


def _citations_from_refs(
    evidence_packet: dict[str, Any],
    *,
    relations: list[dict[str, Any]],
    candidate_obligations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cited = _cited_ref_ids(relations=relations, candidate_obligations=candidate_obligations)
    citations: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str], dict[str, Any]] = {}

    items = evidence_packet.get("items", [])
    if not isinstance(items, list):
        return citations

    for item in items:
        if not isinstance(item, dict) or not _item_matches_cited_refs(item, cited):
            continue
        key = _citation_key(item)
        if key is None:
            continue
        citation = by_key.get(key)
        if citation is None:
            citation = _new_citation(item, f"citation_{len(citations) + 1}")
            by_key[key] = citation
            citations.append(citation)
        _append_unique(citation["item_ids"], item.get("item_id"))
        if item.get("kind") == "variable":
            _append_unique(citation["variable_ids"], item.get("id"))
    return citations


def _evidence_packet_from_landscapes(landscapes: list[dict[str, Any]]) -> dict[str, Any]:
    """Collect reference items and paper leads from landscape artifacts."""
    items: list[dict[str, Any]] = []
    paper_leads: list[dict[str, Any]] = []
    landscape_refs: list[dict[str, Any]] = []
    for landscape_index, landscape in enumerate(landscapes):
        landscape_refs.append(
            {
                "index": landscape_index,
                "kind": landscape.get("kind"),
                "action": landscape.get("action"),
                "target": landscape.get("target"),
            }
        )
        for raw_item in landscape.get("items", []):
            if not isinstance(raw_item, dict):
                continue
            item = dict(raw_item)
            original_item_id = item.get("item_id")
            item["item_id"] = f"item_{len(items)}"
            item["landscape_index"] = landscape_index
            if isinstance(original_item_id, str) and original_item_id:
                item["landscape_item_id"] = original_item_id
            items.append(item)
        for raw_lead in landscape.get("paper_leads", []):
            if isinstance(raw_lead, dict):
                lead = dict(raw_lead)
                lead["landscape_index"] = landscape_index
                paper_leads.append(lead)
    return {
        "landscapes": landscape_refs,
        "items": items,
        "paper_leads": paper_leads,
    }


def build_assessment_from_landscapes(
    *,
    focus: dict[str, Any],
    landscapes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a conservative assessment artifact from landscape reference items."""
    evidence_packet = _evidence_packet_from_landscapes(landscapes)
    items = evidence_packet["items"]

    focus_id = focus.get("id", "focus")
    relations = [
        {
            "type": "background_for",
            "claim": f"Retrieved item is background evidence for {focus_id}.",
            "rationale": "The item was retrieved by a landscape query selected for this focus.",
            "epistemic_status": "candidate",
            "promotion_hint": "none",
            "source_refs": [{"kind": "item", "id": item["item_id"]}],
        }
        for item in items
    ]
    if not relations:
        relations.append(
            {
                "type": "needs_more_evidence",
                "claim": f"No retrieved items are available for {focus_id}.",
                "rationale": (
                    "Assessment cannot classify support or opposition without grounded items."
                ),
                "epistemic_status": "candidate",
                "promotion_hint": "obligation",
                "source_refs": [{"kind": "focus", "id": str(focus_id)}],
            }
        )

    candidate_obligations = [
        {
            "kind": "needs_more_evidence",
            "target": dict(focus),
            "content": (
                "Classify whether the retrieved items support, oppose, qualify, "
                "or undercut the focus."
            ),
            "source_refs": [{"kind": "item", "id": item["item_id"]} for item in items],
        }
    ]
    artifact = build_assessment_artifact(
        focus=focus,
        evidence_packet=evidence_packet,
        relations=relations,
        candidate_obligations=candidate_obligations,
    )
    validate_assessment_artifact(artifact)
    return artifact


def _empty_grounding_ids() -> dict[str, set[str]]:
    return {
        "item": set(),
        "variable": set(),
        "factor": set(),
        "chain": set(),
        "package": set(),
        "paper": set(),
    }


def _add_grounding_id(ids: dict[str, set[str]], kind: str, value: Any) -> None:
    if isinstance(value, str) and value:
        ids[kind].add(value)


def _add_paper_grounding(ids: dict[str, set[str]], paper_id: Any) -> None:
    if isinstance(paper_id, str) and paper_id:
        ids["paper"].add(paper_id)


def _add_item_grounding(ids: dict[str, set[str]], item: dict[str, Any]) -> None:
    _add_grounding_id(ids, "item", item.get("item_id"))
    kind = item.get("kind")
    if isinstance(kind, str) and kind in ids and kind != "item":
        _add_grounding_id(ids, kind, item.get("id"))
    source = item.get("source")
    if isinstance(source, dict):
        _add_paper_grounding(ids, source.get("paper_id"))


def _add_paper_lead_grounding(ids: dict[str, set[str]], lead: dict[str, Any]) -> None:
    _add_paper_grounding(ids, lead.get("paper_id"))
    for variable_id in lead.get("variable_ids", []) or []:
        _add_grounding_id(ids, "variable", variable_id)


def _valid_grounding_ids(evidence_packet: dict[str, Any]) -> dict[str, set[str]]:
    ids = _empty_grounding_ids()
    items = evidence_packet.get("items", [])
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                _add_item_grounding(ids, item)

    paper_leads = evidence_packet.get("paper_leads", [])
    if isinstance(paper_leads, list):
        for lead in paper_leads:
            if isinstance(lead, dict):
                _add_paper_lead_grounding(ids, lead)
    return ids


def validate_assessment_grounding(artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate that relation refs resolve inside the assessment evidence packet."""
    evidence_packet = _require_dict(artifact.get("evidence_packet"), "evidence_packet")
    valid_ids = _valid_grounding_ids(evidence_packet)
    for relation_index, relation in enumerate(artifact.get("relations", [])):
        relation_payload = _require_dict(relation, f"relations[{relation_index}]")
        for ref_index, ref in enumerate(relation_payload.get("source_refs", [])):
            ref_payload = _require_dict(
                ref, f"relations[{relation_index}].source_refs[{ref_index}]"
            )
            kind = _require_non_empty_string(ref_payload, "kind")
            ref_id = _require_non_empty_string(ref_payload, "id")
            if kind in valid_ids and ref_id not in valid_ids[kind]:
                raise AssessmentSchemaError(
                    f"relations[{relation_index}].source_refs[{ref_index}] "
                    f"{kind}:{ref_id} is not grounded in evidence_packet"
                )
    return artifact


def build_assessment_from_analysis(
    *,
    focus: dict[str, Any],
    landscapes: list[dict[str, Any]],
    analysis: dict[str, Any],
    strict_grounding: bool = True,
) -> dict[str, Any]:
    """Build an assessment artifact from agent/LLM analysis and landscapes."""
    evidence_packet = _evidence_packet_from_landscapes(landscapes)
    relations = analysis.get("relations", [])
    if not isinstance(relations, list):
        raise AssessmentSchemaError("analysis.relations must be a list")
    candidate_obligations = analysis.get("candidate_obligations", [])
    if not isinstance(candidate_obligations, list):
        raise AssessmentSchemaError("analysis.candidate_obligations must be a list")
    review = analysis.get("review")
    if review is not None and not isinstance(review, dict):
        raise AssessmentSchemaError("analysis.review must be an object")

    artifact = build_assessment_artifact(
        focus=focus,
        evidence_packet=evidence_packet,
        relations=relations,
        candidate_obligations=candidate_obligations,
        review=review,
    )
    validate_assessment_artifact(artifact)
    if strict_grounding:
        validate_assessment_grounding(artifact)
    return artifact


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

    _require_non_empty_string(relation, "claim")
    _require_non_empty_string(relation, "rationale")
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


def _validate_review(review: Any) -> None:
    payload = _require_dict(review, "review")
    _require_non_empty_string(payload, "language")
    _require_non_empty_string(payload, "depth")
    _require_non_empty_string(payload, "summary")
    sections = payload.get("sections", [])
    if not isinstance(sections, list):
        raise AssessmentSchemaError("review.sections must be a list")
    for index, section in enumerate(sections):
        section_payload = _require_dict(section, f"review.sections[{index}]")
        _require_non_empty_string(section_payload, "title")
        _require_non_empty_string(section_payload, "body")
    for field in ("limitations", "next_queries"):
        value = payload.get(field, [])
        if not isinstance(value, list):
            raise AssessmentSchemaError(f"review.{field} must be a list")


def _validate_string_list(value: Any, field: str) -> None:
    if not isinstance(value, list):
        raise AssessmentSchemaError(f"{field} must be a list")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise AssessmentSchemaError(f"{field}[{index}] must be a non-empty string")


def _validate_citation(citation: Any, index: int) -> None:
    payload = _require_dict(citation, f"citations[{index}]")
    for field in ("id", "source_kind"):
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise AssessmentSchemaError(f"citations[{index}].{field} must be a non-empty string")
    if not isinstance(payload.get("paper_id") or payload.get("source_id"), str):
        raise AssessmentSchemaError(f"citations[{index}] must include paper_id or source_id")
    _validate_string_list(payload.get("item_ids"), f"citations[{index}].item_ids")
    _validate_string_list(payload.get("variable_ids", []), f"citations[{index}].variable_ids")


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

    if "citations" in artifact:
        citations = artifact["citations"]
        if not isinstance(citations, list):
            raise AssessmentSchemaError("citations must be a list")
        for index, citation in enumerate(citations):
            _validate_citation(citation, index)

    if "review" in artifact:
        _validate_review(artifact["review"])

    return artifact


__all__ = [
    "ASSESSMENT_SCHEMA_VERSION",
    "RELATION_PROMOTION_HINTS",
    "VALID_PROMOTION_HINTS",
    "VALID_RELATIONS",
    "AssessmentSchemaError",
    "build_assessment_artifact",
    "build_assessment_from_analysis",
    "build_assessment_from_landscapes",
    "validate_assessment_artifact",
    "validate_assessment_grounding",
    "validate_assessment_relation",
]
