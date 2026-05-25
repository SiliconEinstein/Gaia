"""Unit tests for gaia.lkm_explorer.engine.health (EXPANSION.md §3.A / §4)."""

from __future__ import annotations

from gaia.lkm_explorer.engine.health import (
    DEFAULT_MIN_ORPHAN_COMPONENTS,
    RatifiedSeparation,
    compute_map_health,
)

NS = "github"
PKG = "healthtest"


def qid(label: str) -> str:
    return f"{NS}:{PKG}::{label}"


def edge(*labels: str) -> tuple[str, list[str]]:
    """A reference edge co-referencing the given labels (operator_target kind)."""
    return ("operator_target", [qid(x) for x in labels])


# --------------------------------------------------------------------------- #
# components / largest_fraction
# --------------------------------------------------------------------------- #


def test_single_connected_component_is_healthy():
    # seed-s, a, b all wired into one component.
    surveyed = [qid(x) for x in ("s", "a", "b")]
    edges = [edge("s", "a"), edge("a", "b")]
    health = compute_map_health(surveyed, [qid("s")], edges)
    assert health.component_count == 1
    assert health.largest_fraction == 1.0
    assert health.orphans == ()
    assert health.unratified_orphan_count == 0
    assert not health.is_unhealthy()


def test_two_islands_one_orphan():
    # Core {s,a}; island {b,c} disjoint.
    surveyed = [qid(x) for x in ("s", "a", "b", "c")]
    edges = [edge("s", "a"), edge("b", "c")]
    health = compute_map_health(surveyed, [qid("s")], edges)
    assert health.component_count == 2
    assert len(health.orphans) == 1
    assert health.orphans[0].members == (qid("b"), qid("c"))
    assert health.largest_fraction == 0.5
    assert health.unratified_orphan_count == 1


def test_seed_component_identified_as_core():
    surveyed = [qid(x) for x in ("s", "a", "x", "y")]
    edges = [edge("s", "a"), edge("x", "y")]
    health = compute_map_health(surveyed, [qid("x")], edges)
    core = [c for c in health.components if c.is_seed]
    assert len(core) == 1
    assert qid("x") in core[0].members


def test_no_seed_falls_back_to_largest_component():
    # No resolved seed: the largest component is the core.
    surveyed = [qid(x) for x in ("a", "b", "c", "d", "e")]
    edges = [edge("a", "b"), edge("b", "c"), edge("d", "e")]
    health = compute_map_health(surveyed, [], edges)
    core = [c for c in health.components if c.is_seed]
    assert len(core) == 1
    assert len(core[0].members) == 3  # {a,b,c} is larger than {d,e}


# --------------------------------------------------------------------------- #
# threshold / is_unhealthy
# --------------------------------------------------------------------------- #


def test_one_orphan_below_default_threshold_is_healthy_when_fraction_low():
    # 1 orphan node of 10 surveyed: count 1 < 2 and fraction 0.1 < 0.34 → healthy.
    core = [qid(f"c{i}") for i in range(9)]
    core_edges = [edge(f"c{i}", f"c{i + 1}") for i in range(8)]
    surveyed = [*core, qid("orphan")]
    health = compute_map_health(surveyed, [qid("c0")], core_edges)
    assert health.unratified_orphan_count == 1
    assert not health.is_unhealthy()


def test_two_orphans_crosses_count_threshold():
    surveyed = [qid(x) for x in ("s", "a", "b", "c")]
    edges = [edge("s", "a")]  # b and c are each their own singleton orphan
    health = compute_map_health(surveyed, [qid("s")], edges)
    assert health.unratified_orphan_count >= DEFAULT_MIN_ORPHAN_COMPONENTS
    assert health.is_unhealthy()


def test_orphan_fraction_crosses_threshold():
    # One big orphan: 3 of 5 surveyed nodes are off the core → fraction 0.6 > 0.34.
    surveyed = [qid(x) for x in ("s", "a", "b", "c", "d")]
    edges = [edge("s", "a"), edge("b", "c"), edge("c", "d")]
    health = compute_map_health(surveyed, [qid("s")], edges)
    assert health.unratified_orphan_count == 1
    assert health.orphan_node_fraction == 0.6
    assert health.is_unhealthy()


# --------------------------------------------------------------------------- #
# ratification (exclusion) + provisional reopening (EXPANSION.md §3.E)
# --------------------------------------------------------------------------- #


def test_ratified_islands_read_healthy():
    # Two orphan islands, both ratified → HEALTHY (legitimately multi-domain).
    surveyed = [qid(x) for x in ("s", "a", "b", "c")]
    edges = [edge("s", "a")]
    ratified = [
        RatifiedSeparation(member_qids=frozenset({qid("b")}), rationale="different domain"),
        RatifiedSeparation(member_qids=frozenset({qid("c")}), rationale="different domain"),
    ]
    health = compute_map_health(surveyed, [qid("s")], edges, ratified=ratified)
    assert len(health.orphans) == 2
    assert all(o.ratified for o in health.orphans)
    assert health.unratified_orphan_count == 0
    assert not health.is_unhealthy()
    assert health.ratified_count == 2


def test_ratification_reopens_on_new_bridging_evidence():
    # Island {b,c} ratified, disjoint from core {s,a}.
    surveyed = [qid(x) for x in ("s", "a", "b", "c")]
    ratified = [RatifiedSeparation(member_qids=frozenset({qid("b"), qid("c")}), rationale="x")]

    # Premise still holds: no edge / candidate node spans island↔core → stays
    # ratified, healthy, not reopened.
    edges_before = [edge("s", "a"), edge("b", "c")]
    h0 = compute_map_health(surveyed, [qid("s")], edges_before, ratified=ratified)
    assert h0.unratified_orphan_count == 0
    assert h0.reopened == ()

    # New evidence: an as-yet-unmaterialized node x (a fog contact) is now
    # referenced alongside b (island) in one edge and alongside s (core) in
    # another. b/c stay their own component (x is unsurveyed, so it does not merge
    # them), but a candidate connecting edge now EXISTS → the ratification's
    # premise is stale → REOPEN.
    x = qid("x")  # NOT in `surveyed`
    edges_after = [
        edge("s", "a"),
        edge("b", "c"),
        ("depends_on", [qid("b"), x]),  # x adjacent to island
        ("depends_on", [qid("s"), x]),  # x adjacent to core
    ]
    h1 = compute_map_health(surveyed, [qid("s")], edges_after, ratified=ratified)
    reopened = [c for c in h1.components if c.reopened]
    assert len(reopened) == 1
    assert qid("b") in reopened[0].members
    assert reopened[0].bridge_qid == qid("b")
    assert h1.unratified_orphan_count == 1
    # The reopened island re-enters the unhealthy count (orphan fraction 0.5 > 0.34).
    assert h1.is_unhealthy()


def test_empty_map_is_healthy():
    health = compute_map_health([], [], [])
    assert health.component_count == 0
    assert health.largest_fraction == 0.0
    assert not health.is_unhealthy()
