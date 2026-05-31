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


def _lkm_contacts(m: ExplorationMap) -> list[Contact]:
    return [c for c in m.frontier if c.ref.get("kind") == "lkm"]


# --------------------------------------------------------------------------- #
# basic ingestion: unmaterialized papers become lkm_related contacts          #
# --------------------------------------------------------------------------- #


def test_observe_records_unmaterialized_papers_as_contacts():
    m = ExplorationMap(seeds=[{"kind": "claim", "qid": "example:p::seed"}])
    results = _load_fixture()
    out = observe_lkm_results(
        m, results, materialized=set(), source_qid="example:p::seed", query="free fall"
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


def test_observe_skips_result_with_resolved_gaia_qid():
    # A result whose gaia.qid is set is already in the IR -> NOT a contact.
    m = ExplorationMap()
    results = {
        "results": [
            {
                "id": "lkm:bohrium:gcn_already",
                "gaia": {"qid": "example:p::already"},
                "source": {"paper_id": "111111", "index_id": "bohrium"},
                "rank": {"score": 0.5},
            },
            {
                "id": "lkm:bohrium:gcn_fresh",
                "gaia": {"qid": None},
                "source": {"paper_id": "222222", "index_id": "bohrium"},
                "rank": {"score": 0.4},
            },
        ]
    }
    observe_lkm_results(m, results, materialized=set(), source_qid="s")
    values = {c.ref["value"] for c in _lkm_contacts(m)}
    assert values == {"222222"}, "only the unresolved (fresh) paper is a contact"


def test_observe_skips_already_pulled_paper_by_id():
    # A paper already pulled into the joint view (its id in materialized_paper_ids)
    # is not re-added.
    m = ExplorationMap()
    results = {
        "results": [
            {
                "id": "lkm:bohrium:gcn_pulled",
                "gaia": {"qid": None},
                "source": {"paper_id": "333", "index_id": "bohrium"},
                "rank": {"score": 0.3},
            },
            {
                "id": "lkm:bohrium:gcn_new",
                "gaia": {"qid": None},
                "source": {"paper_id": "444", "index_id": "bohrium"},
                "rank": {"score": 0.3},
            },
        ]
    }
    observe_lkm_results(
        m, results, materialized=set(), materialized_paper_ids={"333"}, source_qid="s"
    )
    assert {c.ref["value"] for c in _lkm_contacts(m)} == {"444"}


# --------------------------------------------------------------------------- #
# de-dup / merge by paper_id                                                  #
# --------------------------------------------------------------------------- #


def test_observe_dedups_two_results_one_paper():
    # Two result rows pointing at the SAME paper_id -> one contact, union node
    # ids, MAX rank.
    m = ExplorationMap()
    results = {
        "results": [
            {
                "id": "lkm:bohrium:gcn_a",
                "gaia": {"qid": None},
                "title": "row a",
                "source": {"paper_id": "555", "index_id": "bohrium", "doi": "10.1/x"},
                "rank": {"score": 0.2},
            },
            {
                "id": "lkm:bohrium:gcn_b",
                "gaia": {"qid": None},
                "title": "row b",
                "source": {"paper_id": "555", "index_id": "bohrium"},
                "rank": {"score": 0.7},
            },
        ]
    }
    observe_lkm_results(m, results, materialized=set(), source_qid="s")
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
    first = {
        "results": [
            {
                "id": "lkm:bohrium:gcn_first",
                "gaia": {"qid": None},
                "source": {"paper_id": "666", "index_id": "bohrium"},
                "rank": {"score": 0.1},
            }
        ]
    }
    second = {
        "results": [
            {
                "id": "lkm:bohrium:gcn_second",
                "gaia": {"qid": None},
                "source": {"paper_id": "666", "index_id": "bohrium"},
                "rank": {"score": 0.9},
            }
        ]
    }
    observe_lkm_results(m, first, materialized=set(), source_qid="src_a", query="q1")
    out2 = observe_lkm_results(m, second, materialized=set(), source_qid="src_b", query="q2")

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
    results = {
        "results": [
            {
                "id": "lkm:bohrium:gcn_again",
                "gaia": {"qid": None},
                "source": {"paper_id": "777", "index_id": "bohrium"},
                "rank": {"score": 0.99},
            }
        ]
    }
    out = observe_lkm_results(m, results, materialized=set(), source_qid="s")
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
