"""Normalized Gaia search result builders.

The provider commands may keep exposing raw upstream payloads, but
``--format gaia-json`` uses these helpers to produce a stable envelope
for downstream agents and future non-LKM providers.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from gaia.cli.commands.search.lkm._servers import DEFAULT_LKM_SERVER_ID


class SearchOutputFormat(StrEnum):
    """Output formats for provider-backed search commands."""

    RAW_JSON = "raw-json"
    GAIA_JSON = "gaia-json"


def normalize_lkm_knowledge(
    payload: dict[str, Any],
    *,
    query: str,
    kind: str = "knowledge",
    server_id: str = DEFAULT_LKM_SERVER_ID,
) -> dict[str, Any]:
    """Normalize LKM /search variables into Gaia search results."""
    data = _dict(payload.get("data"))
    variables = _list(data.get("variables")) or _list(payload.get("variables"))
    papers = _papers(payload)
    results = [
        _normalize_lkm_variable(variable, index=index, papers=papers, server_id=server_id)
        for index, variable in enumerate(variables)
        if isinstance(variable, dict)
    ]
    return _envelope(
        query=query,
        provider="lkm",
        kind=kind,
        results=results,
        server_id=server_id,
    )


def normalize_lkm_reasoning_search(
    payload: dict[str, Any],
    *,
    query: str,
    server_id: str = DEFAULT_LKM_SERVER_ID,
) -> dict[str, Any]:
    """Normalize LKM reasoning-chain search results."""
    data = _dict(payload.get("data"))
    chains = (
        _list(data.get("reasoning_chains"))
        or _list(data.get("chains"))
        or _list(data.get("items"))
        or _list(data.get("results"))
        or _list(payload.get("reasoning_chains"))
    )
    papers = _papers(payload)
    results = [
        _normalize_lkm_chain(chain, index=index, papers=papers, server_id=server_id)
        for index, chain in enumerate(chains)
        if isinstance(chain, dict)
    ]
    return _envelope(
        query=query,
        provider="lkm",
        kind="reasoning",
        results=results,
        server_id=server_id,
    )


def normalize_lkm_paper_graph(
    payload: dict[str, Any],
    *,
    query: str,
    server_id: str = DEFAULT_LKM_SERVER_ID,
) -> dict[str, Any]:
    """Normalize LKM paper graph responses into Gaia package candidates."""
    results = [
        _normalize_lkm_paper_graph_item(item, index=index, server_id=server_id)
        for index, item in enumerate(_paper_graph_items(payload))
    ]
    return _envelope(
        query=query,
        provider="lkm",
        kind="package",
        results=results,
        server_id=server_id,
    )


def _envelope(
    *,
    query: str,
    provider: str,
    kind: str,
    results: list[dict[str, Any]],
    server_id: str | None = None,
) -> dict[str, Any]:
    query_payload = {
        "text": query,
        "provider": provider,
        "kind": kind,
    }
    if server_id is not None:
        query_payload["server_id"] = server_id
    return {
        "schema_version": 1,
        "query": query_payload,
        "results": results,
    }


def _normalize_lkm_variable(
    variable: dict[str, Any],
    *,
    index: int,
    papers: dict[str, dict[str, Any]],
    server_id: str,
) -> dict[str, Any]:
    provider_id = (
        _string(variable.get("id")) or _string(variable.get("global_id")) or f"var_{index}"
    )
    source_package, local_id = _variable_source(variable)
    paper_id = _paper_id(source_package)
    paper = _paper_metadata(papers, source_package=source_package, paper_id=paper_id)
    object_kind = _lkm_variable_kind(_string(variable.get("type")))
    paper_title = _paper_title(paper)
    doi = _string(paper.get("doi"))
    actions: list[dict[str, Any]] = []
    if object_kind == "claim" and provider_id and variable.get("has_reasoning") is not False:
        claim_title = _string(variable.get("title"))
        actions.append(
            {
                "kind": "inspect",
                "ref": _lkm_ref(server_id, "claim", provider_id),
                "label": _inspect_label("claim", claim_title),
                "next_steps": (
                    f"gaia search lkm reasoning --server {server_id} --claim-id {provider_id}"
                ),
            }
        )
    actions.extend(_add_actions(paper_id, server_id=server_id, paper_title=paper_title, doi=doi))
    return {
        "id": _lkm_result_id(server_id, provider_id),
        "provider": "lkm",
        "kind": object_kind,
        "title": _string(variable.get("title")) or provider_id,
        "content": _string(variable.get("content")),
        "rank": {
            "score": _number(variable.get("score"), variable.get("rerank_score")),
            "score_kind": "retrieval",
        },
        "gaia": _gaia_identity(object_kind),
        "source": {
            "provider_id": provider_id,
            "server_id": server_id,
            "source_package": source_package,
            "paper_id": paper_id,
            "paper_title": paper_title,
            "doi": doi,
            "local_id": local_id,
            "role": _string(variable.get("role")),
            "has_evidence": variable.get("has_evidence"),
            "has_reasoning": variable.get("has_reasoning"),
        },
        "actions": actions,
        "raw": {"provider": "lkm", "payload": variable},
    }


def _normalize_lkm_chain(
    chain: dict[str, Any],
    *,
    index: int,
    papers: dict[str, dict[str, Any]],
    server_id: str,
) -> dict[str, Any]:
    provider_id = _chain_provider_id(chain, index=index)
    conclusion = _chain_conclusion(chain)
    paper_id = _string(chain.get("paper_id"))
    source_package = _string(chain.get("source_package")) or _chain_source_package(chain)
    if paper_id is None:
        paper_id = _paper_id(source_package)
    if source_package is None and paper_id is not None:
        source_package = f"paper:{paper_id}"
    paper = _paper_metadata(papers, source_package=source_package, paper_id=paper_id)
    paper_title = _paper_title(paper)
    doi = _string(paper.get("doi"))
    title = (
        _string(chain.get("title"))
        or _string(conclusion.get("title"))
        or paper_title
        or provider_id
    )
    content = _string(chain.get("content")) or _string(conclusion.get("content"))
    has_factors = bool(_list(chain.get("factors")))
    can_compile = _chain_can_compile(chain)
    actions: list[dict[str, Any]] = []
    if not can_compile and paper_id is not None:
        actions.append(
            {
                "kind": "inspect",
                "ref": _lkm_ref(server_id, "paper", paper_id),
                "label": _inspect_label("paper", paper_title),
                "next_steps": (
                    f"gaia search lkm package --server {server_id} --paper-id {paper_id}"
                ),
            }
        )
    actions.extend(_add_actions(paper_id, server_id=server_id, paper_title=paper_title, doi=doi))
    return {
        "id": _lkm_result_id(server_id, provider_id),
        "provider": "lkm",
        "kind": "reasoning_chain",
        "title": title,
        "content": content,
        "rank": {
            "score": _number(chain.get("score"), chain.get("rerank_score")),
            "score_kind": "retrieval",
        },
        "gaia": _gaia_identity("derive" if can_compile else None),
        "source": {
            "provider_id": provider_id,
            "server_id": server_id,
            "source_package": source_package,
            "paper_id": paper_id,
            "paper_title": paper_title,
            "doi": doi,
            "conclusion_id": _string(conclusion.get("id")) or _string(chain.get("conclusion_id")),
            "has_factors": has_factors,
            "can_compile": can_compile,
        },
        "actions": actions,
        "raw": {"provider": "lkm", "payload": chain},
    }


def _chain_provider_id(chain: dict[str, Any], *, index: int) -> str:
    provider_id = (
        _string(chain.get("id"))
        or _string(chain.get("chain_id"))
        or _string(chain.get("factor_id"))
    )
    if provider_id is not None:
        return provider_id
    for factor in _list(chain.get("factors")):
        if not isinstance(factor, dict):
            continue
        factor_id = _string(factor.get("id")) or _string(factor.get("factor_id"))
        if factor_id is not None:
            return factor_id
    return f"chain_{index}"


def _normalize_lkm_paper_graph_item(
    item: dict[str, Any],
    *,
    index: int,
    server_id: str,
) -> dict[str, Any]:
    paper = _dict(item.get("paper")) or item
    paper_id = _string(paper.get("id")) or _paper_id(_string(paper.get("package_id")))
    provider_id = f"paper:{paper_id}" if paper_id is not None else f"package:{index}"
    source_package = _string(paper.get("package_id"))
    if source_package is None and paper_id is not None:
        source_package = f"paper:{paper_id}"
    paper_title = _paper_title(paper)
    title = paper_title or source_package
    doi = _string(paper.get("doi"))
    content = _string(paper.get("en_abstract")) or _string(paper.get("zh_abstract"))
    return {
        "id": _lkm_result_id(server_id, provider_id),
        "provider": "lkm",
        "kind": "package",
        "title": title or provider_id,
        "content": content,
        "rank": {
            "score": _number(item.get("score"), item.get("rerank_score")),
            "score_kind": "retrieval",
        },
        "gaia": _gaia_identity("package"),
        "source": {
            "provider_id": paper_id,
            "server_id": server_id,
            "source_package": source_package,
            "paper_id": paper_id,
            "paper_title": paper_title,
            "doi": doi,
            "stats": _dict(item.get("stats")),
        },
        "actions": _add_actions(paper_id, server_id=server_id, paper_title=paper_title, doi=doi),
        "raw": {"provider": "lkm", "payload": item},
    }


def _gaia_identity(object_kind: str | None) -> dict[str, str | None]:
    return {
        "qid": None,
        "label": None,
        "package": None,
        "version": None,
        "import_name": None,
        "object_kind": object_kind,
    }


def _lkm_result_id(server_id: str, provider_id: str) -> str:
    return f"lkm:{server_id}:{provider_id}"


def _lkm_ref(server_id: str, kind: str, provider_id: str) -> str:
    return f"lkm:{server_id}:{kind}:{provider_id}"


def _inspect_label(kind: str, title: str | None) -> str:
    if title:
        return f'Inspect {kind} "{title}"'
    return f"Inspect {kind}"


def _add_actions(
    paper_id: str | None,
    *,
    server_id: str,
    paper_title: str | None,
    doi: str | None,
) -> list[dict[str, Any]]:
    if paper_id is None:
        return []
    ref = _lkm_ref(server_id, "paper", paper_id)
    return [
        {
            "kind": "add",
            "ref": ref,
            "label": _add_paper_label(paper_title, paper_id),
            "target": {
                "kind": "paper",
                "title": paper_title,
                "doi": doi,
                "server_id": server_id,
                "paper_id": paper_id,
            },
            "next_steps": f"gaia pkg add --lkm-server {server_id} --lkm-paper {paper_id}",
        }
    ]


def _add_paper_label(paper_title: str | None, paper_id: str) -> str:
    if paper_title:
        return f'Add paper "{paper_title}"'
    return f"Add LKM paper {paper_id}"


def _lkm_variable_kind(raw_type: str | None) -> str:
    if raw_type is None:
        return "claim"
    return {
        "claim": "claim",
        "question": "question",
    }.get(raw_type, "note")


def _variable_source(variable: dict[str, Any]) -> tuple[str | None, str | None]:
    provenance = _dict(variable.get("provenance"))
    representative = _dict(provenance.get("representative_lcn"))
    source_package = _string(representative.get("package_id"))
    local_id = _string(representative.get("local_id"))
    if source_package is None:
        source_packages = _list(provenance.get("source_packages"))
        first_source = source_packages[0] if source_packages else None
        source_package = _string(first_source)
    if source_package is None and local_id and "::" in local_id:
        source_package = local_id.split("::", 1)[0]
    return source_package, local_id


def _chain_conclusion(chain: dict[str, Any]) -> dict[str, Any]:
    factors = _list(chain.get("factors"))
    for factor in factors:
        if not isinstance(factor, dict):
            continue
        conclusion = _dict(factor.get("conclusion"))
        if conclusion:
            return conclusion
    conclusion = _dict(chain.get("conclusion"))
    if conclusion:
        return conclusion
    conclusion_id = _string(chain.get("conclusion_id"))
    conclusion_title = _string(chain.get("conclusion_title"))
    conclusion_text = _string(chain.get("conclusion_text"))
    if conclusion_id or conclusion_title or conclusion_text:
        return {
            "id": conclusion_id,
            "title": conclusion_title,
            "content": conclusion_text,
        }
    return {}


def _chain_can_compile(chain: dict[str, Any]) -> bool:
    factors = _list(chain.get("factors"))
    for factor in factors:
        if not isinstance(factor, dict):
            continue
        if _dict(factor.get("conclusion")) and _list(factor.get("premises")):
            return True
    return False


def _chain_source_package(chain: dict[str, Any]) -> str | None:
    if paper_id := _string(chain.get("paper_id")):
        return f"paper:{paper_id}"
    motivating_questions = _list(chain.get("motivating_questions"))
    for question in motivating_questions:
        if isinstance(question, dict) and (source := _string(question.get("source_package"))):
            return source
    conclusion = _chain_conclusion(chain)
    local_id = _string(conclusion.get("local_id"))
    if local_id and "::" in local_id:
        return local_id.split("::", 1)[0]
    return None


def _papers(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data = _dict(payload.get("data"))
    raw_papers = data.get("papers", payload.get("papers"))
    if isinstance(raw_papers, dict):
        paper_map: dict[str, dict[str, Any]] = {}
        for key, value in raw_papers.items():
            if not isinstance(value, dict):
                continue
            paper = _dict(value.get("paper")) or value
            paper_map[str(key)] = paper
            paper_id = _string(paper.get("id")) or _paper_id(_string(paper.get("package_id")))
            if paper_id:
                paper_map[f"paper:{paper_id}"] = paper
        return paper_map
    if isinstance(raw_papers, list):
        papers: dict[str, dict[str, Any]] = {}
        for item in raw_papers:
            if not isinstance(item, dict):
                continue
            paper = _dict(item.get("paper")) or item
            paper_id = _string(paper.get("id")) or _paper_id(_string(paper.get("package_id")))
            if paper_id:
                papers[f"paper:{paper_id}"] = paper
        return papers
    return {}


def _paper_graph_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = _dict(payload.get("data"))
    raw_papers = data.get("papers")
    if isinstance(raw_papers, list):
        return [item for item in raw_papers if isinstance(item, dict)]
    if isinstance(raw_papers, dict):
        return [{"paper": value} for value in raw_papers.values() if isinstance(value, dict)]
    if "paper" in data:
        return [data]
    return []


def _paper_metadata(
    papers: dict[str, dict[str, Any]],
    *,
    source_package: str | None,
    paper_id: str | None,
) -> dict[str, Any]:
    if source_package and source_package in papers:
        return papers[source_package]
    if paper_id and (paper := papers.get(f"paper:{paper_id}")):
        return paper
    return {}


def _paper_title(paper: dict[str, Any]) -> str | None:
    """Return the user-facing paper name from common LKM title fields."""
    return (
        _string(paper.get("en_title"))
        or _string(paper.get("zh_title"))
        or _string(paper.get("title"))
        or _string(paper.get("paper_title"))
        or _string(paper.get("name"))
    )


def _paper_id(source_package: str | None) -> str | None:
    if not source_package:
        return None
    if source_package.startswith("paper:"):
        return source_package.split(":", 1)[1]
    return None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _number(*values: Any) -> int | float | None:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return value
    return None


__all__ = [
    "SearchOutputFormat",
    "normalize_lkm_knowledge",
    "normalize_lkm_paper_graph",
    "normalize_lkm_reasoning_search",
]
