"""Frontier extraction — derive the exploration frontier from a package's IR.

This is build 2 of the exploration machine (SCHEMA.md §7a). It turns a package's
in-memory IR (a :class:`~gaia.engine.ir.graphs.LocalCanonicalGraph`) into the set
of *contacts* that make up the frontier: reference *targets* a surveyed node
points at but which have no materialized ``Knowledge`` body yet.

Semantics (SCHEMA.md §7a, authoritative):

* The **materialized set** = the QIDs that have a ``Knowledge`` node in the IR.
* Every inter-node reference is an **edge by Knowledge ID**. For each edge, any
  referenced QID **not** in the materialized set is a **contact**; its ``sources``
  are the *materialized* co-referenced QIDs in that same edge (the surveyed
  territory the contact is reachable from), tagged with the edge kind.
* Multiple edges to the same contact merge into one :class:`Contact` with the
  union of ``sources``.

Edge sources and their ``edge`` kind:

============================================================  ===================
IR source                                                     edge kind
============================================================  ===================
``Operator`` (standalone + inside ``FormalStrategy``)         ``operator_target``
``Strategy`` (``premises`` + ``conclusion`` + ``background``) ``strategy_given``
``Knowledge.sub_knowledge``                                   ``sub_knowledge``
``lkm_materialize`` ``depends_on`` scaffold                   ``depends_on``
============================================================  ===================

``CompositeStrategy.sub_strategies`` are ``strategy_id`` references (not
Knowledge) and are skipped. ``lkm_related`` contacts are survey-time only
(co-retrieved LKM nodes, not IR-derived) and are out of scope for this build.

The ``depends_on`` scaffold is a special case: ``lkm_materialize`` lowers each
factor into a ``depends_on(...)`` DSL call, which the compiler records **not** in
the ``LocalCanonicalGraph`` but in a sibling *formalization manifest*
(``.gaia/formalization_manifest.json`` / ``CompiledPackage.formalization_manifest``)
as ``{"kind": "depends_on", "conclusion": <qid>, "given": [<qid>, ...],
"background": [<qid>, ...]}``. So this module accepts that manifest as an
*optional companion* to the graph and folds its ``depends_on`` records into the
frontier under the ``depends_on`` edge. When no manifest is passed, the
``depends_on`` edge simply contributes nothing.

This module is **pure**: :func:`extract_frontier` reads the IR and returns a
fresh list of :class:`Contact`; :func:`reconcile_frontier` folds that list into
an :class:`ExplorationMap` without resurrecting or deleting promoted/closed
contacts. No scoring happens here — ``score`` / ``score_features`` stay at their
schema defaults (``None`` / ``{}``) until build 3, the scorer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gaia.engine.exploration.state import Contact, mint_contact_id

if TYPE_CHECKING:
    from gaia.engine.exploration.state import ExplorationMap
    from gaia.engine.ir.graphs import LocalCanonicalGraph

# §7a edge kinds this build derives from the IR (``lkm_related`` is survey-time
# only and out of scope; it is intentionally absent here).
EDGE_OPERATOR_TARGET = "operator_target"
EDGE_STRATEGY_GIVEN = "strategy_given"
EDGE_SUB_KNOWLEDGE = "sub_knowledge"
EDGE_DEPENDS_ON = "depends_on"


def _materialized_qids(ir: LocalCanonicalGraph) -> set[str]:
    """Return the QIDs that have a ``Knowledge`` body in the IR (the surveyed set).

    A ``Knowledge`` node is materialized iff it carries a resolved ``id`` (a QID);
    ``LocalCanonicalGraph`` auto-assigns one to every label-only node at
    validation time, so in a compiled graph this is simply every node's ``id``.
    """
    return {k.id for k in ir.knowledges if k.id is not None}


def _iter_operators(ir: LocalCanonicalGraph) -> list[Any]:
    """Yield every Operator the IR carries: standalone + inside FormalStrategy.

    Standalone operators live on ``ir.operators``; formalized strategies embed
    further operators in ``FormalStrategy.formal_expr.operators``. Both are
    reference edges of kind ``operator_target`` (SCHEMA.md §7a).
    """
    operators: list[Any] = list(ir.operators)
    for strategy in ir.strategies:
        formal_expr = getattr(strategy, "formal_expr", None)
        if formal_expr is not None:
            operators.extend(formal_expr.operators)
    return operators


def _edges_from_ir(
    ir: LocalCanonicalGraph,
    formalization_manifest: dict[str, Any] | None,
) -> list[tuple[str, list[str]]]:
    """Collect every reference edge as ``(edge_kind, [referenced_qids])``.

    Each tuple is one edge: its referenced QIDs are the full set the edge ties
    together (both materialized and not). The caller splits them into the
    contact (unmaterialized) and its sources (materialized co-references).
    """
    edges: list[tuple[str, list[str]]] = []

    # Operators (standalone + embedded): variables[] + conclusion.
    for operator in _iter_operators(ir):
        op_refs: list[str] = [*operator.variables, operator.conclusion]
        edges.append((EDGE_OPERATOR_TARGET, op_refs))

    # Strategies: premises[] + conclusion + background[]. CompositeStrategy
    # carries its own premises/conclusion too; only its ``sub_strategies`` (which
    # are strategy_id refs, not Knowledge) are skipped — and we never read them.
    for strategy in ir.strategies:
        strat_refs: list[str] = list(strategy.premises)
        if strategy.conclusion is not None:
            strat_refs.append(strategy.conclusion)
        if strategy.background:
            strat_refs.extend(strategy.background)
        edges.append((EDGE_STRATEGY_GIVEN, strat_refs))

    # Knowledge.sub_knowledge[]: a node naming its constituent sub-knowledge.
    for knowledge in ir.knowledges:
        sub_knowledge = knowledge.sub_knowledge
        if not sub_knowledge or knowledge.id is None:
            continue
        # The owning node is itself a (materialized) co-reference, so a contact
        # reached through sub_knowledge records the parent as its source.
        edges.append((EDGE_SUB_KNOWLEDGE, [knowledge.id, *sub_knowledge]))

    # depends_on scaffolds — sourced from the formalization manifest, which is a
    # sibling artifact to the IR (lkm_materialize lowers each factor to a
    # depends_on(...) record there, not into LocalCanonicalGraph). conclusion +
    # given[] + background[] are the co-referenced QIDs of the edge.
    if formalization_manifest:
        for record in formalization_manifest.get("dependencies", []):
            if not isinstance(record, dict) or record.get("kind") != EDGE_DEPENDS_ON:
                continue
            dep_refs: list[str] = []
            conclusion = record.get("conclusion")
            if isinstance(conclusion, str):
                dep_refs.append(conclusion)
            dep_refs.extend(g for g in record.get("given", []) if isinstance(g, str))
            dep_refs.extend(b for b in record.get("background", []) if isinstance(b, str))
            edges.append((EDGE_DEPENDS_ON, dep_refs))

    return edges


def extract_frontier(
    ir: LocalCanonicalGraph,
    exploration_map: ExplorationMap | None = None,
    *,
    formalization_manifest: dict[str, Any] | None = None,
) -> list[Contact]:
    """Derive the frontier from a package's IR (SCHEMA.md §7a). Pure function.

    Walks every reference edge in the IR (operators, strategies, sub_knowledge,
    and — when supplied — ``depends_on`` scaffolds from the formalization
    manifest). Any referenced QID **not** in the materialized set is a contact;
    its ``sources`` are the materialized co-referenced QIDs in that same edge,
    each tagged with the edge kind. Multiple edges to one contact merge into a
    single :class:`Contact` with the union of ``sources``.

    Args:
        ir: The in-memory package IR — a
            :class:`~gaia.engine.ir.graphs.LocalCanonicalGraph` whose
            ``knowledges`` define the materialized set and whose
            ``operators`` / ``strategies`` carry the reference edges.
        exploration_map: Optional existing map. When given, a contact that
            already exists for a QID-ref reuses that contact's ``id`` (and its
            ``discovered_round``), so re-extraction is stable across rounds. The
            map is **not** mutated here — see :func:`reconcile_frontier`.
        formalization_manifest: Optional companion manifest
            (``{"dependencies": [...], "materializations": [...]}``) carrying the
            ``depends_on`` scaffold records that ``lkm_materialize`` produces.
            When omitted, the ``depends_on`` edge contributes no contacts.

    Returns:
        A fresh list of :class:`Contact`, one per unmaterialized referenced QID,
        with merged ``sources``. ``score`` / ``score_features`` are left at their
        schema defaults — scoring is build 3.
    """
    materialized = _materialized_qids(ir)
    edges = _edges_from_ir(ir, formalization_manifest)

    # Pre-index existing QID-ref contacts so re-extraction reuses their ids.
    existing_by_qid: dict[str, Contact] = {}
    if exploration_map is not None:
        for contact in exploration_map.frontier:
            if contact.ref.get("kind") == "qid":
                existing_by_qid[str(contact.ref["value"])] = contact

    # qid -> ordered, de-duplicated list of (source_qid, edge) sources.
    sources_by_qid: dict[str, list[dict[str, Any]]] = {}
    seen_source: dict[str, set[tuple[str, str]]] = {}

    for edge_kind, refs in edges:
        unmaterialized = [r for r in refs if r not in materialized]
        if not unmaterialized:
            continue
        co_referenced_sources = [r for r in refs if r in materialized]
        for target in unmaterialized:
            bucket = sources_by_qid.setdefault(target, [])
            seen = seen_source.setdefault(target, set())
            for source_qid in co_referenced_sources:
                key = (source_qid, edge_kind)
                if key in seen:
                    continue
                seen.add(key)
                bucket.append({"qid": source_qid, "edge": edge_kind})

    contacts: list[Contact] = []
    for qid in sorted(sources_by_qid):
        prior = existing_by_qid.get(qid)
        contacts.append(
            Contact(
                id=prior.id if prior is not None else mint_contact_id(),
                ref={"kind": "qid", "value": qid},
                sources=sources_by_qid[qid],
                discovered_round=prior.discovered_round if prior is not None else 0,
            )
        )
    return contacts


def reconcile_frontier(
    exploration_map: ExplorationMap,
    extracted: list[Contact],
    *,
    discovered_round: int | None = None,
) -> ExplorationMap:
    """Fold a freshly extracted frontier into an :class:`ExplorationMap` in place.

    Per SCHEMA.md §7a, reconciliation is additive and non-destructive:

    * **New** contacts (QID not already on the frontier) are appended, stamped
      with ``discovered_round`` when given.
    * **Open** existing contacts have their ``sources`` refreshed from the
      extraction (the IR is authoritative for reachability).
    * **Promoted / closed** contacts (``status`` in ``surveyed`` / ``skipped`` /
      ``deferred``) are left **completely intact** — never resurrected to
      ``open``, never deleted, and their ``sources`` are not touched. They are
      kept for round legibility.

    Only QID-ref contacts are reconciled (extraction yields only those); any
    LKM-handle contacts already on the map are untouched.

    Args:
        exploration_map: The map to update (mutated in place and returned).
        extracted: The output of :func:`extract_frontier`.
        discovered_round: Round to stamp on newly added contacts. When ``None``,
            a new contact keeps the ``discovered_round`` it was extracted with.

    Returns:
        The same ``exploration_map``, updated.
    """
    by_qid: dict[str, Contact] = {}
    for contact in exploration_map.frontier:
        if contact.ref.get("kind") == "qid":
            by_qid[str(contact.ref["value"])] = contact

    for fresh in extracted:
        qid = str(fresh.ref["value"])
        existing = by_qid.get(qid)
        if existing is None:
            if discovered_round is not None:
                fresh.discovered_round = discovered_round
            exploration_map.frontier.append(fresh)
            by_qid[qid] = fresh
            continue
        # Leave promoted/closed contacts entirely intact.
        if existing.status != "open":
            continue
        # Refresh the open contact's reachability from the authoritative IR.
        existing.sources = [dict(s) for s in fresh.sources]

    return exploration_map
