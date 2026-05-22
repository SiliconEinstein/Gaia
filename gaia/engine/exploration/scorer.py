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
================  =========  ===========================================================

The score is the SCHEMA.md §4 weighted sum (the three ``0.0`` terms drop out)::

    score(c) = w_uncertainty*belief_entropy
             + w_relevance*closeness_to_seed
             - w_cost*survey_cost

Weights come from ``exploration_map.policy.weights``. ``beliefs`` is a
``dict[qid -> float]`` (P(x=1) per node — the on-disk shape of
``.gaia/beliefs.json``'s ``beliefs[]``, flattened by the caller); the function
takes the dict so it is trivially testable. No CLI, no loop, no render.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from gaia.engine.exploration.frontier import _edges_from_ir

if TYPE_CHECKING:
    from gaia.engine.exploration.state import ExplorationMap
    from gaia.engine.ir.graphs import LocalCanonicalGraph

# SCHEMA.md §4 — the six score_features keys. belief_entropy is [free];
# closeness_to_seed / survey_cost are [wire-up]; the remaining three are
# deferred 0.0 slots (DESIGN §8).
_DEFERRED_FEATURES = ("tension_potential", "bridge_potential", "new_territory")


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
    adjacency: dict[str, set[str]] = {}
    for _edge_kind, refs in _edges_from_ir(ir, None):
        nodes = [r for r in refs if r]
        for a in nodes:
            for b in nodes:
                if a == b:
                    continue
                adjacency.setdefault(a, set()).add(b)
    return adjacency


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


def score_frontier(
    exploration_map: ExplorationMap,
    *,
    beliefs: dict[str, float],
    ir: LocalCanonicalGraph,
) -> None:
    """Score every open frontier contact in place (SCHEMA.md §7b).

    For each ``status == "open"`` contact, computes the full six-key
    ``score_features`` dict (``belief_entropy`` [free], ``closeness_to_seed`` /
    ``survey_cost`` [wire-up], and the three deferred ``0.0`` slots), the
    weighted ``score``::

        score = w_uncertainty*belief_entropy
              + w_relevance*closeness_to_seed
              - w_cost*survey_cost

    using ``exploration_map.policy.weights``, and stamps ``last_scored_round``
    with the map's current ``round``. Promoted / closed contacts (``status`` not
    ``"open"``) are left untouched, and the IR is never mutated.

    Args:
        exploration_map: The map whose open contacts are scored, in place.
        beliefs: ``qid -> P(x=1)`` for materialized nodes (the flattened
            ``.gaia/beliefs.json`` ``beliefs[]``). Missing nodes are simply
            skipped by the belief_entropy proxy.
        ir: The package IR — a
            :class:`~gaia.engine.ir.graphs.LocalCanonicalGraph` — used only to
            build the undirected adjacency for ``closeness_to_seed``. Read-only.
    """
    weights = exploration_map.policy.weights
    w_uncertainty = float(weights.get("w_uncertainty", 0.0))
    w_relevance = float(weights.get("w_relevance", 0.0))
    w_cost = float(weights.get("w_cost", 0.0))

    seeds = _resolved_seed_qids(exploration_map)
    adjacency = _undirected_adjacency(ir)
    current_round = exploration_map.round

    for contact in exploration_map.frontier:
        if contact.status != "open":
            continue

        source_qids = [str(s["qid"]) for s in contact.sources if s.get("qid")]

        belief_entropy = _belief_entropy(source_qids, beliefs)
        closeness_to_seed = _closeness_to_seed(source_qids, seeds, adjacency)
        # qid contacts are materialize-only ⇒ flat placeholder cost; refine when
        # an LKM-pull cost model exists. w_cost has little bite until then.
        survey_cost = 1.0

        features = {
            "belief_entropy": belief_entropy,
            "closeness_to_seed": closeness_to_seed,
            "survey_cost": survey_cost,
        }
        for key in _DEFERRED_FEATURES:
            features[key] = 0.0

        contact.score_features = features
        contact.score = (
            w_uncertainty * belief_entropy + w_relevance * closeness_to_seed - w_cost * survey_cost
        )
        contact.last_scored_round = current_round
