"""Sectioned final-report writing helpers for the package-native research CLI."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast

from gaia.cli.commands.research_providers import (
    _resolve_litellm_model,
    _run_analysis_provider_litellm,
)
from gaia.cli.commands.research_runtime import _read_json_object_path, _update_run_state
from gaia.engine.research import (
    ResearchPackage,
    render_markdown_with_research_citations,
)
from gaia.engine.research.run import ResearchRunStart


def _read_json_object_ref(ref: str, *, label: str) -> dict[str, object]:
    path = Path(ref)
    if not path.exists():
        msg = f"{label} not found: {ref}"
        raise FileNotFoundError(msg)
    return _read_json_object_path(path)


def _report_provider_input(
    *,
    phase: str,
    topic: str,
    language: str,
    artifact_paths: list[Path],
    focus: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "type": "gaia.research.report_request",
        "phase": phase,
        "topic": topic,
        "language": language,
        "focus": focus,
        "artifacts": [str(path) for path in artifact_paths],
    }
    if extra:
        payload.update(extra)
    return payload


def _report_ref_key(ref: object) -> tuple[str, str] | None:
    if isinstance(ref, str) and ref:
        if ref.startswith("gcn_"):
            return "variable", ref
        if ref.isdigit():
            return "paper", ref
        return "variable", ref
    if not isinstance(ref, dict):
        return None
    kind = ref.get("kind")
    if not isinstance(kind, str) or not kind:
        return None
    ref_id = ref.get("id") or ref.get("paper_id") or ref.get("ref")
    if isinstance(ref_id, int):
        ref_id = str(ref_id)
    if not isinstance(ref_id, str) or not ref_id:
        return None
    return kind, ref_id


def _report_section_ref_keys(section: dict[str, object]) -> list[tuple[str, str]]:
    refs = section.get("evidence_refs")
    if not isinstance(refs, list):
        return []
    keys: list[tuple[str, str]] = []
    for ref in refs:
        key = _report_ref_key(ref)
        if key is not None and key not in keys:
            keys.append(key)
    return keys


def _item_report_ref_keys(item: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    kind = item.get("kind")
    item_id = item.get("id")
    if isinstance(kind, str) and isinstance(item_id, str) and item_id:
        keys.add((kind, item_id))
        if kind == "variable":
            keys.add(("item", item_id))
    stable_item_id = item.get("item_id")
    if isinstance(stable_item_id, str) and stable_item_id:
        keys.add(("item", stable_item_id))
    source = item.get("source")
    paper_id = source.get("paper_id") if isinstance(source, dict) else None
    if isinstance(paper_id, str) and paper_id:
        keys.add(("paper", paper_id))
    package_ref_payload = item.get("package_ref")
    package_ref = package_ref_payload.get("ref") if isinstance(package_ref_payload, dict) else None
    if isinstance(package_ref, str) and package_ref:
        keys.add(("package_ref", package_ref))
    return keys


def _paper_lead_report_ref_keys(lead: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    paper_id = lead.get("paper_id")
    if isinstance(paper_id, str) and paper_id:
        keys.add(("paper", paper_id))
    variable_ids = lead.get("variable_ids")
    if isinstance(variable_ids, list):
        for variable_id in variable_ids:
            if isinstance(variable_id, str) and variable_id:
                keys.add(("variable", variable_id))
    return keys


def _citation_report_ref_keys(citation: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    paper_id = citation.get("paper_id")
    if isinstance(paper_id, str) and paper_id:
        keys.add(("paper", paper_id))
    source_kind = citation.get("source_kind")
    source_id = citation.get("source_id")
    if isinstance(source_kind, str) and isinstance(source_id, str) and source_id:
        keys.add((source_kind, source_id))
    for field, kind in (("item_ids", "item"), ("variable_ids", "variable")):
        values = citation.get(field)
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str) and value:
                    keys.add((kind, value))
    return keys


def _relation_report_ref_keys(relation: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    source_refs = relation.get("source_refs")
    if not isinstance(source_refs, list):
        return keys
    for ref in source_refs:
        key = _report_ref_key(ref)
        if key is not None:
            keys.add(key)
    return keys


def _report_citation_from_item(item: dict[str, Any], citation_id: str) -> dict[str, Any]:
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
    stable_item_id = item.get("item_id") or item.get("id")
    if isinstance(stable_item_id, str) and stable_item_id:
        citation["item_ids"].append(stable_item_id)
    if item.get("kind") == "variable" and isinstance(item.get("id"), str):
        citation["variable_ids"].append(str(item["id"]))
    if isinstance(paper_id, str) and paper_id:
        citation["paper_id"] = paper_id
    elif isinstance(item.get("id"), str):
        citation["source_id"] = item["id"]
    return citation


def _report_citations_from_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        source = item.get("source")
        source_payload = source if isinstance(source, dict) else {}
        paper_id = source_payload.get("paper_id")
        if isinstance(paper_id, str) and paper_id:
            key = ("paper", paper_id)
        else:
            item_id = item.get("id") or item.get("item_id")
            if not isinstance(item_id, str) or not item_id:
                continue
            key = (str(item.get("kind") or "item"), item_id)
        citation = by_key.get(key)
        if citation is None:
            citation = _report_citation_from_item(item, f"section_citation_{len(citations) + 1}")
            by_key[key] = citation
            citations.append(citation)
            continue
        stable_item_id = item.get("item_id") or item.get("id")
        if isinstance(stable_item_id, str) and stable_item_id not in citation["item_ids"]:
            citation["item_ids"].append(stable_item_id)
        if (
            item.get("kind") == "variable"
            and isinstance(item.get("id"), str)
            and item["id"] not in citation["variable_ids"]
        ):
            citation["variable_ids"].append(item["id"])
    return citations


def _append_unique_dict(
    values: list[dict[str, Any]],
    value: dict[str, Any],
    *,
    seen: set[str],
) -> None:
    key = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if key in seen:
        return
    seen.add(key)
    values.append(dict(value))


def _append_unique_keyed_dict(
    values: list[dict[str, Any]],
    value: dict[str, Any],
    *,
    key: str,
    seen: set[str],
) -> None:
    if key in seen:
        return
    seen.add(key)
    values.append(dict(value))


def _item_report_dedupe_key(item: dict[str, Any]) -> str:
    kind = item.get("kind") or "item"
    source_id = item.get("id") or item.get("item_id")
    if isinstance(source_id, str) and source_id:
        return f"{kind}:{source_id}"
    source = item.get("source")
    paper_id = source.get("paper_id") if isinstance(source, dict) else None
    return (
        f"paper:{paper_id}"
        if isinstance(paper_id, str) and paper_id
        else json.dumps(
            item,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _paper_lead_report_dedupe_key(lead: dict[str, Any]) -> str:
    paper_id = lead.get("paper_id")
    return (
        str(paper_id)
        if isinstance(paper_id, str) and paper_id
        else json.dumps(
            lead,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _artifact_evidence_packets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    evidence_packet = payload.get("evidence_packet")
    if isinstance(evidence_packet, dict):
        packets.append(evidence_packet)
    if payload.get("kind") in {"research_landscape", "selected_evidence"}:
        packets.append(payload)
    return packets


def _collect_matching_packet_records(
    packet: dict[str, Any],
    *,
    ref_keys: set[tuple[str, str]],
    items: list[dict[str, Any]],
    paper_leads: list[dict[str, Any]],
    seen_items: set[str],
    seen_leads: set[str],
) -> set[tuple[str, str]]:
    matched: set[tuple[str, str]] = set()
    packet_items = packet.get("items")
    if isinstance(packet_items, list):
        for item in packet_items:
            if not isinstance(item, dict):
                continue
            item_keys = _item_report_ref_keys(item)
            if item_keys.isdisjoint(ref_keys):
                continue
            matched.update(item_keys.intersection(ref_keys))
            _append_unique_keyed_dict(
                items,
                item,
                key=_item_report_dedupe_key(item),
                seen=seen_items,
            )

    packet_leads = packet.get("paper_leads")
    if isinstance(packet_leads, list):
        for lead in packet_leads:
            if not isinstance(lead, dict):
                continue
            lead_keys = _paper_lead_report_ref_keys(lead)
            if lead_keys.isdisjoint(ref_keys):
                continue
            matched.update(lead_keys.intersection(ref_keys))
            _append_unique_keyed_dict(
                paper_leads,
                lead,
                key=_paper_lead_report_dedupe_key(lead),
                seen=seen_leads,
            )
    return matched


def _collect_matching_relations(
    payload: dict[str, Any],
    *,
    ref_keys: set[tuple[str, str]],
    relations: list[dict[str, Any]],
    seen_relations: set[str],
) -> set[tuple[str, str]]:
    matched: set[tuple[str, str]] = set()
    payload_relations = payload.get("relations")
    if not isinstance(payload_relations, list):
        return matched
    for relation in payload_relations:
        if not isinstance(relation, dict):
            continue
        relation_keys = _relation_report_ref_keys(relation)
        if relation_keys.isdisjoint(ref_keys):
            continue
        matched.update(relation_keys.intersection(ref_keys))
        _append_unique_dict(relations, relation, seen=seen_relations)
    return matched


def _collect_matching_citations(
    payload: dict[str, Any],
    *,
    ref_keys: set[tuple[str, str]],
    citations: list[dict[str, Any]],
    seen_citations: set[str],
) -> set[tuple[str, str]]:
    matched: set[tuple[str, str]] = set()
    payload_citations = payload.get("citations")
    if not isinstance(payload_citations, list):
        return matched
    for citation in payload_citations:
        if not isinstance(citation, dict):
            continue
        citation_keys = _citation_report_ref_keys(citation)
        if citation_keys.isdisjoint(ref_keys):
            continue
        matched.update(citation_keys.intersection(ref_keys))
        _append_unique_dict(citations, citation, seen=seen_citations)
    return matched


def _collect_report_section_evidence(
    section: dict[str, object],
    *,
    artifact_paths: list[Path],
) -> dict[str, object]:
    ref_keys = set(_report_section_ref_keys(section))
    context: dict[str, object] = {
        "refs": [
            {"kind": kind, "id": ref_id} for kind, ref_id in _report_section_ref_keys(section)
        ],
        "items": [],
        "paper_leads": [],
        "relations": [],
        "citations": [],
        "missing_refs": [],
    }
    if not ref_keys:
        return context

    items = cast(list[dict[str, Any]], context["items"])
    paper_leads = cast(list[dict[str, Any]], context["paper_leads"])
    relations = cast(list[dict[str, Any]], context["relations"])
    citations = cast(list[dict[str, Any]], context["citations"])
    seen_items: set[str] = set()
    seen_leads: set[str] = set()
    seen_relations: set[str] = set()
    seen_citations: set[str] = set()
    matched_keys: set[tuple[str, str]] = set()

    for path in artifact_paths:
        if not path.exists():
            continue
        payload = _read_json_object_path(path)
        for packet in _artifact_evidence_packets(payload):
            matched_keys.update(
                _collect_matching_packet_records(
                    packet,
                    ref_keys=ref_keys,
                    items=items,
                    paper_leads=paper_leads,
                    seen_items=seen_items,
                    seen_leads=seen_leads,
                )
            )
        matched_keys.update(
            _collect_matching_relations(
                payload,
                ref_keys=ref_keys,
                relations=relations,
                seen_relations=seen_relations,
            )
        )
        matched_keys.update(
            _collect_matching_citations(
                payload,
                ref_keys=ref_keys,
                citations=citations,
                seen_citations=seen_citations,
            )
        )

    for citation in _report_citations_from_items(items):
        _append_unique_dict(citations, citation, seen=seen_citations)

    context["missing_refs"] = [
        {"kind": kind, "id": ref_id}
        for kind, ref_id in _report_section_ref_keys(section)
        if (kind, ref_id) not in matched_keys
    ]
    return context


def _report_citation_primary_key(citation: dict[str, Any]) -> str:
    paper_id = citation.get("paper_id")
    if isinstance(paper_id, str) and paper_id:
        return f"paper:{paper_id}"
    source_kind = citation.get("source_kind")
    source_id = citation.get("source_id")
    if isinstance(source_kind, str) and isinstance(source_id, str) and source_id:
        return f"{source_kind}:{source_id}"
    keys = sorted(_citation_report_ref_keys(citation))
    if keys:
        return "refs:" + json.dumps(keys, ensure_ascii=False)
    payload = dict(citation)
    payload.pop("id", None)
    return "payload:" + json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _merge_report_citation_values(target: dict[str, Any], source: dict[str, Any]) -> None:
    for field in ("item_ids", "variable_ids"):
        existing_values = target.get(field)
        if not isinstance(existing_values, list):
            existing_values = []
            target[field] = existing_values
        values = source.get(field)
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str) and value and value not in existing_values:
                    existing_values.append(value)
    for field in ("title", "doi", "paper_id", "source_kind", "source_id"):
        if not target.get(field) and source.get(field):
            target[field] = source[field]


def _append_report_citation(
    by_key: dict[str, dict[str, Any]],
    citation: dict[str, Any],
) -> None:
    key = _report_citation_primary_key(citation)
    existing = by_key.get(key)
    if existing is None:
        by_key[key] = dict(citation)
        return
    _merge_report_citation_values(existing, citation)


def _fallback_report_citation_for_ref(kind: str, ref_id: str) -> dict[str, Any]:
    citation: dict[str, Any] = {
        "source_kind": kind,
        "source_id": ref_id,
        "title": None,
        "doi": None,
        "item_ids": [],
        "variable_ids": [],
    }
    if kind in {"variable", "item", "factor", "chain"}:
        citation["variable_ids"].append(ref_id)
    elif kind == "paper":
        citation["paper_id"] = ref_id
    return citation


def _append_context_citations(
    context_citations: object,
    by_key: dict[str, dict[str, Any]],
) -> None:
    if isinstance(context_citations, list):
        for citation in context_citations:
            if isinstance(citation, dict):
                _append_report_citation(by_key, citation)


def _append_context_item_citations(
    context_items: object,
    by_key: dict[str, dict[str, Any]],
) -> None:
    if isinstance(context_items, list):
        items = [item for item in context_items if isinstance(item, dict)]
        for citation in _report_citations_from_items(items):
            _append_report_citation(by_key, citation)


def _append_context_relation_citations(
    context_relations: object,
    by_key: dict[str, dict[str, Any]],
) -> None:
    if isinstance(context_relations, list):
        for relation in context_relations:
            if not isinstance(relation, dict):
                continue
            for kind, ref_id in sorted(_relation_report_ref_keys(relation)):
                _append_report_citation(
                    by_key,
                    _fallback_report_citation_for_ref(kind, ref_id),
                )


def _append_context_ref_citations(
    context_refs: object,
    by_key: dict[str, dict[str, Any]],
) -> None:
    if isinstance(context_refs, list):
        for ref in context_refs:
            key = _report_ref_key(ref)
            if key is not None:
                _append_report_citation(
                    by_key,
                    _fallback_report_citation_for_ref(*key),
                )


def _collect_context_report_citations(
    context: dict[str, object],
    by_key: dict[str, dict[str, Any]],
) -> None:
    _append_context_citations(context.get("citations"), by_key)
    _append_context_item_citations(context.get("items"), by_key)
    _append_context_relation_citations(context.get("relations"), by_key)
    _append_context_ref_citations(context.get("refs"), by_key)


def _sectioned_report_citations(section_contexts: list[dict[str, object]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    citations: list[dict[str, Any]] = []
    for context in section_contexts:
        _collect_context_report_citations(context, by_key)
    citations = list(by_key.values())
    for index, citation in enumerate(citations, start=1):
        citation["id"] = f"report_citation_{index}"
    return citations


def _section_id(section: object, *, fallback: str) -> str:
    if isinstance(section, dict):
        raw = section.get("id")
        if isinstance(raw, str) and raw:
            return raw
    return fallback


def _safe_output_suffix(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return safe[:80] or "section"


def _sections_from_report_plan(plan: dict[str, object]) -> list[dict[str, object]]:
    sections = plan.get("sections")
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, dict)]


def _section_markdown(path: Path) -> str:
    payload = _read_json_object_path(path)
    markdown = payload.get("markdown")
    if isinstance(markdown, str) and markdown.strip():
        return markdown.strip()
    title = payload.get("title")
    title_text = title if isinstance(title, str) and title.strip() else path.stem
    return f"## {title_text}\n\n"


def _draft_stitched_report(
    report_plan: dict[str, object],
    section_paths: list[Path],
) -> str:
    title = report_plan.get("title")
    title_text = title if isinstance(title, str) and title.strip() else "Evidence Review"
    abstract = report_plan.get("abstract")
    thesis = report_plan.get("thesis")
    parts = [f"# {title_text.strip()}"]
    if isinstance(abstract, str) and abstract.strip():
        parts.append(f"## 摘要\n\n{abstract.strip()}")
    if isinstance(thesis, str) and thesis.strip():
        parts.append(f"## 主要判断\n\n{thesis.strip()}")
    parts.extend(_section_markdown(path) for path in section_paths)
    return "\n\n".join(part.strip() for part in parts if part.strip())


def _normalize_report_markdown(markdown: str) -> str:
    text = markdown.strip()
    text = re.sub(r"(?<![\n#])(#{1,6} )", r"\n\n\1", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _unwrap_nested_report_citation_ref_lists(markdown: str) -> str:
    supported = "variable|factor|chain|package|paper|package_ref"
    nested_list = re.compile(r"\[((?:\[(?:" + supported + r"):[^\]]+\](?:,\s*)?){2,})\]")
    previous = None
    text = markdown
    while text != previous:
        previous = text
        text = nested_list.sub(r"\1", text)
    return text


def _report_citation_ref_replacements(citations: list[dict[str, Any]]) -> dict[str, str]:
    replacements: dict[str, str] = {}
    supported_kinds = {"variable", "factor", "chain", "package", "paper", "package_ref"}
    for citation in citations:
        paper_id = citation.get("paper_id")
        if isinstance(paper_id, str) and paper_id:
            replacements.setdefault(paper_id, f"[paper:{paper_id}]")
        source_kind = citation.get("source_kind")
        source_id = citation.get("source_id")
        if (
            isinstance(source_kind, str)
            and source_kind in supported_kinds
            and isinstance(source_id, str)
            and source_id
        ):
            replacements.setdefault(source_id, f"[{source_kind}:{source_id}]")
        for field in ("item_ids", "variable_ids"):
            values = citation.get(field)
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str) and value:
                    replacements.setdefault(value, f"[variable:{value}]")
    return replacements


def _normalize_report_citation_refs(markdown: str, citations: list[dict[str, Any]]) -> str:
    replacements = _report_citation_ref_replacements(citations)
    if not replacements:
        return markdown
    alternatives = "|".join(
        re.escape(ref_id) for ref_id in sorted(replacements, key=len, reverse=True)
    )
    bracketed_pattern = re.compile(
        r"(?<![A-Za-z0-9_:/.-])\[(" + alternatives + r")\](?![A-Za-z0-9_:/.-])"
    )
    text = bracketed_pattern.sub(lambda match: replacements[match.group(1)], markdown)
    bare_pattern = re.compile(r"(?<![A-Za-z0-9_:/.-])(" + alternatives + r")(?![A-Za-z0-9_:/.-])")
    return _unwrap_nested_report_citation_ref_lists(
        bare_pattern.sub(lambda match: replacements[match.group(1)], text)
    )


def _normalize_rendered_report_citation_wrappers(markdown: str) -> str:
    citation_group = r"((?:\[[0-9,\- ]+\]\s*(?:[,\uff0c\u3001]\s*)?)+)"

    def replace(match: re.Match[str]) -> str:
        inner = match.group(1).strip(" ,\uff0c\u3001")
        return re.sub(r"\]\s*(?=\[)", "], ", inner)

    text = re.sub(r"\uff08" + citation_group + r"\uff09", replace, markdown)
    return re.sub(r"\(" + citation_group + r"\)", replace, text)


def _run_sectioned_report_writing(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    topic: str,
    language: str,
    model: str,
    focus: str,
    field_map_path: Path | None,
    focus_path: Path,
    landscape_paths: list[Path],
    selected_evidence_paths: list[Path],
    assessment_paths: list[Path],
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
    report_section_concurrency: int,
    json_stream: bool,
) -> tuple[str | None, list[str]]:
    artifact_paths = [
        *([field_map_path] if field_map_path is not None else []),
        focus_path,
        *selected_evidence_paths,
        *assessment_paths,
    ]
    if not selected_evidence_paths or not assessment_paths:
        return None, []

    _update_run_state(run, {"phase": "report_plan"})
    report_plan_json = _run_analysis_provider_litellm(
        research_pkg,
        run,
        phase="report_plan",
        model=model,
        input_payload=_report_provider_input(
            phase="report_plan",
            topic=topic,
            language=language,
            artifact_paths=artifact_paths,
            focus=focus,
        ),
        output_name="report_plan",
        temperature=llm_temperature,
        timeout=llm_timeout,
        max_retries=llm_max_retries,
        max_tokens=llm_max_tokens,
        json_stream=json_stream,
    )
    report_plan = _read_json_object_ref(report_plan_json, label="report-plan JSON")
    sections = _sections_from_report_plan(report_plan)
    section_contexts = [
        _collect_report_section_evidence(
            section,
            artifact_paths=[
                *landscape_paths,
                *artifact_paths,
                Path(report_plan_json),
            ],
        )
        for section in sections
    ]

    def write_section(index: int, section: dict[str, object], context: dict[str, object]) -> str:
        section_id = _section_id(section, fallback=f"section_{index}")
        output_name = f"report_section_{_safe_output_suffix(section_id)}"
        return _run_analysis_provider_litellm(
            research_pkg,
            run,
            phase="report_section",
            model=model,
            input_payload=_report_provider_input(
                phase="report_section",
                topic=topic,
                language=language,
                artifact_paths=[*assessment_paths, Path(report_plan_json)],
                focus=focus,
                extra={
                    "section_id": section_id,
                    "section": section,
                    "section_evidence": context,
                },
            ),
            output_name=output_name,
            temperature=llm_temperature,
            timeout=llm_timeout,
            max_retries=llm_max_retries,
            max_tokens=llm_max_tokens,
            json_stream=json_stream,
        )

    concurrency = max(1, report_section_concurrency)
    section_refs_by_index: dict[int, str] = {}
    if concurrency == 1 or len(sections) <= 1:
        for index, section in enumerate(sections, start=1):
            section_refs_by_index[index] = write_section(
                index,
                section,
                section_contexts[index - 1],
            )
    else:
        with ThreadPoolExecutor(max_workers=min(concurrency, len(sections))) as executor:
            futures = {
                executor.submit(write_section, index, section, section_contexts[index - 1]): index
                for index, section in enumerate(sections, start=1)
            }
            for future in as_completed(futures):
                section_refs_by_index[futures[future]] = future.result()

    section_refs = [section_refs_by_index[index] for index in range(1, len(sections) + 1)]
    section_paths = [Path(section_ref) for section_ref in section_refs]

    draft_markdown = _draft_stitched_report(report_plan, section_paths)
    stitch_json = _run_analysis_provider_litellm(
        research_pkg,
        run,
        phase="report_stitch",
        model=model,
        input_payload=_report_provider_input(
            phase="report_stitch",
            topic=topic,
            language=language,
            artifact_paths=[*assessment_paths, Path(report_plan_json)],
            focus=focus,
            extra={
                "draft_markdown": draft_markdown,
                "stitch_policy": {
                    "primary_source": "draft_markdown is the complete article draft.",
                    "preserve": [
                        (
                            "Preserve the draft's section order, section headings, "
                            "paragraphs, citations, and substantive claims."
                        ),
                        "Preserve the assessment conclusion and uncertainty language.",
                        "Keep inline source refs already present in the draft.",
                        (
                            "Normalize every raw evidence id into renderer syntax: "
                            "[variable:<id>] for variable/item ids and [paper:<id>] "
                            "for paper ids."
                        ),
                    ],
                    "edit": [
                        "Improve title, abstract, transitions, paragraph flow, and conclusion.",
                        "Remove exact repetition and repair local formatting issues.",
                        "Add short connective sentences only when they improve continuity.",
                    ],
                    "avoid": [
                        "Do not compress the article into a short executive summary.",
                        "Do not drop sections or merge all sections into one paragraph.",
                        "Do not leave bare gcn_* ids or bare numeric paper ids in prose.",
                        "Do not add workflow, benchmark, trace, or implementation commentary.",
                    ],
                },
            },
        ),
        output_name="report_stitch",
        temperature=llm_temperature,
        timeout=llm_timeout,
        max_retries=llm_max_retries,
        max_tokens=llm_max_tokens,
        json_stream=json_stream,
    )
    stitch_payload = _read_json_object_ref(stitch_json, label="report-stitch JSON")
    markdown = stitch_payload.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        return None, [report_plan_json, *section_refs, stitch_json]
    citations = _sectioned_report_citations(section_contexts)
    rendered = _normalize_rendered_report_citation_wrappers(
        render_markdown_with_research_citations(
            _normalize_report_citation_refs(
                _normalize_report_markdown(markdown),
                citations,
            ),
            citations=citations,
            language=language,
        )
    )
    return rendered, [report_plan_json, *section_refs, stitch_json]


def _maybe_run_sectioned_report_writing(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    topic: str,
    language: str,
    analysis_provider: str,
    research_mode: str,
    model: str | None,
    assess_model: str | None,
    focus: str,
    field_map_path: Path | None,
    focus_path: Path,
    landscape_paths: list[Path],
    selected_evidence_paths: list[Path],
    assessment_paths: list[Path],
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
    report_section_concurrency: int,
    json_stream: bool,
) -> tuple[str | None, list[str]]:
    if analysis_provider != "litellm" or research_mode != "fast_package_native":
        return None, []
    return _run_sectioned_report_writing(
        research_pkg,
        run,
        topic=topic,
        language=language,
        model=_resolve_litellm_model(assess_model or model),
        focus=focus,
        field_map_path=field_map_path,
        focus_path=focus_path,
        landscape_paths=landscape_paths,
        selected_evidence_paths=selected_evidence_paths,
        assessment_paths=assessment_paths,
        llm_temperature=llm_temperature,
        llm_timeout=llm_timeout,
        llm_max_retries=llm_max_retries,
        llm_max_tokens=llm_max_tokens,
        report_section_concurrency=report_section_concurrency,
        json_stream=json_stream,
    )
