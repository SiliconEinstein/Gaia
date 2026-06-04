"""Materialize LKM paper graphs as local Gaia packages."""

from __future__ import annotations

import json
import keyword
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gaia.engine.ir import LocalCanonicalGraph
from gaia.engine.ir.validator import validate_local_graph
from gaia.engine.packaging import (
    GaiaPackagingError,
    apply_package_priors,
    build_package_manifests,
    compile_loaded_package_artifact,
    load_gaia_package,
    write_compiled_artifacts,
)


@dataclass(frozen=True)
class MaterializedLKMPackage:
    """A generated local Gaia package backed by one LKM paper graph."""

    root: Path
    dist_name: str
    import_name: str
    source_ref: str
    paper_id: str
    index_id: str
    title: str | None
    doi: str | None
    exported_symbol: str | None
    claim_count: int
    question_count: int
    dependency_count: int
    skipped_factor_count: int
    paper_id_inferred: bool
    regenerated_existing: bool


@dataclass(frozen=True)
class _DependencyStatements:
    statements: list[str]
    skipped_factor_count: int


@dataclass(frozen=True)
class _Node:
    provider_id: str
    symbol: str
    type: str
    content: str
    title: str | None
    local_id: str | None
    role: str | None


def materialize_lkm_paper_package(
    payload: dict[str, Any],
    *,
    project_root: Path,
    index_id: str,
    paper_id: str,
    storage_root: Path | None = None,
) -> MaterializedLKMPackage:
    """Write, compile, and return a local Gaia package for an LKM paper graph."""
    item = _select_paper_item(payload, paper_id=paper_id)
    paper = _paper_metadata(item)
    paper_provider_id = _paper_id(paper)
    resolved_paper_id = paper_provider_id or paper_id
    source_ref = f"lkm:{index_id}:paper:{resolved_paper_id}"
    title = _text(paper.get("en_title")) or _text(paper.get("zh_title"))
    doi = _text(paper.get("doi"))
    dist_name = _dist_name(index_id=index_id, paper_id=resolved_paper_id, title=title)
    import_name = dist_name.removesuffix("-gaia").replace("-", "_")
    root = (storage_root or (project_root / ".gaia" / "lkm_packages")) / dist_name
    src = root / "src" / import_name
    regenerated_existing = root.exists()

    root.mkdir(parents=True, exist_ok=True)
    src.mkdir(parents=True, exist_ok=True)
    (root / ".gaia").mkdir(exist_ok=True)

    nodes = _collect_nodes(item, paper=paper, paper_id=resolved_paper_id)
    dependency_result = _dependency_statements(
        item,
        nodes=nodes,
        index_id=index_id,
        paper_id=resolved_paper_id,
        paper_title=title,
        doi=doi,
    )
    dependencies = dependency_result.statements
    exported = [node.symbol for node in nodes if node.type in {"claim", "question"}]
    exported_symbol = next((node.symbol for node in nodes if node.type == "claim"), None)

    _write_pyproject(
        root,
        dist_name=dist_name,
        import_name=import_name,
        index_id=index_id,
        paper_id=resolved_paper_id,
        source_ref=source_ref,
        title=title,
        doi=doi,
    )
    (src / "__init__.py").write_text(
        _module_text(
            nodes,
            dependencies=dependencies,
            exported=exported,
            index_id=index_id,
            paper_id=resolved_paper_id,
            source_ref=source_ref,
            paper_title=title,
            doi=doi,
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        _readme_text(
            dist_name=dist_name,
            source_ref=source_ref,
            title=title,
            doi=doi,
            claim_count=sum(1 for node in nodes if node.type == "claim"),
            question_count=sum(1 for node in nodes if node.type == "question"),
            dependency_count=len(dependencies),
        ),
        encoding="utf-8",
    )
    _compile_generated_package(root)
    return MaterializedLKMPackage(
        root=root,
        dist_name=dist_name,
        import_name=import_name,
        source_ref=source_ref,
        paper_id=resolved_paper_id,
        index_id=index_id,
        title=title,
        doi=doi,
        exported_symbol=exported_symbol,
        claim_count=sum(1 for node in nodes if node.type == "claim"),
        question_count=sum(1 for node in nodes if node.type == "question"),
        dependency_count=len(dependencies),
        skipped_factor_count=dependency_result.skipped_factor_count,
        paper_id_inferred=paper_provider_id is None,
        regenerated_existing=regenerated_existing,
    )


def _select_paper_item(payload: dict[str, Any], *, paper_id: str) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    papers = data.get("papers") if isinstance(data, dict) else None
    if isinstance(papers, list):
        candidates = [item for item in papers if isinstance(item, dict)]
    elif isinstance(papers, dict):
        candidates = [item for item in papers.values() if isinstance(item, dict)]
    else:
        candidates = []
    if not candidates and isinstance(payload.get("paper"), dict):
        candidates = [payload]
    if not candidates:
        raise GaiaPackagingError("LKM paper graph response did not include any paper candidates.")
    for item in candidates:
        metadata = _paper_metadata(item)
        candidate_id = _paper_id(metadata)
        if candidate_id == paper_id:
            return item
    returned_ids: list[str] = []
    for item in candidates:
        candidate_id = _paper_id(_paper_metadata(item))
        if candidate_id and candidate_id not in returned_ids:
            returned_ids.append(candidate_id)
    returned_ids.sort()
    if returned_ids:
        preview = ", ".join(returned_ids[:5])
        if len(returned_ids) > 5:
            preview = f"{preview}, ..."
        raise GaiaPackagingError(
            "LKM paper graph response did not include requested paper id "
            f"{paper_id!r}; returned paper ids: {preview}."
        )
    return candidates[0]


def _paper_metadata(item: dict[str, Any]) -> dict[str, Any]:
    paper = item.get("paper")
    if isinstance(paper, dict):
        return paper
    return item


def _paper_id(paper: dict[str, Any]) -> str | None:
    value = _text(paper.get("id"))
    if value:
        return value
    package_id = _text(paper.get("package_id"))
    if package_id and package_id.startswith("paper:"):
        return package_id.split(":", 1)[1]
    return None


def _collect_nodes(
    item: dict[str, Any],
    *,
    paper: dict[str, Any],
    paper_id: str,
) -> list[_Node]:
    nodes: list[_Node] = []
    seen_ids: set[str] = set()
    used_symbols: set[str] = set()
    for index, raw in enumerate(_raw_lkm_nodes(item)):
        node_type = (_text(raw.get("type")) or "").lower()
        if node_type not in {"claim", "question"}:
            continue
        content = _text(raw.get("content")) or _text(raw.get("title"))
        if not content:
            continue
        provider_id = (
            _text(raw.get("global_id"))
            or _text(raw.get("id"))
            or _text(raw.get("local_id"))
            or f"{node_type}_{index}"
        )
        if provider_id in seen_ids:
            continue
        seen_ids.add(provider_id)
        symbol_seed = _text(raw.get("local_id")) or _text(raw.get("title")) or provider_id
        symbol = _unique_symbol(
            _symbol_from_text(symbol_seed, fallback=f"{node_type}_{index}"),
            used_symbols,
        )
        nodes.append(
            _Node(
                provider_id=provider_id,
                symbol=symbol,
                type=node_type,
                content=content,
                title=_text(raw.get("title")),
                local_id=_text(raw.get("local_id")),
                role=_text(raw.get("role")),
            )
        )

    if any(node.type == "claim" for node in nodes):
        return nodes

    fallback_content = _fallback_claim_content(paper)
    if fallback_content:
        symbol = _unique_symbol(
            _symbol_from_text(_text(paper.get("package_id")) or paper_id),
            used_symbols,
        )
        nodes.insert(
            0,
            _Node(
                provider_id=f"paper:{paper_id}",
                symbol=symbol,
                type="claim",
                content=fallback_content,
                title=_text(paper.get("en_title")) or _text(paper.get("zh_title")),
                local_id=f"paper:{paper_id}",
                role="paper",
            ),
        )
    return nodes


def _raw_lkm_nodes(item: dict[str, Any]) -> list[dict[str, Any]]:
    raw_nodes: list[dict[str, Any]] = []
    for raw in _list(item.get("variables")):
        if isinstance(raw, dict):
            raw_nodes.append(raw)
    for factor in _list(item.get("factors")):
        if not isinstance(factor, dict):
            continue
        conclusion = factor.get("conclusion")
        if isinstance(conclusion, dict):
            raw_nodes.append({**conclusion, "role": conclusion.get("role") or "conclusion"})
        for premise in _list(factor.get("premises")):
            if isinstance(premise, dict):
                raw_nodes.append({**premise, "role": premise.get("role") or "premise"})
    graph = item.get("graph")
    if isinstance(graph, dict):
        for raw in _list(graph.get("nodes")):
            if isinstance(raw, dict):
                raw_nodes.append(_graph_node_payload(raw))
    return raw_nodes


def _raw_lkm_factors(item: dict[str, Any]) -> list[dict[str, Any]]:
    legacy_factors = [factor for factor in _list(item.get("factors")) if isinstance(factor, dict)]
    if legacy_factors:
        return legacy_factors
    return _graph_factors(item)


def _graph_factors(item: dict[str, Any]) -> list[dict[str, Any]]:
    graph = item.get("graph")
    if not isinstance(graph, dict):
        return []
    nodes_by_id = _graph_nodes_by_id(graph)
    edges = [edge for edge in _list(graph.get("edges")) if isinstance(edge, dict)]
    factors: list[dict[str, Any]] = []
    for factor in nodes_by_id.values():
        if _text(factor.get("type")) != "factor":
            continue
        factor_id = _text(factor.get("id"))
        if factor_id is None:
            continue
        premises, dependency_edges = _graph_factor_dependencies(
            edges,
            nodes_by_id=nodes_by_id,
            factor_id=factor_id,
        )
        factors.extend(
            _graph_factor_outputs(
                factor,
                edges=edges,
                nodes_by_id=nodes_by_id,
                factor_id=factor_id,
                premises=premises,
                dependency_edges=dependency_edges,
            )
        )
    return factors


def _graph_nodes_by_id(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for raw in _list(graph.get("nodes")):
        if not isinstance(raw, dict):
            continue
        node_id = _text(raw.get("id"))
        if node_id is not None:
            nodes_by_id[node_id] = _graph_node_payload(raw)
    return nodes_by_id


def _graph_factor_dependencies(
    edges: list[dict[str, Any]],
    *,
    nodes_by_id: dict[str, dict[str, Any]],
    factor_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    premises: list[dict[str, Any]] = []
    dependency_edges: list[dict[str, str]] = []
    for edge in edges:
        edge_type = _text(edge.get("type"))
        source_id = _text(edge.get("source"))
        target_id = _text(edge.get("target"))
        if target_id != factor_id or source_id is None or edge_type is None:
            continue
        if edge_type == "motivates":
            continue
        source = nodes_by_id.get(source_id)
        if source is None or _text(source.get("type")) != "claim":
            continue
        premises.append(source)
        dependency_edges.append({"type": edge_type, "source": source_id, "target": factor_id})
    return premises, dependency_edges


def _graph_factor_outputs(
    factor: dict[str, Any],
    *,
    edges: list[dict[str, Any]],
    nodes_by_id: dict[str, dict[str, Any]],
    factor_id: str,
    premises: list[dict[str, Any]],
    dependency_edges: list[dict[str, str]],
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for edge in edges:
        if _text(edge.get("type")) != "concludes" or _text(edge.get("source")) != factor_id:
            continue
        target_id = _text(edge.get("target"))
        conclusion = nodes_by_id.get(target_id or "")
        if conclusion is None or _text(conclusion.get("type")) != "claim":
            continue
        outputs.append(
            {
                **factor,
                "conclusion": {**conclusion, "role": conclusion.get("role") or "conclusion"},
                "premises": premises,
                "dependency_edges": dependency_edges,
                "factor_type": _text(factor.get("factor_type"))
                or _text(factor.get("kind"))
                or "factor",
                "global_id": _text(factor.get("global_id")) or factor_id,
                "local_id": _text(factor.get("local_id")) or factor_id,
            }
        )
    return outputs


def _graph_node_payload(raw: dict[str, Any]) -> dict[str, Any]:
    role = raw.get("role") or raw.get("kind")
    return {**raw, "role": role}


def _dependency_statements(
    item: dict[str, Any],
    *,
    nodes: list[_Node],
    index_id: str,
    paper_id: str,
    paper_title: str | None,
    doi: str | None,
) -> _DependencyStatements:
    symbol_by_provider_id = {
        node.provider_id: node.symbol for node in nodes if node.type == "claim"
    }
    statements: list[str] = []
    skipped_factor_count = 0
    used_labels: set[str] = set()
    for index, factor in enumerate(_raw_lkm_factors(item)):
        if not isinstance(factor, dict):
            continue
        conclusion = factor.get("conclusion")
        if not isinstance(conclusion, dict):
            skipped_factor_count += 1
            continue
        conclusion_id = _provider_id(conclusion)
        conclusion_symbol = symbol_by_provider_id.get(conclusion_id or "")
        if conclusion_symbol is None:
            skipped_factor_count += 1
            continue
        given: list[str] = []
        for premise in _list(factor.get("premises")):
            if not isinstance(premise, dict):
                continue
            premise_symbol = symbol_by_provider_id.get(_provider_id(premise) or "")
            if premise_symbol is not None:
                given.append(premise_symbol)
        if not given:
            skipped_factor_count += 1
            continue
        label = _unique_symbol(
            _symbol_from_text(_text(factor.get("local_id")) or f"lkm_factor_{index}"),
            used_labels,
        )
        metadata = {
            "provider": "lkm",
            "index_id": index_id,
            "paper_id": paper_id,
            "paper_title": paper_title,
            "doi": doi,
            "factor_id": _text(factor.get("global_id")) or _text(factor.get("local_id")),
            "factor_type": _text(factor.get("factor_type")),
            "subtype": _text(factor.get("subtype")),
            "dependency_edge_types": _dependency_edge_types(factor),
        }
        rationale = _factor_rationale(factor, metadata)
        statements.append(
            f"{label} = depends_on(\n"
            f"    {conclusion_symbol},\n"
            f"    given=[{', '.join(given)}],\n"
            f"    rationale={rationale!r},\n"
            f"    label={label!r},\n"
            f"    metadata={_clean_dict(metadata)!r},\n"
            ")\n"
        )
    return _DependencyStatements(
        statements=statements,
        skipped_factor_count=skipped_factor_count,
    )


def _dependency_edge_types(factor: dict[str, Any]) -> list[str] | None:
    edge_types = {
        edge_type
        for edge in _list(factor.get("dependency_edges"))
        if isinstance(edge, dict) and (edge_type := _text(edge.get("type")))
    }
    if not edge_types:
        return None
    return sorted(edge_types)


def _provider_id(raw: dict[str, Any]) -> str | None:
    return _text(raw.get("global_id")) or _text(raw.get("id")) or _text(raw.get("local_id"))


def _factor_rationale(factor: dict[str, Any], metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    background = _text(factor.get("background"))
    if background:
        parts.append(background)
    for step in _list(factor.get("steps")):
        if isinstance(step, dict):
            reasoning = _text(step.get("reasoning"))
            if reasoning:
                parts.append(reasoning)
    if parts:
        return "\n\n".join(parts)
    return "Derived from the LKM paper graph factor " + json.dumps(
        {k: v for k, v in metadata.items() if v is not None},
        ensure_ascii=False,
        sort_keys=True,
    )


def _module_text(
    nodes: list[_Node],
    *,
    dependencies: list[str],
    exported: list[str],
    index_id: str,
    paper_id: str,
    source_ref: str,
    paper_title: str | None,
    doi: str | None,
) -> str:
    imports = "from gaia.engine.lang import claim, depends_on, question\n\n"
    header = (
        '"""Generated Gaia package from an LKM paper graph.\n\n'
        "LKM factors are recorded as depends_on(...) scaffold dependencies. "
        "They preserve premise-conclusion structure for later Gaia review, "
        "but do not enter BP until materialized as formal reasoning.\n\n"
        "Do not edit generated claim text by hand; regenerate the package from LKM instead.\n"
        '"""\n\n' + imports
    )
    blocks: list[str] = [header]
    for node in nodes:
        metadata = {
            "provider": "lkm",
            "index_id": index_id,
            "paper_id": paper_id,
            "paper_title": paper_title,
            "doi": doi,
            "source_ref": source_ref,
            "node_id": node.provider_id,
            "local_id": node.local_id,
            "role": node.role,
        }
        ctor = "question" if node.type == "question" else "claim"
        blocks.append(
            f"{node.symbol} = {ctor}(\n"
            f"    {node.content!r},\n"
            f"    title={node.title!r},\n"
            f"    metadata={_clean_dict(metadata)!r},\n"
            ")\n\n"
        )
    blocks.extend(statement + "\n" for statement in dependencies)
    blocks.append("__all__ = [\n")
    for symbol in exported:
        blocks.append(f"    {symbol!r},\n")
    blocks.append("]\n")
    return "".join(blocks)


def _write_pyproject(
    root: Path,
    *,
    dist_name: str,
    import_name: str,
    index_id: str,
    paper_id: str,
    source_ref: str,
    title: str | None,
    doi: str | None,
) -> None:
    description = f"LKM paper package: {title or paper_id}"
    text = f"""\
[project]
name = {_toml_string(dist_name)}
version = "0.1.0"
description = {_toml_string(description)}
requires-python = ">=3.12"
dependencies = ["gaia-lang>=0.5.0a1"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{import_name}"]

[tool.gaia]
type = "knowledge-package"
namespace = "lkm"

[tool.gaia.source]
provider = "lkm"
kind = "paper"
index_id = {_toml_string(index_id)}
paper_id = {_toml_string(paper_id)}
ref = {_toml_string(source_ref)}
title = {_toml_string(title or "")}
doi = {_toml_string(doi or "")}
"""
    (root / "pyproject.toml").write_text(text, encoding="utf-8")


def _readme_text(
    *,
    dist_name: str,
    source_ref: str,
    title: str | None,
    doi: str | None,
    claim_count: int,
    question_count: int,
    dependency_count: int,
) -> str:
    return (
        f"# {title or dist_name}\n\n"
        f"- Source: `{source_ref}`\n"
        f"- DOI: {doi or 'n/a'}\n"
        f"- Claims: {claim_count}\n"
        f"- Questions: {question_count}\n"
        f"- Dependencies: {dependency_count} `depends_on(...)` scaffold records\n"
        "\n"
        "`depends_on(...)` is the default generated form for LKM factors. It is "
        "the authoring-scaffold counterpart of `derive(...)`: it records that "
        "a conclusion depends on premises, but keeps the relation unformalized "
        "until a user reviews and materializes it as formal Gaia reasoning.\n"
    )


def _compile_generated_package(root: Path) -> None:
    loaded = load_gaia_package(root)
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()
    validation = validate_local_graph(LocalCanonicalGraph(**ir))
    if validation.errors:
        raise GaiaPackagingError(
            "Generated LKM package did not compile cleanly: " + "; ".join(validation.errors)
        )
    manifests = build_package_manifests(loaded, compiled)
    write_compiled_artifacts(
        root,
        ir,
        manifests=manifests,
        formalization_manifest=compiled.formalization_manifest,
    )


def _fallback_claim_content(paper: dict[str, Any]) -> str | None:
    title = _text(paper.get("en_title")) or _text(paper.get("zh_title"))
    abstract = _text(paper.get("en_abstract")) or _text(paper.get("zh_abstract"))
    if title and abstract:
        return f"The LKM paper {title!r} reports the following abstract: {abstract}"
    if title:
        return f"The LKM paper {title!r} is available as a Gaia package source."
    if abstract:
        return f"An LKM paper reports the following abstract: {abstract}"
    return None


def _dist_name(*, index_id: str, paper_id: str, title: str | None) -> str:
    title_slug = _slug(title or "paper", max_chars=48)
    paper_slug = _slug(paper_id, max_chars=18)
    return f"lkm-{_slug(index_id, max_chars=24)}-{title_slug}-{paper_slug}-gaia"


def _slug(value: str, *, max_chars: int) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    if not slug:
        slug = "item"
    return slug[:max_chars].strip("-") or "item"


def _symbol_from_text(value: str | None, *, fallback: str = "item") -> str:
    if value and "::" in value:
        value = value.rsplit("::", 1)[1]
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    symbol = re.sub(r"\W+", "_", normalized).strip("_").lower()
    if not symbol:
        symbol = fallback
    if symbol[0].isdigit():
        symbol = f"k_{symbol}"
    if keyword.iskeyword(symbol):
        symbol = f"{symbol}_"
    return symbol


def _unique_symbol(base: str, used: set[str]) -> str:
    symbol = base
    suffix = 2
    while symbol in used:
        symbol = f"{base}_{suffix}"
        suffix += 1
    used.add(symbol)
    return symbol


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _toml_string(value: str) -> str:
    """Return a TOML basic string literal for metadata values."""
    parts = ['"']
    for char in value:
        codepoint = ord(char)
        if char == '"':
            parts.append('\\"')
        elif char == "\\":
            parts.append("\\\\")
        elif char == "\b":
            parts.append("\\b")
        elif char == "\t":
            parts.append("\\t")
        elif char == "\n":
            parts.append("\\n")
        elif char == "\f":
            parts.append("\\f")
        elif char == "\r":
            parts.append("\\r")
        elif codepoint < 0x20 or codepoint == 0x7F:
            parts.append(f"\\u{codepoint:04X}")
        else:
            parts.append(char)
    parts.append('"')
    return "".join(parts)


def _clean_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


__all__ = ["MaterializedLKMPackage", "materialize_lkm_paper_package"]
