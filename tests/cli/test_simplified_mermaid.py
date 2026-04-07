"""Tests for simplified Mermaid node selection and rendering."""

from __future__ import annotations

from gaia.cli.commands._simplified_mermaid import (
    render_simplified_mermaid,
    select_simplified_nodes,
)


# ── Task 6: select_simplified_nodes ──


def test_exported_always_included():
    beliefs = {"a": 0.9, "b": 0.5, "c": 0.8}
    priors = {"a": 0.9, "b": 0.9}  # b has big delta (0.9 -> 0.5)
    exported = {"c"}
    selected = select_simplified_nodes(beliefs, priors, exported, max_nodes=2)
    assert "c" in selected
    assert "b" in selected  # highest |belief - prior| = 0.4


def test_max_nodes_respected():
    beliefs = {f"n{i}": 0.5 for i in range(20)}
    priors = {f"n{i}": 0.5 for i in range(20)}
    exported = {f"n{i}" for i in range(5)}
    selected = select_simplified_nodes(beliefs, priors, exported, max_nodes=15)
    assert len(selected) <= 15
    for i in range(5):
        assert f"n{i}" in selected


def test_exported_exceed_max_nodes():
    """When exported ids exceed max_nodes, all exported are still included."""
    beliefs = {f"n{i}": 0.9 for i in range(10)}
    priors = {f"n{i}": 0.5 for i in range(10)}
    exported = {f"n{i}" for i in range(10)}
    selected = select_simplified_nodes(beliefs, priors, exported, max_nodes=5)
    # All exported must be included even if > max_nodes
    for i in range(10):
        assert f"n{i}" in selected


def test_highest_delta_selected():
    """Non-exported nodes are ranked by |belief - prior|."""
    beliefs = {"a": 0.5, "b": 0.9, "c": 0.6, "d": 0.95}
    priors = {"a": 0.5, "b": 0.5, "c": 0.5, "d": 0.5}
    exported = {"a"}
    # a is exported (delta=0), remaining slots=1 → d (delta=0.45) wins over b (0.4)
    selected = select_simplified_nodes(beliefs, priors, exported, max_nodes=2)
    assert "a" in selected
    assert "d" in selected


def test_default_prior_for_missing():
    """Nodes missing from priors dict default to 0.5."""
    beliefs = {"a": 0.9}
    priors: dict[str, float] = {}  # missing → default 0.5
    exported: set[str] = set()
    selected = select_simplified_nodes(beliefs, priors, exported, max_nodes=5)
    assert "a" in selected


# ── Task 7: render_simplified_mermaid ──


def test_render_simplified_mermaid_shows_prior_and_belief():
    ir = {
        "knowledges": [
            {
                "id": "a",
                "label": "hypothesis",
                "type": "claim",
                "content": "H.",
                "title": "Hypothesis",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    beliefs = {"a": 0.85}
    priors = {"a": 0.5}
    exported = {"a"}
    mermaid = render_simplified_mermaid(ir, beliefs, priors, exported)
    assert "0.50" in mermaid and "0.85" in mermaid  # prior → belief shown
    assert "⭐" in mermaid or "★" in mermaid  # exported marker


def test_render_simplified_mermaid_non_exported_no_star():
    ir = {
        "knowledges": [
            {"id": "a", "label": "obs", "type": "setting", "content": "Observation."},
        ],
        "strategies": [],
        "operators": [],
    }
    beliefs = {"a": 0.7}
    priors = {"a": 0.5}
    exported: set[str] = set()
    mermaid = render_simplified_mermaid(ir, beliefs, priors, exported)
    assert "0.50" in mermaid and "0.70" in mermaid
    assert "⭐" not in mermaid and "★" not in mermaid


def test_render_simplified_mermaid_includes_strategy_edges():
    ir = {
        "knowledges": [
            {"id": "a", "label": "premise_a", "type": "claim", "content": "P."},
            {"id": "b", "label": "conclusion_b", "type": "claim", "content": "C."},
        ],
        "strategies": [
            {"type": "deduction", "premises": ["a"], "conclusion": "b"},
        ],
        "operators": [],
    }
    beliefs = {"a": 0.9, "b": 0.85}
    priors = {"a": 0.9, "b": 0.5}
    exported = {"a", "b"}
    mermaid = render_simplified_mermaid(ir, beliefs, priors, exported)
    assert "premise_a" in mermaid
    assert "conclusion_b" in mermaid
    assert "-->" in mermaid


def test_render_simplified_mermaid_includes_operator_edges():
    ir = {
        "knowledges": [
            {"id": "a", "label": "var_a", "type": "claim", "content": "A."},
            {"id": "b", "label": "var_b", "type": "claim", "content": "B."},
        ],
        "strategies": [],
        "operators": [
            {"operator": "contradiction", "variables": ["a", "b"], "conclusion": None},
        ],
    }
    beliefs = {"a": 0.9, "b": 0.1}
    priors = {"a": 0.5, "b": 0.5}
    exported = {"a", "b"}
    mermaid = render_simplified_mermaid(ir, beliefs, priors, exported)
    assert "var_a" in mermaid
    assert "var_b" in mermaid
    # contradiction → undirected edges
    assert "---" in mermaid or "-->" in mermaid


def test_render_simplified_mermaid_graph_td():
    ir = {
        "knowledges": [
            {"id": "a", "label": "node_a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    beliefs = {"a": 0.8}
    priors = {"a": 0.5}
    exported = {"a"}
    mermaid = render_simplified_mermaid(ir, beliefs, priors, exported)
    assert "graph TD" in mermaid
    assert "```mermaid" in mermaid
