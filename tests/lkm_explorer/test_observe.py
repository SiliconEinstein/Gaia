"""Unit tests for gaia.lkm_explorer.engine.observe (SCHEMA.md §7f, build 4d).

`lkm_related` is the PRIMARY frontier source: the unpulled related papers a
`gaia search lkm` survey surfaces become paper-granularity frontier contacts.
These tests drive the pure ingestion engine off a captured-real fixture
(`fixtures/lkm_search_free_fall.json`, public paper metadata) plus small
synthetic variants for de-dup / materialized / promotion.
"""

from __future__ import annotations

import json
from pathlib import Path

from gaia.lkm_explorer.engine.observe import (
    materialized_paper_ids_from_roots,
    observe_lkm_results,
    promote_materialized_lkm_contacts,
)
from gaia.lkm_explorer.engine.state import Contact, ExplorationMap

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "lkm_search_free_fall.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _search(variables: list[dict]) -> dict:
    return {"code": 0, "data": {"variables": variables}}


def _var(
    paper_id: str,
    node_id: str,
    rank: float,
    *,
    title: str | None = None,
    doi: str | None = None,
) -> dict:
    variable = {
        "id": node_id,
        "score": rank,
        "provenance": {"source_packages": [f"paper:{paper_id}"]},
    }
    if title or doi:
        variable["paper"] = {}
        if title:
            variable["paper"]["en_title"] = title
        if doi:
            variable["paper"]["doi"] = doi
    return variable


def _lkm_contacts(m: ExplorationMap) -> list[Contact]:
    return [c for c in m.frontier if c.ref.get("kind") == "lkm"]


# --------------------------------------------------------------------------- #
# basic ingestion: unmaterialized papers become lkm_related contacts          #
# --------------------------------------------------------------------------- #


def test_observe_records_unmaterialized_papers_as_contacts():
    m = ExplorationMap(seeds=[{"kind": "claim", "qid": "example:p::seed"}])
    results = _load_fixture()
    out = observe_lkm_results(
        m,
        results,
        materialized=set(),
        source_qid="example:p::seed",
        query="free fall",
        index_id="bohrium",
    )

    # The fixture's 5 results are 5 distinct unmaterialized papers (qid null).
    contacts = _lkm_contacts(m)
    assert len(contacts) == 5
    assert len(out.new_contacts) == 5
    assert not out.updated_contacts

    for c in contacts:
        assert c.ref["kind"] == "lkm"
        assert c.ref["value"]  # a paper_id
        # Source = the surveyed node, edge lkm_related.
        assert {"qid": "example:p::seed", "edge": "lkm_related"} in c.sources
        # meta carries the LKM provenance the contact needs.
        assert c.meta["paper_id"] == c.ref["value"]
        assert c.meta["query"] == "free fall"
        assert c.meta["index_id"] == "bohrium"
        assert isinstance(c.meta["rank"], float)
        assert c.meta["lkm_node_ids"], "expected the contributing lkm node id(s)"


def test_observe_does_not_treat_raw_lkm_node_id_as_materialized_qid():
    # Raw LKM node ids are provenance for the search result, not Gaia QIDs in
    # the joint materialized set. Paper-level freshness is handled by paper_id.
    m = ExplorationMap()
    results = _search(
        [
            _var("111111", "gcn_already", 0.5),
            _var("222222", "gcn_fresh", 0.4),
        ]
    )
    observe_lkm_results(
        m,
        results,
        materialized={"lkm:bohrium:gcn_already"},
        source_qid="s",
        index_id="bohrium",
    )
    values = {c.ref["value"] for c in _lkm_contacts(m)}
    assert values == {"111111", "222222"}


def test_observe_skips_already_pulled_paper_by_id():
    # A paper already pulled into the joint view (its id in materialized_paper_ids)
    # is not re-added.
    m = ExplorationMap()
    results = _search([_var("333", "gcn_pulled", 0.3), _var("444", "gcn_new", 0.3)])
    observe_lkm_results(
        m,
        results,
        materialized=set(),
        materialized_paper_ids={"333"},
        source_qid="s",
        index_id="bohrium",
    )
    assert {c.ref["value"] for c in _lkm_contacts(m)} == {"444"}


# --------------------------------------------------------------------------- #
# de-dup / merge by paper_id                                                  #
# --------------------------------------------------------------------------- #


def test_observe_dedups_two_results_one_paper():
    # Two result rows pointing at the SAME paper_id -> one contact, union node
    # ids, MAX rank.
    m = ExplorationMap()
    results = _search(
        [
            _var("555", "gcn_a", 0.2, title="row a", doi="10.1/x"),
            _var("555", "gcn_b", 0.7, title="row b"),
        ]
    )
    observe_lkm_results(m, results, materialized=set(), source_qid="s", index_id="bohrium")
    contacts = _lkm_contacts(m)
    assert len(contacts) == 1
    c = contacts[0]
    assert c.ref["value"] == "555"
    assert c.meta["rank"] == 0.7  # max of the two
    assert set(c.meta["lkm_node_ids"]) == {"lkm:bohrium:gcn_a", "lkm:bohrium:gcn_b"}
    assert c.meta["doi"] == "10.1/x"


def test_observe_merges_across_two_calls():
    # A second observation of the same paper (different source) merges sources +
    # node ids and keeps the higher rank, without adding a second contact.
    m = ExplorationMap()
    first = _search([_var("666", "gcn_first", 0.1)])
    second = _search([_var("666", "gcn_second", 0.9)])
    observe_lkm_results(
        m, first, materialized=set(), source_qid="src_a", query="q1", index_id="bohrium"
    )
    out2 = observe_lkm_results(
        m, second, materialized=set(), source_qid="src_b", query="q2", index_id="bohrium"
    )

    contacts = _lkm_contacts(m)
    assert len(contacts) == 1
    assert out2.updated_contacts == ["666"]
    c = contacts[0]
    assert {s["qid"] for s in c.sources} == {"src_a", "src_b"}
    assert c.meta["rank"] == 0.9
    assert set(c.meta["lkm_node_ids"]) == {"lkm:bohrium:gcn_first", "lkm:bohrium:gcn_second"}
    # First-seen query is preserved.
    assert c.meta["query"] == "q1"


def test_observe_leaves_promoted_lkm_contact_intact():
    # A promoted (surveyed) lkm contact must not be merged into / reopened.
    m = ExplorationMap()
    m.frontier.append(
        Contact(
            id="ct_done",
            ref={"kind": "lkm", "value": "777"},
            status="surveyed",
            meta={"paper_id": "777", "rank": 0.1},
        )
    )
    results = _search([_var("777", "gcn_again", 0.99)])
    out = observe_lkm_results(m, results, materialized=set(), source_qid="s", index_id="bohrium")
    assert not out.new_contacts and not out.updated_contacts
    c = next(c for c in m.frontier if c.ref["value"] == "777")
    assert c.status == "surveyed"
    assert c.meta["rank"] == 0.1  # untouched


# --------------------------------------------------------------------------- #
# promotion: a pulled paper flips its contact to surveyed                      #
# --------------------------------------------------------------------------- #


def test_promote_materialized_lkm_contact():
    m = ExplorationMap()
    m.frontier.append(
        Contact(
            id="ct_p",
            ref={"kind": "lkm", "value": "888"},
            sources=[{"qid": "s", "edge": "lkm_related"}],
            meta={"paper_id": "888", "title": "T", "rank": 0.3, "lkm_node_ids": ["n"]},
        )
    )
    promoted = promote_materialized_lkm_contacts(m, materialized_paper_ids={"888"}, survey_round=3)
    assert promoted == ["888"]
    c = next(c for c in m.frontier if c.ref["value"] == "888")
    assert c.status == "surveyed"
    # A SurveyRecord keyed by a synthetic lkm:paper qid was recorded.
    rec = m.surveyed["lkm:paper:888"]
    assert rec.survey_round == 3
    assert rec.promoted_from_contact == "ct_p"
    # lkm_origin carries the paper metadata (minus the node-id list).
    assert rec.lkm_origin["paper_id"] == "888"
    assert "lkm_node_ids" not in rec.lkm_origin


def test_promote_ignores_unmatched_and_non_open():
    m = ExplorationMap()
    m.frontier.append(Contact(id="ct_open", ref={"kind": "lkm", "value": "999"}))
    promoted = promote_materialized_lkm_contacts(m, materialized_paper_ids={"000"}, survey_round=1)
    assert promoted == []
    assert m.frontier[0].status == "open"


def test_materialized_paper_ids_from_roots():
    roots = [
        Path("/x/root"),
        Path("/x/.gaia/lkm_packages/free-fall-813135328909983744-gaia"),
        Path("/x/.gaia/lkm_packages/drag_812270081076625408_gaia"),
    ]
    found = materialized_paper_ids_from_roots(roots)
    assert "813135328909983744" in found
    assert "812270081076625408" in found
