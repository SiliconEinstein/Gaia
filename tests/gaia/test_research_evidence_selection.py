"""Tests for selected deep-evidence packets used by research runs."""

from __future__ import annotations

from gaia.engine.research.evidence_selection import build_selected_evidence_artifact


def _landscape() -> dict[str, object]:
    return {
        "kind": "research_landscape",
        "action": "explore.expand",
        "items": [
            {
                "kind": "variable",
                "id": "claim_support",
                "variable_type": "claim",
                "content": "Large-scale simulation reports emergent symmetry.",
                "source": {"paper_id": "P_SUPPORT", "paper_title": "Support paper"},
            },
            {
                "kind": "variable",
                "id": "claim_oppose",
                "variable_type": "claim",
                "content": "Finite-size drift is consistent with weak first-order behavior.",
                "source": {"paper_id": "P_OPPOSE", "paper_title": "Opposition paper"},
            },
            {
                "kind": "variable",
                "id": "claim_background",
                "variable_type": "claim",
                "content": "Background material not matched by focus terms.",
                "source": {"paper_id": "P_BACKGROUND", "paper_title": "Background"},
            },
        ],
        "paper_leads": [
            {
                "paper_id": "P_SUPPORT",
                "title": "Support paper",
                "variable_ids": ["claim_support"],
            },
            {
                "paper_id": "P_OPPOSE",
                "title": "Opposition paper",
                "variable_ids": ["claim_oppose"],
            },
            {
                "paper_id": "P_BACKGROUND",
                "title": "Background",
                "variable_ids": ["claim_background"],
            },
        ],
    }


def test_selected_evidence_prefers_focus_matching_items_and_plans_deep_pull() -> None:
    artifact = build_selected_evidence_artifact(
        focus={"kind": "focus", "id": "weak-first-order", "title": "weak first order"},
        landscapes=[_landscape()],
        max_items=2,
        max_papers=2,
        max_chains=2,
    )

    item_ids = [item["id"] for item in artifact["evidence_packet"]["items"]]
    assert item_ids == ["claim_oppose", "claim_support"]
    assert artifact["evidence_packet"]["paper_leads"] == [
        {
            "paper_id": "P_OPPOSE",
            "title": "Opposition paper",
            "variable_ids": ["claim_oppose"],
            "landscape_index": 0,
        },
        {
            "paper_id": "P_SUPPORT",
            "title": "Support paper",
            "variable_ids": ["claim_support"],
            "landscape_index": 0,
        },
    ]
    assert artifact["materialization_plan"] == {
        "paper_ids": ["P_OPPOSE", "P_SUPPORT"],
        "claim_ids": [],
        "chain_claim_ids": ["claim_oppose", "claim_support"],
    }
    assert artifact["selection"]["items_considered"] == 3
    assert artifact["selection"]["unique_items_considered"] == 3
    assert artifact["selection"]["items_selected"] == 2
    assert artifact["selection_policy"]["mode"] == "fast"
    assert artifact["coverage_audit"]["selected_unique_papers"] == 2
    assert len(artifact["omitted_relevant_evidence"]) == 1


def test_review_selection_uses_wider_paper_diverse_packet_and_audit() -> None:
    items = []
    paper_leads = []
    for index in range(8):
        paper_id = f"P{index}"
        claim_id = f"claim_{index}"
        items.append(
            {
                "kind": "variable",
                "id": claim_id,
                "variable_type": "claim",
                "content": f"Review focus evidence item {index}.",
                "source": {"paper_id": paper_id, "paper_title": f"Paper {index}"},
            }
        )
        paper_leads.append(
            {
                "paper_id": paper_id,
                "title": f"Paper {index}",
                "variable_ids": [claim_id],
            }
        )
    items.append(dict(items[0]))
    landscape = {
        "kind": "research_landscape",
        "action": "explore.expand",
        "items": items,
        "paper_leads": paper_leads,
    }

    artifact = build_selected_evidence_artifact(
        focus={
            "kind": "focus",
            "id": "review-focus",
            "title": "review focus",
            "evidence_refs": [
                {"kind": "variable", "id": "claim_0"},
                {"kind": "paper", "id": "P3"},
            ],
        },
        landscapes=[landscape],
        selection_mode="review",
        max_items=5,
        max_papers=4,
        max_chains=4,
        max_omitted=2,
    )

    packet = artifact["evidence_packet"]
    selected_papers = {
        item["source"]["paper_id"]
        for item in packet["items"]
        if isinstance(item.get("source"), dict)
    }
    assert artifact["selection_policy"] == {
        "mode": "review",
        "max_items": 5,
        "max_papers": 4,
        "max_chains": 4,
        "max_omitted": 2,
    }
    assert artifact["selection"]["items_considered"] == 9
    assert artifact["selection"]["unique_items_considered"] == 8
    assert artifact["selection"]["duplicate_items_considered"] == 1
    assert artifact["selection"]["items_selected"] == 5
    assert len(selected_papers) == 5
    assert artifact["coverage_audit"]["focus_refs_total"] == 2
    assert artifact["coverage_audit"]["focus_refs_selected"] == 2
    assert len(artifact["omitted_relevant_evidence"]) == 2
