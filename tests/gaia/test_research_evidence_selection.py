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
    assert artifact["selection"]["items_selected"] == 2
