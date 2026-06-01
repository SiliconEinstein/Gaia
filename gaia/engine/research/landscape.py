"""Package-native Explore Scan landscape artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gaia.lkm_explorer.engine.landscape import (
    LandscapeBatch,
    build_landscape,
)


@dataclass(frozen=True)
class ScanBatch:
    """One normalized LKM search envelope supplied to ``explore --mode scan``."""

    search_results: dict[str, Any]
    query: str | None = None
    source_qid: str | None = None
    path: str | None = None


def _pull_candidates(paper_leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for lead in paper_leads:
        paper_id = str(lead["paper_id"])
        index_id = lead.get("index_id") or "bohrium"
        queries = lead.get("queries")
        query_count = len(queries) if isinstance(queries, list) else 0
        candidates.append(
            {
                "paper_id": paper_id,
                "title": lead.get("title"),
                "doi": lead.get("doi"),
                "index_id": index_id,
                "status": "candidate",
                "command": f"gaia pkg add --lkm-index {index_id} --lkm-paper {paper_id}",
                "rationale": f"surfaced by {query_count} scan query family/families",
                "evidence_refs": [
                    {"kind": "lkm_node", "id": node_id}
                    for node_id in lead.get("lkm_node_ids", [])
                    if isinstance(node_id, str)
                ],
            }
        )
    return candidates


def _coverage_gaps(query_provenance: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for query in query_provenance:
        if int(query.get("paper_leads", 0)) == 0:
            gaps.append(
                {
                    "kind": "empty_query_family",
                    "status": "candidate",
                    "query_index": query.get("index"),
                    "query": query.get("query"),
                    "suggestion": "Broaden or rephrase this query family before assessment.",
                }
            )
    if len(query_provenance) == 1:
        gaps.append(
            {
                "kind": "single_query_family",
                "status": "candidate",
                "query_index": query_provenance[0].get("index"),
                "query": query_provenance[0].get("query"),
                "suggestion": "Add at least one contrasting query family for breadth-first scan.",
            }
        )
    return gaps


def _candidate_focuses(
    query_provenance: list[dict[str, Any]],
    paper_leads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    focuses: list[dict[str, Any]] = []
    first_papers = [
        {"kind": "lkm_paper", "paper_id": lead["paper_id"]}
        for lead in paper_leads[:3]
        if isinstance(lead.get("paper_id"), str)
    ]
    for query in query_provenance:
        if int(query.get("paper_leads", 0)) <= 0:
            continue
        index = int(query.get("index", len(focuses)))
        query_text = query.get("query") or f"query family {index}"
        focuses.append(
            {
                "id": f"candidate_focus_query_{index}",
                "kind": "query_family",
                "status": "candidate",
                "question": f"What are the main evidence tensions around: {query_text}?",
                "evidence_refs": [
                    {"kind": "lkm_search_query", "query_index": index},
                    *first_papers,
                ],
            }
        )
    return focuses


def build_research_landscape(
    batches: list[ScanBatch],
    *,
    pull_budget: int = 0,
) -> dict[str, Any]:
    """Build a package-native research landscape from LKM search batches."""
    landscape = build_landscape(
        [
            LandscapeBatch(
                search_results=batch.search_results,
                query=batch.query,
                source_qid=batch.source_qid,
                path=batch.path,
            )
            for batch in batches
        ],
        materialized=set(),
        materialized_paper_ids=set(),
    ).to_dict()
    paper_leads = list(landscape["paper_leads"])
    query_provenance = list(landscape["queries"])
    candidate_focuses = _candidate_focuses(query_provenance, paper_leads)
    coverage_gaps = _coverage_gaps(query_provenance)
    return {
        "schema_version": 1,
        "kind": "research_landscape",
        "action": "explore.scan",
        "created_at": landscape["created_at"],
        "pull_budget": pull_budget,
        "query_provenance": query_provenance,
        "stats": landscape["stats"],
        "paper_leads": paper_leads,
        "pull_candidates": _pull_candidates(paper_leads),
        "candidate_coverage_gaps": coverage_gaps,
        "coverage_map": {
            "query_families": query_provenance,
            "claim_method_clusters": [],
            "under_covered_regions": coverage_gaps,
            "candidate_focus_ids": [focus["id"] for focus in candidate_focuses],
            "paper_overlap": [
                {
                    "paper_id": lead["paper_id"],
                    "queries": lead.get("queries", []),
                    "lkm_node_ids": lead.get("lkm_node_ids", []),
                }
                for lead in paper_leads
                if len(lead.get("queries", [])) > 1
            ],
        },
        "candidate_focuses": candidate_focuses,
        "notes": [
            "This is a breadth-first landscape artifact, not an assessment.",
            "Candidate focuses are artifact-local until accepted through gaia inquiry.",
        ],
    }


__all__ = ["ScanBatch", "build_research_landscape"]
