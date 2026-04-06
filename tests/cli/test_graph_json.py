"""Tests for graph.json generator."""

from __future__ import annotations

import json

from gaia.cli.commands._graph_json import generate_graph_json


def test_graph_json_has_nodes_and_edges():
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
                "metadata": {"figure": "artifacts/fig1.png"},
            },
            {
                "id": "github:test_pkg::b",
                "label": "b",
                "type": "claim",
                "content": "Claim B.",
                "module": "motivation",
            },
        ],
        "strategies": [
            {
                "type": "deduction",
                "premises": ["github:test_pkg::a"],
                "conclusion": "github:test_pkg::b",
                "reason": "A implies B.",
            },
        ],
        "operators": [],
    }
    beliefs = {
        "beliefs": [
            {"knowledge_id": "github:test_pkg::a", "belief": 0.9, "label": "a"},
            {"knowledge_id": "github:test_pkg::b", "belief": 0.8, "label": "b"},
        ]
    }
    exported = {"github:test_pkg::b"}
    result = generate_graph_json(ir, beliefs_data=beliefs, exported_ids=exported)
    data = json.loads(result)
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    node_b = next(n for n in data["nodes"] if n["label"] == "b")
    assert node_b["belief"] == 0.8
    assert node_b["exported"] is True
    edge = data["edges"][0]
    assert edge["strategy_type"] == "deduction"


def test_operator_edges():
    """Operator entries produce edges with operator_type."""
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::x",
                "label": "x",
                "type": "claim",
                "content": "X.",
                "module": "m",
            },
            {
                "id": "github:test_pkg::not_x",
                "label": "not_x",
                "type": "claim",
                "content": "NOT X.",
                "module": "m",
            },
        ],
        "strategies": [],
        "operators": [
            {
                "operator": "NOT",
                "variables": ["github:test_pkg::x"],
                "conclusion": "github:test_pkg::not_x",
                "reason": "negation of x",
            },
        ],
    }
    result = generate_graph_json(ir)
    data = json.loads(result)
    assert len(data["edges"]) == 1
    edge = data["edges"][0]
    assert edge["type"] == "operator"
    assert edge["operator_type"] == "NOT"
    assert edge["source"] == "github:test_pkg::x"
    assert edge["target"] == "github:test_pkg::not_x"


def test_helper_node_filtering():
    """Nodes with labels starting with __ are filtered out."""
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "Claim A.",
                "module": "m",
            },
            {
                "id": "github:test_pkg::__helper",
                "label": "__helper",
                "type": "claim",
                "content": "Helper node.",
                "module": "m",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    result = generate_graph_json(ir)
    data = json.loads(result)
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["label"] == "a"


def test_param_data_priors():
    """Prior values from param_data are included in nodes."""
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "Claim A.",
                "module": "m",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    param_data = {"priors": [{"knowledge_id": "github:test_pkg::a", "value": 0.7}]}
    result = generate_graph_json(ir, param_data=param_data)
    data = json.loads(result)
    assert data["nodes"][0]["prior"] == 0.7


def test_no_beliefs_or_params():
    """generate_graph_json works with no beliefs or param data."""
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "Claim A.",
                "module": "m",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    result = generate_graph_json(ir)
    data = json.loads(result)
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["belief"] is None
    assert data["nodes"][0]["prior"] is None
    assert data["nodes"][0]["exported"] is False
