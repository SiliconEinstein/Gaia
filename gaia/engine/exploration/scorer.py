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
``bridge_potential``  activated ``1.0`` iff surveying/wiring the contact connects an orphan
                             component to the seed core (sources span ≥2 components, or it is
                             adjacent to an orphan) — needs a ``MapHealth`` (EXPANSION.md §3.B);
                             ``0.0`` without one. Identical for qid + lkm contacts.
``new_territory``   activated qid coverage via ``MapHealth`` (EXPANSION.md §3.B): low for
                             intra-paper drilling (all sources in one surveyed component),
                             higher for reaching a fresh region; lkm keeps its rank-derived
                             signal. ``0.0`` for qid without a ``MapHealth``.
``tension_potential`` deferred ``0.0`` (Inquisitor deferred this iteration — EXPANSION.md §3.B).
``obligation_pressure`` build 12 ``1.0`` iff the contact's ``ref`` QID or any of its
                             ``sources[].qid`` matches an OPEN synthetic obligation's
                             ``target_qid`` — **or is one hop from it** in the IR
                             adjacency (theme 006, so a claim-QID obligation reaches
                             the adjacent frontier contacts that feed it) — else ``0.0``.
                             Obligations
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

**Cold-start relevance (theme 010).** The stored LKM ``rank`` ALSO feeds a
*relevance* facet for lkm contacts, **distinct from** ``new_territory``
(coverage): it is folded into ``closeness_to_seed`` via ``max(graph_closeness,
r/(1+r))``. With a free-text cold-start seed (``qid: null``) the graph
``closeness_to_seed`` is ``0.0`` everywhere, so ranking would otherwise be
novelty-only; this rank-derived relevance gives on-topic high-rank seed-query
papers a non-zero, rank-differentiated relevance so they outrank tangential
ones — and once the seed RESOLVES (build 4c free-text resolution, theme 010a) a
stronger graph closeness simply wins the ``max``. qid contacts are untouched.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gaia.engine.exploration.frontier import _edges_from_ir

if TYPE_CHECKING:
    from gaia.engine.exploration.health import MapHealth
    from gaia.engine.exploration.state import ExplorationMap
    from gaia.engine.inquiry.state import SyntheticObligation
    from gaia.engine.ir.graphs import LocalCanonicalGraph

# SCHEMA.md §4 — the six score_features keys. belief_entropy is [free];
# closeness_to_seed / survey_cost are [wire-up]. ``tension_potential`` stays a
# deferred 0.0 slot (Inquisitor, EXPANSION.md §3.B — deferred this iteration);
# ``bridge_potential`` and qid ``new_territory`` are now ACTIVATED via MapHealth
# (EXPANSION.md §3.B). When no MapHealth is supplied they fall back to 0.0 (the
# pre-expansion behaviour), so the qid-deferred set is just tension.
_QID_DEFERRED_FEATURES = ("tension_potential",)

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
# --lkm-paper` is genuinely heavier *effort*, so an lkm contact still costs more.
#
# The constant is bounded, though, so the cost asymmetry cannot defeat the
# expansion goal (EXPANSION.md §1, the 0327 acceptance test). The pathology: an
# external pull is *rewarded* with `new_territory` AND *penalised* with the
# heavier cost - and at the old ``2.0`` the cost penalty (``w_cost*(2.0-1.0)``)
# out-weighed the coverage benefit (``w_coverage*(nt_lkm-nt_drill)``) under the
# coverage-light doctrines (Surveyor/Diplomat, ``w_coverage=0.3``), so a pulled
# paper's own intra-paper drilling contacts still out-ranked external papers even
# after the coverage slot was activated. That double-counts the same act (open
# territory) once as benefit and once as cost.
#
# Fix: keep the effort signal (lkm > qid) but cap the cost so the cost *gap*
# never exceeds the coverage *benefit* an external pull buys, in any doctrine.
# Tightest doctrine: Surveyor/Diplomat ``w_coverage=0.3``, ``w_cost=0.2``;
# minimum coverage benefit is ``0.3*(0.5-0.2)=0.09`` (external floor 0.5 vs.
# intra-paper drilling 0.2), so we need ``0.2*(C-1) < 0.09`` -> ``C < 1.45``.
# ``1.25`` keeps a clear margin (cost gap ``0.2*0.25=0.05 < 0.09``) while leaving
# lkm strictly heavier than a qid. (There is still no real LKM-pull cost model;
# this stays a principled placeholder, just one that no longer fights the design.)
LKM_SURVEY_COST = 1.25


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


def _lkm_rank_relevance(contact_meta: dict[str, Any]) -> float:
    """Map an LKM paper-contact's stored rank into a RELEVANCE signal (theme 010).

    The stored LKM ``rank`` is the originating seed query's retrieval score for
    this paper — a direct "how on-topic to what we asked" signal, **distinct from**
    ``new_territory`` (coverage / how unexplored). A free-text cold-start seed has
    no resolved QID, so graph ``closeness_to_seed`` is ``0.0`` for every contact
    and ranking degenerates to novelty-only; this rank-derived relevance gives
    on-topic high-rank papers a non-zero relevance even before the seed resolves,
    so they outrank tangential low-rank ones. Squashed by ``r/(1+r)`` into
    ``[0, 1)`` (a missing/zero rank ⇒ ``0.0``).
    """
    rank = contact_meta.get("rank")
    if isinstance(rank, (int, float)) and rank > 0:
        r = float(rank)
        return r / (1.0 + r)
    return 0.0


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


@dataclass(frozen=True)
class _ComponentIndex:
    """Precomputed component membership used by the activated coverage/bridge slots.

    Derived once per ``score_frontier`` from a :class:`MapHealth`:

    * ``component_of`` — surveyed QID → its component index;
    * ``core_members`` — surveyed QIDs in the seed/core component;
    * ``orphan_members`` — surveyed QIDs in any orphan (non-core) component;
    * ``surveyed_papers`` — count of distinct surveyed components (a proxy for
      "how many already-surveyed regions exist", used to scale qid coverage).
    """

    component_of: dict[str, int]
    core_members: frozenset[str]
    orphan_members: frozenset[str]
    component_count: int


def _component_index(health: MapHealth | None) -> _ComponentIndex | None:
    """Build a :class:`_ComponentIndex` from a MapHealth, or ``None`` if absent."""
    if health is None:
        return None
    component_of: dict[str, int] = {}
    core: set[str] = set()
    orphan: set[str] = set()
    for i, comp in enumerate(health.components):
        for qid in comp.members:
            component_of[qid] = i
        if comp.is_seed:
            core.update(comp.members)
        else:
            orphan.update(comp.members)
    return _ComponentIndex(
        component_of=component_of,
        core_members=frozenset(core),
        orphan_members=frozenset(orphan),
        component_count=len(health.components),
    )


def _bridge_potential(
    source_qids: list[str],
    ref_value: str | None,
    index: _ComponentIndex | None,
    adjacency: dict[str, set[str]],
    *,
    is_drilling: bool = False,
) -> float:
    """``1.0`` iff surveying/wiring this contact would connect an orphan to the core.

    Activated bridge slot (EXPANSION.md §3.B), high iff the contact is the kind of
    edge that heals fragmentation:

    * **spans ≥2 components** — its sources (the surveyed nodes it is reached
      from) fall in two or more distinct surveyed components, so authoring the
      contact ties those components together; OR
    * **adjacent to an orphan** — a source (or the ref QID itself) is in an orphan
      component, or is a graph neighbour of an orphan member — so wiring the
      contact pulls a disconnected island toward the core.

    Binary by design (mirrors ``obligation_pressure``): the doctrine weight
    ``w_bridge`` *is* the bump a bridging contact gets, so Diplomat / Cartographer
    reliably surface it. ``0.0`` when no MapHealth is available (the pre-expansion
    behaviour) or there are no orphans to bridge.

    ``is_drilling`` (0327 acceptance fix, live-surfaced): a *pulled-but-
    unformalized* contact references a single materialized internal claim of a
    pulled paper's orphan island. Its ref QID **is** an orphan member, so the
    "touches an orphan" branch below would mark it a bridge — but formalizing one
    more internal claim of an island does NOT connect that island to the core
    (the island stays orphan relative to root; the true bridge is a root→island
    ``derive`` the agent authors in a consolidate turn, not a frontier
    drilling-contact). Under Cartographer/Diplomat (``w_bridge=1.0``) this bogus
    bridge bonus floods the frontier with all N internal claims of every pulled
    paper, defeating the expansion goal exactly as the territory bug did. So a
    drilling contact never claims bridge potential — it is intra-island drilling,
    not a core bridge.
    """
    if index is None or not index.orphan_members or is_drilling:
        return 0.0
    anchors = set(source_qids)
    if ref_value is not None:
        anchors.add(ref_value)
    # Spans >=2 distinct surveyed components.
    comps = {index.component_of[a] for a in anchors if a in index.component_of}
    if len(comps) >= 2:
        return 1.0
    # Touches an orphan directly...
    if anchors & index.orphan_members:
        return 1.0
    # ...or is one hop from an orphan member in the joint adjacency.
    for a in anchors:
        if adjacency.get(a, set()) & index.orphan_members:
            return 1.0
    return 0.0


def _qid_new_territory(
    source_qids: list[str],
    index: _ComponentIndex | None,
    *,
    is_drilling: bool = False,
) -> float:
    """Coverage for a qid contact: external expansion vs. intra-paper drilling.

    Activated qid coverage slot (EXPANSION.md §3.B) — the *unthrottle*. A qid
    contact whose sources are all inside ONE already-surveyed component is
    *drilling* into a paper you already have (low territory); one whose sources
    reach across components, or that has no surveyed source at all (a dangling
    reference into the unsurveyed), is opening fresher territory (higher).

    This fixes the documented ranking pathology: a freshly-pulled paper's own
    intra-paper ``depends_on`` contacts (all sources in that one paper's
    component) now get a LOW ``new_territory`` and stop out-ranking external
    ``lkm_related`` papers under an uncertainty/coverage-weighted doctrine.

    Scale:

    * **``is_drilling``** ⇒ ``0.2`` (intra-paper drilling, regardless of sources) —
      see below;
    * no surveyed source ⇒ ``1.0`` (a pure reach into the fog — maximal novelty);
    * sources span ≥2 components ⇒ ``0.7`` (cross-region — opening new territory);
    * sources all in one component ⇒ ``0.2`` (intra-paper drilling — low).

    ``is_drilling`` (0327 acceptance fix): the *pulled-but-unformalized* worklist
    contacts (``JointView._pulled_unformalized_contacts``) reference a claim that
    is **already materialized** in a pulled dependency package — its body is on
    disk, it just is not wired into the root graph yet. Formalizing it drills into
    a paper you have already pulled; it opens NO new territory. But those contacts
    carry **empty ``sources``** (a freshly-pulled paper has no co-reference into
    the surveyed core yet), so the ``not in_set`` branch below would otherwise
    score them ``1.0`` — the "fog-reach" branch — and they would out-rank external
    ``lkm_related`` papers (EXPANSION.md §1 / project INDEX open thread). The
    *materialized-set* provenance (carried by the caller as ``is_drilling``, since
    ``sources`` are empty) is the right signal: a materialized ref is drilling,
    not fog. So drilling pins to the low ``0.2`` and never reaches the fog branch.

    ``0.0`` when no MapHealth is available (pre-expansion behaviour). Distinct
    from ``closeness_to_seed`` (relevance): a far-flung dangling ref is high
    territory but may be low relevance — the doctrine weights trade them off.
    """
    if index is None:
        return 0.0
    if is_drilling:
        return 0.2
    in_set = [q for q in source_qids if q in index.component_of]
    if not in_set:
        return 1.0
    comps = {index.component_of[q] for q in in_set}
    if len(comps) >= 2:
        return 0.7
    return 0.2


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


def load_open_obligations(pkg: str | Path) -> list[SyntheticObligation]:
    """Load a package's OPEN synthetic obligations (CLIENT.md build 12 steer 3).

    Reuses the inquiry state loader (``gaia.engine.inquiry.state.load_state``) — no
    hand-parsing of ``.gaia/inquiry/state.json``. ``synthetic_obligations`` holds
    *only* open obligations (``gaia inquiry obligation close`` deletes the row), so
    the returned list is already the open set. Missing state ⇒ empty list ⇒ the
    scorer's ``obligation_pressure`` is ``0.0`` everywhere (graceful).

    This is the single SDK seam both ``gaia-lkm-explore turn`` (the orchestrator)
    and the standalone ``frontier`` verb feed into :func:`score_frontier`'s
    ``obligations=`` so the two agree on ``obligation_pressure``.

    Args:
        pkg: The knowledge-package directory.

    Returns:
        The open synthetic obligations (possibly empty).
    """
    from gaia.engine.inquiry.state import load_state

    return list(load_state(str(pkg)).synthetic_obligations)


def _obligation_pressure(
    ref_value: str | None,
    source_qids: list[str],
    obligation_targets: set[str],
    adjacency: dict[str, set[str]],
) -> float:
    """``1.0`` iff the contact discharges (or is one hop from) an open obligation.

    Binary by design (CLIENT.md steer 3): a contact either discharges an open
    obligation or it does not. ``obligation_targets`` is precomputed once per
    ``score_frontier`` call from the open obligations.

    Match rule (theme 006 — option (c), both parts):

    * **direct** — the contact's ref QID or any source QID *is* an obligation
      ``target_qid`` (the build-12 behaviour); OR
    * **one hop** — the contact's ref QID or any source QID is a direct neighbour
      (one hop) of a ``target_qid`` in the IR adjacency the scorer already builds.
      This reaches obligations keyed on an authored **claim QID**: a frontier
      contact adjacent to that claim (e.g. a paper feeding it) is pressed even
      though the claim is not itself the contact's ref/source. ONE hop only — no
      transitive propagation.
    """
    if not obligation_targets:
        return 0.0
    # The contact's graph anchors: its own ref QID (qid contacts) + its sources.
    anchors = set(source_qids)
    if ref_value is not None:
        anchors.add(ref_value)
    # Direct: an anchor IS an obligation target.
    if anchors & obligation_targets:
        return 1.0
    # One hop: an anchor is a direct neighbour of an obligation target. The
    # adjacency is symmetric, so it suffices to check each target's neighbourhood.
    for target in obligation_targets:
        if anchors & adjacency.get(target, set()):
            return 1.0
    return 0.0


def recompute_obligation_pressure(
    exploration_map: ExplorationMap,
    *,
    obligations: Iterable[SyntheticObligation] | None,
    edges: list[tuple[str, list[str]]] | None = None,
) -> None:
    """Recompute only ``obligation_pressure`` for every OPEN contact, in place.

    A lighter, belief-free refresh of just the agent-visible obligation term —
    used by surfaces that must reflect *current* obligation state without a full
    re-score (e.g. ``gaia-lkm-explore status`` after an ``obligation close``, so a
    just-closed obligation stops showing its formerly-pressed contact as pressing).
    The match rule is identical to :func:`score_frontier` (ref/source direct OR
    one-hop adjacency); the overall ``score`` is left untouched.

    Args:
        exploration_map: The map whose open contacts' ``obligation_pressure`` is
            recomputed in place. Other features and ``score`` are not modified.
        obligations: The package's OPEN synthetic obligations (already open-only).
            ``None`` / empty ⇒ ``0.0`` everywhere.
        edges: The joint cross-package edge set for the one-hop adjacency. When
            omitted/empty, only the direct ref/source match can fire.
    """
    obligation_targets = _obligation_targets(obligations)
    adjacency = _adjacency_from_edges(edges or [])
    for contact in exploration_map.frontier:
        if contact.status != "open":
            continue
        source_qids = [str(s["qid"]) for s in contact.sources if s.get("qid")]
        ref_value = contact.ref.get("value")
        pressure = _obligation_pressure(
            str(ref_value) if ref_value is not None else None,
            source_qids,
            obligation_targets,
            adjacency,
        )
        features = dict(contact.score_features)
        features["obligation_pressure"] = pressure
        contact.score_features = features


def score_frontier(
    exploration_map: ExplorationMap,
    *,
    beliefs: dict[str, float],
    ir: LocalCanonicalGraph | None = None,
    edges: list[tuple[str, list[str]]] | None = None,
    obligations: Iterable[SyntheticObligation] | None = None,
    health: MapHealth | None = None,
    materialized: Iterable[str] | None = None,
) -> None:
    """Score every open frontier contact in place (SCHEMA.md §7b / §7e).

    For each ``status == "open"`` contact, computes the full ``score_features``
    dict (``belief_entropy`` [free], ``closeness_to_seed`` / ``survey_cost``
    [wire-up], ``new_territory`` / ``bridge_potential`` [activated via MapHealth —
    EXPANSION.md §3.B], the deferred ``tension_potential`` ``0.0`` slot, and
    ``obligation_pressure`` [build 12]), the weighted ``score``::

        score = w_uncertainty*belief_entropy
              + w_relevance*closeness_to_seed
              + w_coverage*new_territory
              + w_bridge*bridge_potential
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
        health: The :class:`~gaia.engine.exploration.health.MapHealth` for the
            joint graph (EXPANSION.md §3.B). When supplied, it activates
            ``bridge_potential`` (qid + lkm: high iff surveying/wiring the contact
            connects an orphan component to the core) and a real qid
            ``new_territory`` (low for intra-paper drilling, higher for reaching a
            sparsely-surveyed region). ``None`` ⇒ both stay ``0.0`` for qid
            contacts (the pre-expansion behaviour); lkm ``new_territory`` is still
            its rank-derived signal. ``tension_potential`` stays ``0.0`` regardless
            (Inquisitor deferred — EXPANSION.md §3.B).
        materialized: The JOINT materialized-QID set (``JointView.materialized``).
            Used only as the *provenance* signal that classifies a qid contact as
            intra-paper **drilling** rather than fog-reach (0327 acceptance fix): a
            qid contact whose ``ref`` QID is in this set references a claim already
            materialized in a pulled dependency — formalizing it drills into a
            paper you already have (``new_territory = 0.2``), even though its
            ``sources`` are empty (which would otherwise hit the ``1.0`` fog-reach
            branch). ``None`` ⇒ no contact is treated as drilling (the
            pre-expansion behaviour); harmless when ``health`` is also absent.
    """
    if edges is None and ir is None:
        raise ValueError("score_frontier requires exactly one of `edges` or `ir`")

    weights = exploration_map.policy.weights
    w_uncertainty = float(weights.get("w_uncertainty", 0.0))
    w_relevance = float(weights.get("w_relevance", 0.0))
    w_coverage = float(weights.get("w_coverage", 0.0))
    w_bridge = float(weights.get("w_bridge", 0.0))
    w_cost = float(weights.get("w_cost", 0.0))
    w_obligation = float(weights.get("w_obligation", 0.0))

    obligation_targets = _obligation_targets(obligations)
    component_index = _component_index(health)
    materialized_set = set(materialized) if materialized is not None else set()
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
        # 0327 acceptance fix (provenance signal): a qid contact whose ref QID is
        # already in the joint materialized set is a *pulled-but-unformalized*
        # claim — drilling into a paper you have, not a fog-reach into new
        # territory and not a core bridge. An lkm contact's ref is a paper id, so
        # it is never in the materialized claim-QID set ⇒ never drilling.
        is_drilling = not is_lkm and ref_value is not None and str(ref_value) in materialized_set

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
            adjacency,
        )
        # Activated bridge slot (EXPANSION.md §3.B) — identical for qid & lkm:
        # high iff surveying/wiring this contact would connect an orphan to the
        # core. 0.0 when no MapHealth was supplied (pre-expansion behaviour) or
        # the contact is intra-island drilling (a pulled-unformalized internal
        # claim is not a core bridge — see _bridge_potential).
        bridge_potential = _bridge_potential(
            source_qids,
            str(ref_value) if ref_value is not None else None,
            component_index,
            adjacency,
            is_drilling=is_drilling,
        )

        if is_lkm:
            # An unpulled related paper *is* fresh territory; the stored LKM rank
            # breaks ties. Survey cost is a full paper pull ⇒ heavier than a qid.
            new_territory = _lkm_new_territory(contact.meta)
            survey_cost = LKM_SURVEY_COST
            # (theme 010) Relevance facet from the originating query's LKM rank —
            # distinct from new_territory (coverage). Folded into closeness_to_seed
            # via max() so an on-topic high-rank paper has non-zero relevance even
            # when the seed is unresolved (graph closeness 0.0) or the contact is
            # off the resolved subgraph; a resolved-seed graph closeness still wins
            # when it is the stronger signal.
            closeness_to_seed = max(closeness_to_seed, _lkm_rank_relevance(contact.meta))
            features = {
                "belief_entropy": belief_entropy,
                "closeness_to_seed": closeness_to_seed,
                "survey_cost": survey_cost,
                "tension_potential": 0.0,
                "bridge_potential": bridge_potential,
                "new_territory": new_territory,
                "obligation_pressure": obligation_pressure,
            }
        else:
            # qid contacts are materialize-only ⇒ flat placeholder cost.
            # ``new_territory`` is now ACTIVATED via MapHealth (external expansion
            # vs. intra-paper drilling — EXPANSION.md §3.B); ``tension_potential``
            # stays a 0.0 deferred slot (Inquisitor deferred this iteration).
            # ``is_drilling`` (computed above from the materialized-set provenance)
            # pins a pulled-but-unformalized claim to the low drilling territory
            # even though its sources are empty (which would otherwise score 1.0).
            new_territory = _qid_new_territory(
                source_qids, component_index, is_drilling=is_drilling
            )
            survey_cost = 1.0
            features = {
                "belief_entropy": belief_entropy,
                "closeness_to_seed": closeness_to_seed,
                "survey_cost": survey_cost,
                "bridge_potential": bridge_potential,
                "new_territory": new_territory,
            }
            for key in _QID_DEFERRED_FEATURES:
                features[key] = 0.0
            features["obligation_pressure"] = obligation_pressure

        contact.score_features = features
        contact.score = (
            w_uncertainty * belief_entropy
            + w_relevance * closeness_to_seed
            + w_coverage * new_territory
            + w_bridge * bridge_potential
            + w_obligation * obligation_pressure
            - w_cost * survey_cost
        )
        contact.last_scored_round = current_round
