"""Tests for gaia wiki page generation."""

from gaia.cli.commands._wiki import (
    generate_all_wiki,
    generate_wiki_home,
    generate_wiki_inference,
    generate_wiki_module,
)


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


def test_wiki_module_page_has_structured_claims():
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::hyp",
                "label": "hyp",
                "type": "claim",
                "content": "Hypothesis.",
                "module": "motivation",
                "metadata": {"figure": "artifacts/fig1.png"},
            },
        ],
        "strategies": [
            {
                "type": "deduction",
                "premises": ["github:test_pkg::a"],
                "conclusion": "github:test_pkg::hyp",
                "reason": "Derived from A.",
            },
        ],
        "operators": [],
    }
    beliefs_data = {
        "beliefs": [
            {"knowledge_id": "github:test_pkg::hyp", "belief": 0.85, "label": "hyp"},
        ]
    }
    param_data = {
        "priors": [
            {"knowledge_id": "github:test_pkg::hyp", "value": 0.5},
        ]
    }
    md = generate_wiki_module(ir, "motivation", beliefs_data=beliefs_data, param_data=param_data)
    assert "# Module: motivation" in md
    assert "### hyp" in md
    assert "**QID:**" in md
    assert "**Content:** Hypothesis." in md
    assert "**Prior:** 0.50" in md
    assert "**Belief:** 0.85" in md
    assert "**Derived from:** deduction" in md
    assert "**Reasoning:** Derived from A." in md


def test_wiki_inference_results():
    ir = {
        "knowledges": [
            {"id": "github:test_pkg::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
        "package_name": "test_pkg",
        "namespace": "github",
    }
    beliefs_data = {
        "beliefs": [{"knowledge_id": "github:test_pkg::a", "belief": 0.9, "label": "a"}],
        "diagnostics": {"converged": True, "iterations_run": 2},
    }
    param_data = {"priors": [{"knowledge_id": "github:test_pkg::a", "value": 0.8}]}
    md = generate_wiki_inference(ir, beliefs_data, param_data)
    assert "Converged" in md
    assert "0.80" in md  # prior
    assert "0.90" in md  # belief


def test_generate_all_wiki_returns_dict_of_pages():
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "motivation",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    pages = generate_all_wiki(ir, beliefs_data=None, param_data=None)
    assert "Home.md" in pages
    assert any(k.startswith("Module-") for k in pages)
