"""Markdown rendering for package-native research artifacts."""

from __future__ import annotations

import json
import re
from typing import Any


class ResearchReportError(ValueError):
    """Raised when a research artifact cannot be rendered."""


INLINE_REF_RE = re.compile(
    r"\[(variable|factor|chain|package|paper|package_ref):([A-Za-z0-9_.:-]+)\]"
)
ADJACENT_NUMERIC_REF_RE = re.compile(r"(?:\[\d+\])+")
CN_SENTENCE_PUNCTUATION = "\u3002\uff01\uff1f"
CN_CLAUSE_PUNCTUATION = "\uff0c\u3001\uff1b\uff1a"
CN_SENTENCE_CITATION_RE = re.compile(rf"([{CN_SENTENCE_PUNCTUATION}])(\[\d+(?:[-,]\d+)*\])")
CN_CLAUSE_CITATION_RE = re.compile(rf"([{CN_CLAUSE_PUNCTUATION}])(\[\d+(?:[-,]\d+)*\])")
EN_SENTENCE_CITATION_RE = re.compile(r"([.!?])(\[\d+(?:[-,]\d+)*\])")
CN_PUNCTUATION = f"{CN_SENTENCE_PUNCTUATION}{CN_CLAUSE_PUNCTUATION}"
CN_PUNCTUATION_SPACE_RE = re.compile(rf"([{CN_PUNCTUATION}])\s+(?=[\u4e00-\u9fff])")


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


def _replace_refs_in_bullet_list(items: object, context: dict[str, Any]) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["_None._", ""]
    lines = [f"- {_cell(_replace_inline_item_refs(item, context))}" for item in items]
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


def _add_citation_ref(
    ids: dict[tuple[str, str], str],
    kind: str,
    ref_id: object,
    citation_id: str,
) -> None:
    if isinstance(ref_id, str) and ref_id:
        ids.setdefault((kind, ref_id), citation_id)


def _citation_ids_by_ref(citations: object) -> dict[tuple[str, str], str]:
    ids: dict[tuple[str, str], str] = {}
    if not isinstance(citations, list):
        return ids
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        citation_id = citation.get("id")
        if not isinstance(citation_id, str):
            continue
        item_ids = citation.get("item_ids")
        if isinstance(item_ids, list):
            for item_id in item_ids:
                _add_citation_ref(ids, "variable", item_id, citation_id)
        variable_ids = citation.get("variable_ids")
        if isinstance(variable_ids, list):
            for variable_id in variable_ids:
                _add_citation_ref(ids, "variable", variable_id, citation_id)
        _add_citation_ref(ids, "paper", citation.get("paper_id"), citation_id)
        source_kind = citation.get("source_kind")
        source_id = citation.get("source_id")
        if isinstance(source_kind, str):
            _add_citation_ref(ids, source_kind, source_id, citation_id)
    return ids


def _citation_context(citations: object) -> dict[str, Any]:
    citations_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(citations, list):
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            citation_id = citation.get("id")
            if isinstance(citation_id, str) and citation_id:
                citations_by_id[citation_id] = citation
    return {
        "citation_ids_by_ref": _citation_ids_by_ref(citations),
        "citations_by_id": citations_by_id,
        "numbers_by_id": {},
        "ordered_ids": [],
    }


def _citation_number(citation_id: str, context: dict[str, Any]) -> int:
    numbers_by_id = context["numbers_by_id"]
    if citation_id not in numbers_by_id:
        numbers_by_id[citation_id] = len(context["ordered_ids"]) + 1
        context["ordered_ids"].append(citation_id)
    return int(numbers_by_id[citation_id])


def _compact_numbers(numbers: list[int]) -> str:
    unique_numbers = sorted(set(numbers))
    if not unique_numbers:
        return ""

    ranges: list[str] = []
    start = previous = unique_numbers[0]
    for number in unique_numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append(f"{start}-{previous}" if start != previous else str(start))
        start = previous = number
    ranges.append(f"{start}-{previous}" if start != previous else str(start))
    return ",".join(ranges)


def _compact_adjacent_numeric_refs(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        numbers = [int(value) for value in re.findall(r"\d+", match.group(0))]
        return f"[{_compact_numbers(numbers)}]"

    return ADJACENT_NUMERIC_REF_RE.sub(replace, text)


def _normalize_citation_punctuation(text: str) -> str:
    text = CN_SENTENCE_CITATION_RE.sub(r"\2\1", text)
    text = CN_CLAUSE_CITATION_RE.sub(r"\2\1", text)
    text = EN_SENTENCE_CITATION_RE.sub(r"\2\1", text)
    return CN_PUNCTUATION_SPACE_RE.sub(r"\1", text)


def _replace_inline_item_refs(text: object, context: dict[str, Any]) -> object:
    if not isinstance(text, str):
        return text

    def replace(match: re.Match[str]) -> str:
        kind, ref_id = match.groups()
        citation_id = context["citation_ids_by_ref"].get((kind, ref_id))
        if not citation_id:
            return match.group(0)
        return f"[{_citation_number(citation_id, context)}]"

    replaced = INLINE_REF_RE.sub(replace, text)
    replaced = _compact_adjacent_numeric_refs(replaced)
    return _normalize_citation_punctuation(replaced)


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


def _is_zh(language: object) -> bool:
    return isinstance(language, str) and language.lower().startswith("zh")


def _citation_title(citation: dict[str, Any], *, language: object = None) -> str:
    title = citation.get("title")
    if not isinstance(title, str) or not title or title.startswith("gcn_"):
        return "题名未解析" if _is_zh(language) else "Title metadata unresolved"
    return title


def _citation_reference(citation: dict[str, Any], number: int, *, language: object = None) -> str:
    title = _citation_title(citation, language=language)
    doi = citation.get("doi")
    if isinstance(doi, str) and doi:
        doi_text = f"DOI: {doi}."
    else:
        doi_text = "DOI 未提供。" if _is_zh(language) else "DOI unavailable."
    terminal_punctuation = (".", "?", "!", "\u3002", "\uff1f", "\uff01")
    separator = " " if title.endswith(terminal_punctuation) else ". "
    return f"[{number}] {title}{separator}{doi_text}"


def _render_citations(
    citations: object,
    *,
    language: object = None,
    context: dict[str, Any] | None = None,
) -> list[str]:
    lines = _section("参考文献" if _is_zh(language) else "Citations")
    if not isinstance(citations, list) or not citations:
        lines.extend(["_None._", ""])
        return lines

    if context is not None and context.get("ordered_ids"):
        citations_by_id = context["citations_by_id"]
        for citation_id in context["ordered_ids"]:
            citation = citations_by_id.get(citation_id)
            number = context["numbers_by_id"].get(citation_id)
            if isinstance(citation, dict) and isinstance(number, int):
                lines.append(_citation_reference(citation, number, language=language))
        lines.append("")
        return lines

    number = 1
    for citation in citations:
        if isinstance(citation, dict):
            lines.append(_citation_reference(citation, number, language=language))
            number += 1
    lines.append("")
    return lines


def render_markdown_with_research_citations(
    markdown: str,
    *,
    citations: object,
    language: object = None,
) -> str:
    """Replace inline research refs in arbitrary markdown and append references."""
    context = _citation_context(citations)
    rendered = _replace_inline_item_refs(markdown, context)
    rendered_text = rendered if isinstance(rendered, str) else str(rendered)
    rendered_text = rendered_text.rstrip()
    citation_lines = _render_citations(citations, language=language, context=context)
    if not context.get("ordered_ids"):
        return rendered_text + "\n"
    return rendered_text + "\n\n" + "\n".join(citation_lines).rstrip() + "\n"


def _render_evidence_table(
    table: object,
    *,
    context: dict[str, Any],
    language: object = None,
) -> list[str]:
    if not isinstance(table, list) or not table:
        return []

    rows = [row for row in table if isinstance(row, dict)]
    if not rows:
        return []

    columns: list[str] = []
    for row in rows:
        for key in row:
            if isinstance(key, str) and key not in columns:
                columns.append(key)

    lines = _section("证据概览" if _is_zh(language) else "Evidence Overview")
    lines.extend(
        [
            "| " + " | ".join(_cell(column) for column in columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                _cell(_replace_inline_item_refs(row.get(column), context)) for column in columns
            )
            + " |"
        )
    lines.append("")
    return lines


def _render_figure_specs(
    figures: object,
    *,
    context: dict[str, Any],
    language: object = None,
) -> list[str]:
    if not isinstance(figures, list) or not figures:
        return []

    lines = _section("图表建议" if _is_zh(language) else "Figure Suggestions")
    for index, figure in enumerate(figures, start=1):
        if not isinstance(figure, dict):
            continue
        title = figure.get("title") or f"Figure {index}"
        lines.append(
            f"### 图 {index}: {_cell(title)}"
            if _is_zh(language)
            else f"### Figure {index}: {_cell(title)}"
        )
        lines.append("")
        fields = [
            ("purpose", "用途"),
            ("visual_structure", "视觉结构"),
            ("data_needed", "所需数据"),
            ("takeaway", "预期结论"),
        ]
        for field, zh_label in fields:
            value = figure.get(field)
            if value in (None, "", [], {}):
                continue
            label = zh_label if _is_zh(language) else field.replace("_", " ").title()
            lines.append(f"- **{label}**: {_cell(_replace_inline_item_refs(value, context))}")
        lines.append("")
    return lines


def _render_assessment(artifact: dict[str, Any]) -> str:
    review = artifact.get("review", {})
    language = review.get("language") if isinstance(review, dict) else artifact.get("language")
    zh = _is_zh(language)
    title = review.get("title") if isinstance(review, dict) else None
    if not isinstance(title, str) or not title:
        title = "研究评估" if zh else "Research Assessment"
    lines = _heading(title)
    focus = artifact.get("focus", {})
    focus_id = focus.get("id") if isinstance(focus, dict) else None
    evidence_packet = artifact.get("evidence_packet", {})
    items = evidence_packet.get("items", []) if isinstance(evidence_packet, dict) else []
    paper_leads = (
        evidence_packet.get("paper_leads", []) if isinstance(evidence_packet, dict) else []
    )
    citations = artifact.get("citations", [])
    citation_context = _citation_context(citations)
    item_count = len(items) if isinstance(items, list) else 0
    paper_lead_count = len(paper_leads) if isinstance(paper_leads, list) else 0

    if isinstance(review, dict) and review:
        abstract = review.get("abstract")
        if isinstance(abstract, str) and abstract:
            lines.extend(_section("摘要" if zh else "Abstract"))
            lines.extend([_cell(_replace_inline_item_refs(abstract, citation_context)), ""])

        key_points = review.get("key_points", [])
        if isinstance(key_points, list) and key_points:
            lines.extend(_section("要点" if zh else "Key Points"))
            lines.extend(_replace_refs_in_bullet_list(key_points, citation_context))

        lines.extend(_section("综述正文" if zh else "Review"))
        lines.extend([f"### {'核心判断' if zh else 'Core Assessment'}", ""])
        lines.extend(
            [_cell(_replace_inline_item_refs(review.get("summary"), citation_context)), ""]
        )
        sections = review.get("sections", [])
        if isinstance(sections, list) and sections:
            for section in sections:
                if not isinstance(section, dict):
                    continue
                lines.append(f"### {_cell(section.get('title'))}")
                lines.append("")
                lines.append(
                    _cell(_replace_inline_item_refs(section.get("body"), citation_context))
                )
                lines.append("")
        else:
            lines.extend(["_None._", ""])

        lines.extend(
            _render_evidence_table(
                review.get("evidence_table", []),
                context=citation_context,
                language=language,
            )
        )

        lines.extend(
            _render_figure_specs(
                review.get("figure_specs", []),
                context=citation_context,
                language=language,
            )
        )

        lines.extend(_section("局限性" if zh else "Limitations"))
        limitations = review.get("limitations", [])
        if isinstance(limitations, list) and limitations:
            lines.extend(_replace_refs_in_bullet_list(limitations, citation_context))
        else:
            lines.extend(["_None._", ""])

        lines.extend(_section("后续研究问题" if zh else "Next Research Questions"))
        lines.extend(_replace_refs_in_bullet_list(review.get("next_queries", []), citation_context))
    else:
        lines.extend(
            [
                (
                    f"本报告围绕 `{_cell(focus_id)}` 评估 {item_count} 条检索证据和 "
                    f"{paper_lead_count} 篇候选文献。"
                    if zh
                    else (
                        f"Focus `{_cell(focus_id)}` is evaluated using {item_count} "
                        f"retrieved evidence record(s) and {paper_lead_count} candidate paper(s)."
                    )
                ),
                "",
            ]
        )

    lines.extend(_render_citations(citations, language=language, context=citation_context))

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


def _render_proposal(artifact: dict[str, Any]) -> str:
    lines = _heading("Research Proposal")
    source_assessment = artifact.get("source_assessment")
    focus_id = (
        source_assessment.get("focus_id")
        if isinstance(source_assessment, dict)
        else "assessment_focus"
    )
    lines.extend(
        [
            f"- schema_version: {_cell(artifact.get('schema_version'))}",
            f"- source_assessment: {_cell(focus_id)}",
            "",
        ]
    )

    lines.extend(_section("Proposals"))
    proposals = artifact.get("proposals", [])
    if isinstance(proposals, list) and proposals:
        lines.extend(
            [
                "| id | kind | status | priority | question | rationale | source_refs |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for proposal in proposals:
            if not isinstance(proposal, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(proposal.get("id")),
                        _cell(proposal.get("kind")),
                        _cell(proposal.get("status")),
                        _cell(proposal.get("priority")),
                        _cell(proposal.get("question")),
                        _cell(proposal.get("rationale")),
                        _cell(_format_refs(proposal.get("source_refs"))),
                    ]
                )
                + " |"
            )
        lines.append("")
    else:
        lines.extend(["_None._", ""])

    lines.extend(_section("Hypotheses"))
    hypotheses = artifact.get("hypotheses", [])
    if isinstance(hypotheses, list) and hypotheses:
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, dict):
                continue
            lines.append(f"- {_cell(hypothesis.get('content'))}")
        lines.append("")
    else:
        lines.extend(["_None._", ""])

    lines.extend(_section("Candidate Obligations"))
    obligations = artifact.get("candidate_obligations", [])
    if isinstance(obligations, list) and obligations:
        for obligation in obligations:
            if not isinstance(obligation, dict):
                continue
            kind = obligation.get("kind")
            prefix = f"{kind}: " if isinstance(kind, str) and kind else ""
            lines.append(f"- {_cell(prefix + str(obligation.get('content') or ''))}")
        lines.append("")
    else:
        lines.extend(["_None._", ""])

    lines.extend(_section("Notes"))
    lines.extend(_bullet_list(artifact.get("notes", [])))
    return "\n".join(lines).rstrip() + "\n"


def _reader_text(value: object, context: dict[str, Any]) -> str:
    replaced = _replace_inline_item_refs(value, context)
    text = "" if replaced is None else str(replaced)
    return INLINE_REF_RE.sub("", text).strip()


def _dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _list_like(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _review_payload(assessment: dict[str, Any]) -> dict[str, Any]:
    review = assessment.get("review")
    return review if isinstance(review, dict) else {}


def _review_language(assessments: list[dict[str, Any]]) -> object:
    for assessment in assessments:
        review = _review_payload(assessment)
        language = review.get("language") or assessment.get("language")
        if isinstance(language, str) and language:
            return language
    return "en"


def _focus_questions_by_id(focus_artifacts: list[dict[str, Any]]) -> dict[str, str]:
    questions: dict[str, str] = {}
    for artifact in focus_artifacts:
        for focus in _dicts(artifact.get("focuses")):
            focus_id = focus.get("id")
            question = focus.get("question")
            if isinstance(focus_id, str) and isinstance(question, str) and question.strip():
                questions.setdefault(focus_id, question.strip())
    return questions


def _assessment_focus_id(assessment: dict[str, Any]) -> str | None:
    focus = assessment.get("focus")
    focus_id = focus.get("id") if isinstance(focus, dict) else None
    return focus_id if isinstance(focus_id, str) and focus_id else None


def _assessment_title(
    assessment: dict[str, Any],
    *,
    focus_questions: dict[str, str],
    zh: bool,
) -> str:
    review = _review_payload(assessment)
    title = review.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    focus_id = _assessment_focus_id(assessment)
    if focus_id and focus_id in focus_questions:
        return focus_questions[focus_id]
    return "证据评估" if zh else "Evidence Assessment"


def _final_report_title(
    *,
    assessments: list[dict[str, Any]],
    focus_questions: dict[str, str],
    zh: bool,
) -> str:
    if len(assessments) == 1:
        return _assessment_title(assessments[0], focus_questions=focus_questions, zh=zh)
    return "综合循证研究报告" if zh else "Integrated Evidence Review"


def _namespaced_citations(assessments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for index, assessment in enumerate(assessments, start=1):
        for citation in _dicts(assessment.get("citations")):
            citation_id = citation.get("id")
            if not isinstance(citation_id, str) or not citation_id:
                continue
            namespaced = dict(citation)
            namespaced["id"] = f"a{index}_{citation_id}"
            citations.append(namespaced)
    return citations


def _append_abstract(
    lines: list[str],
    assessments: list[dict[str, Any]],
    *,
    context: dict[str, Any],
    zh: bool,
) -> None:
    reviews = [_review_payload(assessment) for assessment in assessments]
    abstracts = [
        _reader_text(review.get("abstract"), context)
        for review in reviews
        if _reader_text(review.get("abstract"), context)
    ]
    if abstracts:
        lines.extend(_section("摘要" if zh else "Abstract"))
        lines.extend([abstracts[0], ""])
        return
    summaries = [
        _reader_text(review.get("summary"), context)
        for review in reviews
        if _reader_text(review.get("summary"), context)
    ]
    if summaries:
        lines.extend(_section("摘要" if zh else "Abstract"))
        lines.extend([summaries[0], ""])


def _append_key_points(
    lines: list[str],
    assessments: list[dict[str, Any]],
    *,
    context: dict[str, Any],
    zh: bool,
) -> None:
    key_points: list[str] = []
    for assessment in assessments:
        for point in _list_like(_review_payload(assessment).get("key_points")):
            text = _reader_text(point, context)
            if text and text not in key_points:
                key_points.append(text)
    if not key_points:
        return
    lines.extend(_section("关键结论" if zh else "Key Findings"))
    for point in key_points[:8]:
        lines.append(f"- {point}")
    lines.append("")


def _append_assessment_review(
    lines: list[str],
    assessment: dict[str, Any],
    *,
    context: dict[str, Any],
    focus_questions: dict[str, str],
    include_title: bool,
    zh: bool,
) -> None:
    review = _review_payload(assessment)
    if include_title:
        lines.extend(
            _section(_assessment_title(assessment, focus_questions=focus_questions, zh=zh))
        )
    summary = _reader_text(review.get("summary"), context)
    if summary:
        lines.extend([f"### {'核心判断' if zh else 'Core Assessment'}", "", summary, ""])
    for section in _dicts(review.get("sections")):
        title = section.get("title")
        body = _reader_text(section.get("body"), context)
        if isinstance(title, str) and title.strip() and body:
            lines.extend([f"### {_cell(title.strip())}", "", body, ""])
    lines.extend(
        _render_evidence_table(
            review.get("evidence_table", []),
            context=context,
            language=review.get("language"),
        )
    )


def _append_relation_synthesis(
    lines: list[str],
    assessments: list[dict[str, Any]],
    *,
    context: dict[str, Any],
    zh: bool,
) -> None:
    grouped: dict[str, list[str]] = {}
    for assessment in assessments:
        for relation in _dicts(assessment.get("relations")):
            relation_type = relation.get("type")
            claim = _reader_text(relation.get("claim"), context)
            rationale = _reader_text(relation.get("rationale"), context)
            if not isinstance(relation_type, str) or not claim:
                continue
            sentence = f"{claim} {rationale}".strip()
            grouped.setdefault(relation_type, [])
            if sentence not in grouped[relation_type]:
                grouped[relation_type].append(sentence)
    ordered_types = ["supports", "opposes", "qualifies", "undercuts", "needs_more_evidence"]
    labels = {
        "supports": "支持性证据" if zh else "Supportive Evidence",
        "opposes": "反向证据" if zh else "Opposing Evidence",
        "qualifies": "限定条件" if zh else "Qualifying Evidence",
        "undercuts": "方法性削弱" if zh else "Methodological Undercuts",
        "needs_more_evidence": "仍缺关键证据" if zh else "Evidence Gaps",
    }
    if not any(grouped.get(relation_type) for relation_type in ordered_types):
        return
    lines.extend(_section("证据分层与争议点" if zh else "Evidence Grading And Tensions"))
    for relation_type in ordered_types:
        claims = grouped.get(relation_type, [])
        if not claims:
            continue
        lines.append(f"### {labels[relation_type]}")
        lines.append("")
        for claim in claims[:4]:
            lines.append(f"- {claim}")
        lines.append("")


def _append_limitations_and_tests(
    lines: list[str],
    assessments: list[dict[str, Any]],
    *,
    context: dict[str, Any],
    zh: bool,
) -> None:
    limitations: list[str] = []
    next_queries: list[str] = []
    for assessment in assessments:
        review = _review_payload(assessment)
        for item in _list_like(review.get("limitations")):
            text = _reader_text(item, context)
            if text and text not in limitations:
                limitations.append(text)
        for item in _list_like(review.get("next_queries")):
            text = _reader_text(item, context)
            if text and text not in next_queries:
                next_queries.append(text)
    if limitations:
        lines.extend(_section("局限性" if zh else "Limitations"))
        for limitation in limitations:
            lines.append(f"- {limitation}")
        lines.append("")
    if next_queries:
        lines.extend(_section("后续研究问题" if zh else "Future Research Questions"))
        for query in next_queries:
            lines.append(f"- {query}")
        lines.append("")


def render_final_research_report_markdown(
    *,
    focus_artifacts: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
) -> str:
    """Render the reader-facing evidence report for all completed analyses."""
    if not assessments:
        raise ResearchReportError("final report requires at least one assessment artifact")
    language = _review_language(assessments)
    zh = _is_zh(language)
    focus_questions = _focus_questions_by_id(focus_artifacts)
    citations = _namespaced_citations(assessments)
    context = _citation_context(citations)
    lines = _heading(
        _final_report_title(assessments=assessments, focus_questions=focus_questions, zh=zh)
    )
    _append_abstract(lines, assessments, context=context, zh=zh)
    _append_key_points(lines, assessments, context=context, zh=zh)
    for assessment in assessments:
        _append_assessment_review(
            lines,
            assessment,
            context=context,
            focus_questions=focus_questions,
            include_title=len(assessments) > 1,
            zh=zh,
        )
    _append_relation_synthesis(lines, assessments, context=context, zh=zh)
    _append_limitations_and_tests(lines, assessments, context=context, zh=zh)
    rendered_citations = _render_citations(citations, language=language, context=context)
    if context.get("ordered_ids"):
        lines.extend(rendered_citations)
    return "\n".join(lines).rstrip() + "\n"


def render_research_artifact_markdown(artifact: dict[str, Any]) -> str:
    """Render a package-native research artifact as readable Markdown."""
    kind = artifact.get("kind")
    if kind == "focus_synthesis":
        return _render_focus_synthesis(artifact)
    if kind == "assessment":
        return _render_assessment(artifact)
    if kind == "research_proposal":
        return _render_proposal(artifact)
    if kind == "research_stop":
        return _render_stop(artifact)
    raise ResearchReportError(f"unsupported research artifact kind: {kind!r}")


__all__ = [
    "ResearchReportError",
    "render_final_research_report_markdown",
    "render_research_artifact_markdown",
]
