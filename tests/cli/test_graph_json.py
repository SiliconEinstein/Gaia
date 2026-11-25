"""Tests for graph.json generator (v2: strategy/operator as nodes)."""

from __future__ import annotations

import json

import pytest

from gaia.cli.commands._graph_json import generate_graph_json

pytestmark = pytest.mark.pr_gate


def _make_ir(
    knowledges: list[dict] | None = None,
    strategies: list[dict] | None = None,
    operators: list[dict] | None = None,
    module_order: list[str] | None = None,
) -> dict:
    return {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": knowledges or [],
        "strategies": strategies or [],
        "operators": operators or [],
        "module_order": module_order or [],
    }


def test_knowledge_nodes_emitted():
    ir = _make_ir(
        knowledges=[
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "title": "Claim A",
                "type": "claim",
                "content": "Claim A.",
                "module": "m1",
                "metadata": {"figure": "fig.png"},
            },
        ],
        module_order=["m1"],
    )
    beliefs = {"beliefs": [{"knowledge_id": "github:test_pkg::a", "belief": 0.9, "label": "a"}]}
    params = {"priors": [{"knowledge_id": "github:test_pkg::a", "value": 0.7}]}
    exported = {"github:test_pkg::a"}
    data = json.loads(
        generate_graph_json(ir, beliefs_data=beliefs, param_data=params, exported_ids=exported)
    )
    nodes = [n for n in data["nodes"] if n["type"] != "strategy"]
    assert len(nodes) == 1
    n = nodes[0]
    assert n["id"] == "github:test_pkg::a"
    assert n["belief"] == 0.9
    assert n["prior"] == 0.7
    assert n["exported"] is True
    assert n["module"] == "m1"


def test_strategy_becomes_node_with_role_edges():
    ir = _make_ir(
        knowledges=[
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "m1",
            },
            {
                "id": "github:test_pkg::b",
                "label": "b",
                "type": "claim",
                "content": "B.",
                "module": "m1",
            },
        ],
        strategies=[
            {
                "type": "deduction",
                "premises": ["github:test_pkg::a"],
                "background": [],
                "conclusion": "github:test_pkg::b",
                "reason": "A implies B.",
            },
        ],
        module_order=["m1"],
    )
    data = json.loads(generate_graph_json(ir))
    strat_nodes = [n for n in data["nodes"] if n["type"] == "strategy"]
    assert len(strat_nodes) == 1
    sn = strat_nodes[0]
    assert sn["strategy_type"] == "deduction"
    assert sn["module"] == "m1"
    premise_edges = [e for e in data["edges"] if e["role"] == "premise"]
    concl_edges = [e for e in data["edges"] if e["role"] == "conclusion"]
    assert len(premise_edges) == 1
    assert premise_edges[0]["source"] == "github:test_pkg::a"
    assert premise_edges[0]["target"] == sn["id"]
    assert len(concl_edges) == 1
    assert concl_edges[0]["source"] == sn["id"]
    assert concl_edges[0]["target"] == "github:test_pkg::b"


def test_background_edges_have_background_role():
    ir = _make_ir(
        knowledges=[
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "m1",
            },
            {
                "id": "github:test_pkg::bg",
                "label": "bg",
                "type": "setting",
                "content": "BG.",
                "module": "m1",
            },
            {
                "id": "github:test_pkg::b",
                "label": "b",
                "type": "claim",
                "content": "B.",
                "module": "m1",
            },
        ],
        strategies=[
            {
                "type": "deduction",
                "premises": ["github:test_pkg::a"],
                "background": ["github:test_pkg::bg"],
                "conclusion": "github:test_pkg::b",
                "reason": "",
            },
        ],
        module_order=["m1"],
    )
    data = json.loads(generate_graph_json(ir))
    bg_edges = [e for e in data["edges"] if e["role"] == "background"]
    assert len(bg_edges) == 1
    assert bg_edges[0]["source"] == "github:test_pkg::bg"


def test_operator_becomes_node():
    ir = _make_ir(
        knowledges=[
            {
                "id": "github:test_pkg::x",
                "label": "x",
                "type": "claim",
                "content": "X.",
                "module": "m1",
            },
            {
                "id": "github:test_pkg::not_x",
                "label": "not_x",
                "type": "claim",
                "content": "NOT X.",
                "module": "m1",
            },
        ],
        operators=[
            {
                "operator": "NOT",
                "variables": ["github:test_pkg::x"],
                "conclusion": "github:test_pkg::not_x",
                "reason": "negation",
            },
        ],
        module_order=["m1"],
    )
    data = json.loads(generate_graph_json(ir))
    op_nodes = [n for n in data["nodes"] if n["type"] == "operator"]
    assert len(op_nodes) == 1
    assert op_nodes[0]["operator_type"] == "NOT"
    var_edges = [e for e in data["edges"] if e["role"] == "variable"]
    concl_edges = [e for e in data["edges"] if e["role"] == "conclusion"]
    assert len(var_edges) == 1
    assert len(concl_edges) == 1


def test_modules_array():
    ir = _make_ir(
        knowledges=[
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "m1",
            },
            {
                "id": "github:test_pkg::b",
                "label": "b",
                "type": "claim",
                "content": "B.",
                "module": "m1",
            },
            {
                "id": "github:test_pkg::c",
                "label": "c",
                "type": "claim",
                "content": "C.",
                "module": "m2",
            },
        ],
        strategies=[
            {
                "type": "deduction",
                "premises": ["github:test_pkg::a"],
                "background": [],
                "conclusion": "github:test_pkg::b",
                "reason": "",
            },
        ],
        module_order=["m1", "m2"],
    )
    data = json.loads(generate_graph_json(ir))
    modules = data["modules"]
    assert len(modules) == 2
    m1 = next(m for m in modules if m["id"] == "m1")
    assert m1["order"] == 0
    assert m1["node_count"] == 2
    assert m1["strategy_count"] == 1
    m2 = next(m for m in modules if m["id"] == "m2")
    assert m2["order"] == 1
    assert m2["node_count"] == 1
    assert m2["strategy_count"] == 0


def test_cross_module_edges():
    ir = _make_ir(
        knowledges=[
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "m1",
            },
            {
                "id": "github:test_pkg::b",
                "label": "b",
                "type": "claim",
                "content": "B.",
                "module": "m2",
            },
        ],
        strategies=[
            {
                "type": "deduction",
                "premises": ["github:test_pkg::a"],
                "background": [],
                "conclusion": "github:test_pkg::b",
                "reason": "",
            },
        ],
        module_order=["m1", "m2"],
    )
    data = json.loads(generate_graph_json(ir))
    xmod = data["cross_module_edges"]
    assert len(xmod) == 1
    assert xmod[0]["from_module"] == "m1"
    assert xmod[0]["to_module"] == "m2"
    assert xmod[0]["count"] == 1


def test_helper_nodes_filtered():
    ir = _make_ir(
        knowledges=[
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "m1",
            },
            {
                "id": "github:test_pkg::__helper",
                "label": "__helper",
                "type": "claim",
                "content": "Helper.",
                "module": "m1",
            },
            {
                "id": "github:test_pkg::_anon_001",
                "label": "_anon_001",
                "type": "claim",
                "content": "Anonymous helper.",
                "module": "m1",
            },
        ],
        module_order=["m1"],
    )
    data = json.loads(generate_graph_json(ir))
    knowledge_nodes = [n for n in data["nodes"] if n["type"] not in ("strategy", "operator")]
    assert len(knowledge_nodes) == 1
    assert knowledge_nodes[0]["label"] == "a"


def test_no_beliefs_or_params():
    ir = _make_ir(
        knowledges=[
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "m1",
            },
        ],
        module_order=["m1"],
    )
    data = json.loads(generate_graph_json(ir))
    assert data["nodes"][0]["belief"] is None
    assert data["nodes"][0]["prior"] is None
    assert data["nodes"][0]["exported"] is False


def _two_claim_ir(strategy: dict) -> dict:
    """IR with claims a -> (strategy) -> b, for strategy-field tests."""
    return _make_ir(
        knowledges=[
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "m1",
            },
            {
                "id": "github:test_pkg::b",
                "label": "b",
                "type": "claim",
                "content": "B.",
                "module": "m1",
            },
        ],
        strategies=[
            {
                "type": "infer",
                "premises": ["github:test_pkg::a"],
                "conclusion": "github:test_pkg::b",
                **strategy,
            },
        ],
        module_order=["m1"],
    )


def _only_strategy_node(data: dict) -> dict:
    (node,) = [n for n in data["nodes"] if n["type"] == "strategy"]
    return node


def test_strategy_reason_joined_from_steps():
    """Compiled IR stores the author's reasoning at steps[i].reasoning."""
    ir = _two_claim_ir({"steps": [{"reasoning": "First step."}, {"reasoning": "Second step."}]})
    node = _only_strategy_node(json.loads(generate_graph_json(ir)))
    assert node["reason"] == "First step.\n\nSecond step."


def test_strategy_reason_from_metadata_reason():
    """Plain-string DSL reason= compiles into metadata['reason']."""
    ir = _two_claim_ir({"metadata": {"reason": "Plain-string reason."}})
    node = _only_strategy_node(json.loads(generate_graph_json(ir)))
    assert node["reason"] == "Plain-string reason."


def test_strategy_reason_steps_win_over_metadata():
    ir = _two_claim_ir(
        {
            "steps": [{"reasoning": "Step text."}],
            "metadata": {"reason": "Metadata text."},
        }
    )
    node = _only_strategy_node(json.loads(generate_graph_json(ir)))
    assert node["reason"] == "Step text."


def test_strategy_effect_from_conditional_probabilities():
    """Single-premise infer CPT [p(c|not p), p(c|p)] yields a signed effect."""
    ir = _two_claim_ir({"conditional_probabilities": [0.9, 0.09]})
    data = json.loads(generate_graph_json(ir))
    node = _only_strategy_node(data)
    assert node["conditional_probabilities"] == [0.9, 0.09]
    assert node["effect"] == pytest.approx(-0.81)
    (conclusion_edge,) = [e for e in data["edges"] if e["role"] == "conclusion"]
    assert conclusion_edge["effect"] == pytest.approx(-0.81)


def test_strategy_effect_none_without_cpt():
    """Strategy forms without an inline CPT stay unscored, not guessed."""
    ir = _two_claim_ir({"steps": [{"reasoning": "Some reasoning."}]})
    data = json.loads(generate_graph_json(ir))
    node = _only_strategy_node(data)
    assert node["effect"] is None
    assert node["conditional_probabilities"] is None
    (conclusion_edge,) = [e for e in data["edges"] if e["role"] == "conclusion"]
    assert conclusion_edge["effect"] is None


def test_strategy_effect_multi_given_gated_cpt():
    """The gated multi-premise CPT keeps the effect contrast in its last two slots.

    ``infer(evidence, hypothesis=..., given=[...])`` compiles to a 2^(k+1)-entry
    CPT whose only non-MaxEnt slots are ``gate_mask`` (= index -2, all givens
    true / premise false) and ``gate_mask|1`` (= index -1, all true) — see
    ``_infer_conditional_probabilities``. Locks that ``cp[-1] - cp[-2]`` stays
    the p(e|h) - p(e|not h) contrast at every premise count.
    """
    ir = _make_ir(
        knowledges=[
            {
                "id": f"github:test_pkg::{name}",
                "label": name,
                "type": "claim",
                "content": f"{name}.",
                "module": "m1",
            }
            # Neutral names on purpose: the compiler orders premises as
            # [hypothesis, *givens] (bit 0 = hypothesis), and the effect
            # arithmetic below is order-insensitive either way.
            for name in ("premise_a", "premise_b", "conclusion_c")
        ],
        strategies=[
            {
                "type": "infer",
                "premises": ["github:test_pkg::premise_a", "github:test_pkg::premise_b"],
                "conclusion": "github:test_pkg::conclusion_c",
                # given_count=1 layout: [0.5, 0.5, p(e|not h), p(e|h)]
                "conditional_probabilities": [0.5, 0.5, 0.25, 0.75],
            },
        ],
        module_order=["m1"],
    )
    data = json.loads(generate_graph_json(ir))
    node = _only_strategy_node(data)
    assert node["effect"] == pytest.approx(0.5)
    (conclusion_edge,) = [e for e in data["edges"] if e["role"] == "conclusion"]
    assert conclusion_edge["effect"] == pytest.approx(0.5)
