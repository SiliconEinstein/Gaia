"""Markdown rendering for package-native research artifacts."""

from __future__ import annotations

import json
from typing import Any


class ResearchReportError(ValueError):
    """Raised when a research artifact cannot be rendered."""


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("\n", " ").replace("|", "\\|")


def _json_cell(value: object) -> str:
    if value in (None, "", [], {}):
        return ""
    return _cell(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _heading(title: str) -> list[str]:
    return [f"# {title}", ""]


def _section(title: str) -> list[str]:
    return [f"## {title}", ""]


def _bullet_list(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["_None._", ""]
    lines = [f"- {_cell(item)}" for item in items]
    lines.append("")
    return lines


def _format_refs(refs: object) -> str:
    if not isinstance(refs, list) or not refs:
        return ""
    formatted: list[str] = []
    for ref in refs:
        if not isinstance(ref, dict):
            formatted.append(str(ref))
            continue
        kind = ref.get("kind", "ref")
        ref_id = ref.get("id") or ref.get("paper_id") or ref.get("query_index")
        formatted.append(f"{kind}:{ref_id}" if ref_id is not None else str(kind))
    return ", ".join(formatted)


def _relation_counts(relations: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not isinstance(relations, list):
        return counts
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        relation_type = relation.get("type")
        if isinstance(relation_type, str) and relation_type:
            counts[relation_type] = counts.get(relation_type, 0) + 1
    return counts


def _render_focus_synthesis(artifact: dict[str, Any]) -> str:
    lines = _heading("Research Focus Synthesis")
    lines.extend(
        [
            f"- schema_version: {_cell(artifact.get('schema_version'))}",
            f"- language: {_cell(artifact.get('language'))}",
            "",
        ]
    )

    lines.extend(_section("Focuses"))
    lines.extend(
        [
            "| id | priority | readiness | status | question | coverage | "
            "evidence_refs | suggested_queries |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    focuses = artifact.get("focuses", [])
    if isinstance(focuses, list):
        for focus in focuses:
            if not isinstance(focus, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(focus.get("id")),
                        _cell(focus.get("priority")),
                        _cell(focus.get("readiness")),
                        _cell(focus.get("status")),
                        _cell(focus.get("question")),
                        _json_cell(focus.get("coverage")),
                        _cell(_format_refs(focus.get("evidence_refs"))),
                        _cell("; ".join(focus.get("suggested_queries", [])))
                        if isinstance(focus.get("suggested_queries"), list)
                        else "",
                    ]
                )
                + " |"
            )
    lines.append("")

    lines.extend(_section("Rationales"))
    if isinstance(focuses, list) and focuses:
        for focus in focuses:
            if not isinstance(focus, dict):
                continue
            lines.append(f"### {_cell(focus.get('id'))}")
            lines.append("")
            lines.append(_cell(focus.get("rationale")))
            lines.append("")
    else:
        lines.extend(["_None._", ""])

    lines.extend(_section("Coverage Gaps"))
    gaps = artifact.get("coverage_gaps", [])
    if isinstance(gaps, list) and gaps:
        lines.extend(["| kind | description | evidence_refs |", "| --- | --- | --- |"])
        for gap in gaps:
            if not isinstance(gap, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(gap.get("kind")),
                        _cell(gap.get("description")),
                        _cell(_format_refs(gap.get("evidence_refs"))),
                    ]
                )
                + " |"
            )
        lines.append("")
    else:
        lines.extend(["_None._", ""])

    lines.extend(_section("Notes"))
    lines.extend(_bullet_list(artifact.get("notes", [])))
    return "\n".join(lines).rstrip() + "\n"


def _render_assessment(artifact: dict[str, Any]) -> str:
    lines = _heading("Research Assessment")
    focus = artifact.get("focus", {})
    focus_id = focus.get("id") if isinstance(focus, dict) else None
    evidence_packet = artifact.get("evidence_packet", {})
    snippets = evidence_packet.get("snippets", []) if isinstance(evidence_packet, dict) else []
    paper_leads = (
        evidence_packet.get("paper_leads", []) if isinstance(evidence_packet, dict) else []
    )
    relations = artifact.get("relations", [])
    relation_counts = _relation_counts(relations)
    relation_mix = ", ".join(f"{key}: {value}" for key, value in sorted(relation_counts.items()))

    lines.extend(
        [
            f"- schema_version: {_cell(artifact.get('schema_version'))}",
            f"- focus: {_cell(focus_id)}",
            f"- snippets: {len(snippets) if isinstance(snippets, list) else 0}",
            f"- paper_leads: {len(paper_leads) if isinstance(paper_leads, list) else 0}",
            f"- relations: {len(relations) if isinstance(relations, list) else 0}",
            f"- relation_mix: {_cell(relation_mix)}",
            "",
        ]
    )

    review = artifact.get("review", {})
    if isinstance(review, dict) and review:
        lines.extend(_section("Review Summary"))
        lines.extend([_cell(review.get("summary")), ""])
        lines.extend(_section("Review Sections"))
        sections = review.get("sections", [])
        if isinstance(sections, list) and sections:
            for section in sections:
                if not isinstance(section, dict):
                    continue
                lines.append(f"### {_cell(section.get('title'))}")
                lines.append("")
                lines.append(_cell(section.get("body")))
                lines.append("")
        else:
            lines.extend(["_None._", ""])

        lines.extend(_section("Limitations"))
        lines.extend(_bullet_list(review.get("limitations", [])))
        lines.extend(_section("Next Queries"))
        lines.extend(_bullet_list(review.get("next_queries", [])))

    lines.extend(_section("Relations"))
    if isinstance(relations, list) and relations:
        lines.extend(
            [
                "| type | claim | rationale | status | promotion_hint | source_refs |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(relation.get("type")),
                        _cell(relation.get("claim")),
                        _cell(relation.get("rationale")),
                        _cell(relation.get("epistemic_status")),
                        _cell(relation.get("promotion_hint")),
                        _cell(_format_refs(relation.get("source_refs"))),
                    ]
                )
                + " |"
            )
        lines.append("")
    else:
        lines.extend(["_None._", ""])

    lines.extend(_section("Candidate Obligations"))
    obligations = artifact.get("candidate_obligations", [])
    if isinstance(obligations, list) and obligations:
        lines.extend(["| kind | content | source_refs |", "| --- | --- | --- |"])
        for obligation in obligations:
            if not isinstance(obligation, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(obligation.get("kind")),
                        _cell(obligation.get("content")),
                        _cell(_format_refs(obligation.get("source_refs"))),
                    ]
                )
                + " |"
            )
        lines.append("")
    else:
        lines.extend(["_None._", ""])

    return "\n".join(lines).rstrip() + "\n"


def _render_stop(artifact: dict[str, Any]) -> str:
    lines = _heading("Research Stop Criteria")
    lines.extend(
        [
            f"- schema_version: {_cell(artifact.get('schema_version'))}",
            f"- recommendation: {_cell(artifact.get('recommendation'))}",
            f"- should_stop: {_cell(artifact.get('should_stop'))}",
            "",
        ]
    )
    dimensions = artifact.get("dimensions", {})
    lines.extend(_section("Dimensions"))
    if isinstance(dimensions, dict) and dimensions:
        lines.extend(["| dimension | status | score | reason |", "| --- | --- | --- | --- |"])
        for name, dimension in sorted(dimensions.items()):
            if not isinstance(dimension, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(name),
                        _cell(dimension.get("status")),
                        _cell(dimension.get("score")),
                        _cell(dimension.get("reason")),
                    ]
                )
                + " |"
            )
        lines.append("")
    else:
        lines.extend(["_None._", ""])

    lines.extend(_section("Reasons"))
    lines.extend(_bullet_list(artifact.get("reasons", [])))
    lines.extend(_section("Metrics"))
    metrics = artifact.get("metrics", {})
    if isinstance(metrics, dict) and metrics:
        for key, value in sorted(metrics.items()):
            lines.append(f"- {key}: {_cell(value)}")
        lines.append("")
    else:
        lines.extend(["_None._", ""])
    return "\n".join(lines).rstrip() + "\n"


def render_research_artifact_markdown(artifact: dict[str, Any]) -> str:
    """Render a package-native research artifact as readable Markdown."""
    kind = artifact.get("kind")
    if kind == "focus_synthesis":
        return _render_focus_synthesis(artifact)
    if kind == "assessment":
        return _render_assessment(artifact)
    if kind == "research_stop":
        return _render_stop(artifact)
    raise ResearchReportError(f"unsupported research artifact kind: {kind!r}")


__all__ = ["ResearchReportError", "render_research_artifact_markdown"]
