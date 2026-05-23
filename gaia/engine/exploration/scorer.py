"""Policy scorer — score the frontier per the current round's dial.

This is build 3 of the exploration machine (SCHEMA.md §7b). It walks the
**open** contacts of an :class:`~gaia.engine.exploration.state.ExplorationMap`
and fills in each one's ``score`` (a float), its full ``score_features`` dict
(all six SCHEMA.md §4 keys), and its ``last_scored_round``. Promoted / closed
contacts are left untouched, and the IR is **never** mutated.

Key modeling decision (SCHEMA.md §7b, resolving DESIGN §9): a contact is
*unmaterialized*, so it has no belief / position of its own. **Every feature is
proxied from the contact's ``sources``** — its materialized neighbours, read off
engine state. Per-feature, for a contact ``c``:

================  =========  ===========================================================
feature           tag        computation
================  =========  ===========================================================
``belief_entropy``  free     mean over ``c.sources`` of binary entropy
                             ``H(p) = -p*log2 p - (1-p)*log2(1-p)``, ``p = beliefs[src]``.
                             Sources with no belief entry are skipped; if no source has a
                             belief, ``0.0``.
``closeness_to_seed`` wire-up min hop-distance ``d`` from any ``c.source`` to any resolved
                             seed (``map.seeds[].qid`` that is non-null) over the
                             **undirected IR adjacency** (two knowledge nodes are adjacent
                             iff they co-appear in the same operator/strategy edge — reuses
                             the build-2 edge enumeration); ``closeness = 1/(1+d)``. No
                             resolved seeds / unreachable ⇒ ``0.0``.
``survey_cost``     wire-up  flat ``1.0`` for qid contacts (materialize-only placeholder;
                             refine when an LKM-pull cost model exists — ``w_cost`` has
                             little bite until then).
``tension_potential``, deferred ``0.0`` (schema slots only — DESIGN §8 defers
``bridge_potential``,           bridge/coverage; tension-wiring is a later build 3b).
``new_territory``
``obligation_pressure`` build 12 ``1.0`` iff the contact's ``ref`` QID or any of its
                             ``sources[].qid`` matches an OPEN synthetic obligation's
                             ``target_qid`` (CLIENT.md steer 3), else ``0.0``. Obligations
                             are an inquiry-side concept loaded from
                             ``.gaia/inquiry/state.json``; ``synthetic_obligations`` holds
                             only OPEN ones (``obligation close`` deletes the row). Agent-
                             visible (NOT in :data:`BELIEF_FEATURE_KEYS`) — it is the
                             steering signal the agent is meant to act on. When no
                             obligations are supplied the feature is ``0.0`` for every
                             contact (graceful default).
================  =========  ===========================================================

The score is the SCHEMA.md §4 weighted sum (the ``0.0`` terms drop out)::

    score(c) = w_uncertainty*belief_entropy
             + w_relevance*closeness_to_seed
             + w_coverage*new_territory
             + w_obligation*obligation_pressure
             - w_cost*survey_cost

Weights come from ``exploration_map.policy.weights``. ``beliefs`` is a
``dict[qid -> float]`` (P(x=1) per node — the on-disk shape of
``.gaia/beliefs.json``'s ``beliefs[]``, flattened by the caller); the function
takes the dict so it is trivially testable. No CLI, no loop, no render.

**LKM paper-contacts (SCHEMA.md §7f, build 4d).** A contact whose ``ref.kind`` is
``"lkm"`` has no graph position, so it proxies ``belief_entropy`` /
``closeness_to_seed`` from its **source** node(s) (the surveyed nodes whose LKM
survey surfaced it) exactly as a qid contact does. Two things differ: its stored
LKM ``rank`` maps into the ``new_territory`` feature (an unpulled related paper
*is* fresh territory — so this previously-deferred slot is **live for lkm
contacts only**, scaled by ``w_coverage``), and its ``survey_cost`` is
:data:`LKM_SURVEY_COST` (a full paper pull, heavier than a qid's flat ``1.0``).
qid-contact scoring is unchanged from build 3/4c (``new_territory`` stays ``0.0``,
so the new ``w_coverage`` term drops out for them).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from gaia.engine.exploration.frontier import _edges_from_ir

if TYPE_CHECKING:
    from gaia.engine.exploration.state import ExplorationMap
    from gaia.engine.inquiry.state import SyntheticObligation
    from gaia.engine.ir.graphs import LocalCanonicalGraph

# SCHEMA.md §4 — the six score_features keys. belief_entropy is [free];
# closeness_to_seed / survey_cost are [wire-up]; the remaining three are
# deferred 0.0 slots (DESIGN §8) for a qid contact.
_DEFERRED_FEATURES = ("tension_potential", "bridge_potential", "new_territory")

# CLIENT.md build 11 steer 4 (Jaynes' robot) — the belief-derived score_features
# keys stripped from every AGENT-FACING surface. The engine still RANKS by
# belief (``score_frontier`` below sets ``contact.score`` from a belief-weighted
# sum, untouched); this tuple drives only what the agent is shown, never the
# math. ``belief_entropy`` is the sole belief-derived feature.
BELIEF_FEATURE_KEYS = ("belief_entropy",)


def sanitize_score_features(score_features: dict[str, Any]) -> dict[str, Any]:
    """Return ``score_features`` with belief-derived keys removed (steer 4).

    Drops every key in :data:`BELIEF_FEATURE_KEYS` (currently ``belief_entropy``)
    so the agent never sees the belief math, while keeping the non-belief signals
    (``closeness_to_seed``, ``new_territory``, ``survey_cost``, and the 0.0
    ``tension_potential`` / ``bridge_potential`` slots). Ranking is unaffected: it
    runs on the full feature vector before this is ever called.
    """
    return {k: v for k, v in score_features.items() if k not in BELIEF_FEATURE_KEYS}


# SCHEMA.md §7f — survey cost of an LKM paper-contact. A qid contact is
# materialize-only (flat 1.0); pulling a whole paper via `gaia pkg add
# --lkm-paper` is strictly heavier, so an lkm contact costs more. 2.0 keeps the
# ordering qid < lkm without overwhelming the live w_uncertainty/w_relevance
# terms at the default doctrine weights (w_cost ~ 0.2 ⇒ a 0.2 cost penalty).
LKM_SURVEY_COST = 2.0


def binary_entropy(p: float) -> float:
    """Return the binary (Shannon) entropy ``H(p)`` in bits.

    ``H(p) = -p*log2(p) - (1-p)*log2(1-p)``, the entropy of a Bernoulli(``p``)
    variable. Maximal (``1.0``) at ``p = 0.5``; zero at the certain ends
    ``p = 0`` and ``p = 1`` (guarded so we never take ``log2(0)``).

    Args:
        p: A probability in ``[0, 1]`` — here ``P(x=1)`` for a node.

    Returns:
        The entropy in bits, in ``[0.0, 1.0]``.
    """
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


def _adjacency_from_edges(edges: list[tuple[str, list[str]]]) -> dict[str, set[str]]:
    """Build undirected adjacency from a ``(edge_kind, [qids])`` edge list.

    Two QIDs are adjacent iff they co-appear in the same edge. This is the shared
    core: a single-graph scorer passes ``_edges_from_ir(ir, None)``; the joint
    scorer (SCHEMA.md §7e) passes the cross-package joint edge set so
    ``closeness_to_seed`` spans the whole dependency graph.

    Args:
        edges: ``(edge_kind, [referenced_qids])`` reference edges.

    Returns:
        A symmetric ``qid -> set[neighbour qid]`` map. Self-loops are dropped.
    """
    adjacency: dict[str, set[str]] = {}
    for _edge_kind, refs in edges:
        nodes = [r for r in refs if r]
        for a in nodes:
            for b in nodes:
                if a == b:
                    continue
                adjacency.setdefault(a, set()).add(b)
    return adjacency


def _undirected_adjacency(ir: LocalCanonicalGraph) -> dict[str, set[str]]:
    """Build the undirected IR adjacency (SCHEMA.md §7b ``closeness_to_seed``).

    Two QIDs are adjacent iff they co-appear in the same operator / strategy /
    sub_knowledge edge. Reuses build 2's :func:`_edges_from_ir` enumeration so
    the scorer and the frontier extractor agree on what an "edge" is; the
    ``depends_on`` manifest edge is intentionally not folded in here (the scorer
    is given only the graph, matching ``extract_frontier(ir)`` with no manifest).

    Args:
        ir: The package IR whose reference edges define adjacency.

    Returns:
        A symmetric ``qid -> set[neighbour qid]`` map. Self-loops are dropped.
    """
    return _adjacency_from_edges(_edges_from_ir(ir, None))


def _resolved_seed_qids(exploration_map: ExplorationMap) -> set[str]:
    """Return the set of non-null seed QIDs (the resolved inquiry origins)."""
    seeds: set[str] = set()
    for seed in exploration_map.seeds:
        qid = seed.get("qid")
        if isinstance(qid, str) and qid:
            seeds.add(qid)
    return seeds


def _min_hops_to_seeds(
    starts: set[str],
    seeds: set[str],
    adjacency: dict[str, set[str]],
) -> int | None:
    """Min hop-distance from any ``start`` to any ``seed`` over ``adjacency``.

    A multi-source breadth-first search seeded with all ``starts`` at once
    (distance 0); the first time it dequeues a node in ``seeds`` that distance
    is the global minimum. Returns ``None`` when no seed is reachable.

    Args:
        starts: The contact's materialized source QIDs (BFS frontier 0).
        seeds: The resolved seed QIDs to reach.
        adjacency: The undirected IR adjacency.

    Returns:
        The minimum hop count, or ``None`` if unreachable / no starts.
    """
    if not starts or not seeds:
        return None
    # A start that is itself a seed is distance 0.
    if starts & seeds:
        return 0
    seen = set(starts)
    frontier = set(starts)
    distance = 0
    while frontier:
        distance += 1
        nxt: set[str] = set()
        for node in frontier:
            for neighbour in adjacency.get(node, ()):
                if neighbour in seen:
                    continue
                if neighbour in seeds:
                    return distance
                seen.add(neighbour)
                nxt.add(neighbour)
        frontier = nxt
    return None


def _belief_entropy(source_qids: list[str], beliefs: dict[str, float]) -> float:
    """Mean binary entropy over the sources that carry a belief (SCHEMA.md §7b).

    Sources with no entry in ``beliefs`` are skipped; if none of the sources has
    a belief, the feature is ``0.0``.
    """
    entropies = [binary_entropy(beliefs[q]) for q in source_qids if q in beliefs]
    if not entropies:
        return 0.0
    return sum(entropies) / len(entropies)


def _closeness_to_seed(
    source_qids: list[str],
    seeds: set[str],
    adjacency: dict[str, set[str]],
) -> float:
    """``1/(1+d)`` for the min seed hop-distance ``d``; ``0.0`` if unreachable."""
    d = _min_hops_to_seeds(set(source_qids), seeds, adjacency)
    if d is None:
        return 0.0
    return 1.0 / (1.0 + d)


def _lkm_new_territory(contact_meta: dict[str, Any]) -> float:
    """Map an LKM paper-contact's stored rank into a ``new_territory`` signal.

    An unpulled related paper *is* fresh territory (SCHEMA.md §7f), so its
    ``new_territory`` is high by construction. The stored LKM ``rank`` (a
    retrieval score, typically small and positive) breaks ties toward the
    better-retrieved paper without dominating: territory floors at ``0.5`` and the
    rank (squashed into ``[0, 0.5]`` by ``r/(1+r)``) adds on top, so a
    paper-contact's ``new_territory`` lands in ``[0.5, 1.0)``. A missing rank ⇒
    the ``0.5`` floor.
    """
    rank = contact_meta.get("rank")
    bonus = 0.0
    if isinstance(rank, (int, float)) and rank > 0:
        r = float(rank)
        bonus = r / (1.0 + r)  # squashed into [0, 1); small ranks stay small
    return 0.5 + 0.5 * bonus


def _obligation_targets(
    obligations: Iterable[SyntheticObligation] | None,
) -> set[str]:
    """Collect the ``target_qid`` set of the open synthetic obligations.

    ``obligations`` is the inquiry state's ``synthetic_obligations`` list, which
    holds *only* open obligations (``gaia inquiry obligation close`` deletes the
    row — see ``gaia/cli/commands/inquiry.py``). ``None`` (no inquiry state /
    nothing loaded) yields the empty set, so ``obligation_pressure`` is ``0.0``
    everywhere (graceful default).
    """
    if not obligations:
        return set()
    return {o.target_qid for o in obligations if getattr(o, "target_qid", None)}


def _obligation_pressure(
    ref_value: str | None,
    source_qids: list[str],
    obligation_targets: set[str],
) -> float:
    """``1.0`` iff the contact's ref QID or any source QID is an obligation target.

    Binary by design (CLIENT.md steer 3): a contact either discharges an open
    obligation or it does not. ``obligation_targets`` is precomputed once per
    ``score_frontier`` call from the open obligations.
    """
    if not obligation_targets:
        return 0.0
    if ref_value is not None and ref_value in obligation_targets:
        return 1.0
    if obligation_targets.intersection(source_qids):
        return 1.0
    return 0.0


def score_frontier(
    exploration_map: ExplorationMap,
    *,
    beliefs: dict[str, float],
    ir: LocalCanonicalGraph | None = None,
    edges: list[tuple[str, list[str]]] | None = None,
    obligations: Iterable[SyntheticObligation] | None = None,
) -> None:
    """Score every open frontier contact in place (SCHEMA.md §7b / §7e).

    For each ``status == "open"`` contact, computes the full ``score_features``
    dict (``belief_entropy`` [free], ``closeness_to_seed`` / ``survey_cost``
    [wire-up], the deferred ``0.0`` slots, and ``obligation_pressure`` [build 12]),
    the weighted ``score``::

        score = w_uncertainty*belief_entropy
              + w_relevance*closeness_to_seed
              + w_coverage*new_territory
              + w_obligation*obligation_pressure
              - w_cost*survey_cost

    using ``exploration_map.policy.weights``, and stamps ``last_scored_round``
    with the map's current ``round``. Promoted / closed contacts (``status`` not
    ``"open"``) are left untouched, and the IR is never mutated.

    The ``closeness_to_seed`` adjacency can span the **joint** dependency graph:
    pass ``edges`` (the joint edge set from
    :class:`~gaia.engine.exploration.frontier.JointView`) and adjacency is built
    from those cross-package edges; otherwise pass ``ir`` and adjacency is built
    from the single root graph (build-3 behaviour). Exactly one of ``edges`` /
    ``ir`` must be supplied.

    Args:
        exploration_map: The map whose open contacts are scored, in place.
        beliefs: ``qid -> P(x=1)`` for materialized nodes (the flattened
            ``.gaia/beliefs.json`` ``beliefs[]``). Missing nodes are simply
            skipped by the belief_entropy proxy.
        ir: The package IR — a
            :class:`~gaia.engine.ir.graphs.LocalCanonicalGraph` — used only to
            build the single-graph undirected adjacency. Read-only. Ignored when
            ``edges`` is given.
        edges: The joint cross-package edge set; when given, adjacency spans the
            whole dependency graph (SCHEMA.md §7e).
        obligations: The package's OPEN synthetic obligations (the inquiry state's
            ``synthetic_obligations`` list — already open-only). A contact whose
            ``ref`` QID or any ``sources[].qid`` matches an obligation's
            ``target_qid`` gets ``obligation_pressure = 1.0``. ``None`` ⇒ the
            feature is ``0.0`` everywhere (CLIENT.md steer 3, graceful default).
    """
    if edges is None and ir is None:
        raise ValueError("score_frontier requires exactly one of `edges` or `ir`")

    weights = exploration_map.policy.weights
    w_uncertainty = float(weights.get("w_uncertainty", 0.0))
    w_relevance = float(weights.get("w_relevance", 0.0))
    w_coverage = float(weights.get("w_coverage", 0.0))
    w_cost = float(weights.get("w_cost", 0.0))
    w_obligation = float(weights.get("w_obligation", 0.0))

    obligation_targets = _obligation_targets(obligations)
    seeds = _resolved_seed_qids(exploration_map)
    if edges is not None:
        adjacency = _adjacency_from_edges(edges)
    else:
        assert ir is not None  # narrowed by the guard above
        adjacency = _undirected_adjacency(ir)
    current_round = exploration_map.round

    for contact in exploration_map.frontier:
        if contact.status != "open":
            continue

        source_qids = [str(s["qid"]) for s in contact.sources if s.get("qid")]
        is_lkm = contact.ref.get("kind") == "lkm"
        ref_value = contact.ref.get("value")

        # Both flavours proxy belief_entropy / closeness from the SOURCE node(s)
        # — an lkm paper-contact has no graph position of its own, so it borrows
        # its surveyed source's standing (SCHEMA.md §7f).
        belief_entropy = _belief_entropy(source_qids, beliefs)
        closeness_to_seed = _closeness_to_seed(source_qids, seeds, adjacency)
        # Build 12 (CLIENT.md steer 3): does this contact discharge an open
        # obligation? Agent-visible steering term, identical for qid & lkm.
        obligation_pressure = _obligation_pressure(
            str(ref_value) if ref_value is not None else None,
            source_qids,
            obligation_targets,
        )

        if is_lkm:
            # An unpulled related paper *is* fresh territory; the stored LKM rank
            # breaks ties. Survey cost is a full paper pull ⇒ heavier than a qid.
            new_territory = _lkm_new_territory(contact.meta)
            survey_cost = LKM_SURVEY_COST
            features = {
                "belief_entropy": belief_entropy,
                "closeness_to_seed": closeness_to_seed,
                "survey_cost": survey_cost,
                "tension_potential": 0.0,
                "bridge_potential": 0.0,
                "new_territory": new_territory,
                "obligation_pressure": obligation_pressure,
            }
        else:
            # qid contacts are materialize-only ⇒ flat placeholder cost; the
            # three deferred features stay 0.0 (build 3/4c behaviour, unchanged).
            new_territory = 0.0
            survey_cost = 1.0
            features = {
                "belief_entropy": belief_entropy,
                "closeness_to_seed": closeness_to_seed,
                "survey_cost": survey_cost,
            }
            for key in _DEFERRED_FEATURES:
                features[key] = 0.0
            features["obligation_pressure"] = obligation_pressure

        contact.score_features = features
        contact.score = (
            w_uncertainty * belief_entropy
            + w_relevance * closeness_to_seed
            + w_coverage * new_territory
            + w_obligation * obligation_pressure
            - w_cost * survey_cost
        )
        contact.last_scored_round = current_round
