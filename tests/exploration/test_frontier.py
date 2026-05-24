"""Unit tests for gaia.engine.exploration.frontier (SCHEMA.md §7a)."""

from __future__ import annotations

from typing import Any

from gaia.engine.exploration.frontier import extract_frontier, reconcile_frontier
from gaia.engine.exploration.state import Contact, ExplorationMap
from gaia.engine.ir.graphs import LocalCanonicalGraph
from gaia.engine.ir.knowledge import Knowledge
from gaia.engine.ir.operator import Operator
from gaia.engine.ir.strategy import FormalExpr, FormalStrategy, Strategy

NS = "github"
PKG = "frontiertest"


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


def _contact_by_value(contacts: list[Contact], value: str) -> Contact:
    matches = [c for c in contacts if c.ref["value"] == value]
    assert len(matches) == 1, f"expected exactly one contact for {value!r}, got {len(matches)}"
    return matches[0]


def _source_pairs(contact: Contact) -> set[tuple[str, str]]:
    return {(s["qid"], s["edge"]) for s in contact.sources}


def test_fully_materialized_graph_yields_no_contacts():
    # Every referenced QID has a Knowledge body -> frontier is empty.
    graph = make_graph(
        knowledges=[claim("a"), claim("b"), claim("both")],
        operators=[
            Operator(
                operator="conjunction",
                variables=[qid("a"), qid("b")],
                conclusion=qid("both"),
            )
        ],
    )
    assert extract_frontier(graph) == []


def test_unmaterialized_operator_conclusion_is_contact():
    # 'both' has no Knowledge body -> it is a contact reached via operator_target,
    # sourced by the materialized variables a + b.
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
    contacts = extract_frontier(graph)
    assert len(contacts) == 1
    contact = _contact_by_value(contacts, qid("both"))
    assert contact.ref == {"kind": "qid", "value": qid("both")}
    assert _source_pairs(contact) == {
        (qid("a"), "operator_target"),
        (qid("b"), "operator_target"),
    }
    # No scoring in this build.
    assert contact.score is None
    assert contact.score_features == {}
    assert contact.status == "open"


def test_unmaterialized_operator_variable_is_contact():
    # An unmaterialized *input* variable is equally a contact.
    graph = make_graph(
        knowledges=[claim("a"), claim("both")],
        operators=[
            Operator(
                operator="conjunction",
                variables=[qid("a"), qid("b")],
                conclusion=qid("both"),
            )
        ],
    )
    contacts = extract_frontier(graph)
    contact = _contact_by_value(contacts, qid("b"))
    assert _source_pairs(contact) == {
        (qid("a"), "operator_target"),
        (qid("both"), "operator_target"),
    }


def test_unmaterialized_strategy_premise_is_contact():
    # 'p' is an unmaterialized premise -> contact via strategy_given,
    # sourced by the materialized conclusion + background.
    graph = make_graph(
        knowledges=[claim("c"), claim("bg")],
        strategies=[
            Strategy(
                scope="local",
                type="infer",
                premises=[qid("p")],
                conclusion=qid("c"),
                background=[qid("bg")],
                conditional_probabilities=[0.2, 0.9],
            )
        ],
    )
    contacts = extract_frontier(graph)
    contact = _contact_by_value(contacts, qid("p"))
    assert _source_pairs(contact) == {
        (qid("c"), "strategy_given"),
        (qid("bg"), "strategy_given"),
    }


def test_unmaterialized_sub_knowledge_is_contact():
    # A composition names sub_knowledge that is not authored -> contact via
    # sub_knowledge, sourced by the owning (materialized) parent node.
    parent = Knowledge(
        id=qid("comp"),
        type="composition",
        content="composition body",
        template_name="t",
        template_version="1",
        sub_knowledge=[qid("part1"), qid("part2")],
        conclusion=qid("part1"),
    )
    graph = make_graph(knowledges=[parent, claim("part1")])
    contacts = extract_frontier(graph)
    # part1 is materialized; part2 is the contact. Its sources are the
    # materialized co-references in the same sub_knowledge edge: the owning
    # parent 'comp' and the sibling 'part1'.
    contact = _contact_by_value(contacts, qid("part2"))
    assert _source_pairs(contact) == {
        (qid("comp"), "sub_knowledge"),
        (qid("part1"), "sub_knowledge"),
    }


def test_formal_strategy_embedded_operator_is_operator_target():
    # Operators embedded inside FormalStrategy.formal_expr count as operator_target.
    graph = make_graph(
        knowledges=[claim("a"), claim("c")],
        strategies=[
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=[qid("a")],
                conclusion=qid("c"),
                formal_expr=FormalExpr(
                    operators=[
                        Operator(
                            operator="implication",
                            variables=[qid("a"), qid("c")],
                            conclusion=qid("imp"),
                        )
                    ]
                ),
            )
        ],
    )
    contacts = extract_frontier(graph)
    # 'imp' (the embedded operator conclusion) is unmaterialized -> contact.
    contact = _contact_by_value(contacts, qid("imp"))
    assert _source_pairs(contact) == {
        (qid("a"), "operator_target"),
        (qid("c"), "operator_target"),
    }


def test_depends_on_scaffold_from_formalization_manifest():
    # depends_on scaffolds live in the formalization manifest, not the graph.
    graph = make_graph(knowledges=[claim("concl"), claim("g1")])
    manifest = {
        "version": 1,
        "dependencies": [
            {
                "kind": "depends_on",
                "label": "f0",
                "conclusion": qid("concl"),
                "given": [qid("g1"), qid("g2")],
            }
        ],
        "materializations": [],
    }
    contacts = extract_frontier(graph, formalization_manifest=manifest)
    # g2 is the unmaterialized given -> contact via depends_on.
    contact = _contact_by_value(contacts, qid("g2"))
    assert _source_pairs(contact) == {
        (qid("concl"), "depends_on"),
        (qid("g1"), "depends_on"),
    }
    # Without the manifest, depends_on contributes nothing.
    assert extract_frontier(graph) == []


def test_multiple_edges_to_one_contact_merge_sources():
    # 'x' is referenced by an operator AND a strategy -> one merged Contact with
    # the union of sources, each tagged by its own edge kind.
    graph = make_graph(
        knowledges=[claim("a"), claim("c")],
        operators=[
            Operator(
                operator="implication",
                variables=[qid("a"), qid("x")],
                conclusion=qid("c"),
            )
        ],
        strategies=[
            Strategy(
                scope="local",
                type="infer",
                premises=[qid("x")],
                conclusion=qid("c"),
                conditional_probabilities=[0.2, 0.9],
            )
        ],
    )
    contacts = extract_frontier(graph)
    contact = _contact_by_value(contacts, qid("x"))
    assert _source_pairs(contact) == {
        (qid("a"), "operator_target"),
        (qid("c"), "operator_target"),
        (qid("c"), "strategy_given"),
    }


def test_composite_strategy_sub_strategies_skipped():
    # CompositeStrategy.sub_strategies are strategy_id refs, never Knowledge:
    # they must never produce a contact.
    from gaia.engine.ir.strategy import CompositeStrategy

    graph = make_graph(
        knowledges=[claim("c")],
        strategies=[
            CompositeStrategy(
                scope="local",
                type="induction",
                premises=[qid("c")],
                conclusion=qid("c"),
                sub_strategies=["lcs_deadbeefdeadbeef", "lcs_cafebabecafebabe"],
            )
        ],
    )
    contacts = extract_frontier(graph)
    # No contact whose ref value is a strategy_id.
    assert all(not c.ref["value"].startswith("lcs_") for c in contacts)


def test_extract_is_pure_and_reuses_existing_ids():
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
    first = extract_frontier(graph)
    assert len(first) == 1
    cid = first[0].id

    # An existing map carrying that contact -> re-extraction reuses its id.
    m = ExplorationMap(frontier=[first[0]])
    second = extract_frontier(graph, m)
    assert second[0].id == cid
    # The map is not mutated by extraction.
    assert m.frontier[0] is first[0]


def test_reconcile_adds_new_and_refreshes_open_contacts():
    m = ExplorationMap(round=2)
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
    extracted = extract_frontier(graph, m)
    reconcile_frontier(m, extracted, discovered_round=2)
    assert len(m.frontier) == 1
    contact = _contact_by_value(m.frontier, qid("both"))
    assert contact.discovered_round == 2
    assert contact.status == "open"

    # A later round adds a third materialized node 'c' that also points at 'both';
    # reconciling refreshes the open contact's sources from the new IR.
    graph2 = make_graph(
        knowledges=[claim("a"), claim("b"), claim("c")],
        operators=[
            Operator(
                operator="conjunction",
                variables=[qid("a"), qid("b")],
                conclusion=qid("both"),
            ),
            Operator(
                operator="implication",
                variables=[qid("c"), qid("both")],
                conclusion=qid("z"),
            ),
        ],
    )
    extracted2 = extract_frontier(graph2, m)
    reconcile_frontier(m, extracted2, discovered_round=3)
    refreshed = _contact_by_value(m.frontier, qid("both"))
    # 'both' is now also reachable from c via the second operator.
    assert (qid("c"), "operator_target") in _source_pairs(refreshed)
    # Same contact object/id kept (not re-minted) and round not bumped.
    assert refreshed.id == contact.id
    assert refreshed.discovered_round == 2
    # 'z' is a brand-new contact discovered in round 3.
    assert _contact_by_value(m.frontier, qid("z")).discovered_round == 3


def test_reconcile_preserves_promoted_and_closed_contacts():
    m = ExplorationMap(round=4)
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
    extracted = extract_frontier(graph, m)
    reconcile_frontier(m, extracted, discovered_round=4)
    contact = _contact_by_value(m.frontier, qid("both"))

    # Survey it: status flips, a SurveyRecord is added.
    m.promote_contact(contact.id, survey_round=5)
    assert m.find_contact(contact.id).status == "surveyed"
    promoted_sources = _source_pairs(m.find_contact(contact.id))

    # Mark a second contact as skipped to cover the closed branch.
    m.frontier.append(
        Contact(
            id="ct_skipped01",
            ref={"kind": "qid", "value": qid("skipme")},
            sources=[{"qid": qid("a"), "edge": "operator_target"}],
            status="skipped",
        )
    )

    # Re-extract: 'both' would still be a contact (its body is not in this graph),
    # and 'skipme' is no longer referenced at all. Reconcile must NOT resurrect or
    # delete either of them, nor touch their sources.
    extracted2 = extract_frontier(graph, m)
    reconcile_frontier(m, extracted2, discovered_round=6)

    surveyed = m.find_contact(contact.id)
    assert surveyed is not None
    assert surveyed.status == "surveyed"  # not resurrected to open
    assert _source_pairs(surveyed) == promoted_sources  # sources untouched

    skipped = m.find_contact("ct_skipped01")
    assert skipped is not None  # not deleted
    assert skipped.status == "skipped"
    assert _source_pairs(skipped) == {(qid("a"), "operator_target")}


# --------------------------------------------------------------------------- #
# Free-text seed resolution (theme 010a)                                      #
# --------------------------------------------------------------------------- #


def test_resolve_freetext_seed_matches_best_materialized_node_by_overlap():
    from gaia.engine.exploration.frontier import resolve_freetext_seed_qid

    materialized = {qid("hubble"), qid("sterile")}
    node_texts = {
        qid("hubble"): "hubble_tension Resolving the Hubble constant tension with SH0ES",
        qid("sterile"): "sterile_neutrino Sterile neutrino dark matter constraints",
    }
    # The seed text overlaps the on-topic node strongly, the tangential one not.
    matched = resolve_freetext_seed_qid(
        "Why is the Hubble constant tension unresolved?", materialized, node_texts
    )
    assert matched == qid("hubble")


def test_resolve_freetext_seed_requires_min_overlap():
    from gaia.engine.exploration.frontier import resolve_freetext_seed_qid

    materialized = {qid("x")}
    node_texts = {qid("x"): "completely unrelated quantum chromodynamics lattice"}
    # No meaningful overlap -> no resolution (stays cold).
    result = resolve_freetext_seed_qid("dark energy expansion history", materialized, node_texts)
    assert result is None


def test_resolve_freetext_seed_only_returns_materialized():
    from gaia.engine.exploration.frontier import resolve_freetext_seed_qid

    # A perfect-overlap node that is NOT in the materialized set must not win.
    materialized: set[str] = set()
    node_texts = {qid("unmat"): "dark energy expansion history supernovae"}
    result = resolve_freetext_seed_qid("dark energy expansion history", materialized, node_texts)
    assert result is None


# --------------------------------------------------------------------------- #
# Pulled-but-unformalized dependency claims (build 16)                         #
# --------------------------------------------------------------------------- #

from pathlib import Path  # noqa: E402

from gaia.engine.exploration.frontier import (  # noqa: E402
    JointView,
    _edges_from_ir,
    _materialized_qids,
)

DEP_NS = "lkm"
DEP_PKG = "lkm_bohrium_demo_paper_42"


def dep_qid(label: str) -> str:
    return f"{DEP_NS}:{DEP_PKG}::{label}"


def dep_graph(knowledges: list[Knowledge]) -> LocalCanonicalGraph:
    return LocalCanonicalGraph(
        namespace=DEP_NS, package_name=DEP_PKG, knowledges=knowledges, operators=[], strategies=[]
    )


def _joint_view(
    root: LocalCanonicalGraph,
    dep: LocalCanonicalGraph,
    *,
    root_path: Path,
    dep_path: Path,
) -> JointView:
    view = JointView()
    view.graphs = [root, dep]
    view.package_roots = [root_path, dep_path]
    view.materialized = _materialized_qids(root) | _materialized_qids(dep)
    view.edges = _edges_from_ir(root, None) + _edges_from_ir(dep, None)
    return view


def test_pulled_dep_claims_surface_as_unformalized_contacts(tmp_path):
    # A pulled paper's claims are materialized in the dep package but not wired
    # into the root reasoning graph -> they surface as a "formalize me" worklist.
    root = make_graph(knowledges=[claim("seed"), claim("my_synthesis")])
    dep = dep_graph(
        [
            Knowledge(id=dep_qid("p1"), type="claim", content="low-ell power deficit confirmed"),
            Knowledge(id=dep_qid("p2"), type="claim", content="quadrupole alignment at 3 sigma"),
        ]
    )
    view = _joint_view(root, dep, root_path=tmp_path / "root", dep_path=tmp_path / "dep")

    contacts = view.extract()
    pulled = {c.ref["value"]: c for c in contacts if c.meta.get("pulled_unformalized")}
    assert set(pulled) == {dep_qid("p1"), dep_qid("p2")}
    # Each carries the claim's text as a human title (the bare `p1` label is opaque).
    assert "deficit" in pulled[dep_qid("p1")].meta["title"]
    assert pulled[dep_qid("p1")].ref["kind"] == "qid"
    # Root's own claims are never pulled-contacts.
    assert all(not v.startswith(NS) for v in pulled)


def test_formalized_dep_claim_is_not_surfaced(tmp_path):
    # A root edge referencing a dep claim = it's formalized into the reasoning
    # graph -> it must NOT appear as a pulled-unformalized contact (p2 still does).
    root = make_graph(
        knowledges=[claim("seed"), claim("my_synthesis")],
        operators=[
            Operator(
                operator="conjunction",
                variables=[qid("my_synthesis"), dep_qid("p1")],
                conclusion=qid("seed"),
            )
        ],
    )
    dep = dep_graph(
        [
            Knowledge(id=dep_qid("p1"), type="claim", content="formalized via root operator"),
            Knowledge(id=dep_qid("p2"), type="claim", content="still just pulled"),
        ]
    )
    view = _joint_view(root, dep, root_path=tmp_path / "root", dep_path=tmp_path / "dep")

    pulled = {c.ref["value"] for c in view.extract() if c.meta.get("pulled_unformalized")}
    assert dep_qid("p1") not in pulled  # formalized
    assert dep_qid("p2") in pulled  # still pulled-unformalized


def test_engine_internal_dep_nodes_are_skipped(tmp_path):
    root = make_graph(knowledges=[claim("seed")])
    dep = dep_graph(
        [
            Knowledge(id=dep_qid("p1"), type="claim", content="real claim"),
            Knowledge(id=dep_qid("_anon_000"), type="claim", content="engine internal"),
        ]
    )
    view = _joint_view(root, dep, root_path=tmp_path / "root", dep_path=tmp_path / "dep")
    pulled = {c.ref["value"] for c in view.extract() if c.meta.get("pulled_unformalized")}
    assert dep_qid("p1") in pulled
    assert dep_qid("_anon_000") not in pulled


def test_root_only_view_has_no_pulled_contacts(tmp_path):
    root = make_graph(knowledges=[claim("seed"), claim("a")])
    view = JointView()
    view.graphs = [root]
    view.package_roots = [tmp_path / "root"]
    view.materialized = _materialized_qids(root)
    view.edges = _edges_from_ir(root, None)
    assert all(not c.meta.get("pulled_unformalized") for c in view.extract())


def test_reconcile_retires_formalized_pulled_contact():
    # An open pulled-unformalized contact that is absent from the fresh extraction
    # (it got formalized) is retired to `surveyed`; an ordinary open contact that
    # is merely absent is left untouched.
    m = ExplorationMap()
    m.frontier.append(
        Contact(
            id="ct_pulled1",
            ref={"kind": "qid", "value": dep_qid("p1")},
            status="open",
            meta={"pulled_unformalized": True, "title": "low-ell deficit"},
        )
    )
    m.frontier.append(
        Contact(id="ct_ordinary", ref={"kind": "qid", "value": qid("ordinary")}, status="open")
    )
    # Fresh extraction still has p2 (pulled) but NOT p1 (now formalized) and NOT
    # the ordinary contact.
    fresh = [
        Contact(
            id="ct_pulled2",
            ref={"kind": "qid", "value": dep_qid("p2")},
            status="open",
            meta={"pulled_unformalized": True, "title": "quadrupole alignment"},
        )
    ]
    reconcile_frontier(m, fresh)
    by_qid = {str(c.ref["value"]): c for c in m.frontier}
    assert by_qid[dep_qid("p1")].status == "surveyed"  # formalized -> retired
    assert by_qid[qid("ordinary")].status == "open"  # untouched (not a pulled contact)
