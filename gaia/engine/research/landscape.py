"""Package-native Explore Scan landscape artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ScanBatch:
    """One normalized LKM search envelope supplied to ``explore --mode scan``."""

    search_results: dict[str, Any]
    query: str | None = None
    source_qid: str | None = None
    path: str | None = None


@dataclass
class PaperLead:
    """One deduplicated unpulled paper lead in a research landscape."""

    paper_id: str
    title: str | None = None
    doi: str | None = None
    index_id: str | None = None
    best_rank: float | None = None
    queries: list[str] = field(default_factory=list)
    source_qids: list[str] = field(default_factory=list)
    lkm_node_ids: list[str] = field(default_factory=list)
    result_count: int = 0

    def merge_query(self, query: str | None) -> None:
        """Record a surfacing query once, preserving first-seen order."""
        if query and query not in self.queries:
            self.queries.append(query)

    def merge_source(self, source_qid: str | None) -> None:
        """Record a survey source once, preserving first-seen order."""
        if source_qid and source_qid not in self.source_qids:
            self.source_qids.append(source_qid)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible lead payload."""
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "doi": self.doi,
            "index_id": self.index_id,
            "best_rank": self.best_rank,
            "queries": list(self.queries),
            "source_qids": list(self.source_qids),
            "lkm_node_ids": list(self.lkm_node_ids),
            "result_count": self.result_count,
        }


def _query_text(search_results: dict[str, Any], fallback: str | None = None) -> str | None:
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    query = search_results.get("query")
    if isinstance(query, dict):
        text = query.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


def _result_count(search_results: dict[str, Any]) -> int:
    results = search_results.get("results")
    return len(results) if isinstance(results, list) else 0


def _result_paper_id(result: dict[str, Any]) -> str | None:
    source = result.get("source")
    if isinstance(source, dict):
        paper_id = source.get("paper_id")
        if isinstance(paper_id, str) and paper_id:
            return paper_id
    for action in result.get("actions", []) or []:
        if not isinstance(action, dict):
            continue
        target = action.get("target")
        if isinstance(target, dict):
            paper_id = target.get("paper_id")
            if isinstance(paper_id, str) and paper_id:
                return paper_id
    return None


def _result_is_materialized(result: dict[str, Any]) -> bool:
    gaia = result.get("gaia")
    if not isinstance(gaia, dict):
        return False
    qid = gaia.get("qid")
    return isinstance(qid, str) and bool(qid)


def _result_rank(result: dict[str, Any]) -> float | None:
    rank = result.get("rank")
    if isinstance(rank, dict):
        score = rank.get("score")
        if isinstance(score, (int, float)):
            return float(score)
    return None


def _result_index_id(result: dict[str, Any]) -> str | None:
    source = result.get("source")
    if isinstance(source, dict):
        index_id = source.get("index_id")
        if isinstance(index_id, str) and index_id:
            return index_id
    for action in result.get("actions", []) or []:
        if not isinstance(action, dict):
            continue
        target = action.get("target")
        if isinstance(target, dict):
            index_id = target.get("index_id")
            if isinstance(index_id, str) and index_id:
                return index_id
    return None


def _merge_lead_row(lead: PaperLead, result: dict[str, Any]) -> None:
    source = result.get("source")
    source_payload: dict[str, Any] = source if isinstance(source, dict) else {}
    title = source_payload.get("paper_title") or result.get("title")
    doi = source_payload.get("doi")
    index_id = _result_index_id(result)
    rank = _result_rank(result)
    node_id = result.get("id")

    if lead.title is None and isinstance(title, str) and title:
        lead.title = title
    if lead.doi is None and isinstance(doi, str) and doi:
        lead.doi = doi
    if lead.index_id is None and index_id is not None:
        lead.index_id = index_id
    if rank is not None and (lead.best_rank is None or rank > lead.best_rank):
        lead.best_rank = rank
    if isinstance(node_id, str) and node_id and node_id not in lead.lkm_node_ids:
        lead.lkm_node_ids.append(node_id)


def _paper_leads_for_batch(
    batch: ScanBatch,
    *,
    materialized: set[str],
    materialized_paper_ids: set[str],
) -> list[PaperLead]:
    results = batch.search_results.get("results")
    if not isinstance(results, list):
        return []

    leads: dict[str, PaperLead] = {}
    for result in results:
        if not isinstance(result, dict) or _result_is_materialized(result):
            continue
        paper_id = _result_paper_id(result)
        if paper_id is None or paper_id in materialized or paper_id in materialized_paper_ids:
            continue
        lead = leads.get(paper_id)
        if lead is None:
            lead = PaperLead(paper_id=paper_id)
            leads[paper_id] = lead
        _merge_lead_row(lead, result)
    return list(leads.values())


def _paper_leads(
    batches: list[ScanBatch],
    *,
    materialized: set[str],
    materialized_paper_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    leads_by_paper: dict[str, PaperLead] = {}
    queries: list[dict[str, Any]] = []

    for index, batch in enumerate(batches):
        query = _query_text(batch.search_results, batch.query)
        raw_results = _result_count(batch.search_results)
        batch_leads = _paper_leads_for_batch(
            batch,
            materialized=materialized,
            materialized_paper_ids=materialized_paper_ids,
        )
        queries.append(
            {
                "index": index,
                "query": query,
                "source_qid": batch.source_qid,
                "path": batch.path,
                "raw_results": raw_results,
                "paper_leads": len(batch_leads),
            }
        )
        for batch_lead in batch_leads:
            lead = leads_by_paper.get(batch_lead.paper_id)
            if lead is None:
                lead = PaperLead(
                    paper_id=batch_lead.paper_id,
                    title=batch_lead.title,
                    doi=batch_lead.doi,
                    index_id=batch_lead.index_id,
                )
                leads_by_paper[batch_lead.paper_id] = lead
            if lead.title is None and batch_lead.title:
                lead.title = batch_lead.title
            if lead.doi is None and batch_lead.doi:
                lead.doi = batch_lead.doi
            if lead.index_id is None and batch_lead.index_id:
                lead.index_id = batch_lead.index_id
            if batch_lead.best_rank is not None and (
                lead.best_rank is None or batch_lead.best_rank > lead.best_rank
            ):
                lead.best_rank = batch_lead.best_rank
            lead.merge_query(query)
            lead.merge_source(batch.source_qid)
            for node_id in batch_lead.lkm_node_ids:
                if node_id not in lead.lkm_node_ids:
                    lead.lkm_node_ids.append(node_id)
            lead.result_count += len(batch_lead.lkm_node_ids)

    sorted_leads = sorted(
        leads_by_paper.values(),
        key=lambda lead: (
            -(lead.best_rank or 0.0),
            -lead.result_count,
            lead.paper_id,
        ),
    )
    return queries, [lead.to_dict() for lead in sorted_leads]


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
    materialized: set[str] | None = None,
    materialized_paper_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Build a package-native research landscape from LKM search batches."""
    query_provenance, paper_leads = _paper_leads(
        batches,
        materialized=materialized or set(),
        materialized_paper_ids=materialized_paper_ids or set(),
    )
    candidate_focuses = _candidate_focuses(query_provenance, paper_leads)
    coverage_gaps = _coverage_gaps(query_provenance)
    stats = {
        "query_batches": len(query_provenance),
        "raw_results": sum(int(query.get("raw_results", 0)) for query in query_provenance),
        "paper_leads": len(paper_leads),
    }
    return {
        "schema_version": 1,
        "kind": "research_landscape",
        "action": "explore.scan",
        "created_at": datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "pull_budget": pull_budget,
        "query_provenance": query_provenance,
        "stats": stats,
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
