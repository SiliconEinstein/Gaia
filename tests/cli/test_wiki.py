"""Tests for gaia wiki Home.md generation."""

from gaia.cli.commands._wiki import generate_wiki_home


def test_wiki_home_has_title_and_index():
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "Claim A.",
                "module": "motivation",
            },
            {
                "id": "github:test_pkg::b",
                "label": "b",
                "type": "setting",
                "content": "Setting B.",
                "module": "motivation",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    md = generate_wiki_home(ir, beliefs_data=None)
    assert "# test_pkg" in md
    assert "| a |" in md
    assert "motivation" in md


def _make_ir(extra_knowledges=None):
    """Return a minimal IR dict, optionally with extra knowledge nodes."""
    knowledges = [
        {
            "id": "github:test_pkg::a",
            "label": "a",
            "type": "claim",
            "content": "Claim A.",
            "module": "motivation",
        },
        {
            "id": "github:test_pkg::b",
            "label": "b",
            "type": "setting",
            "content": "Setting B.",
            "module": "motivation",
        },
    ]
    if extra_knowledges:
        knowledges.extend(extra_knowledges)
    return {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": knowledges,
        "strategies": [],
        "operators": [],
    }


def test_helper_nodes_excluded_from_claim_index():
    """Helper nodes (label starting with __) must not appear in the claim index table."""
    ir = _make_ir(
        extra_knowledges=[
            {
                "id": "github:test_pkg::__helper",
                "label": "__helper",
                "type": "claim",
                "content": "Helper node.",
                "module": "motivation",
            },
        ]
    )
    md = generate_wiki_home(ir, beliefs_data=None)
    assert "__helper" not in md
    # Module count should exclude the helper: 2 real nodes only
    assert "(2 nodes)" in md


def test_belief_values_displayed():
    """When beliefs_data is provided, belief values appear in the table."""
    ir = _make_ir()
    beliefs_data = {
        "beliefs": [
            {"knowledge_id": "github:test_pkg::a", "belief": 0.85},
        ]
    }
    md = generate_wiki_home(ir, beliefs_data=beliefs_data)
    assert "0.85" in md


def test_em_dash_for_missing_beliefs():
    """When no beliefs_data is provided, em-dash appears for every row."""
    ir = _make_ir()
    md = generate_wiki_home(ir, beliefs_data=None)
    assert "\u2014" in md
