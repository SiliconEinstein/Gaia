"""LKM-related ingestion — the primary frontier source (SCHEMA.md §7f, build 4d).

The 4c live re-run proved the ``depends_on`` frontier fills in *within* a
self-contained materialized paper but rarely opens new territory. The expansion
signal is **``lkm_related``** (SCHEMA.md §3b): the papers an LKM survey surfaces
that you have **not pulled yet**. This module turns raw
``gaia search lkm knowledge`` JSON into ``lkm_related`` frontier contacts.

The actionable unit is the **paper** (``gaia pkg add --lkm-paper <paper_id>``
pulls a whole paper), so ``lkm_related`` contacts are **paper-granularity**:

* ``ref = {"kind": "lkm", "value": <paper_id>}``;
* ``sources = [{"qid": <surveyed node that prompted the search>, "edge":
  "lkm_related"}]`` (union across observations);
* ``meta`` carries the LKM metadata the contact needs to be ranked and pulled
  (``paper_id``, ``title``, ``doi``, the max LKM relevance rank seen, the
  surfacing ``query``, and the related ``lkm_node_ids`` — the raw LKM variable
  ids that pointed at this paper).

De-dup is by ``paper_id``: a paper surfaced by several results (or across
several observations) is **one** contact with the union of its sources + node
ids and the **max** rank seen. A result whose paper is **already materialized**
in the joint view is **not** a contact (and an existing matching contact is
promoted by the round / frontier path, not here).

This module is **pure** and testable against fixture search JSON — no live LKM:
:func:`observe_lkm_results` reads the parsed JSON + the joint materialized set
and merges contacts into an :class:`ExplorationMap` in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from gaia.lkm_explorer.engine.state import Contact, mint_contact_id

if TYPE_CHECKING:
    from gaia.lkm_explorer.engine.state import ExplorationMap

# The single edge kind an LKM-related paper-contact is reached through.
EDGE_LKM_RELATED = "lkm_related"


@dataclass
class _PaperLead:
    """One unmaterialized paper distilled from the LKM search results.

    Aggregates every result row that points at the same ``paper_id`` into a
    single paper-granularity lead: the best (max) LKM rank seen, the human
    metadata (first non-empty title/doi), and the set of contributing LKM node
    ids.
    """

    paper_id: str
    title: str | None = None
    doi: str | None = None
    rank: float | None = None
    index_id: str | None = None
    lkm_node_ids: list[str] | None = None

    def __post_init__(self) -> None:
        if self.lkm_node_ids is None:
            self.lkm_node_ids = []


def _variables(search_results: dict[str, Any]) -> list[dict[str, Any]]:
    data = _dict(search_results.get("data"))
    raw = data.get("variables", search_results.get("variables"))
    return [item for item in _list(raw) if isinstance(item, dict)]


def _variable_paper_id(variable: dict[str, Any]) -> str | None:
    """Return the paper id referenced by a raw LKM variable."""
    for key in ("paper_id", "source_package", "package_id", "local_id"):
        if paper_id := _paper_id_from_any(variable.get(key)):
            return paper_id
    provenance = _dict(variable.get("provenance"))
    representative = _dict(provenance.get("representative_lcn"))
    for key in ("package_id", "local_id"):
        if paper_id := _paper_id_from_any(representative.get(key)):
            return paper_id
    for source_package in _list(provenance.get("source_packages")):
        if paper_id := _paper_id_from_any(source_package):
            return paper_id
    return None


def _variable_rank(variable: dict[str, Any]) -> float | None:
    """Return a raw LKM variable's relevance rank, if present."""
    for key in ("retrieval_score", "relevance_score", "score", "rerank_score"):
        score = variable.get(key)
        if isinstance(score, (int, float)):
            return float(score)
    return None


def _variable_node_id(variable: dict[str, Any], *, index_id: str | None) -> str | None:
    raw_id = _text(variable.get("id")) or _text(variable.get("global_id"))
    if raw_id is None:
        return None
    return f"lkm:{index_id}:{raw_id}" if index_id else raw_id


def _paper_metadata(variable: dict[str, Any]) -> dict[str, Any]:
    for key in ("paper", "paper_enrich", "paper_metadata"):
        if metadata := _dict(variable.get(key)):
            return metadata
    return {}


def _variable_title(variable: dict[str, Any]) -> str | None:
    paper = _paper_metadata(variable)
    for key in ("en_title", "title", "paper_title"):
        if title := _text(paper.get(key)):
            return title
    return _text(variable.get("paper_title"))


def _variable_doi(variable: dict[str, Any]) -> str | None:
    paper = _paper_metadata(variable)
    return _text(paper.get("doi")) or _text(variable.get("doi"))


def _paper_id_from_any(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    if text.startswith("paper:"):
        return text.split("::", 1)[0].split(":", 1)[1]
    return text if text.isdigit() else None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def distill_paper_leads(
    search_results: dict[str, Any],
    *,
    materialized: set[str],
    materialized_paper_ids: set[str] | None = None,
    index_id: str | None = None,
) -> list[_PaperLead]:
    """Reduce LKM search JSON to unmaterialized paper-granularity leads.

    Walks raw ``data.variables[]`` and groups rows by ``paper_id``. A row is
    **dropped** when (a) it has no paper id, or (b) its paper is already pulled —
    its ``paper_id`` is in ``materialized_paper_ids``. An already-pulled paper
    is not fresh territory, so it is not a contact (a matching contact, if any,
    is promoted by the round/frontier path —
    :func:`promote_materialized_lkm_contacts` — not here).

    Args:
        search_results: The parsed raw ``gaia search lkm knowledge`` JSON.
        materialized: The joint-view materialized QID set. Raw LKM paper/node
            ids are not Gaia QIDs; paper freshness is checked with
            ``materialized_paper_ids``.
        materialized_paper_ids: Paper ids already pulled into the joint view
            (encoded in the dependency sub-package dir names — SCHEMA.md §7f).
        index_id: LKM index used for this search. Raw LKM JSON does not carry
            Gaia's configured index id, so the caller supplies it when known.

    Returns:
        One :class:`_PaperLead` per distinct unmaterialized paper, max rank and
        unioned node ids merged in.
    """
    # Kept in the signature because observe/landscape callers pass the joint
    # Gaia QID set; raw LKM paper freshness is checked by materialized_paper_ids.
    del materialized

    variables = _variables(search_results)
    if not variables:
        return []
    pulled = materialized_paper_ids or set()

    leads: dict[str, _PaperLead] = {}
    for variable in variables:
        paper_id = _variable_paper_id(variable)
        if paper_id is None or paper_id in pulled:
            continue
        lead = leads.get(paper_id)
        if lead is None:
            lead = _PaperLead(paper_id=paper_id)
            leads[paper_id] = lead
        _merge_lead_row(lead, variable, index_id=index_id)

    return list(leads.values())


def _merge_lead_row(
    lead: _PaperLead,
    variable: dict[str, Any],
    *,
    index_id: str | None,
) -> None:
    """Fold one raw LKM variable into an aggregating :class:`_PaperLead`."""
    title = _variable_title(variable)
    doi = _variable_doi(variable)
    rank = _variable_rank(variable)
    node_id = _variable_node_id(variable, index_id=index_id)

    if lead.title is None and title:
        lead.title = title
    if lead.doi is None and doi:
        lead.doi = doi
    if lead.index_id is None and index_id is not None:
        lead.index_id = index_id
    if rank is not None and (lead.rank is None or rank > lead.rank):
        lead.rank = rank
    node_ids = lead.lkm_node_ids
    if isinstance(node_id, str) and node_id and node_ids is not None and node_id not in node_ids:
        node_ids.append(node_id)


def _existing_lkm_contact(exploration_map: ExplorationMap, paper_id: str) -> Contact | None:
    """Return the existing ``lkm`` contact for ``paper_id``, or ``None``."""
    for contact in exploration_map.frontier:
        if contact.ref.get("kind") == "lkm" and str(contact.ref.get("value")) == paper_id:
            return contact
    return None


def _merge_source(contact: Contact, source_qid: str | None) -> None:
    """Union an ``lkm_related`` source onto a contact (de-duplicated)."""
    if not source_qid:
        return
    for existing in contact.sources:
        if existing.get("qid") == source_qid and existing.get("edge") == EDGE_LKM_RELATED:
            return
    contact.sources.append({"qid": source_qid, "edge": EDGE_LKM_RELATED})


def _merge_meta(contact: Contact, lead: _PaperLead, query: str | None) -> None:
    """Merge a lead's LKM metadata onto a contact's ``meta`` (max rank, union ids)."""
    meta = dict(contact.meta)
    meta["paper_id"] = lead.paper_id
    if lead.title and not meta.get("title"):
        meta["title"] = lead.title
    if lead.doi and not meta.get("doi"):
        meta["doi"] = lead.doi
    if lead.index_id and not meta.get("index_id"):
        meta["index_id"] = lead.index_id
    if query and not meta.get("query"):
        meta["query"] = query
    # Max rank seen across observations.
    prior_rank = meta.get("rank")
    if lead.rank is not None:
        meta["rank"] = (
            lead.rank
            if not isinstance(prior_rank, (int, float))
            else max(float(prior_rank), lead.rank)
        )
    # Union the contributing LKM node ids.
    node_ids = list(meta.get("lkm_node_ids", []))
    for nid in lead.lkm_node_ids or []:
        if nid not in node_ids:
            node_ids.append(nid)
    meta["lkm_node_ids"] = node_ids
    contact.meta = meta


@dataclass
class ObserveResult:
    """Summary of an :func:`observe_lkm_results` ingestion.

    Attributes:
        new_contacts: paper ids added as fresh ``lkm_related`` contacts.
        updated_contacts: paper ids whose existing contact was merged into.
        skipped_materialized: paper ids dropped because already materialized
            (their matching contact, if any, is promoted on the next round).
    """

    new_contacts: list[str]
    updated_contacts: list[str]
    skipped_materialized: list[str]


def observe_lkm_results(
    exploration_map: ExplorationMap,
    search_results: dict[str, Any],
    *,
    materialized: set[str],
    materialized_paper_ids: set[str] | None = None,
    source_qid: str | None = None,
    query: str | None = None,
    index_id: str | None = None,
    discovered_round: int | None = None,
) -> ObserveResult:
    """Fold LKM search results into ``lkm_related`` frontier contacts (SCHEMA §7f).

    For every result whose **paper** is not materialized in the joint view, an
    ``lkm_related`` paper-contact is added (or, if one already exists for that
    ``paper_id``, merged into — union sources + node ids, keep the max rank).
    Promoted / closed ``lkm`` contacts are left intact (their sources/meta are
    not refreshed), mirroring :func:`reconcile_frontier`'s treatment of qid
    contacts.

    The function is additive and never deletes contacts; promotion of a paper
    once it is materialized happens in the round / frontier path
    (:func:`promote_materialized_lkm_contacts`), not here.

    Args:
        exploration_map: The map to grow (mutated in place).
        search_results: Parsed raw ``gaia search lkm knowledge`` JSON.
        materialized: The joint-view materialized QID set (the surveyed
            territory). Raw LKM paper/node ids are not Gaia QIDs; already pulled
            papers are supplied via ``materialized_paper_ids``.
        materialized_paper_ids: Paper ids already pulled into the joint view —
            skipped (already explored), not re-added as fresh contacts.
        source_qid: The surveyed node whose survey prompted this LKM search; it
            becomes the contact's ``lkm_related`` source.
        query: The surfacing query text, stored on ``meta`` for legibility.
        index_id: LKM index used for this search.
        discovered_round: Round to stamp on newly added contacts.

    Returns:
        An :class:`ObserveResult` summarising what was added / merged / skipped.
    """
    leads = distill_paper_leads(
        search_results,
        materialized=materialized,
        materialized_paper_ids=materialized_paper_ids,
        index_id=index_id,
    )

    new_ids: list[str] = []
    updated_ids: list[str] = []

    for lead in leads:
        existing = _existing_lkm_contact(exploration_map, lead.paper_id)
        if existing is not None:
            # Leave promoted/closed contacts entirely intact (parallels
            # reconcile_frontier): only an open contact is merged into.
            if existing.status != "open":
                continue
            _merge_source(existing, source_qid)
            _merge_meta(existing, lead, query)
            updated_ids.append(lead.paper_id)
            continue

        contact = Contact(
            id=mint_contact_id(),
            ref={"kind": "lkm", "value": lead.paper_id},
            sources=[],
            discovered_round=discovered_round or 0,
        )
        _merge_source(contact, source_qid)
        _merge_meta(contact, lead, query)
        exploration_map.frontier.append(contact)
        new_ids.append(lead.paper_id)

    return ObserveResult(
        new_contacts=new_ids,
        updated_contacts=updated_ids,
        skipped_materialized=[],
    )


def promote_materialized_lkm_contacts(
    exploration_map: ExplorationMap,
    *,
    materialized_paper_ids: set[str],
    survey_round: int,
) -> list[str]:
    """Flip ``lkm_related`` contacts whose paper is now materialized (SCHEMA §7f).

    A paper pulled via ``gaia pkg add --lkm-paper <id>`` appears in the joint
    view as a dependency sub-package; its dist/import name encodes the paper id
    (e.g. ``…-<paper_id>-gaia``). When an open ``lkm`` contact's ``paper_id`` is
    in ``materialized_paper_ids`` the contact is **promoted**: its status flips to
    ``surveyed`` and — so ``status`` and the round log agree — a
    :class:`~gaia.lkm_explorer.engine.state.SurveyRecord` keyed by an
    ``lkm:paper:<id>`` synthetic qid is recorded with ``promoted_from_contact``.

    Args:
        exploration_map: The map whose lkm contacts are promoted (mutated).
        materialized_paper_ids: Paper ids now present in the joint view.
        survey_round: The round that materialized them.

    Returns:
        The paper ids whose contacts were promoted this call.
    """
    from gaia.lkm_explorer.engine.state import SurveyRecord

    promoted: list[str] = []
    for contact in exploration_map.frontier:
        if contact.ref.get("kind") != "lkm" or contact.status != "open":
            continue
        paper_id = str(contact.ref.get("value"))
        if paper_id not in materialized_paper_ids:
            continue
        contact.status = "surveyed"
        survey_qid = f"lkm:paper:{paper_id}"
        exploration_map.surveyed[survey_qid] = SurveyRecord(
            qid=survey_qid,
            survey_round=survey_round,
            lkm_origin={k: v for k, v in contact.meta.items() if k != "lkm_node_ids"},
            promoted_from_contact=contact.id,
        )
        promoted.append(paper_id)
    return promoted


def materialized_paper_ids_from_roots(package_roots: list[Any]) -> set[str]:
    """Extract paper ids encoded in the joint view's dependency package roots.

    ``gaia pkg add --lkm-paper <paper_id>`` lands a paper as a dependency
    sub-package under ``<root>/.gaia/lkm_packages/<dist>/`` whose dist/import name
    embeds the paper id (commonly ``…-<paper_id>-gaia`` / ``…_<paper_id>_gaia``).
    A pulled paper is therefore detectable from the joint view's
    ``package_roots`` directory names without importing anything.

    Args:
        package_roots: The :class:`~gaia.lkm_explorer.engine.frontier.JointView`
            ``package_roots`` (root + every loaded dep, as ``Path``-likes).

    Returns:
        The set of paper-id digit-runs found in those directory names.
    """
    import re
    from pathlib import Path

    found: set[str] = set()
    for root in package_roots:
        name = Path(str(root)).name
        # Paper ids are long digit runs; match any 6+ digit token in the dist dir.
        for token in re.findall(r"\d{6,}", name):
            found.add(token)
    return found
