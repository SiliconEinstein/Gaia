"""Unit tests for gaia.engine.exploration.discoveries (SCHEMA.md §6 / §7c)."""

from __future__ import annotations

from typing import Any

from gaia.engine.exploration.discoveries import (
    KIND_CONTRADICTION,
    KIND_KEYSTONE,
    KIND_SETTLED_CORE,
    compute_discoveries,
    detect_contradictions,
    detect_keystones,
    detect_settled_core,
)
from gaia.engine.ir.graphs import LocalCanonicalGraph
from gaia.engine.ir.knowledge import Knowledge
from gaia.engine.ir.operator import Operator

NS = "github"
PKG = "disctest"


def qid(label: str) -> str:
    """Compose a QID in the test namespace/package."""
    return f"{NS}:{PKG}::{label}"


def claim(label: str) -> Knowledge:
    """A minimal materialized claim Knowledge node."""
    return Knowledge(id=qid(label), type="claim", content=label)


def make_graph(
    *,
    knowledges: list[Knowledge],
    operators: list[Operator] | None = None,
    strategies: list[Any] | None = None,
) -> LocalCanonicalGraph:
    """Build a LocalCanonicalGraph for the test namespace/package."""
    return LocalCanonicalGraph(
        namespace=NS,
        package_name=PKG,
        knowledges=knowledges,
        operators=operators or [],
        strategies=strategies or [],
    )


# --------------------------------------------------------------------------- #
# contradiction
# --------------------------------------------------------------------------- #


def test_contradiction_on_belief_drop():
    # A node whose belief fell by more than the threshold between rounds.
    graph = make_graph(knowledges=[claim("a"), claim("b")])
    prev = {qid("a"): 0.80, qid("b"): 0.50}
    curr = {qid("a"): 0.30, qid("b"): 0.52}  # a dropped 0.50; b barely moved

    discoveries = detect_contradictions(graph, curr, prev)

    assert len(discoveries) == 1
    disc = discoveries[0]
    assert disc["kind"] == KIND_CONTRADICTION
    assert disc["ids"] == [qid("a")]
    assert "dropped" in disc["note"]


def test_contradiction_first_round_has_no_baseline():
    # Round 0: no previous beliefs => no belief-drop contradiction can fire.
    graph = make_graph(knowledges=[claim("a")])
    discoveries = detect_contradictions(graph, {qid("a"): 0.1}, {})
    assert discoveries == []


def test_contradiction_small_drop_below_threshold_ignored():
    graph = make_graph(knowledges=[claim("a")])
    prev = {qid("a"): 0.60}
    curr = {qid("a"): 0.50}  # drop of 0.10 < 0.30 threshold
    assert detect_contradictions(graph, curr, prev) == []


def test_contradiction_prior_dissent_via_ir_dict():
    # detect_prior_dissent reads the IR-as-dict claim metadata prior_records.
    graph = make_graph(knowledges=[claim("a")])
    ir_dict = {
        "knowledges": [
            {
                "id": qid("a"),
                "label": "a",
                "type": "claim",
                "metadata": {
                    "prior_records": [
                        {"value": 0.2, "source_id": "s1"},
                        {"value": 0.9, "source_id": "s2"},
                    ]
                },
            }
        ]
    }
    discoveries = detect_contradictions(graph, {}, {}, ir_dict=ir_dict)
    assert len(discoveries) == 1
    assert discoveries[0]["kind"] == KIND_CONTRADICTION
    assert discoveries[0]["ids"] == [qid("a")]
    assert "dissent" in discoveries[0]["note"]


# --------------------------------------------------------------------------- #
# keystone
# --------------------------------------------------------------------------- #


def _keystone_graph() -> LocalCanonicalGraph:
    # Three conjunction operators, each pairing `hub` (conclusion) with two
    # distinct premises. `hub` co-occurs with 6 distinct nodes (in-degree 6);
    # every premise co-occurs only with its pair partner + hub (in-degree 2).
    knowledges = [claim(f"p{i}") for i in range(6)] + [claim("hub")]
    operators = [
        Operator(
            operator="conjunction",
            variables=[qid(f"p{2 * i}"), qid(f"p{2 * i + 1}")],
            conclusion=qid("hub"),
        )
        for i in range(3)
    ]
    return make_graph(knowledges=knowledges, operators=operators)


def test_keystone_on_high_indegree_node():
    discoveries = detect_keystones(_keystone_graph(), min_indegree=3)

    hub_hits = [d for d in discoveries if d["ids"] == [qid("hub")]]
    assert len(hub_hits) == 1
    assert hub_hits[0]["kind"] == KIND_KEYSTONE
    assert "referenced by" in hub_hits[0]["note"]
    # The premises (in-degree 2) are below the threshold and not reported.
    assert all(d["ids"] != [qid("p0")] for d in discoveries)


def test_keystone_below_threshold_not_reported():
    knowledges = [claim("p0"), claim("p1"), claim("hub")]
    operators = [
        Operator(operator="conjunction", variables=[qid("p0"), qid("p1")], conclusion=qid("hub"))
    ]
    graph = make_graph(knowledges=knowledges, operators=operators)
    # Every node co-occurs with exactly 2 others (in-degree 2) < threshold 3.
    assert detect_keystones(graph, min_indegree=3) == []


# --------------------------------------------------------------------------- #
# settled_core
# --------------------------------------------------------------------------- #


def test_settled_core_on_near_certain_beliefs():
    beliefs = {
        qid("hi"): 0.98,  # entropy ~0.14 < eps -> settled
        qid("lo"): 0.02,  # entropy ~0.14 < eps -> settled
        qid("mid"): 0.50,  # entropy 1.0 -> not settled
    }
    discoveries = detect_settled_core(beliefs, epsilon=0.2)

    settled_ids = {d["ids"][0] for d in discoveries}
    assert settled_ids == {qid("hi"), qid("lo")}
    assert all(d["kind"] == KIND_SETTLED_CORE for d in discoveries)


def test_settled_core_empty_when_all_uncertain():
    assert detect_settled_core({qid("a"): 0.5, qid("b"): 0.45}, epsilon=0.2) == []


# --------------------------------------------------------------------------- #
# compute_discoveries — the aggregate
# --------------------------------------------------------------------------- #


def test_compute_discoveries_concatenates_all_kinds():
    graph = _keystone_graph()

    prev = {qid("p0"): 0.8}
    curr = {qid("p0"): 0.3, qid("hub"): 0.99}  # p0 drops; hub settles

    discoveries = compute_discoveries(graph, curr, prev)
    kinds = {d["kind"] for d in discoveries}
    assert KIND_CONTRADICTION in kinds
    assert KIND_KEYSTONE in kinds
    assert KIND_SETTLED_CORE in kinds
