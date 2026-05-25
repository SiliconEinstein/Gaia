"""Paper-level landscape staging for LKM exploration.

The normal frontier loop expands one ranked contact at a time. A landscape pass
is deliberately shallower: it consumes one or more already-run ``gaia search lkm``
JSON envelopes, deduplicates them to paper-level leads, and produces a neutral
pull-order artifact. It does not call LKM, author Gaia source, or encode any
field-specific schema such as PICO, evidence hierarchy, or endpoint categories.
Those belong in optional tactics layered above this generic paper-lead table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from gaia.engine.exploration.observe import distill_paper_leads
from gaia.engine.exploration.state import Contact, ExplorationMap

LANDSCAPE_SCHEMA_VERSION = 1


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _query_text(search_results: dict[str, Any], fallback: str | None = None) -> str | None:
    """Return explicit query text, else the normalized envelope query."""
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


@dataclass
class LandscapeBatch:
    """One saved LKM search envelope supplied to a landscape pass."""

    search_results: dict[str, Any]
    query: str | None = None
    source_qid: str | None = None
    path: str | None = None


@dataclass
class LandscapeLead:
    """One deduplicated unpulled paper lead in a landscape artifact."""

    paper_id: str
    title: str | None = None
    doi: str | None = None
    index_id: str | None = None
    best_rank: float | None = None
    queries: list[str] = field(default_factory=list)
    source_qids: list[str] = field(default_factory=list)
    lkm_node_ids: list[str] = field(default_factory=list)
    result_count: int = 0
    existing_contact_id: str | None = None
    existing_contact_status: str | None = None

    def merge_query(self, query: str | None) -> None:
        """Record a surfacing query once, preserving first-seen order."""
        if query and query not in self.queries:
            self.queries.append(query)

    def merge_source(self, source_qid: str | None) -> None:
        """Record a survey source once, preserving first-seen order."""
        if source_qid and source_qid not in self.source_qids:
            self.source_qids.append(source_qid)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible representation."""
        payload: dict[str, Any] = {
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
        if self.existing_contact_id is not None:
            payload["existing_contact_id"] = self.existing_contact_id
            payload["existing_contact_status"] = self.existing_contact_status
        return payload


@dataclass
class Landscape:
    """A neutral, paper-level view of multiple LKM search batches."""

    created_at: str
    queries: list[dict[str, Any]]
    paper_leads: list[LandscapeLead]

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible artifact."""
        paper_leads = [lead.to_dict() for lead in self.paper_leads]
        return {
            "schema_version": LANDSCAPE_SCHEMA_VERSION,
            "kind": "exploration_landscape",
            "created_at": self.created_at,
            "queries": [dict(q) for q in self.queries],
            "stats": {
                "query_batches": len(self.queries),
                "raw_results": sum(int(q.get("raw_results", 0)) for q in self.queries),
                "paper_leads": len(paper_leads),
            },
            "paper_leads": paper_leads,
            "recommended_pull_order": [lead.paper_id for lead in self.paper_leads],
            "notes": [
                "Paper leads are topic-neutral and schema-neutral.",
                "Domain-specific classifications should be added by an optional tactic/profile.",
            ],
        }


def _existing_lkm_contacts(exploration_map: ExplorationMap | None) -> dict[str, Contact]:
    if exploration_map is None:
        return {}
    out: dict[str, Contact] = {}
    for contact in exploration_map.frontier:
        if contact.ref.get("kind") != "lkm":
            continue
        paper_id = str(contact.ref.get("value"))
        if paper_id:
            out[paper_id] = contact
    return out


def build_landscape(
    batches: list[LandscapeBatch],
    *,
    materialized: set[str],
    materialized_paper_ids: set[str] | None = None,
    exploration_map: ExplorationMap | None = None,
) -> Landscape:
    """Build a deduplicated paper-lead landscape from saved LKM search results.

    Args:
        batches: Search envelopes to aggregate. They should be normalized
            ``gaia-json`` results from ``gaia search lkm``.
        materialized: Joint materialized QID set. Results already materialized as
            Gaia QIDs are skipped.
        materialized_paper_ids: Paper IDs already pulled into the joint view.
        exploration_map: Optional current map used only to annotate whether a
            paper already has a frontier contact.

    Returns:
        A :class:`Landscape` ordered by neutral pull priority: best retrieval
        rank, then number of surfacing result rows, then paper id.
    """
    leads_by_paper: dict[str, LandscapeLead] = {}
    queries: list[dict[str, Any]] = []
    existing_contacts = _existing_lkm_contacts(exploration_map)

    for index, batch in enumerate(batches):
        query = _query_text(batch.search_results, batch.query)
        raw_results = _result_count(batch.search_results)
        distilled = distill_paper_leads(
            batch.search_results,
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
                "paper_leads": len(distilled),
            }
        )
        for paper in distilled:
            lead = leads_by_paper.get(paper.paper_id)
            if lead is None:
                contact = existing_contacts.get(paper.paper_id)
                lead = LandscapeLead(
                    paper_id=paper.paper_id,
                    title=paper.title,
                    doi=paper.doi,
                    index_id=paper.index_id,
                    existing_contact_id=contact.id if contact is not None else None,
                    existing_contact_status=contact.status if contact is not None else None,
                )
                leads_by_paper[paper.paper_id] = lead
            if lead.title is None and paper.title:
                lead.title = paper.title
            if lead.doi is None and paper.doi:
                lead.doi = paper.doi
            if lead.index_id is None and paper.index_id:
                lead.index_id = paper.index_id
            if paper.rank is not None and (lead.best_rank is None or paper.rank > lead.best_rank):
                lead.best_rank = paper.rank
            lead.merge_query(query)
            lead.merge_source(batch.source_qid)
            for node_id in paper.lkm_node_ids or []:
                if node_id not in lead.lkm_node_ids:
                    lead.lkm_node_ids.append(node_id)
            lead.result_count += len(paper.lkm_node_ids or [])

    paper_leads = sorted(
        leads_by_paper.values(),
        key=lambda lead: (
            -(lead.best_rank or 0.0),
            -lead.result_count,
            lead.paper_id,
        ),
    )
    return Landscape(created_at=_utcnow(), queries=queries, paper_leads=paper_leads)


__all__ = [
    "LANDSCAPE_SCHEMA_VERSION",
    "Landscape",
    "LandscapeBatch",
    "LandscapeLead",
    "build_landscape",
]
