"""Tests for docs/detailed-reasoning.md generator (legacy gaia compile --readme/--module-graphs)."""

from typer.testing import CliRunner

from gaia.cli.commands._detailed_reasoning import (
    _render_overview_graph,
    generate_detailed_reasoning,
    render_knowledge_nodes,
    render_mermaid,
    topo_layers,
)
from gaia.cli.main import app

runner = CliRunner()


# ── topo_layers ──


def test_topo_layers_linear_chain():
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "C."},
        ],
        "strategies": [
            {"premises": ["ns:p::a"], "conclusion": "ns:p::b", "type": "noisy_and"},
            {"premises": ["ns:p::b"], "conclusion": "ns:p::c", "type": "noisy_and"},
        ],
        "operators": [],
    }
    layers = topo_layers(ir)
    assert layers["ns:p::a"] == 0
    assert layers["ns:p::b"] == 1
    assert layers["ns:p::c"] == 2


def test_topo_layers_independent_premises():
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "C."},
        ],
        "strategies": [
            {"premises": ["ns:p::a", "ns:p::b"], "conclusion": "ns:p::c", "type": "noisy_and"},
        ],
        "operators": [],
    }
    layers = topo_layers(ir)
    assert layers["ns:p::a"] == 0
    assert layers["ns:p::b"] == 0
    assert layers["ns:p::c"] == 1


def test_topo_layers_settings_always_layer_0():
    ir = {
        "knowledges": [
            {"id": "ns:p::s", "label": "s", "type": "setting", "content": "S."},
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    layers = topo_layers(ir)
    assert layers["ns:p::s"] == 0
    assert layers["ns:p::a"] == 0


# ── render_mermaid ──


def test_mermaid_basic():
    ir = {
        "knowledges": [
            {"id": "ns:p::obs", "label": "obs", "type": "claim", "content": "Obs."},
            {"id": "ns:p::hyp", "label": "hyp", "type": "claim", "content": "Hyp."},
            {"id": "ns:p::env", "label": "env", "type": "setting", "content": "Env."},
        ],
        "strategies": [
            {
                "premises": ["ns:p::obs"],
                "conclusion": "ns:p::hyp",
                "type": "noisy_and",
                "metadata": {"reason": "because"},
            },
        ],
        "operators": [],
    }
    md = render_mermaid(ir)
    assert "graph TD" in md
    assert "obs[" in md
    assert "hyp[" in md
    assert "env[" in md
    # Strategy rendered as intermediate stadium node
    assert '(["noisy_and"])' in md
    assert "obs --> strat_0" in md
    assert "strat_0 --> hyp" in md
    assert ":::weak" in md  # noisy_and is a weakpoint
    assert ":::setting" in md


def test_mermaid_hides_helper_claims():
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::__helper_abc", "label": "__helper_abc", "type": "claim", "content": "h"},
        ],
        "strategies": [],
        "operators": [],
    }
    md = render_mermaid(ir)
    assert "__helper_abc" not in md
    assert "a[" in md


def test_mermaid_with_beliefs():
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    md = render_mermaid(ir, beliefs={"ns:p::a": 0.85})
    assert "0.85" in md


# ── render_knowledge_nodes ──


def test_render_knowledge_nodes_narrative_order():
    ir = {
        "knowledges": [
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "Conclusion."},
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "Premise A."},
            {"id": "ns:p::s", "label": "s", "type": "setting", "content": "Setting."},
        ],
        "strategies": [
            {
                "premises": ["ns:p::a"],
                "conclusion": "ns:p::c",
                "type": "noisy_and",
                "metadata": {"reason": "A supports C."},
            },
        ],
        "operators": [],
    }
    md = render_knowledge_nodes(ir)
    pos_s = md.index("#### s")
    pos_a = md.index("#### a")
    pos_c = md.index("#### c")
    assert pos_s < pos_a < pos_c


def test_render_knowledge_nodes_hyperlinks():
    ir = {
        "knowledges": [
            {
                "id": "ns:p::a",
                "label": "a",
                "title": "Alpha Title",
                "type": "claim",
                "content": "A.",
            },
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
        ],
        "strategies": [
            {
                "premises": ["ns:p::a"],
                "conclusion": "ns:p::b",
                "type": "noisy_and",
                "metadata": {"reason": "A implies B."},
            },
        ],
        "operators": [],
    }
    md = render_knowledge_nodes(ir)
    assert '<a id="a"></a>' in md
    assert "[Alpha Title](#a)" in md


def test_render_knowledge_nodes_with_beliefs():
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    md = render_knowledge_nodes(ir, beliefs={"ns:p::a": 0.85}, priors={"ns:p::a": 0.90})
    assert "0.90" in md
    assert "0.85" in md


# ── generate_detailed_reasoning ──


def test_generate_detailed_reasoning_without_beliefs():
    ir = {
        "namespace": "github",
        "package_name": "test_pkg",
        "knowledges": [
            {"id": "github:test_pkg::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    pkg_metadata = {"name": "test-pkg-gaia", "description": "A test package."}
    md = generate_detailed_reasoning(ir, pkg_metadata)
    assert "# test-pkg-gaia" in md
    assert "A test package." in md
    assert "## Knowledge Graph" in md
    assert "## Knowledge Nodes" in md
    assert "## Inference Results" not in md


def test_generate_detailed_reasoning_with_beliefs():
    ir = {
        "namespace": "github",
        "package_name": "test_pkg",
        "knowledges": [
            {"id": "github:test_pkg::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    pkg_metadata = {"name": "test-pkg-gaia", "description": "Test."}
    beliefs_data = {
        "beliefs": [{"knowledge_id": "github:test_pkg::a", "label": "a", "belief": 0.85}],
        "diagnostics": {"converged": True, "iterations_run": 10},
    }
    param_data = {
        "priors": [{"knowledge_id": "github:test_pkg::a", "value": 0.90}],
    }
    md = generate_detailed_reasoning(
        ir, pkg_metadata, beliefs_data=beliefs_data, param_data=param_data
    )
    assert "## Inference Results" in md
    assert "0.85" in md
    assert "converged" in md.lower()


# ── CLI integration ──


def test_render_docs_flag_generates_detailed_reasoning(tmp_path):
    """gaia render --target docs writes docs/detailed-reasoning.md."""
    pkg_dir = tmp_path / "docs_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "docs-pkg-gaia"\nversion = "1.0.0"\n'
        'description = "A test package."\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "docs_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'a = claim("Premise A.")\n'
        'b = claim("Premise B.")\n'
        'c = claim("Conclusion.")\n'
        "s = deduction([a, b], c)\n"
        '__all__ = ["a", "b", "c", "s"]\n'
    )
    (pkg_src / "priors.py").write_text(
        "from . import a, b, c\n\n"
        "PRIORS: dict = {\n"
        '    a: (0.8, "ok"),\n'
        '    b: (0.8, "ok"),\n'
        '    c: (0.4, "ok"),\n'
        "}\n"
    )

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0
    assert runner.invoke(app, ["infer", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert result.exit_code == 0, f"Failed: {result.output}"

    content = (pkg_dir / "docs" / "detailed-reasoning.md").read_text()
    assert "# docs-pkg-gaia" in content
    assert "A test package." in content
    assert "```mermaid" in content
    assert "#### a" in content
    assert "#### b" in content
    assert "#### c" in content


# ── overview graph ──


def test_overview_graph_shows_transitive_deps():
    """Overview graph connects exported conclusions through non-exported intermediates."""
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A.", "exported": True},
            {"id": "ns:p::mid", "label": "mid", "type": "claim", "content": "Mid."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B.", "exported": True},
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "C.", "exported": True},
        ],
        "strategies": [
            {"premises": ["ns:p::a"], "conclusion": "ns:p::mid", "type": "noisy_and"},
            {"premises": ["ns:p::mid"], "conclusion": "ns:p::b", "type": "noisy_and"},
        ],
        "operators": [],
    }
    lines = _render_overview_graph(ir)
    md = "\n".join(lines)
    assert "## Overview" in md
    assert "graph LR" in md
    # a → mid → b, so overview shows a --> b (transitive through mid)
    assert "a --> b" in md
    # mid is not exported, so it should NOT appear
    assert "mid" not in md


def test_overview_graph_stops_at_nearest_exported():
    """Overview graph stops at nearest exported dependency — no redundant transitive edges."""
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A.", "exported": True},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B.", "exported": True},
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "C.", "exported": True},
        ],
        "strategies": [
            {"premises": ["ns:p::a"], "conclusion": "ns:p::b", "type": "noisy_and"},
            {"premises": ["ns:p::b"], "conclusion": "ns:p::c", "type": "noisy_and"},
        ],
        "operators": [],
    }
    lines = _render_overview_graph(ir)
    md = "\n".join(lines)
    assert "a --> b" in md
    assert "b --> c" in md
    # a --> c should NOT appear (redundant — a→b→c already shown)
    assert "a --> c" not in md


def test_overview_graph_empty_when_no_deps():
    """Overview graph returns empty when exported nodes are all independent."""
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A.", "exported": True},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B.", "exported": True},
        ],
        "strategies": [],
        "operators": [],
    }
    assert _render_overview_graph(ir) == []


def test_overview_graph_empty_when_single_export():
    """Overview graph returns empty with fewer than 2 exported nodes."""
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A.", "exported": True},
        ],
        "strategies": [],
        "operators": [],
    }
    assert _render_overview_graph(ir) == []


# ── module narrative ──


def test_module_sections_with_per_module_mermaid():
    """Multi-module: first module skips Mermaid, subsequent modules get diagrams."""
    ir = {
        "module_order": ["sec_a", "sec_b"],
        "knowledges": [
            {
                "id": "ns:p::x",
                "label": "x",
                "type": "claim",
                "content": "X.",
                "module": "sec_a",
                "declaration_index": 0,
                "exported": False,
            },
            {
                "id": "ns:p::y",
                "label": "y",
                "type": "claim",
                "content": "Y.",
                "module": "sec_a",
                "declaration_index": 1,
                "exported": False,
            },
            {
                "id": "ns:p::z",
                "label": "z",
                "type": "claim",
                "content": "Z.",
                "module": "sec_b",
                "declaration_index": 0,
                "exported": True,
            },
        ],
        "strategies": [
            {"premises": ["ns:p::x"], "conclusion": "ns:p::z", "type": "noisy_and"},
        ],
        "operators": [],
    }
    md = render_knowledge_nodes(ir)
    assert "## sec_a" in md
    assert "## sec_b" in md
    assert md.index("#### x") < md.index("#### z")
    assert md.index("#### y") < md.index("#### z")
    # First module (sec_a) skips Mermaid; sec_b gets one
    assert md.count("```mermaid") == 1
    sec_b_section = md.split("## sec_b")[1]
    assert "x" in sec_b_section.split("```")[1]


def test_module_sections_preserve_root_segments():
    ir = {
        "module_order": ["sec_a"],
        "knowledges": [
            {
                "id": "ns:p::intro",
                "label": "intro",
                "type": "setting",
                "content": "Intro.",
                "module": None,
                "declaration_index": 0,
            },
            {
                "id": "ns:p::x",
                "label": "x",
                "type": "claim",
                "content": "X.",
                "module": "sec_a",
                "declaration_index": 0,
            },
            {
                "id": "ns:p::outro",
                "label": "outro",
                "type": "claim",
                "content": "Outro.",
                "module": None,
                "declaration_index": 1,
            },
        ],
        "strategies": [],
        "operators": [],
    }
    md = render_knowledge_nodes(ir)
    assert md.index("## Root") < md.index("## sec_a") < md.index("## Root (continued)")
    assert md.index("#### intro") < md.index("#### x") < md.index("#### outro")


def test_exported_marker():
    ir = {
        "module_order": ["mod"],
        "knowledges": [
            {
                "id": "ns:p::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "mod",
                "declaration_index": 0,
                "exported": True,
            },
            {
                "id": "ns:p::b",
                "label": "b",
                "type": "claim",
                "content": "B.",
                "module": "mod",
                "declaration_index": 1,
                "exported": False,
            },
        ],
        "strategies": [],
        "operators": [],
    }
    md = render_knowledge_nodes(ir)
    assert "\u2605" in md.split("#### a")[1].split("#### b")[0]
    assert "\u2605" not in md.split("#### b")[1]


def test_introduction_with_exported_knowledge():
    """Introduction shows exported knowledge when no motivation module."""
    from gaia.cli.commands._detailed_reasoning import generate_detailed_reasoning

    ir = {
        "namespace": "github",
        "package_name": "test_pkg",
        "knowledges": [
            {
                "id": "ns:p::main_result",
                "label": "main_result",
                "type": "claim",
                "content": "The main conclusion.",
                "exported": True,
            },
            {
                "id": "ns:p::context",
                "label": "context",
                "type": "setting",
                "content": "Shared context.",
                "exported": True,
            },
            {
                "id": "ns:p::internal",
                "label": "internal",
                "type": "claim",
                "content": "An internal claim.",
                "exported": False,
            },
        ],
        "strategies": [],
        "operators": [],
    }
    md = generate_detailed_reasoning(ir, {"name": "test-gaia", "description": "Test."})
    assert "## Introduction" in md
    assert "The main conclusion." in md
    assert "Shared context." in md
    # Internal claim should NOT be in introduction
    intro = md.split("## Introduction")[1].split("##")[0]
    assert "An internal claim." not in intro


def test_motivation_module_suppresses_introduction():
    """When motivation module exists, no separate Introduction section."""
    from gaia.cli.commands._detailed_reasoning import generate_detailed_reasoning

    ir = {
        "namespace": "github",
        "package_name": "test_pkg",
        "module_order": ["motivation", "results"],
        "knowledges": [
            {
                "id": "ns:p::bg",
                "label": "bg",
                "type": "setting",
                "content": "Background.",
                "module": "motivation",
                "declaration_index": 0,
            },
            {
                "id": "ns:p::result",
                "label": "result",
                "type": "claim",
                "content": "Result.",
                "module": "results",
                "declaration_index": 0,
                "exported": True,
            },
        ],
        "strategies": [],
        "operators": [],
    }
    md = generate_detailed_reasoning(ir, {"name": "test-gaia", "description": "Test."})
    assert "## Introduction" not in md
    assert "## motivation" in md
    assert "## results" in md


# ── coverage: operator edges, inference results, single-file fallback ──


def test_mermaid_operator_edges():
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "C."},
        ],
        "strategies": [],
        "operators": [
            {
                "operator": "contradiction",
                "variables": ["ns:p::a", "ns:p::b"],
                "conclusion": "ns:p::c",
            },
        ],
    }
    md = render_mermaid(ir)
    # Contradiction rendered as hexagon node with ⊗ symbol
    assert "\u2297" in md  # ⊗ symbol
    assert ":::contra" in md
    assert "a --- oper_0" in md
    assert "b --- oper_0" in md
    assert "oper_0 --- c" in md  # non-helper conclusion shown


def test_generate_detailed_reasoning_with_inference_results():
    from gaia.cli.commands._detailed_reasoning import generate_detailed_reasoning

    ir = {
        "namespace": "github",
        "package_name": "test_pkg",
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
        ],
        "strategies": [
            {"premises": ["ns:p::a"], "conclusion": "ns:p::b", "type": "noisy_and"},
        ],
        "operators": [],
    }
    beliefs_data = {
        "beliefs": [
            {"knowledge_id": "ns:p::a", "label": "a", "belief": 0.90},
            {"knowledge_id": "ns:p::b", "label": "b", "belief": 0.70},
        ],
        "diagnostics": {"converged": True, "iterations_run": 5},
    }
    param_data = {
        "priors": [{"knowledge_id": "ns:p::a", "value": 0.95}],
    }
    md = generate_detailed_reasoning(
        ir, {"name": "test-gaia"}, beliefs_data=beliefs_data, param_data=param_data
    )
    assert "## Inference Results" in md
    assert "| a |" in md or "| [a]" in md
    assert "0.90" in md
    assert "independent" in md
    assert "derived" in md


def test_single_file_fallback_has_global_graph():
    """Single-file package (no module_order) renders one global Mermaid graph."""
    ir = {
        "knowledges": [
            {"id": "ns:p::s", "label": "s", "type": "setting", "content": "S."},
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    md = render_knowledge_nodes(ir)
    assert "## Knowledge Graph" in md
    assert "```mermaid" in md
    assert "### Settings" in md
    assert "### Claims" in md


def test_mermaid_deduction_deterministic():
    """Deduction strategy renders without :::weak styling."""
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "C."},
        ],
        "strategies": [
            {"premises": ["ns:p::a", "ns:p::b"], "conclusion": "ns:p::c", "type": "deduction"},
        ],
        "operators": [],
    }
    md = render_mermaid(ir)
    assert '(["deduction"])' in md
    # deduction is deterministic — no :::weak on the strategy node
    strat_line = [line for line in md.split("\n") if "strat_0" in line and '(["' in line][0]
    assert ":::weak" not in strat_line
    assert "a --> strat_0" in md
    assert "b --> strat_0" in md
    assert "strat_0 --> c" in md


def test_mermaid_background_dashed_edge():
    """Background claims connect to strategy nodes with dashed edges."""
    ir = {
        "knowledges": [
            {"id": "ns:p::ctx", "label": "ctx", "type": "setting", "content": "Context."},
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
        ],
        "strategies": [
            {
                "premises": ["ns:p::a"],
                "conclusion": "ns:p::b",
                "type": "noisy_and",
                "background": ["ns:p::ctx"],
            },
        ],
        "operators": [],
    }
    md = render_mermaid(ir)
    assert "a --> strat_0" in md  # premise: solid arrow
    assert "ctx -.-> strat_0" in md  # background: dashed arrow
    assert "strat_0 --> b" in md


def test_mermaid_equivalence_undirected():
    """Equivalence operator uses undirected (---) edges."""
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
            {"id": "ns:p::__eq_ab", "label": "__eq_ab", "type": "claim", "content": "helper"},
        ],
        "strategies": [],
        "operators": [
            {
                "operator": "equivalence",
                "variables": ["ns:p::a", "ns:p::b"],
                "conclusion": "ns:p::__eq_ab",
            },
        ],
    }
    md = render_mermaid(ir)
    assert "\u2261" in md  # ≡ symbol
    assert "a --- oper_0" in md
    assert "b --- oper_0" in md
    # Helper conclusion hidden — no edge to __eq_ab
    assert "__eq_ab" not in md


def test_mermaid_disjunction_directed():
    """Disjunction operator uses directed (-->) edges."""
    ir = {
        "knowledges": [
            {"id": "ns:p::h1", "label": "h1", "type": "claim", "content": "H1."},
            {"id": "ns:p::h2", "label": "h2", "type": "claim", "content": "H2."},
            {"id": "ns:p::disj", "label": "disj", "type": "claim", "content": "Disj."},
        ],
        "strategies": [],
        "operators": [
            {
                "operator": "disjunction",
                "variables": ["ns:p::h1", "ns:p::h2"],
                "conclusion": "ns:p::disj",
            },
        ],
    }
    md = render_mermaid(ir)
    assert "\u2228" in md  # ∨ symbol
    assert "h1 --> oper_0" in md
    assert "h2 --> oper_0" in md
    assert "oper_0 --> disj" in md


def test_mermaid_operator_cross_module_visibility():
    """Operators pull in cross-module variables when one variable is in node_ids."""
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
            {"id": "ns:p::__c_ab", "label": "__c_ab", "type": "claim", "content": "helper"},
        ],
        "strategies": [],
        "operators": [
            {
                "operator": "contradiction",
                "variables": ["ns:p::a", "ns:p::b"],
                "conclusion": "ns:p::__c_ab",
            },
        ],
    }
    # Only a is in this module; b should be pulled in as external
    md = render_mermaid(ir, node_ids={"ns:p::a"})
    assert "a[" in md
    assert "b[" in md  # pulled in via operator
    assert ":::external" in md  # b is external
    assert "a --- oper_0" in md
    assert "b --- oper_0" in md


def test_mermaid_with_node_ids_filter():
    """render_mermaid with node_ids only shows specified nodes + external premises."""
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "C."},
        ],
        "strategies": [
            {"premises": ["ns:p::a"], "conclusion": "ns:p::b", "type": "noisy_and"},
        ],
        "operators": [],
    }
    md = render_mermaid(ir, node_ids={"ns:p::b"})
    assert "b[" in md
    assert "a[" in md  # external premise pulled in
    assert "c[" not in md  # not in node_ids, not connected
