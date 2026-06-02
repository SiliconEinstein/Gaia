"""Markdown rendering for package-native research artifacts."""

from __future__ import annotations

import json
import re
from typing import Any


class ResearchReportError(ValueError):
    """Raised when a research artifact cannot be rendered."""


INLINE_ITEM_REF_RE = re.compile(r"\[item:([A-Za-z0-9_.:-]+)\]")
ADJACENT_CITATION_REF_RE = re.compile(r"(\[citation_\d+\])(?:\1)+")


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


def _join_string_list(values: object) -> str:
    if not isinstance(values, list):
        return ""
    return "; ".join(str(value) for value in values if isinstance(value, str) and value)


def _citation_ids_by_item(citations: object) -> dict[str, str]:
    ids: dict[str, str] = {}
    if not isinstance(citations, list):
        return ids
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        citation_id = citation.get("id")
        item_ids = citation.get("item_ids")
        if not isinstance(citation_id, str) or not isinstance(item_ids, list):
            continue
        for item_id in item_ids:
            if isinstance(item_id, str) and item_id and item_id not in ids:
                ids[item_id] = citation_id
    return ids


def _replace_inline_item_refs(text: object, citation_ids_by_item: dict[str, str]) -> object:
    if not isinstance(text, str):
        return text

    def replace(match: re.Match[str]) -> str:
        item_id = match.group(1)
        citation_id = citation_ids_by_item.get(item_id)
        return f"[{citation_id}]" if citation_id else match.group(0)

    replaced = INLINE_ITEM_REF_RE.sub(replace, text)
    return ADJACENT_CITATION_REF_RE.sub(r"\1", replaced)


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


def _render_citations(citations: object) -> list[str]:
    lines = _section("Citations")
    if not isinstance(citations, list) or not citations:
        lines.extend(["_None._", ""])
        return lines

    lines.extend(
        [
            "| id | source | title | doi | item_ids | variable_ids |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        source = citation.get("paper_id") or citation.get("source_id")
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(citation.get("id")),
                    _cell(source),
                    _cell(citation.get("title")),
                    _cell(citation.get("doi")),
                    _cell(_join_string_list(citation.get("item_ids"))),
                    _cell(_join_string_list(citation.get("variable_ids"))),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _render_assessment(artifact: dict[str, Any]) -> str:
    lines = _heading("Research Assessment")
    focus = artifact.get("focus", {})
    focus_id = focus.get("id") if isinstance(focus, dict) else None
    evidence_packet = artifact.get("evidence_packet", {})
    items = evidence_packet.get("items", []) if isinstance(evidence_packet, dict) else []
    paper_leads = (
        evidence_packet.get("paper_leads", []) if isinstance(evidence_packet, dict) else []
    )
    citations = artifact.get("citations", [])
    citation_ids_by_item = _citation_ids_by_item(citations)
    item_count = len(items) if isinstance(items, list) else 0
    paper_lead_count = len(paper_leads) if isinstance(paper_leads, list) else 0

    lines.extend(
        [
            (
                f"Focus `{_cell(focus_id)}` is assessed against an evidence packet "
                f"containing {item_count} item(s) and {paper_lead_count} paper lead(s)."
            ),
            "",
        ]
    )

    review = artifact.get("review", {})
    if isinstance(review, dict) and review:
        lines.extend(_section("Mini Review"))
        lines.extend(["### Summary", ""])
        lines.extend(
            [_cell(_replace_inline_item_refs(review.get("summary"), citation_ids_by_item)), ""]
        )
        sections = review.get("sections", [])
        if isinstance(sections, list) and sections:
            for section in sections:
                if not isinstance(section, dict):
                    continue
                lines.append(f"### {_cell(section.get('title'))}")
                lines.append("")
                lines.append(
                    _cell(_replace_inline_item_refs(section.get("body"), citation_ids_by_item))
                )
                lines.append("")
        else:
            lines.extend(["_None._", ""])

        lines.extend(["### Limitations", ""])
        limitations = review.get("limitations", [])
        if isinstance(limitations, list) and limitations:
            lines.extend(
                [
                    f"- {_cell(_replace_inline_item_refs(item, citation_ids_by_item))}"
                    for item in limitations
                ]
            )
            lines.append("")
        else:
            lines.extend(["_None._", ""])

        lines.extend(["### Next Research Questions", ""])
        lines.extend(_bullet_list(review.get("next_queries", [])))

    lines.extend(_render_citations(citations))

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
