"""Markdown rendering for package-native research artifacts."""

from __future__ import annotations

import json
import re
from typing import Any


class ResearchReportError(ValueError):
    """Raised when a research artifact cannot be rendered."""


INLINE_ITEM_REF_RE = re.compile(r"\[item:([A-Za-z0-9_.:-]+)\]")
RELATION_LABELS = {
    "supports": "支持性证据",
    "opposes": "反对性证据",
    "qualifies": "限定性证据",
    "undercuts": "方法性削弱",
    "background_for": "背景证据",
    "needs_more_evidence": "证据不足",
}
RELATION_ORDER = [
    "supports",
    "opposes",
    "qualifies",
    "undercuts",
    "background_for",
    "needs_more_evidence",
]
STATUS_LABELS = {
    "candidate": "候选判断",
    "provisional": "暂定判断",
    "accepted": "已接受判断",
}
PROMOTION_HINT_LABELS = {
    "derive": "可进一步形式化为 derive 关系",
    "infer": "可进一步形式化为 infer 关系",
    "depends_on": "可进一步形式化为 depends_on 关系",
    "contradict": "可进一步形式化为 contradict 关系",
    "question": "适合转成后续 research question",
    "obligation": "适合转成待核查 obligation",
    "none": "暂不建议写回稳定知识图谱",
}
OBLIGATION_KIND_LABELS = {
    "needs_more_evidence": "需要补充证据",
    "needs_original_text": "需要核对原文",
    "needs_method_check": "需要方法核查",
    "needs_quantification": "需要定量化",
}


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


def _citation_ids_by_ref(citations: object) -> dict[tuple[str, str], str]:
    ids: dict[tuple[str, str], str] = {}
    if not isinstance(citations, list):
        return ids
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        citation_id = citation.get("id")
        if not isinstance(citation_id, str) or not citation_id:
            continue
        for item_id in citation.get("item_ids", []):
            if isinstance(item_id, str) and item_id:
                ids.setdefault(("item", item_id), citation_id)
        for variable_id in citation.get("variable_ids", []):
            if isinstance(variable_id, str) and variable_id:
                ids.setdefault(("variable", variable_id), citation_id)
        paper_id = citation.get("paper_id")
        if isinstance(paper_id, str) and paper_id:
            ids.setdefault(("paper", paper_id), citation_id)
        source_kind = citation.get("source_kind")
        source_id = citation.get("source_id")
        if isinstance(source_kind, str) and isinstance(source_id, str) and source_id:
            ids.setdefault((source_kind, source_id), citation_id)
    return ids


def _replace_inline_item_refs(text: object, citation_ids_by_item: dict[str, str]) -> object:
    if not isinstance(text, str):
        return text

    def replace(match: re.Match[str]) -> str:
        item_id = match.group(1)
        citation_id = citation_ids_by_item.get(item_id)
        return f"[{citation_id}]" if citation_id else match.group(0)

    return INLINE_ITEM_REF_RE.sub(replace, text)


def _append_unique_string(values: list[str], value: object) -> None:
    if isinstance(value, str) and value and value not in values:
        values.append(value)


def _label_from_snake(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "其他"
    return value.replace("_", " ")


def _source_labels_for_refs(
    refs: object,
    citation_ids_by_ref: dict[tuple[str, str], str],
) -> str:
    labels: list[str] = []
    if not isinstance(refs, list):
        return ""
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        kind = ref.get("kind")
        ref_id = ref.get("id") or ref.get("paper_id")
        if not isinstance(kind, str) or not isinstance(ref_id, str):
            continue
        citation_id = citation_ids_by_ref.get((kind, ref_id))
        if citation_id:
            _append_unique_string(labels, f"[{citation_id}]")
    if labels:
        return ", ".join(labels)
    return "来源保留在原始 assessment artifact 中"


def _relation_group_title(relation_type: object) -> str:
    if isinstance(relation_type, str):
        return RELATION_LABELS.get(relation_type, _label_from_snake(relation_type))
    return "其他证据"


def _relation_meta(relation: dict[str, Any]) -> str:
    status = relation.get("epistemic_status")
    promotion_hint = relation.get("promotion_hint")
    status_label = STATUS_LABELS.get(status) if isinstance(status, str) else None
    promotion_label = (
        PROMOTION_HINT_LABELS.get(promotion_hint) if isinstance(promotion_hint, str) else None
    )
    labels = [label for label in [status_label, promotion_label] if label]
    return "; ".join(labels)


def _render_evidence_interpretation(
    relations: object,
    *,
    citations: object,
    citation_ids_by_item: dict[str, str],
) -> list[str]:
    lines = _section("Evidence Interpretation")
    if not isinstance(relations, list) or not relations:
        lines.extend(["_None._", ""])
        return lines

    grouped: dict[str, list[dict[str, Any]]] = {}
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        relation_type = relation.get("type")
        key = relation_type if isinstance(relation_type, str) and relation_type else "other"
        grouped.setdefault(key, []).append(relation)

    citation_ids_by_ref = _citation_ids_by_ref(citations)
    ordered_types = [
        *[relation_type for relation_type in RELATION_ORDER if relation_type in grouped],
        *sorted(relation_type for relation_type in grouped if relation_type not in RELATION_ORDER),
    ]
    for relation_type in ordered_types:
        lines.append(f"### {_relation_group_title(relation_type)}")
        lines.append("")
        for relation in grouped[relation_type]:
            claim = _cell(_replace_inline_item_refs(relation.get("claim"), citation_ids_by_item))
            rationale = _cell(
                _replace_inline_item_refs(relation.get("rationale"), citation_ids_by_item)
            )
            source_labels = _source_labels_for_refs(
                relation.get("source_refs"),
                citation_ids_by_ref,
            )
            meta = _relation_meta(relation)
            line = f"- {claim}"
            if rationale:
                line += f" 依据: {rationale}"
            if source_labels:
                line += f" 来源: {source_labels}"
            if meta:
                line += f" 审查状态: {meta}"
            lines.append(line)
        lines.append("")
    return lines


def _render_open_assessment_questions(
    obligations: object,
    *,
    citations: object,
    citation_ids_by_item: dict[str, str],
) -> list[str]:
    lines = _section("Open Assessment Questions")
    if not isinstance(obligations, list) or not obligations:
        lines.extend(["_None._", ""])
        return lines

    citation_ids_by_ref = _citation_ids_by_ref(citations)
    for obligation in obligations:
        if not isinstance(obligation, dict):
            continue
        kind = obligation.get("kind")
        kind_label = (
            OBLIGATION_KIND_LABELS.get(kind, _label_from_snake(kind))
            if isinstance(kind, str)
            else "待解决问题"
        )
        content = _cell(_replace_inline_item_refs(obligation.get("content"), citation_ids_by_item))
        source_labels = _source_labels_for_refs(
            obligation.get("source_refs"),
            citation_ids_by_ref,
        )
        line = f"- **{kind_label}**: {content}"
        if source_labels:
            line += f" (相关来源: {source_labels})"
        lines.append(line)
    lines.append("")
    return lines


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
    relations = artifact.get("relations", [])
    citations = artifact.get("citations", [])
    citation_ids_by_item = _citation_ids_by_item(citations)
    relation_counts = _relation_counts(relations)
    relation_mix = ", ".join(f"{key}: {value}" for key, value in sorted(relation_counts.items()))

    lines.extend(
        [
            f"- schema_version: {_cell(artifact.get('schema_version'))}",
            f"- focus: {_cell(focus_id)}",
            f"- items: {len(items) if isinstance(items, list) else 0}",
            f"- paper_leads: {len(paper_leads) if isinstance(paper_leads, list) else 0}",
            f"- relations: {len(relations) if isinstance(relations, list) else 0}",
            f"- relation_mix: {_cell(relation_mix)}",
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
    lines.extend(
        _render_evidence_interpretation(
            relations,
            citations=citations,
            citation_ids_by_item=citation_ids_by_item,
        )
    )
    lines.extend(
        _render_open_assessment_questions(
            artifact.get("candidate_obligations", []),
            citations=citations,
            citation_ids_by_item=citation_ids_by_item,
        )
    )

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
