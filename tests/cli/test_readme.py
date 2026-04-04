"""Tests for gaia compile --readme."""

from typer.testing import CliRunner

from gaia.cli.commands._readme import (
    generate_readme,
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
    assert "obs -->|noisy_and| hyp" in md
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


# ── generate_readme ──


def test_generate_readme_without_beliefs():
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
    md = generate_readme(ir, pkg_metadata)
    assert "# test-pkg-gaia" in md
    assert "A test package." in md
    assert "## Knowledge Graph" in md
    assert "## Knowledge Nodes" in md
    assert "## Inference Results" not in md


def test_generate_readme_with_beliefs():
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
    md = generate_readme(ir, pkg_metadata, beliefs_data=beliefs_data, param_data=param_data)
    assert "## Inference Results" in md
    assert "0.85" in md
    assert "converged" in md.lower()


# ── CLI integration ──


def test_compile_readme_flag_generates_readme(tmp_path):
    pkg_dir = tmp_path / "readme_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "readme-pkg-gaia"\nversion = "1.0.0"\n'
        'description = "A test package."\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "readme_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, noisy_and\n\n"
        'a = claim("Premise A.")\n'
        'b = claim("Premise B.")\n'
        'c = claim("Conclusion.", given=[a, b])\n'
        '__all__ = ["a", "b", "c"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir), "--readme"])
    assert result.exit_code == 0, f"Failed: {result.output}"

    readme = (pkg_dir / "README.md").read_text()
    assert "# readme-pkg-gaia" in readme
    assert "A test package." in readme
    assert "```mermaid" in readme
    assert "## Knowledge Nodes" in readme
    assert readme.index("#### a") < readme.index("#### c")
    assert readme.index("#### b") < readme.index("#### c")
    assert "[a](#a)" in readme or "[b](#b)" in readme


# ── module narrative ──


def test_module_sections_with_per_module_mermaid():
    """Multi-module: each module gets its own section with Mermaid diagram."""
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
    # Module section headings
    assert "## sec_a" in md
    assert "## sec_b" in md
    # Order: sec_a nodes before sec_b
    assert md.index("#### x") < md.index("#### z")
    assert md.index("#### y") < md.index("#### z")
    # Per-module Mermaid diagrams
    assert md.count("```mermaid") == 2
    # sec_b's diagram should show x as external premise
    sec_b_section = md.split("## sec_b")[1]
    assert "x" in sec_b_section.split("```")[1]  # x appears in sec_b's mermaid


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
    from gaia.cli.commands._readme import generate_readme

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
    md = generate_readme(ir, {"name": "test-gaia", "description": "Test."})
    assert "## Introduction" in md
    assert "The main conclusion." in md
    assert "Shared context." in md
    # Internal claim should NOT be in introduction
    intro = md.split("## Introduction")[1].split("##")[0]
    assert "An internal claim." not in intro


def test_motivation_module_suppresses_introduction():
    """When motivation module exists, no separate Introduction section."""
    from gaia.cli.commands._readme import generate_readme

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
    md = generate_readme(ir, {"name": "test-gaia", "description": "Test."})
    assert "## Introduction" not in md
    assert "## motivation" in md
    assert "## results" in md
