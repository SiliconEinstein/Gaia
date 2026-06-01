"""LKM-specific adapters for Gaia research loop artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaia.lkm_explorer.engine.landscape import LandscapeBatch, build_landscape
from gaia.research_loop.schemas import ARTIFACT_SCHEMA


def build_landscape_from_raw_results(
    pkg: str | Path,
    *,
    raw_results: list[tuple[str, Path]],
    round_number: int,
) -> dict[str, Any]:
    """Build a research-loop landscape artifact from saved LKM search JSON."""
    batches: list[LandscapeBatch] = []
    raw_refs: list[dict[str, str]] = []
    evidence_snippets: list[dict[str, Any]] = []
    for query, path in raw_results:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object at {path}")
        batches.append(LandscapeBatch(search_results=payload, query=query, path=str(path)))
        raw_refs.append({"query": query, "path": str(path)})
        evidence_snippets.extend(_evidence_snippets_from_search(payload, query=query))

    landscape = build_landscape(
        batches,
        materialized=set(),
        materialized_paper_ids=set(),
        exploration_map=None,
    ).to_dict()
    paper_leads = landscape.get("paper_leads", [])
    if isinstance(paper_leads, list):
        paper_leads = _attach_snippets_to_paper_leads(paper_leads, evidence_snippets)
    else:
        paper_leads = []
    return {
        "schema": ARTIFACT_SCHEMA,
        "kind": "landscape",
        "round": round_number,
        "pkg": str(Path(pkg).resolve()),
        "raw_results": raw_refs,
        "paper_leads": paper_leads,
        "evidence_snippets": evidence_snippets,
        "coverage": {
            "paper_count": len(paper_leads),
            "snippet_count": len(evidence_snippets),
        },
        "source_landscape": landscape,
    }


def _evidence_snippets_from_search(payload: dict[str, Any], *, query: str) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    results = payload.get("results", [])
    if not isinstance(results, list):
        return snippets
    for result in results:
        if not isinstance(result, dict):
            continue
        content = result.get("content")
        source = result.get("source", {})
        if not isinstance(content, str) or not content.strip() or not isinstance(source, dict):
            continue
        paper_id = source.get("paper_id")
        if not isinstance(paper_id, str) or not paper_id:
            continue
        rank = result.get("rank", {})
        snippets.append(
            {
                "paper_id": paper_id,
                "paper_title": source.get("paper_title"),
                "doi": source.get("doi"),
                "lkm_node_id": result.get("id"),
                "kind": result.get("kind"),
                "role": source.get("role"),
                "local_id": source.get("local_id"),
                "query": query,
                "rank_score": rank.get("score") if isinstance(rank, dict) else None,
                "content": content,
            }
        )
    return snippets


def _attach_snippets_to_paper_leads(
    paper_leads: list[Any],
    evidence_snippets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    snippets_by_paper: dict[str, list[dict[str, Any]]] = {}
    for snippet in evidence_snippets:
        paper_id = snippet.get("paper_id")
        if isinstance(paper_id, str):
            snippets_by_paper.setdefault(paper_id, []).append(snippet)

    enriched: list[dict[str, Any]] = []
    for lead in paper_leads:
        if not isinstance(lead, dict):
            continue
        copy = dict(lead)
        paper_id = copy.get("paper_id")
        snippets = snippets_by_paper.get(paper_id, []) if isinstance(paper_id, str) else []
        copy["evidence_snippets"] = snippets[:3]
        copy["snippet_count"] = len(snippets)
        enriched.append(copy)
    return enriched
