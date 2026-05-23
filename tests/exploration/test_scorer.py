"""Unit tests for gaia.engine.exploration.scorer (SCHEMA.md §7b)."""

from __future__ import annotations

import math
from typing import Any

from gaia.engine.exploration.frontier import extract_frontier, reconcile_frontier
from gaia.engine.exploration.scorer import (
    binary_entropy,
    sanitize_score_features,
    score_frontier,
)
from gaia.engine.exploration.state import Contact, ExplorationMap, doctrine_policy
from gaia.engine.inquiry.state import SyntheticObligation
from gaia.engine.ir.graphs import LocalCanonicalGraph
from gaia.engine.ir.knowledge import Knowledge
from gaia.engine.ir.operator import Operator

NS = "github"
PKG = "scorertest"

# The score_features keys SCHEMA.md §7b requires populated (+ build-12
# obligation_pressure, CLIENT.md steer 3).
ALL_FEATURE_KEYS = {
    "belief_entropy",
    "closeness_to_seed",
    "survey_cost",
    "tension_potential",
    "bridge_potential",
    "new_territory",
    "obligation_pressure",
}


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


def _contact_by_value(m: ExplorationMap, value: str) -> Contact:
    matches = [c for c in m.frontier if c.ref["value"] == value]
    assert len(matches) == 1, f"expected exactly one contact for {value!r}, got {len(matches)}"
    return matches[0]


# --------------------------------------------------------------------------- #
# binary_entropy
# --------------------------------------------------------------------------- #


def test_binary_entropy_edge_cases():
    assert binary_entropy(0.0) == 0.0
    assert binary_entropy(1.0) == 0.0
    assert binary_entropy(0.5) == 1.0


def test_binary_entropy_symmetry_and_range():
    # H(p) == H(1-p) and is in [0, 1].
    for p in (0.1, 0.25, 0.4, 0.7, 0.9):
        assert math.isclose(binary_entropy(p), binary_entropy(1.0 - p))
        assert 0.0 <= binary_entropy(p) <= 1.0


def test_binary_entropy_guards_out_of_range():
    # The guard treats <=0 / >=1 as certain (entropy 0), never logs of <= 0.
    assert binary_entropy(-0.5) == 0.0
    assert binary_entropy(1.5) == 0.0


# --------------------------------------------------------------------------- #
# belief_entropy proxy (mean over sources)
# --------------------------------------------------------------------------- #


def test_belief_entropy_is_mean_over_sources():
    # 'both' is a contact sourced from materialized a (belief 0.5 -> H=1.0) and
    # b (belief 0.0 -> H=0.0); belief_entropy = mean = 0.5.
    graph = make_graph(
        knowledges=[claim("a"), claim("b")],
        operators=[
            Operator(
                operator="conjunction",
                variables=[qid("a"), qid("b")],
                conclusion=qid("both"),
            )
        ],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    beliefs = {qid("a"): 0.5, qid("b"): 0.0}
    score_frontier(m, beliefs=beliefs, ir=graph)
    contact = _contact_by_value(m, qid("both"))
    assert math.isclose(contact.score_features["belief_entropy"], 0.5)


def test_belief_entropy_skips_sources_without_belief():
    # Only a carries a belief; b is missing -> mean over the one source with a
    # belief (a: 0.5 -> H=1.0).
    graph = make_graph(
        knowledges=[claim("a"), claim("b")],
        operators=[
            Operator(
                operator="conjunction",
                variables=[qid("a"), qid("b")],
                conclusion=qid("both"),
            )
        ],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={qid("a"): 0.5}, ir=graph)
    contact = _contact_by_value(m, qid("both"))
    assert math.isclose(contact.score_features["belief_entropy"], 1.0)


def test_belief_entropy_zero_when_no_source_has_belief():
    graph = make_graph(
        knowledges=[claim("a"), claim("b")],
        operators=[
            Operator(
                operator="conjunction",
                variables=[qid("a"), qid("b")],
                conclusion=qid("both"),
            )
        ],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={}, ir=graph)
    contact = _contact_by_value(m, qid("both"))
    assert contact.score_features["belief_entropy"] == 0.0


# --------------------------------------------------------------------------- #
# closeness_to_seed (undirected IR adjacency BFS)
# --------------------------------------------------------------------------- #


def _chain_graph() -> LocalCanonicalGraph:
    # Two operator edges chaining seed -- mid (via op1) and mid -- far (via op2),
    # with unmaterialized contacts hanging off each: 'c1' one hop from seed
    # (sourced by seed itself), 'c2' two hops (sourced by 'far').
    #
    #   op1: variables=[seed, mid]  conclusion=c1   -> c1 contact, sources {seed, mid}
    #   op2: variables=[mid, far]   conclusion=link -> all materialized (no contact)
    #   op3: variables=[far]        conclusion=c2   -> c2 contact, source {far}
    return make_graph(
        knowledges=[claim("seed"), claim("mid"), claim("far"), claim("link")],
        operators=[
            Operator(
                operator="conjunction",
                variables=[qid("seed"), qid("mid")],
                conclusion=qid("c1"),
            ),
            Operator(
                operator="implication",
                variables=[qid("mid"), qid("far")],
                conclusion=qid("link"),
            ),
            Operator(
                operator="negation",
                variables=[qid("far")],
                conclusion=qid("c2"),
            ),
        ],
    )


def test_closeness_one_hop_from_seed():
    graph = _chain_graph()
    m = ExplorationMap(seeds=[{"kind": "claim", "text": "s", "qid": qid("seed")}])
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={}, ir=graph)
    # c1's sources include 'seed' itself -> distance 0 -> closeness 1/(1+0)=1.0.
    c1 = _contact_by_value(m, qid("c1"))
    assert math.isclose(c1.score_features["closeness_to_seed"], 1.0)


def test_closeness_two_hops_from_seed():
    graph = _chain_graph()
    m = ExplorationMap(seeds=[{"kind": "claim", "text": "s", "qid": qid("seed")}])
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={}, ir=graph)
    # c2's only source is 'far'; far -- mid -- seed is 2 hops -> 1/(1+2).
    c2 = _contact_by_value(m, qid("c2"))
    assert math.isclose(c2.score_features["closeness_to_seed"], 1.0 / 3.0)


def test_closeness_unreachable_is_zero():
    # A disconnected component: 'iso' references 'isoc' but neither touches seed.
    graph = make_graph(
        knowledges=[claim("seed"), claim("iso")],
        operators=[
            Operator(
                operator="negation",
                variables=[qid("iso")],
                conclusion=qid("isoc"),
            )
        ],
    )
    m = ExplorationMap(seeds=[{"kind": "claim", "text": "s", "qid": qid("seed")}])
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={}, ir=graph)
    isoc = _contact_by_value(m, qid("isoc"))
    assert isoc.score_features["closeness_to_seed"] == 0.0


def test_closeness_zero_when_no_resolved_seed():
    graph = _chain_graph()
    # Seed present but qid unresolved (None) -> no resolved seeds -> 0.0.
    m = ExplorationMap(seeds=[{"kind": "claim", "text": "s", "qid": None}])
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={}, ir=graph)
    for contact in m.frontier:
        assert contact.score_features["closeness_to_seed"] == 0.0


# --------------------------------------------------------------------------- #
# survey_cost + deferred slots + full weighted score
# --------------------------------------------------------------------------- #


def test_survey_cost_is_flat_one_and_deferred_slots_zero():
    graph = make_graph(
        knowledges=[claim("a")],
        operators=[
            Operator(
                operator="negation",
                variables=[qid("a")],
                conclusion=qid("b"),
            )
        ],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={}, ir=graph)
    contact = _contact_by_value(m, qid("b"))
    assert contact.score_features["survey_cost"] == 1.0
    assert contact.score_features["tension_potential"] == 0.0
    assert contact.score_features["bridge_potential"] == 0.0
    assert contact.score_features["new_territory"] == 0.0


def test_all_six_feature_keys_populated():
    graph = _chain_graph()
    m = ExplorationMap(seeds=[{"kind": "claim", "text": "s", "qid": qid("seed")}])
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={qid("seed"): 0.5}, ir=graph)
    for contact in m.frontier:
        assert set(contact.score_features) == ALL_FEATURE_KEYS


def test_full_weighted_score_for_known_doctrine():
    # Surveyor doctrine: w_uncertainty=1.0, w_relevance=0.4, w_cost=0.2
    # (w_tension/w_bridge/w_coverage irrelevant — their features are 0.0).
    graph = _chain_graph()
    m = ExplorationMap(
        seeds=[{"kind": "claim", "text": "s", "qid": qid("seed")}],
        policy=doctrine_policy("Surveyor"),
        round=4,
    )
    reconcile_frontier(m, extract_frontier(graph, m))
    # seed belief 0.5 -> H=1.0; c1 is sourced by {seed, mid}, only seed has a
    # belief -> belief_entropy = 1.0; c1 closeness = 1.0 (distance 0).
    score_frontier(m, beliefs={qid("seed"): 0.5}, ir=graph)
    c1 = _contact_by_value(m, qid("c1"))
    expected = 1.0 * 1.0 + 0.4 * 1.0 - 0.2 * 1.0
    assert math.isclose(c1.score, expected)
    # last_scored_round stamped from the map's current round.
    assert c1.last_scored_round == 4


def test_score_uses_policy_weights():
    # A custom dial with only w_relevance live isolates the closeness term.
    graph = _chain_graph()
    weights = {
        "w_tension": 0.0,
        "w_uncertainty": 0.0,
        "w_bridge": 0.0,
        "w_coverage": 0.0,
        "w_relevance": 2.0,
        "w_cost": 0.0,
    }
    from gaia.engine.exploration.state import Policy

    m = ExplorationMap(
        seeds=[{"kind": "claim", "text": "s", "qid": qid("seed")}],
        policy=Policy(doctrine="custom", weights=weights),
    )
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={}, ir=graph)
    c1 = _contact_by_value(m, qid("c1"))
    # score = 2.0 * closeness(=1.0) = 2.0.
    assert math.isclose(c1.score, 2.0)


# --------------------------------------------------------------------------- #
# promoted / closed contacts are skipped; IR is not mutated
# --------------------------------------------------------------------------- #


def test_promoted_and_closed_contacts_are_skipped():
    graph = make_graph(
        knowledges=[claim("a"), claim("b")],
        operators=[
            Operator(
                operator="conjunction",
                variables=[qid("a"), qid("b")],
                conclusion=qid("both"),
            )
        ],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    open_contact = _contact_by_value(m, qid("both"))

    # A surveyed (promoted) contact and a skipped one — both must stay untouched.
    surveyed = Contact(
        id="ct_surveyed1",
        ref={"kind": "qid", "value": qid("done")},
        sources=[{"qid": qid("a"), "edge": "operator_target"}],
        status="surveyed",
        score=0.99,
        score_features={"belief_entropy": 0.42},
        last_scored_round=1,
    )
    skipped = Contact(
        id="ct_skipped1",
        ref={"kind": "qid", "value": qid("nope")},
        sources=[{"qid": qid("a"), "edge": "operator_target"}],
        status="skipped",
    )
    m.frontier.extend([surveyed, skipped])

    score_frontier(m, beliefs={qid("a"): 0.5, qid("b"): 0.5}, ir=graph)

    # Open contact got scored.
    assert open_contact.score is not None
    assert set(open_contact.score_features) == ALL_FEATURE_KEYS
    # Promoted contact untouched (stale cached values preserved).
    assert surveyed.score == 0.99
    assert surveyed.score_features == {"belief_entropy": 0.42}
    assert surveyed.last_scored_round == 1
    # Skipped contact never scored.
    assert skipped.score is None
    assert skipped.score_features == {}
    assert skipped.last_scored_round is None


def test_score_frontier_does_not_mutate_ir():
    graph = make_graph(
        knowledges=[claim("a")],
        operators=[
            Operator(
                operator="negation",
                variables=[qid("a")],
                conclusion=qid("b"),
            )
        ],
    )
    before_knowledge_ids = sorted(k.id for k in graph.knowledges)
    before_operator_count = len(graph.operators)
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={qid("a"): 0.5}, ir=graph)
    assert sorted(k.id for k in graph.knowledges) == before_knowledge_ids
    assert len(graph.operators) == before_operator_count


# --------------------------------------------------------------------------- #
# Joint edge-set scoring (SCHEMA.md §7e): closeness_to_seed spans the joint    #
# cross-package adjacency, not just the root graph.                            #
# --------------------------------------------------------------------------- #


def test_score_frontier_closeness_spans_joint_edge_set():
    # Seed is a dep-owned QID; the contact's source is a root-owned QID. There is
    # NO root-graph edge linking them, so a root-only adjacency cannot reach the
    # seed (closeness 0.0). The JOINT edge set carries a depends_on edge tying
    # root_src <-> dep_seed, so closeness becomes 1/(1+1) = 0.5.
    seed = "lkm:dep::dep_seed"
    root_src = "github:scorertest::root_src"
    contact_qid = "lkm:dep::dep_unmaterialized"

    m = ExplorationMap(policy=doctrine_policy("Surveyor"), seeds=[{"kind": "claim", "qid": seed}])
    m.frontier.append(
        Contact(
            id="ct_joint01",
            ref={"kind": "qid", "value": contact_qid},
            sources=[{"qid": root_src, "edge": "depends_on"}],
        )
    )

    # Joint edges: a depends_on edge co-referencing the seed, the root source,
    # and the unmaterialized contact (the manifest record shape).
    joint_edges = [("depends_on", [seed, root_src, contact_qid])]

    score_frontier(m, beliefs={}, edges=joint_edges)
    contact = m.frontier[0]
    assert contact.score_features["closeness_to_seed"] == 0.5
    assert set(contact.score_features) == ALL_FEATURE_KEYS


def test_score_frontier_requires_edges_or_ir():
    import pytest

    m = ExplorationMap()
    with pytest.raises(ValueError, match="exactly one of"):
        score_frontier(m, beliefs={})


# --------------------------------------------------------------------------- #
# lkm_related paper-contact scoring (SCHEMA.md §7f, build 4d)                  #
# --------------------------------------------------------------------------- #


def test_lkm_contact_populates_all_six_features_and_new_territory():
    # An lkm paper-contact proxies belief_entropy/closeness from its source qid,
    # gets a live new_territory from its stored rank, and a heavier survey_cost.
    from gaia.engine.exploration.scorer import LKM_SURVEY_COST

    graph = make_graph(knowledges=[claim("seed")])
    m = ExplorationMap(
        seeds=[{"kind": "claim", "qid": qid("seed")}],
        policy=doctrine_policy("Cartographer"),
    )
    m.frontier.append(
        Contact(
            id="ct_lkm1",
            ref={"kind": "lkm", "value": "813135"},
            sources=[{"qid": qid("seed"), "edge": "lkm_related"}],
            meta={"paper_id": "813135", "rank": 0.3},
        )
    )
    score_frontier(m, beliefs={qid("seed"): 0.5}, ir=graph)
    c = m.frontier[0]
    assert set(c.score_features) == ALL_FEATURE_KEYS
    # belief_entropy proxied from the source (0.5 -> H=1.0).
    assert math.isclose(c.score_features["belief_entropy"], 1.0)
    # closeness: the source IS a seed -> distance 0 -> 1.0.
    assert math.isclose(c.score_features["closeness_to_seed"], 1.0)
    # new_territory is live and in [0.5, 1.0).
    nt = c.score_features["new_territory"]
    assert 0.5 <= nt < 1.0
    # survey_cost is the heavier lkm constant.
    assert c.score_features["survey_cost"] == LKM_SURVEY_COST
    assert c.score is not None


def test_lkm_new_territory_floors_without_rank():
    graph = make_graph(knowledges=[claim("seed")])
    m = ExplorationMap(policy=doctrine_policy("Cartographer"))
    m.frontier.append(
        Contact(
            id="ct_lkm2",
            ref={"kind": "lkm", "value": "p"},
            sources=[{"qid": qid("seed"), "edge": "lkm_related"}],
            meta={"paper_id": "p"},  # no rank
        )
    )
    score_frontier(m, beliefs={}, ir=graph)
    assert m.frontier[0].score_features["new_territory"] == 0.5


def test_lkm_higher_rank_scores_higher_new_territory():
    graph = make_graph(knowledges=[claim("seed")])
    m = ExplorationMap(policy=doctrine_policy("Cartographer"))
    m.frontier.extend(
        [
            Contact(
                id="ct_lo",
                ref={"kind": "lkm", "value": "lo"},
                sources=[{"qid": qid("seed"), "edge": "lkm_related"}],
                meta={"paper_id": "lo", "rank": 0.01},
            ),
            Contact(
                id="ct_hi",
                ref={"kind": "lkm", "value": "hi"},
                sources=[{"qid": qid("seed"), "edge": "lkm_related"}],
                meta={"paper_id": "hi", "rank": 0.9},
            ),
        ]
    )
    score_frontier(m, beliefs={}, ir=graph)
    lo = _contact_by_value(m, "lo")
    hi = _contact_by_value(m, "hi")
    assert hi.score_features["new_territory"] > lo.score_features["new_territory"]


def test_qid_contact_scoring_unchanged_with_coverage_term():
    # Adding the w_coverage*new_territory term must not regress qid contacts:
    # their new_territory is 0.0, so the score equals the build-3 formula.
    graph = _chain_graph()
    m = ExplorationMap(
        seeds=[{"kind": "claim", "qid": qid("seed")}],
        policy=doctrine_policy("Surveyor"),
        round=4,
    )
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={qid("seed"): 0.5}, ir=graph)
    c1 = _contact_by_value(m, qid("c1"))
    assert c1.score_features["new_territory"] == 0.0
    expected = 1.0 * 1.0 + 0.4 * 1.0 - 0.2 * 1.0  # build-3 formula, coverage drops out
    assert math.isclose(c1.score, expected)


# --------------------------------------------------------------------------- #
# obligation_pressure (CLIENT.md build 12, steer 3)                           #
# --------------------------------------------------------------------------- #


def _oblig(target: str) -> SyntheticObligation:
    """An open synthetic obligation about ``target`` (open == present in list)."""
    return SyntheticObligation(qid=mint(target), target_qid=target, content="show it")


def mint(label: str) -> str:
    return f"oblig_{label}"


def test_obligation_pressure_one_when_ref_matches():
    # The contact's ref QID is the obligation's target_qid -> pressure 1.0.
    graph = make_graph(
        knowledges=[claim("a")],
        operators=[Operator(operator="negation", variables=[qid("a")], conclusion=qid("b"))],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={}, ir=graph, obligations=[_oblig(qid("b"))])
    contact = _contact_by_value(m, qid("b"))
    assert contact.score_features["obligation_pressure"] == 1.0


def test_obligation_pressure_one_when_source_matches():
    # The contact's source QID matches the obligation target -> pressure 1.0.
    graph = make_graph(
        knowledges=[claim("a"), claim("b")],
        operators=[
            Operator(operator="conjunction", variables=[qid("a"), qid("b")], conclusion=qid("c"))
        ],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    # 'c' is sourced by {a, b}; an obligation on source 'a' boosts it.
    score_frontier(m, beliefs={}, ir=graph, obligations=[_oblig(qid("a"))])
    contact = _contact_by_value(m, qid("c"))
    assert contact.score_features["obligation_pressure"] == 1.0


def test_obligation_pressure_zero_when_no_match():
    graph = make_graph(
        knowledges=[claim("a")],
        operators=[Operator(operator="negation", variables=[qid("a")], conclusion=qid("b"))],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={}, ir=graph, obligations=[_oblig(qid("unrelated"))])
    contact = _contact_by_value(m, qid("b"))
    assert contact.score_features["obligation_pressure"] == 0.0


def test_obligation_pressure_zero_when_none_supplied():
    # Graceful default: obligations=None -> 0.0 everywhere.
    graph = make_graph(
        knowledges=[claim("a")],
        operators=[Operator(operator="negation", variables=[qid("a")], conclusion=qid("b"))],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={}, ir=graph)
    contact = _contact_by_value(m, qid("b"))
    assert contact.score_features["obligation_pressure"] == 0.0


def test_closed_obligation_does_not_boost():
    # "Closed" == removed from the synthetic_obligations list (gaia inquiry
    # obligation close deletes the row). An empty/absent list is the closed state,
    # so a contact that WOULD have matched gets no boost.
    graph = make_graph(
        knowledges=[claim("a")],
        operators=[Operator(operator="negation", variables=[qid("a")], conclusion=qid("b"))],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    # The obligation on qid('b') was closed -> not in the list passed in.
    score_frontier(m, beliefs={}, ir=graph, obligations=[])
    contact = _contact_by_value(m, qid("b"))
    assert contact.score_features["obligation_pressure"] == 0.0


def test_w_obligation_in_presets_and_matching_contact_outranks():
    # w_obligation present in every preset; a matching contact outranks a
    # non-matching one all else equal (same sources/structure, only the
    # obligation differs).
    from gaia.engine.exploration.state import DOCTRINE_PRESETS

    for preset in DOCTRINE_PRESETS.values():
        assert "w_obligation" in preset
        assert preset["w_obligation"] > 0.0

    # Two sibling contacts off the same seed/source: 'match' is the obligation
    # target, 'plain' is not. Everything else (closeness, belief) is identical.
    graph = make_graph(
        knowledges=[claim("seed")],
        operators=[
            Operator(operator="negation", variables=[qid("seed")], conclusion=qid("match")),
            Operator(operator="negation", variables=[qid("seed")], conclusion=qid("plain")),
        ],
    )
    m = ExplorationMap(
        seeds=[{"kind": "claim", "qid": qid("seed")}],
        policy=doctrine_policy("Surveyor"),
    )
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={qid("seed"): 0.5}, ir=graph, obligations=[_oblig(qid("match"))])
    match = _contact_by_value(m, qid("match"))
    plain = _contact_by_value(m, qid("plain"))
    assert match.score_features["obligation_pressure"] == 1.0
    assert plain.score_features["obligation_pressure"] == 0.0
    # The only difference is the obligation term, so match must outrank plain by
    # exactly w_obligation (Surveyor default 1.0).
    assert match.score > plain.score
    assert math.isclose(match.score - plain.score, 1.0)


def test_obligation_pressure_survives_sanitize_but_belief_stripped():
    # Agent-visibility contract (CLIENT.md steers 3 & 4): obligation_pressure is
    # NOT a belief key, so sanitize keeps it; belief_entropy is stripped.
    graph = make_graph(
        knowledges=[claim("a")],
        operators=[Operator(operator="negation", variables=[qid("a")], conclusion=qid("b"))],
    )
    m = ExplorationMap()
    reconcile_frontier(m, extract_frontier(graph, m))
    score_frontier(m, beliefs={qid("a"): 0.5}, ir=graph, obligations=[_oblig(qid("b"))])
    contact = _contact_by_value(m, qid("b"))
    sanitized = sanitize_score_features(contact.score_features)
    assert "obligation_pressure" in sanitized
    assert sanitized["obligation_pressure"] == 1.0
    assert "belief_entropy" not in sanitized


def test_lkm_contact_gets_obligation_pressure():
    # An lkm paper-contact's obligation_pressure matches on its source qid too.
    graph = make_graph(knowledges=[claim("seed")])
    m = ExplorationMap(
        seeds=[{"kind": "claim", "qid": qid("seed")}],
        policy=doctrine_policy("Cartographer"),
    )
    m.frontier.append(
        Contact(
            id="ct_lkm_ob",
            ref={"kind": "lkm", "value": "p1"},
            sources=[{"qid": qid("seed"), "edge": "lkm_related"}],
            meta={"paper_id": "p1", "rank": 0.3},
        )
    )
    score_frontier(m, beliefs={}, ir=graph, obligations=[_oblig(qid("seed"))])
    c = m.frontier[0]
    assert set(c.score_features) == ALL_FEATURE_KEYS
    assert c.score_features["obligation_pressure"] == 1.0
