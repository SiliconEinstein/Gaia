"""Unit tests for package-native research landscape utilities."""

from __future__ import annotations

from typing import Any

from gaia.engine.research.landscape import ScanBatch, build_research_landscape


def _search(query: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "query": {"text": query, "provider": "lkm", "kind": "knowledge"},
        "results": rows,
    }


def _row(
    paper_id: str,
    variable_id: str,
    score: float,
    *,
    title: str,
    qid: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"lkm:bohrium:{variable_id}",
        "kind": "claim",
        "title": f"Claim from {title}",
        "content": f"Claim content from {title}.",
        "gaia": {"qid": qid},
        "source": {
            "provider_id": variable_id,
            "paper_id": paper_id,
            "paper_title": title,
            "doi": "10.1/example",
            "index_id": "bohrium",
        },
        "rank": {"score": score},
    }


def test_research_landscape_dedupes_leads_and_preserves_provenance() -> None:
    payload = build_research_landscape(
        [
            ScanBatch(
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
            ScanBatch(
                _search(
                    "alternate query",
                    [
                        _row("P1", "n3", 0.9, title="Paper One"),
                        _row("P3", "n4", 0.1, title="Paper Three"),
                    ],
                ),
                source_qid="example:pkg::other",
                path="b.json",
            ),
        ]
    )

    assert payload["kind"] == "research_landscape"
    assert payload["stats"] == {
        "query_batches": 2,
        "raw_results": 4,
        "paper_leads": 3,
    }
    assert [lead["paper_id"] for lead in payload["paper_leads"]] == ["P1", "P2", "P3"]
    p1 = payload["paper_leads"][0]
    assert p1["best_rank"] == 0.9
    assert p1["queries"] == ["seed query", "alternate query"]
    assert p1["source_qids"] == ["example:pkg::seed", "example:pkg::other"]
    assert p1["variable_ids"] == ["n1", "n3"]
    assert p1["result_count"] == 2
    assert "retrieved_snippets" not in payload
    assert payload["items"][0]["item_id"] == "n1"
    assert payload["items"][0]["display_index"] == 0
    assert payload["items"][0]["kind"] == "variable"
    assert payload["items"][0]["id"] == "n1"
    assert payload["items"][0]["variable_type"] == "claim"
    assert payload["items"][0]["content"] == "Claim content from Paper One."
    assert payload["items"][0]["source"]["paper_id"] == "P1"
    assert payload["items"][0]["provenance"]["result_id"] == "lkm:bohrium:n1"
    assert payload["query_provenance"][0]["path"] == "a.json"
    assert payload["pull_candidates"][0]["paper_id"] == "P1"
    assert payload["pull_candidates"][0]["evidence_refs"] == [
        {"kind": "variable", "id": "n1"},
        {"kind": "variable", "id": "n3"},
    ]


def test_research_landscape_skips_materialized_and_pulled_papers() -> None:
    payload = build_research_landscape(
        [
            ScanBatch(
                _search(
                    "q",
                    [
                        _row("P1", "n1", 0.8, title="Already materialized", qid="pkg::q1"),
                        _row("P2", "n2", 0.7, title="Pulled Paper"),
                        _row("P3", "n3", 0.6, title="Fresh Paper"),
                    ],
                )
            )
        ],
        materialized_paper_ids={"P2"},
    )

    assert [lead["paper_id"] for lead in payload["paper_leads"]] == ["P3"]
    assert payload["pull_candidates"][0]["command"] == (
        "gaia pkg add --lkm-index bohrium --lkm-paper P3"
    )
