"""Map connectivity health — the ``MapHealth`` primitive (EXPANSION.md §3.A).

The expand↔consolidate iteration adds one genuinely new engine primitive: a pure
function that measures the **connectivity** of the joint exploration graph. It
powers the activated scorer slots (``bridge_potential`` / qid ``new_territory``),
the ``auto`` mode cadence, the maintainability readout, and the consolidate
bridging task — all from one place.

A :class:`MapHealth` answers, over the JOINT undirected adjacency (the same edge
set the scorer / frontier already share):

* which weakly-connected components the surveyed territory falls into;
* what fraction of surveyed nodes sit in the biggest component
  (``largest_fraction``);
* which components are **orphans** — surveyed islands not in the seed's
  component (the disconnected pulled papers EXPANSION.md §1 describes);
* whether the map is *unhealthy past the fragmentation threshold* — the single
  predicate that triggers an ``auto`` consolidate turn (EXPANSION.md §4).

**Ratified-aware (EXPANSION.md §3.E).** Some islands are *legitimately* disjoint
(genuinely different domains). The agent can ratify a whole component as
separate; a ratified-and-still-valid island is **excluded** from the unhealthy
count (a map of 3 components, all ratified, reads HEALTHY). A ratification is
**provisional**: it is honored only while its premise still holds — when a later
expansion introduces a node that bridges the ratified island to the core, the
ratification is **REOPENED** and the island returns to the unhealthy count and
the consolidate worklist. The reopen test reuses the same bridge adjacency check
the scorer's ``bridge_potential`` uses — no separate machinery.

Pure, deterministic, no I/O — mirrors :mod:`gaia.engine.exploration.discoveries`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from gaia.engine.exploration.scorer import _adjacency_from_edges

# EXPANSION.md §4 — default fragmentation threshold. The map is "unhealthy past
# the threshold" iff there are at least this many un-ratified orphan components
# OR the orphan node fraction exceeds :data:`DEFAULT_ORPHAN_FRACTION`. Threshold
# over hair-trigger (user, 2026-05-25): the map is allowed to fragment a little
# and grow uninterrupted, then healed in a sweep once fragmentation crosses here.
DEFAULT_MIN_ORPHAN_COMPONENTS = 2
DEFAULT_ORPHAN_FRACTION = 0.34


@dataclass(frozen=True)
class RatifiedSeparation:
    """An island the agent judged a legitimately-separate region (EXPANSION.md §3.E).

    Per-component granularity (user, 2026-05-25): the agent ratifies a whole
    island, not individual contacts. ``member_qids`` is the surveyed-node set of
    the island at ratification time; ``rationale`` is the agent's one-line
    scientific reason it is legitimately disjoint; ``round`` and
    ``evidence_fingerprint`` capture the joint-graph state it was judged under so
    the provisional-reopen test (below) can tell whether new evidence has changed
    the premise.

    This dataclass is the in-memory shape the health computation consumes;
    :class:`~gaia.engine.exploration.state.ExplorationMap` persists the same
    fields as plain dicts in ``ratified_separations`` (additive, back-compat).
    """

    member_qids: frozenset[str]
    rationale: str = ""
    round: int = 0
    evidence_fingerprint: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> RatifiedSeparation:
        """Rehydrate from the persisted ``map.json`` payload (defensive on types)."""
        members = raw.get("member_qids", [])
        if not isinstance(members, (list, tuple, set, frozenset)):
            members = []
        fp = raw.get("evidence_fingerprint", {})
        round_raw = raw.get("round", 0)
        round_val = round_raw if isinstance(round_raw, int) else 0
        return cls(
            member_qids=frozenset(str(q) for q in members),
            rationale=str(raw.get("rationale", "")),
            round=round_val,
            evidence_fingerprint=dict(fp) if isinstance(fp, dict) else {},
        )


@dataclass(frozen=True)
class Component:
    """One weakly-connected component of the surveyed territory.

    Attributes:
        members: the surveyed QIDs in this component (sorted, for legibility).
        is_seed: whether this component contains a resolved seed (the core).
        ratified: whether this component is covered by a still-valid
            :class:`RatifiedSeparation` (excluded from the unhealthy count).
        reopened: whether this component was ratified but its ratification is now
            stale — a newly-surveyed node bridges it to the core, so it counts as
            un-ratified again (EXPANSION.md §3.E provisional reopening).
        bridge_qid: when ``reopened`` (or when a non-seed component is adjacent to
            the core through an unmaterialized contact), the QID whose presence
            now connects this island to the core — surfaced in the worklist note.
    """

    members: tuple[str, ...]
    is_seed: bool = False
    ratified: bool = False
    reopened: bool = False
    bridge_qid: str | None = None


@dataclass(frozen=True)
class MapHealth:
    """The connectivity readout over the joint graph (EXPANSION.md §3.A / §4).

    Attributes:
        components: every surveyed component, seed component first then by size.
        largest_fraction: share of surveyed nodes in the biggest component
            (``1.0`` for a fully-connected map, ``0.0`` for an empty one).
        orphans: the non-seed components (surveyed islands off the core).
        orphan_node_fraction: share of surveyed nodes that sit in an orphan.
        unratified_orphan_count: orphans that are neither bridged nor
            validly-ratified (a reopened ratification counts here) — the quantity
            the fragmentation threshold is measured against.
        reopened: the components whose ratification went stale this compute.
    """

    components: tuple[Component, ...]
    largest_fraction: float
    orphans: tuple[Component, ...]
    orphan_node_fraction: float
    unratified_orphan_count: int
    reopened: tuple[Component, ...]

    @property
    def component_count(self) -> int:
        """Number of surveyed components."""
        return len(self.components)

    @property
    def ratified_count(self) -> int:
        """Number of still-valid (non-reopened) ratified components."""
        return sum(1 for c in self.components if c.ratified and not c.reopened)

    def is_unhealthy(
        self,
        *,
        min_orphan_components: int = DEFAULT_MIN_ORPHAN_COMPONENTS,
        orphan_fraction: float = DEFAULT_ORPHAN_FRACTION,
    ) -> bool:
        """Whether fragmentation is past the threshold (EXPANSION.md §4).

        Unhealthy ⇔ there exist un-ratified orphan components (a reopened
        ratification counts as un-ratified) **in a quantity past the threshold**:
        at least ``min_orphan_components`` of them OR an orphan node fraction
        above ``orphan_fraction``. Non-coercive by construction — fragmentation is
        tolerated below the threshold and healed in a sweep past it.
        """
        if self.unratified_orphan_count <= 0:
            return False
        return (
            self.unratified_orphan_count >= min_orphan_components
            or self.orphan_node_fraction > orphan_fraction
        )


def _weakly_connected_components(
    nodes: set[str],
    adjacency: dict[str, set[str]],
) -> list[set[str]]:
    """Partition ``nodes`` into weakly-connected components over ``adjacency``.

    Only edges *between two ``nodes``* connect (an edge to an unmaterialized
    contact does not pull a fog node into a component). A node with no in-set
    neighbour is its own singleton component. Deterministic: components are
    discovered in sorted-node order via flood fill.
    """
    seen: set[str] = set()
    components: list[set[str]] = []
    for start in sorted(nodes):
        if start in seen:
            continue
        comp: set[str] = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in comp:
                continue
            comp.add(node)
            seen.add(node)
            for neighbour in adjacency.get(node, ()):  # only in-set neighbours connect
                if neighbour in nodes and neighbour not in comp:
                    stack.append(neighbour)
        components.append(comp)
    return components


def _bridges_to_core(
    island: set[str],
    core: set[str],
    edges: list[tuple[str, list[str]]],
    adjacency: dict[str, set[str]],
) -> str | None:
    """Return a QID that links ``island`` to ``core``, or ``None`` (EXPANSION.md §3.E/B).

    The same adjacency notion ``bridge_potential`` uses: a *candidate connecting
    edge now exists* iff —

    * some reference edge **co-references** a member of ``island`` and a member of
      ``core`` (a direct spanning edge — would also merge the components, so this
      mainly fires the round the bridge first appears); OR
    * a node ``x`` is **adjacent to both** the island and the core — typically an
      as-yet-unmaterialized contact ``x`` that two separate edges tie to an island
      member and to a core member respectively. The components are still disjoint
      (``x`` is not surveyed, so it does not merge them), yet authoring ``x`` (or
      the connecting edge) *would* wire the island to the core — the provisional
      reopen trigger.

    Returns the first such bridging QID — preferring a concrete island member the
    spanning edge ties in (so the worklist note can name *which* new evidence
    reopens the island), then the connecting node ``x`` — or ``None`` when the two
    are still genuinely disjoint.
    """
    if not island or not core:
        return None
    # Direct spanning edge.
    for _edge_kind, refs in edges:
        present = [r for r in refs if r]
        touches_island = any(r in island for r in present)
        touches_core = any(r in core for r in present)
        if touches_island and touches_core:
            for r in present:
                if r in island:
                    return r
            return present[0]
    # A connecting node adjacent to both (e.g. an unmaterialized contact).
    island_neighbours: set[str] = set()
    for m in island:
        island_neighbours |= adjacency.get(m, set())
    for x in sorted(island_neighbours):
        if adjacency.get(x, set()) & core:
            # Prefer naming an island member that x ties in, for the note.
            tied = sorted(adjacency.get(x, set()) & island)
            return tied[0] if tied else x
    return None


def compute_map_health(
    surveyed: Iterable[str],
    seeds: Iterable[str],
    edges: list[tuple[str, list[str]]],
    *,
    ratified: Iterable[RatifiedSeparation] = (),
) -> MapHealth:
    """Compute the connectivity health of the joint exploration graph (EXPANSION.md §3.A).

    Pure and deterministic. Builds the undirected adjacency from ``edges`` (reuses
    :func:`~gaia.engine.exploration.scorer._adjacency_from_edges`), partitions the
    ``surveyed`` set into weakly-connected components, identifies the seed
    component as the core, and classifies every other component as an orphan —
    excluding components covered by a *still-valid* ratified separation.

    Ratification is honored provisionally: for each ratified component, the
    bridge test (:func:`_bridges_to_core`) is re-run against the current joint
    edges; if a connecting edge now exists, the ratification is **reopened** and
    the island re-enters the unhealthy count (EXPANSION.md §3.E).

    Args:
        surveyed: the surveyed-node QIDs (``map.surveyed`` keys).
        seeds: the resolved seed QIDs (the core anchor); empty ⇒ the largest
            component is treated as the core (best-effort, so health still reads
            on a seedless map).
        edges: the JOINT ``(edge_kind, [referenced_qids])`` edge set — the same
            list :class:`~gaia.engine.exploration.frontier.JointView` exposes.
        ratified: the in-memory ratified separations (per component); a component
            whose member set matches one is excluded unless reopened.

    Returns:
        A :class:`MapHealth` readout.
    """
    surveyed_set = {q for q in surveyed if q}
    seed_set = {q for q in seeds if q} & surveyed_set
    adjacency = _adjacency_from_edges(edges)
    raw_components = _weakly_connected_components(surveyed_set, adjacency)

    n_surveyed = len(surveyed_set)
    largest_fraction = (
        max((len(c) for c in raw_components), default=0) / n_surveyed if n_surveyed else 0.0
    )

    # Identify the seed/core component. Prefer the component containing a seed;
    # fall back to the largest component when no seed is resolved (so a seedless
    # map still has a defined core and meaningful orphans).
    core_members: set[str] = set()
    if seed_set:
        for comp in raw_components:
            if comp & seed_set:
                core_members |= comp
    elif raw_components:
        core_members = max(raw_components, key=lambda c: (len(c), sorted(c)))

    # Index ratified separations by their member set for exact per-component match.
    ratified_by_members: dict[frozenset[str], RatifiedSeparation] = {
        r.member_qids: r for r in ratified
    }

    components: list[Component] = []
    orphans: list[Component] = []
    reopened: list[Component] = []
    unratified_orphan_count = 0
    orphan_nodes = 0

    for comp in raw_components:
        is_seed = bool(comp & core_members) and bool(core_members)
        members = tuple(sorted(comp))
        rat = ratified_by_members.get(frozenset(comp))
        is_ratified = rat is not None
        is_reopened = False
        bridge_qid: str | None = None

        if not is_seed:
            orphan_nodes += len(comp)
            # Does a connecting edge to the core now exist? Reuse the bridge check.
            bridge_qid = _bridges_to_core(comp, core_members, edges, adjacency)
            if is_ratified and bridge_qid is not None:
                # Provisional reopen: the ratification's premise is stale.
                is_reopened = True
            if (not is_ratified) or is_reopened:
                unratified_orphan_count += 1

        component = Component(
            members=members,
            is_seed=is_seed,
            ratified=is_ratified,
            reopened=is_reopened,
            bridge_qid=bridge_qid if (not is_seed) else None,
        )
        components.append(component)
        if not is_seed:
            orphans.append(component)
        if is_reopened:
            reopened.append(component)

    # Order: seed component(s) first, then orphans by descending size then members.
    components.sort(key=lambda c: (not c.is_seed, -len(c.members), c.members))
    orphans.sort(key=lambda c: (-len(c.members), c.members))

    orphan_node_fraction = orphan_nodes / n_surveyed if n_surveyed else 0.0

    return MapHealth(
        components=tuple(components),
        largest_fraction=largest_fraction,
        orphans=tuple(orphans),
        orphan_node_fraction=orphan_node_fraction,
        unratified_orphan_count=unratified_orphan_count,
        reopened=tuple(reopened),
    )


__all__ = [
    "DEFAULT_MIN_ORPHAN_COMPONENTS",
    "DEFAULT_ORPHAN_FRACTION",
    "Component",
    "MapHealth",
    "RatifiedSeparation",
    "compute_map_health",
]
