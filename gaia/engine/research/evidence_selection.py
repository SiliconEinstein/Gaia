"""Select compact deep-evidence packets from broad research landscapes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

SELECTED_EVIDENCE_SCHEMA_VERSION = 1


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_selected_evidence_artifact(
    *,
    focus: dict[str, Any],
    landscapes: list[dict[str, Any]],
    max_items: int = 12,
    max_papers: int = 6,
    max_chains: int = 6,
) -> dict[str, Any]:
    """Build a compact evidence packet and deep-materialization plan for assessment."""
    packet = _evidence_packet_from_landscapes(landscapes)
    ranked_items = sorted(
        packet["items"],
        key=lambda item: _item_rank(item, focus=focus),
    )
    selected_items = ranked_items[:max_items]
    selected_paper_leads = _paper_leads_for_items(
        packet["paper_leads"],
        selected_items=selected_items,
        max_papers=max_papers,
    )
    evidence_packet = {
        "landscapes": packet["landscapes"],
        "items": selected_items,
        "paper_leads": selected_paper_leads,
    }
    return {
        "schema_version": SELECTED_EVIDENCE_SCHEMA_VERSION,
        "kind": "selected_evidence",
        "created_at": _utcnow(),
        "focus": dict(focus),
        "evidence_packet": evidence_packet,
        "materialization_plan": {
            "paper_ids": _paper_ids(selected_paper_leads, limit=max_papers),
            "claim_ids": [],
            "chain_claim_ids": _claim_ids(selected_items, limit=max_chains),
        },
        "selection": {
            "items_considered": len(packet["items"]),
            "items_selected": len(selected_items),
            "paper_leads_considered": len(packet["paper_leads"]),
            "paper_leads_selected": len(selected_paper_leads),
        },
    }


def _evidence_packet_from_landscapes(landscapes: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    paper_leads: list[dict[str, Any]] = []
    landscape_refs: list[dict[str, Any]] = []
    for landscape_index, landscape in enumerate(landscapes):
        landscape_refs.append(
            {
                "index": landscape_index,
                "kind": landscape.get("kind"),
                "action": landscape.get("action"),
                "target": landscape.get("target"),
            }
        )
        for raw_item in landscape.get("items", []):
            if not isinstance(raw_item, dict):
                continue
            item = dict(raw_item)
            item.setdefault("item_id", _stable_item_id(item, fallback=f"item_{len(items)}"))
            item.setdefault("display_index", len(items))
            item["landscape_index"] = landscape_index
            items.append(item)
        for raw_lead in landscape.get("paper_leads", []):
            if not isinstance(raw_lead, dict):
                continue
            lead = dict(raw_lead)
            lead["landscape_index"] = landscape_index
            paper_leads.append(lead)
    return {"landscapes": landscape_refs, "items": items, "paper_leads": paper_leads}


def _stable_item_id(item: dict[str, Any], *, fallback: str) -> str:
    kind = item.get("kind")
    source_id = item.get("id")
    if isinstance(kind, str) and kind != "item" and isinstance(source_id, str) and source_id:
        return source_id
    item_id = item.get("item_id")
    if isinstance(item_id, str) and item_id:
        return item_id
    source = item.get("source")
    paper_id = source.get("paper_id") if isinstance(source, dict) else None
    return paper_id if isinstance(paper_id, str) and paper_id else fallback


def _item_rank(item: dict[str, Any], *, focus: dict[str, Any]) -> tuple[int, int, str]:
    text = " ".join(
        str(value)
        for value in [
            item.get("id"),
            item.get("title"),
            item.get("content"),
            _paper_title(item),
        ]
        if value
    ).lower()
    focus_terms = _focus_terms(focus)
    matched_terms = sum(1 for term in focus_terms if term in text)
    has_claim = item.get("kind") == "variable" and item.get("variable_type") == "claim"
    display_index = item.get("display_index")
    order = display_index if isinstance(display_index, int) else 0
    return (-matched_terms, 0 if has_claim else 1, f"{order:08d}")


def _focus_terms(focus: dict[str, Any]) -> list[str]:
    text = " ".join(
        str(value) for value in [focus.get("id"), focus.get("title"), focus.get("content")] if value
    )
    terms: list[str] = []
    for raw in text.replace("-", " ").replace("_", " ").split():
        term = raw.strip().lower()
        if len(term) >= 4 and term not in terms:
            terms.append(term)
    return terms


def _paper_title(item: dict[str, Any]) -> str | None:
    source = item.get("source")
    title = source.get("paper_title") if isinstance(source, dict) else None
    return title if isinstance(title, str) else None


def _paper_leads_for_items(
    paper_leads: list[dict[str, Any]],
    *,
    selected_items: list[dict[str, Any]],
    max_papers: int,
) -> list[dict[str, Any]]:
    selected_papers = _paper_ids_from_items(selected_items)
    by_id = {
        lead.get("paper_id"): lead
        for lead in paper_leads
        if isinstance(lead.get("paper_id"), str) and lead.get("paper_id")
    }
    leads: list[dict[str, Any]] = []
    for paper_id in selected_papers:
        lead = by_id.get(paper_id)
        if lead is not None:
            leads.append(dict(lead))
        if len(leads) >= max_papers:
            break
    return leads


def _paper_ids_from_items(items: list[dict[str, Any]]) -> list[str]:
    paper_ids: list[str] = []
    for item in items:
        source = item.get("source")
        paper_id = source.get("paper_id") if isinstance(source, dict) else None
        if isinstance(paper_id, str) and paper_id and paper_id not in paper_ids:
            paper_ids.append(paper_id)
    return paper_ids


def _paper_ids(leads: list[dict[str, Any]], *, limit: int) -> list[str]:
    ids: list[str] = []
    for lead in leads:
        paper_id = lead.get("paper_id")
        if isinstance(paper_id, str) and paper_id and paper_id not in ids:
            ids.append(paper_id)
        if len(ids) >= limit:
            break
    return ids


def _claim_ids(items: list[dict[str, Any]], *, limit: int) -> list[str]:
    ids: list[str] = []
    for item in items:
        if item.get("kind") != "variable" or item.get("variable_type") != "claim":
            continue
        claim_id = item.get("id")
        if isinstance(claim_id, str) and claim_id and claim_id not in ids:
            ids.append(claim_id)
        if len(ids) >= limit:
            break
    return ids
