"""Unit tests for neutral paper-level landscape staging."""

from __future__ import annotations

from typing import Any

from gaia.lkm_explorer.engine.landscape import LandscapeBatch, build_landscape
from gaia.lkm_explorer.engine.state import Contact, ExplorationMap


def _search(query: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "query": {"text": query, "provider": "lkm", "kind": "knowledge"},
        "results": rows,
    }


def _row(
    paper_id: str,
    node_id: str,
    rank: float,
    *,
    title: str | None = None,
    qid: str | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "title": title,
        "gaia": {"qid": qid},
        "source": {"paper_id": paper_id, "index_id": "bohrium"},
        "rank": {"score": rank},
    }


def test_landscape_dedupes_paper_leads_across_query_batches():
    landscape = build_landscape(
        [
            LandscapeBatch(
                _search(
                    "seed query",
                    [
                        _row("P1", "n1", 0.2, title="Paper One"),
                        _row("P2", "n2", 0.5, title="Paper Two"),
                    ],
                ),
                source_qid="example:pkg::seed",
                path="a.json",
            ),
            LandscapeBatch(
                _search(
                    "alternate query",
                    [
                        _row("P1", "n3", 0.9, title="Paper One"),
                        _row("P3", "n4", 0.1, title="Paper Three"),
                    ],
                ),
                source_qid="example:pkg::seed",
                path="b.json",
            ),
        ],
        materialized=set(),
    )

    payload = landscape.to_dict()
    assert payload["kind"] == "exploration_landscape"
    assert payload["stats"] == {
        "query_batches": 2,
        "raw_results": 4,
        "paper_leads": 3,
    }
    assert payload["recommended_pull_order"] == ["P1", "P2", "P3"]

    p1 = payload["paper_leads"][0]
    assert p1["paper_id"] == "P1"
    assert p1["best_rank"] == 0.9
    assert p1["queries"] == ["seed query", "alternate query"]
    assert p1["source_qids"] == ["example:pkg::seed"]
    assert set(p1["lkm_node_ids"]) == {"n1", "n3"}
    assert p1["result_count"] == 2


def test_landscape_skips_materialized_and_annotates_existing_contacts():
    exploration_map = ExplorationMap()
    exploration_map.frontier.append(
        Contact(
            id="ct_p2",
            ref={"kind": "lkm", "value": "P2"},
            status="open",
            meta={"paper_id": "P2"},
        )
    )

    landscape = build_landscape(
        [
            LandscapeBatch(
                _search(
                    "q",
                    [
                        _row("P1", "n1", 0.8, qid="example:pkg::already"),
                        _row("P2", "n2", 0.7),
                        _row("P3", "n3", 0.6),
                    ],
                )
            )
        ],
        materialized=set(),
        materialized_paper_ids={"P3"},
        exploration_map=exploration_map,
    )

    payload = landscape.to_dict()
    assert [lead["paper_id"] for lead in payload["paper_leads"]] == ["P2"]
    assert payload["paper_leads"][0]["existing_contact_id"] == "ct_p2"
    assert payload["paper_leads"][0]["existing_contact_status"] == "open"
