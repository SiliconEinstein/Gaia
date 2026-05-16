"""Tests for the `gaia inspect starmap` command."""

from __future__ import annotations

import json
import re
from typing import ClassVar

import pytest
from typer.testing import CliRunner

from gaia.cli.commands._dot import to_dot
from gaia.cli.commands._stellaris_svg import (
    inject_defs,
    post_process_stellaris_svg,
    recolor_background,
)
from gaia.cli.main import app

runner = CliRunner()


def _write_base_package(pkg_dir, *, name: str, version: str = "1.0.0") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "{version}"\n'
        'description = "Test package."\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / name).mkdir()


def _write_minimal_source(pkg_dir, name: str) -> None:
    (pkg_dir / name / "__init__.py").write_text(
        "from gaia.engine.lang import claim, derive\n\n"
        'evidence_a = claim("Observed evidence A.")\n'
        'evidence_b = claim("Observed evidence B.")\n'
        'hypothesis = claim("Main hypothesis.")\n'
        "derive(hypothesis, given=[evidence_a, evidence_b], rationale='test', label='s')\n"
        '__all__ = ["evidence_a", "evidence_b", "hypothesis"]\n'
    )


def _write_priors(pkg_dir, name: str) -> None:
    (pkg_dir / name / "priors.py").write_text(
        "from . import evidence_a, evidence_b, hypothesis\n\n"
        "from gaia.engine.lang import register_prior\n"
        'register_prior(evidence_a, value=0.9, justification="Direct observation.")\n'
        'register_prior(evidence_b, value=0.8, justification="Supporting observation.")\n'
        'register_prior(hypothesis, value=0.4, justification="Base rate.")\n'
    )


def _prepare_inferred_package(tmp_path, name: str = "starmap_demo"):
    """Create, compile, and infer a package. Returns pkg_dir."""
    pkg_dir = tmp_path / name
    _write_base_package(pkg_dir, name=name)
    _write_minimal_source(pkg_dir, name)
    _write_priors(pkg_dir, name)
    assert runner.invoke(app, ["build", "compile", str(pkg_dir)]).exit_code == 0
    assert runner.invoke(app, ["run", "infer", str(pkg_dir)]).exit_code == 0
    return pkg_dir


def _extract_graph_data(html: str) -> dict:
    """Parse the JSON payload injected by `gaia inspect starmap` out of the HTML."""
    match = re.search(r"window\.GRAPH_DATA = (.*?);</script>", html, re.DOTALL)
    assert match is not None, "window.GRAPH_DATA assignment not found in starmap HTML"
    return json.loads(match.group(1))


def test_starmap_default_output(tmp_path):
    """Happy path: writes .gaia/starmap.html with a parseable graph payload."""
    pkg_dir = _prepare_inferred_package(tmp_path)

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    out_path = pkg_dir / ".gaia" / "starmap.html"
    assert out_path.exists()
    html = out_path.read_text()
    assert "window.GRAPH_DATA" in html

    data = _extract_graph_data(html)
    knowledge_nodes = [n for n in data["nodes"] if n["type"] not in ("strategy", "operator")]
    authored_nodes = [n for n in knowledge_nodes if not n["metadata"].get("generated")]
    # 3 authored knowledge nodes: evidence_a, evidence_b, hypothesis.
    assert len(authored_nodes) == 3
    labels = {n["label"] for n in authored_nodes}
    assert labels == {"evidence_a", "evidence_b", "hypothesis"}

    # Beliefs and priors should be threaded through.
    assert any(n.get("belief") is not None for n in authored_nodes)
    assert any(n.get("prior") is not None for n in authored_nodes)

    # Success message reports counts.
    assert "Wrote starmap to" in result.output
    assert "nodes" in result.output and "edges" in result.output


def test_starmap_custom_output(tmp_path):
    """`--out` overrides the default path (relative to package dir)."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_custom")
    custom = "build/star.html"

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--out", custom])
    assert result.exit_code == 0, result.output

    expected = pkg_dir / custom
    assert expected.exists()
    assert not (pkg_dir / ".gaia" / "starmap.html").exists()


def test_starmap_creates_parent_dirs(tmp_path):
    """`--out` honors nested paths and creates parent directories."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_nested")
    nested = "nested/dir/foo.html"

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--out", nested])
    assert result.exit_code == 0, result.output

    out_path = pkg_dir / nested
    assert out_path.exists()
    assert out_path.parent.is_dir()


def test_starmap_absolute_out_path(tmp_path):
    """Absolute `--out` is honored as-is, ignoring the package directory."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_abs")
    abs_out = tmp_path / "elsewhere" / "starmap.html"

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--out", str(abs_out)])
    assert result.exit_code == 0, result.output
    assert abs_out.exists()


def test_starmap_without_beliefs(tmp_path):
    """Without `gaia infer`, starmap still produces HTML; beliefs are absent."""
    pkg_dir = tmp_path / "starmap_no_infer"
    _write_base_package(pkg_dir, name="starmap_no_infer")
    _write_minimal_source(pkg_dir, "starmap_no_infer")
    assert runner.invoke(app, ["build", "compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    out_path = pkg_dir / ".gaia" / "starmap.html"
    assert out_path.exists()

    data = _extract_graph_data(out_path.read_text())
    knowledge_nodes = [n for n in data["nodes"] if n["type"] not in ("strategy", "operator")]
    assert knowledge_nodes, "expected knowledge nodes in payload"
    assert all(n["belief"] is None for n in knowledge_nodes)


def test_starmap_missing_ir(tmp_path):
    """Without `gaia compile`, starmap exits non-zero with a clear message."""
    pkg_dir = tmp_path / "starmap_no_compile"
    _write_base_package(pkg_dir, name="starmap_no_compile")
    _write_minimal_source(pkg_dir, "starmap_no_compile")

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code != 0
    assert "missing compiled artifacts" in result.output


# ── DOT format ──────────────────────────────────────────────────────────────


def test_starmap_dot_default_output(tmp_path):
    """`--format dot` writes `.gaia/starmap.dot` with paper-ready Graphviz content."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_dot")

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--format", "dot"])
    assert result.exit_code == 0, result.output

    out_path = pkg_dir / ".gaia" / "starmap.dot"
    assert out_path.exists()
    # Default HTML must NOT have been emitted in dot mode.
    assert not (pkg_dir / ".gaia" / "starmap.html").exists()

    content = out_path.read_text()
    assert content.startswith("digraph starmap")
    # At least one cluster (every knowledge node belongs to a module).
    assert "subgraph cluster_" in content
    # At least one directed edge.
    assert "->" in content
    # All three knowledge ids should appear, quoted (compiled ids are
    # namespaced, e.g. "github:starmap_dot::evidence_a").
    assert '::evidence_a"' in content
    assert '::evidence_b"' in content
    assert '::hypothesis"' in content


def test_starmap_dot_custom_out(tmp_path):
    """`--format dot --out path.dot` lands the file at the chosen path."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_dot_custom")
    custom = "build/diagram.dot"

    result = runner.invoke(
        app, ["inspect", "starmap", str(pkg_dir), "--format", "dot", "--out", custom]
    )
    assert result.exit_code == 0, result.output

    expected = pkg_dir / custom
    assert expected.exists()
    content = expected.read_text()
    assert content.startswith("digraph starmap")
    # Default dot path must not have been written.
    assert not (pkg_dir / ".gaia" / "starmap.dot").exists()


def test_starmap_dot_belief_annotation(tmp_path):
    """With priors+beliefs present, knowledge nodes carry a `(P → B)` substring."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_dot_belief")

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--format", "dot"])
    assert result.exit_code == 0, result.output

    content = (pkg_dir / ".gaia" / "starmap.dot").read_text()
    # Belief annotation: a node label contains "→" and a "(0.<digits>" group.
    assert "→" in content, content
    assert re.search(r"\(0\.\d", content), content


def test_starmap_dot_no_beliefs(tmp_path):
    """Without `gaia infer`, dot still renders and skips trend arrows."""
    pkg_dir = tmp_path / "starmap_dot_no_infer"
    _write_base_package(pkg_dir, name="starmap_dot_no_infer")
    _write_minimal_source(pkg_dir, "starmap_dot_no_infer")
    assert runner.invoke(app, ["build", "compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--format", "dot"])
    assert result.exit_code == 0, result.output

    content = (pkg_dir / ".gaia" / "starmap.dot").read_text()
    assert content.startswith("digraph starmap")
    # No belief-trend arrows in any node label without inferred beliefs.
    assert "↑" not in content
    assert "↓" not in content


def test_starmap_dot_topology_based_floating():
    """Strategy/operator nodes touching ≥2 modules render outside any cluster.

    Floating decision is purely topology-based: any strategy or operator that
    bridges multiple modules floats at top level. There is no module-name
    hardcode (e.g. ``cross_paper``) — module names are user-controlled.
    """
    graph_json = json.dumps(
        {
            "nodes": [
                {
                    "id": "p:paper_x::a",
                    "type": "claim",
                    "label": "a",
                    "title": "a",
                    "module": "paper_x",
                },
                {
                    "id": "p:paper_x::b",
                    "type": "claim",
                    "label": "b",
                    "title": "b",
                    "module": "paper_x",
                },
                {
                    "id": "p:paper_x::s",
                    "type": "strategy",
                    "strategy_type": "deduction",
                    "module": "paper_x",
                },
                {
                    "id": "p:paper_y::c",
                    "type": "claim",
                    "label": "c",
                    "title": "c",
                    "module": "paper_y",
                },
                {
                    "id": "p:bridge::s",
                    "type": "strategy",
                    "strategy_type": "deduction",
                    "module": "paper_y",
                },
            ],
            "edges": [
                {"source": "p:paper_x::a", "target": "p:paper_x::s", "role": "premise"},
                {"source": "p:paper_x::s", "target": "p:paper_x::b", "role": "conclusion"},
                {"source": "p:paper_x::b", "target": "p:bridge::s", "role": "premise"},
                {"source": "p:bridge::s", "target": "p:paper_y::c", "role": "conclusion"},
            ],
        }
    )

    dot = to_dot(graph_json)
    assert "subgraph cluster_paper_x" in dot
    assert "subgraph cluster_paper_y" in dot

    paper_x_block = dot.split("subgraph cluster_paper_x", 1)[1].split("}", 1)[0]
    assert '"p:paper_x::s"' in paper_x_block

    floating_marker = "// cross-module strategy/operator nodes (outside clusters)"
    assert floating_marker in dot, dot
    floating_block = dot.split(floating_marker, 1)[1].split("// edges", 1)[0]
    assert '"p:bridge::s"' in floating_block


def test_starmap_dot_no_floating_module_name_hardcode():
    """A user-named ``cross_paper`` module is treated like any other module.

    Regression: earlier the emitter unboxed ``cross_paper`` by filename
    convention. That hardcode is removed — users own their module names.
    """
    graph_json = json.dumps(
        {
            "nodes": [
                {
                    "id": "p:cross_paper::a",
                    "type": "claim",
                    "label": "a",
                    "title": "a",
                    "module": "cross_paper",
                },
                {
                    "id": "p:cross_paper::b",
                    "type": "claim",
                    "label": "b",
                    "title": "b",
                    "module": "cross_paper",
                },
                {
                    "id": "p:cross_paper::s",
                    "type": "strategy",
                    "strategy_type": "deduction",
                    "module": "cross_paper",
                },
            ],
            "edges": [
                {"source": "p:cross_paper::a", "target": "p:cross_paper::s", "role": "premise"},
                {"source": "p:cross_paper::s", "target": "p:cross_paper::b", "role": "conclusion"},
            ],
        }
    )

    dot = to_dot(graph_json)
    assert "subgraph cluster_cross_paper" in dot
    cluster_block = dot.split("subgraph cluster_cross_paper", 1)[1].split("}", 1)[0]
    assert '"p:cross_paper::s"' in cluster_block


# ── Stellaris theme ─────────────────────────────────────────────────────────


def _make_stellaris_fixture() -> str:
    """Synthetic graph_json exercising every node/edge type the spec covers."""
    return json.dumps(
        {
            "nodes": [
                {
                    "id": "p:m::s_setting",
                    "type": "setting",
                    "label": "s_setting",
                    "title": "the setting",
                    "module": "m",
                },
                {
                    "id": "p:m::premise_a",
                    "type": "claim",
                    "label": "premise_a",
                    "title": "premise A",
                    "module": "m",
                },
                {
                    "id": "p:m::derived_a",
                    "type": "claim",
                    "label": "derived_a",
                    "title": "derived A",
                    "module": "m",
                    "exported": True,
                },
                {
                    "id": "p:m::q",
                    "type": "question",
                    "label": "q",
                    "title": "the question",
                    "module": "m",
                },
                {
                    "id": "strat_ded",
                    "type": "strategy",
                    "strategy_type": "deduction",
                    "module": "m",
                },
                {
                    "id": "strat_sup",
                    "type": "strategy",
                    "strategy_type": "support",
                    "module": "m",
                },
                {"id": "op_contra", "type": "operator", "operator_type": "contradiction"},
                {"id": "op_equiv", "type": "operator", "operator_type": "equivalence"},
                {"id": "op_impl", "type": "operator", "operator_type": "implication"},
                {"id": "op_compl", "type": "operator", "operator_type": "complement"},
                {"id": "op_disj", "type": "operator", "operator_type": "disjunction"},
                {"id": "op_conj", "type": "operator", "operator_type": "conjunction"},
            ],
            "edges": [
                {"source": "p:m::premise_a", "target": "strat_ded", "role": "premise"},
                {"source": "p:m::s_setting", "target": "strat_ded", "role": "background"},
                {"source": "strat_ded", "target": "p:m::derived_a", "role": "conclusion"},
                {"source": "p:m::premise_a", "target": "strat_sup", "role": "premise"},
                {"source": "strat_sup", "target": "p:m::derived_a", "role": "conclusion"},
                {"source": "p:m::premise_a", "target": "op_contra", "role": "variable"},
                {"source": "op_contra", "target": "p:m::q", "role": "conclusion"},
                {"source": "p:m::premise_a", "target": "op_equiv", "role": "variable"},
                {"source": "op_equiv", "target": "p:m::q", "role": "conclusion"},
                {"source": "p:m::premise_a", "target": "op_impl", "role": "variable"},
                {"source": "op_impl", "target": "p:m::q", "role": "conclusion"},
                {"source": "p:m::premise_a", "target": "op_compl", "role": "variable"},
                {"source": "op_compl", "target": "p:m::q", "role": "conclusion"},
                {"source": "p:m::premise_a", "target": "op_disj", "role": "variable"},
                {"source": "op_disj", "target": "p:m::q", "role": "conclusion"},
                {"source": "p:m::premise_a", "target": "op_conj", "role": "variable"},
                {"source": "op_conj", "target": "p:m::q", "role": "conclusion"},
            ],
        }
    )


def _node_line(dot: str, nid: str) -> str:
    return next(
        line
        for line in dot.splitlines()
        if f'"{nid}"' in line and "label=" in line and "->" not in line
    )


def _edge_line(dot: str, src: str, tgt: str) -> str:
    return next(line for line in dot.splitlines() if f'"{src}" -> "{tgt}"' in line)


def test_to_dot_stellaris_layout_and_bg():
    """Stellaris theme switches to sfdp layout + deep-space bg + tuning knobs."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    assert "layout=sfdp" in dot
    assert 'bgcolor="#05060f"' in dot
    assert "K=1.2" in dot
    assert "repulsiveforce=2.0" in dot
    assert "overlap=prism" in dot
    assert "overlap_scaling=4" in dot
    assert 'sep="+12"' in dot
    assert "splines=true" in dot


def test_to_dot_light_theme_keeps_existing_layout():
    """Light (default) theme keeps the existing TB / non-sfdp layout."""
    dot = to_dot(_make_stellaris_fixture())
    assert "rankdir=TB" in dot
    assert "layout=sfdp" not in dot
    assert 'bgcolor="#05060f"' not in dot


def test_to_dot_stellaris_dark_alias():
    """`theme="dark"` aliases stellaris."""
    dot_dark = to_dot(_make_stellaris_fixture(), theme="dark")
    dot_stellaris = to_dot(_make_stellaris_fixture(), theme="stellaris")
    assert dot_dark == dot_stellaris


def test_to_dot_stellaris_knowledge_palette():
    """Stellaris theme assigns spec'd hex pairs to claim/setting/exported."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")

    premise_line = _node_line(dot, "p:m::premise_a")
    assert "#11253d" in premise_line
    assert "#5fa8e0" in premise_line

    derived_line = _node_line(dot, "p:m::derived_a")
    assert "#1f3a24" in derived_line
    assert "#ffd24a" in derived_line
    assert 'class="root"' in derived_line
    assert "★" in derived_line

    setting_line = _node_line(dot, "p:m::s_setting")
    assert "#1c1c2a" in setting_line
    assert "#6d6d80" in setting_line


def test_to_dot_question_knowledge_branch_stellaris():
    """Question knowledge nodes render with a dashed amber box (open inquiry)."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    q_line = _node_line(dot, "p:m::q")
    assert "#332416" in q_line
    assert "#caa84a" in q_line
    assert "dashed" in q_line


def test_to_dot_question_knowledge_branch_light():
    """Question branch also exists in light theme (with a light palette)."""
    dot = to_dot(_make_stellaris_fixture())
    q_line = _node_line(dot, "p:m::q")
    assert "dashed" in q_line


def test_to_dot_six_operators_distinct_symbols():
    """Each of the 6 OperatorType values renders with its own unicode symbol."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")

    def op_label(nid: str) -> str:
        line = _node_line(dot, nid)
        m = re.search(r'label="([^"]*)"', line)
        assert m, line
        return m.group(1)

    assert "⊗" in op_label("op_contra")
    assert "⊙" in op_label("op_equiv")
    assert "⊃" in op_label("op_impl")
    assert "¬" in op_label("op_compl")
    assert "∨" in op_label("op_disj")
    assert "∧" in op_label("op_conj")


def test_to_dot_contradiction_operator_carries_class():
    """Contradiction operator nodes carry class="contradiction" for SVG glow."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    contra_line = _node_line(dot, "op_contra")
    assert 'class="contradiction"' in contra_line
    assert "#3a0a14" in contra_line
    assert "#ff4060" in contra_line


def test_to_dot_neutral_operators_share_palette():
    """The 5 non-contradiction operators share a neutral grey palette."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    for nid in ("op_equiv", "op_impl", "op_compl", "op_disj", "op_conj"):
        line = _node_line(dot, nid)
        assert "#1a1a24" in line, f"{nid} line: {line}"
        assert "#7d7d8e" in line, f"{nid} line: {line}"


def test_to_dot_support_strategy_diamond_with_glow_class():
    """Support strategies render as gold-glowing diamonds; non-support stay ellipses."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")

    sup_line = _node_line(dot, "strat_sup")
    assert "shape=diamond" in sup_line
    assert 'class="support"' in sup_line
    assert "#2a2410" in sup_line
    assert "#ffc44a" in sup_line

    ded_line = _node_line(dot, "strat_ded")
    assert "shape=ellipse" in ded_line
    assert 'class="support"' not in ded_line


def test_to_dot_edge_role_styling_premise():
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    line = _edge_line(dot, "p:m::premise_a", "strat_ded")
    assert "penwidth=1.0" in line
    assert "dashed" not in line


def test_to_dot_edge_role_styling_background():
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    line = _edge_line(dot, "p:m::s_setting", "strat_ded")
    assert "dashed" in line
    assert "penwidth=0.8" in line


def test_to_dot_edge_role_styling_variable():
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    line = _edge_line(dot, "p:m::premise_a", "op_equiv")
    assert "penwidth=1.0" in line
    assert "dashed" not in line


def test_to_dot_edge_role_styling_conclusion():
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    line = _edge_line(dot, "strat_ded", "p:m::derived_a")
    assert "penwidth=1.2" in line
    assert "dashed" not in line


def test_to_dot_contradiction_incident_edges_recolored():
    """Edges incident to a contradiction operator are recolored bright red, dir=none."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    line = _edge_line(dot, "p:m::premise_a", "op_contra")
    assert "#ff5470" in line
    assert "penwidth=1.4" in line
    assert "dir=none" in line


def test_starmap_cli_theme_flag(tmp_path):
    """`gaia starmap --format dot --theme stellaris` produces dot with sfdp layout."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_theme")
    result = runner.invoke(
        app, ["inspect", "starmap", str(pkg_dir), "--format", "dot", "--theme", "stellaris"]
    )
    assert result.exit_code == 0, result.output
    content = (pkg_dir / ".gaia" / "starmap.dot").read_text()
    assert "layout=sfdp" in content
    assert 'bgcolor="#05060f"' in content


def test_starmap_cli_theme_default_is_light(tmp_path):
    """Without `--theme`, output stays on the light/TB layout (regression guard)."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_default_theme")
    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--format", "dot"])
    assert result.exit_code == 0, result.output
    content = (pkg_dir / ".gaia" / "starmap.dot").read_text()
    assert "layout=sfdp" not in content
    assert 'bgcolor="#05060f"' not in content
    assert "rankdir=TB" in content


def test_starmap_cli_theme_dark_alias(tmp_path):
    """`--theme dark` is accepted and produces stellaris output."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_dark")
    result = runner.invoke(
        app, ["inspect", "starmap", str(pkg_dir), "--format", "dot", "--theme", "dark"]
    )
    assert result.exit_code == 0, result.output
    content = (pkg_dir / ".gaia" / "starmap.dot").read_text()
    assert "layout=sfdp" in content


def test_starmap_cli_theme_invalid(tmp_path):
    """Unknown theme exits non-zero with a clear message."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_bad_theme")
    result = runner.invoke(
        app, ["inspect", "starmap", str(pkg_dir), "--format", "dot", "--theme", "bogus"]
    )
    assert result.exit_code != 0
    assert "theme" in result.output.lower()


# ── _stellaris_svg unit tests ────────────────────────────────────────────────


def test_inject_defs_adds_block_after_svg_tag():
    """Defs block is inserted immediately after the opening <svg> tag."""
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="100"><g/></svg>'
    out = inject_defs(svg)
    assert "<defs>" in out
    assert 'id="space-bg"' in out
    assert 'id="contra-glow"' in out
    assert 'id="support-glow"' in out
    assert 'id="root-glow"' in out
    # Defs come after the opening svg tag, before the first <g>.
    svg_open_end = out.index(">", out.index("<svg")) + 1
    defs_start = out.index("<defs>")
    g_start = out.index("<g")
    assert svg_open_end <= defs_start < g_start


def test_inject_defs_includes_class_style_selectors():
    """The injected <style> binds class selectors to the three glow filters."""
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>'
    out = inject_defs(svg)
    assert ".contradiction { filter: url(#contra-glow); }" in out
    assert ".support       { filter: url(#support-glow); }" in out
    assert ".root          { filter: url(#root-glow); }" in out


def test_inject_defs_idempotent():
    """Calling inject_defs twice does not double the defs block."""
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>'
    once = inject_defs(svg)
    twice = inject_defs(once)
    assert once == twice
    assert once.count("<defs>") == 1


def test_recolor_background_replaces_stellaris_bg_polygon():
    """A <polygon fill="#05060f"> canvas gets repainted to url(#space-bg)."""
    svg = '<svg><g><polygon fill="#05060f" stroke="transparent" points="0,0"/></g></svg>'
    out = recolor_background(svg)
    assert 'fill="url(#space-bg)"' in out
    assert 'fill="#05060f"' not in out


def test_recolor_background_replaces_white_canvas_polygon():
    """Fallback path: a white-canvas polygon (no bgcolor set) is repainted."""
    svg = '<svg><g><polygon fill="white" stroke="none" points="0,0"/></g></svg>'
    out = recolor_background(svg)
    assert 'fill="url(#space-bg)"' in out


def test_recolor_background_only_touches_first_matching_polygon():
    """Recolour exactly one polygon; node-shape polygons stay untouched."""
    svg = (
        "<svg>"
        '<g><polygon fill="#05060f" stroke="transparent" points="0,0"/>'
        '<polygon fill="#05060f" stroke="black" points="1,1"/></g>'
        "</svg>"
    )
    out = recolor_background(svg)
    # First (canvas) polygon repainted; second (node-shape lookalike) preserved.
    assert out.count('fill="url(#space-bg)"') == 1
    assert out.count('fill="#05060f"') == 1


def test_recolor_background_idempotent():
    """A second pass is a no-op when url(#space-bg) is already present."""
    svg = '<svg><g><polygon fill="#05060f" stroke="transparent" points="0,0"/></g></svg>'
    once = recolor_background(svg)
    twice = recolor_background(once)
    assert once == twice


def test_post_process_stellaris_svg_combines_both_steps():
    """The convenience wrapper applies defs + bg recolour together."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g><polygon fill="#05060f" stroke="transparent" points="0,0"/></g>'
        "</svg>"
    )
    out = post_process_stellaris_svg(svg)
    assert "<defs>" in out
    assert 'id="space-bg"' in out
    assert 'fill="url(#space-bg)"' in out


# ── CLI --format svg integration tests ───────────────────────────────────────


def _has_graphviz() -> bool:
    """Return True iff sfdp + dot are on PATH."""
    import shutil

    return shutil.which("sfdp") is not None and shutil.which("dot") is not None


def test_starmap_svg_invalid_format_rejected(tmp_path):
    """`--format` only accepts 'html', 'dot', 'svg'."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_bad_fmt")
    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--format", "garbage"])
    assert result.exit_code != 0
    assert "format" in result.output.lower()


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_stellaris_end_to_end(tmp_path):
    """`--format svg --theme stellaris` writes a paper-ready glowing SVG."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_stellaris")
    result = runner.invoke(
        app, ["inspect", "starmap", str(pkg_dir), "--format", "svg", "--theme", "stellaris"]
    )
    assert result.exit_code == 0, result.output

    out_path = pkg_dir / ".gaia" / "starmap.svg"
    assert out_path.exists()
    svg = out_path.read_text(encoding="utf-8")

    # Top-level structural sanity.
    assert svg.lstrip().startswith("<?xml") or svg.lstrip().startswith("<svg")
    assert "</svg>" in svg

    # Stellaris defs injected.
    assert "<defs>" in svg
    assert 'id="space-bg"' in svg
    assert 'id="contra-glow"' in svg
    assert 'id="support-glow"' in svg
    assert 'id="root-glow"' in svg

    # Style block ties class markers to filters.
    assert "filter: url(#contra-glow)" in svg
    assert "filter: url(#support-glow)" in svg
    assert "filter: url(#root-glow)" in svg

    # Background polygon repainted to the radial gradient.
    assert 'fill="url(#space-bg)"' in svg

    # The exported claim (★ root) carries the ``root`` class — Graphviz
    # prefixes its own ``node`` class so the rendered attribute is
    # ``class="node root"``. The CSS selector ``.root`` matches either way.
    assert re.search(r'class="[^"]*\broot\b[^"]*"', svg) is not None


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_stellaris_well_formed_xml(tmp_path):
    """The emitted SVG parses as valid XML (no broken regex surgery)."""
    import xml.etree.ElementTree as ET

    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_xml")
    result = runner.invoke(
        app, ["inspect", "starmap", str(pkg_dir), "--format", "svg", "--theme", "stellaris"]
    )
    assert result.exit_code == 0, result.output

    out_path = pkg_dir / ".gaia" / "starmap.svg"
    # ET.parse raises on malformed XML — that's the assertion.
    ET.parse(out_path)


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_dark_alias(tmp_path):
    """`--theme dark` produces the same stellaris SVG output."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_dark")
    result = runner.invoke(
        app, ["inspect", "starmap", str(pkg_dir), "--format", "svg", "--theme", "dark"]
    )
    assert result.exit_code == 0, result.output
    svg = (pkg_dir / ".gaia" / "starmap.svg").read_text(encoding="utf-8")
    assert "<defs>" in svg
    assert 'id="contra-glow"' in svg
    assert 'fill="url(#space-bg)"' in svg


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_light_no_defs(tmp_path):
    """Light theme SVG goes through `dot` and skips the stellaris post-process."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_light")
    result = runner.invoke(
        app, ["inspect", "starmap", str(pkg_dir), "--format", "svg", "--theme", "light"]
    )
    assert result.exit_code == 0, result.output

    svg = (pkg_dir / ".gaia" / "starmap.svg").read_text(encoding="utf-8")
    # No stellaris-specific glow filters or radial gradient.
    assert 'id="space-bg"' not in svg
    assert 'id="contra-glow"' not in svg
    assert 'id="support-glow"' not in svg
    assert 'id="root-glow"' not in svg
    # Still a valid SVG document.
    assert "</svg>" in svg


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_default_theme_is_light(tmp_path):
    """`--format svg` without `--theme` defaults to the light variant."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_default")
    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--format", "svg"])
    assert result.exit_code == 0, result.output
    svg = (pkg_dir / ".gaia" / "starmap.svg").read_text(encoding="utf-8")
    assert 'id="contra-glow"' not in svg


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_custom_out_path(tmp_path):
    """`--out` overrides the default `.gaia/starmap.svg` location."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_custom_out")
    custom = "figures/star.svg"
    result = runner.invoke(
        app,
        [
            "inspect",
            "starmap",
            str(pkg_dir),
            "--format",
            "svg",
            "--theme",
            "stellaris",
            "--out",
            custom,
        ],
    )
    assert result.exit_code == 0, result.output
    out_path = pkg_dir / custom
    assert out_path.exists()
    assert "<defs>" in out_path.read_text(encoding="utf-8")


def test_starmap_svg_graphviz_missing_error_message(tmp_path, monkeypatch):
    """When graphviz binaries are absent we get a clear actionable error."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_no_gv")

    # Pretend graphviz is missing for both `sfdp` and `dot`.
    import shutil

    real_which = shutil.which

    def fake_which(cmd, *args, **kwargs):
        if cmd in ("sfdp", "dot"):
            return None
        return real_which(cmd, *args, **kwargs)

    monkeypatch.setattr("shutil.which", fake_which)

    result = runner.invoke(
        app, ["inspect", "starmap", str(pkg_dir), "--format", "svg", "--theme", "stellaris"]
    )
    assert result.exit_code != 0
    msg = result.output.lower()
    assert "graphviz" in msg
    # The error names the missing binary so users know what to install.
    assert "sfdp" in result.output or "dot" in result.output


def test_to_dot_stellaris_strategy_labels_stripped():
    """In stellaris, strategy nodes are shape-only — no inline type text."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    # The fixture has both deduction and support strategies.
    for nid in ("strat_ded", "strat_sup"):
        line = _node_line(dot, nid)
        m = re.search(r'label="([^"]*)"', line)
        assert m and m.group(1) == "", f"{nid} expected empty label, got line: {line}"


def test_to_dot_stellaris_operator_labels_symbol_only():
    """In stellaris, operator nodes carry only the unicode symbol."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    expectations = {
        "op_contra": "⊗",
        "op_equiv": "⊙",
        "op_impl": "⊃",
        "op_compl": "¬",
        "op_disj": "∨",
        "op_conj": "∧",
    }
    for nid, sym in expectations.items():
        line = _node_line(dot, nid)
        m = re.search(r'label="([^"]*)"', line)
        assert m, line
        label = m.group(1)
        assert label == sym, f"{nid} label was {label!r}, expected {sym!r}"


def test_to_dot_light_strategy_label_keeps_type_name():
    """Light theme retains inline type names (paper-friendly default)."""
    dot = to_dot(_make_stellaris_fixture(), theme="light")
    # Deduction strategy text still shows in label.
    s_line = _node_line(dot, "strat_ded")
    assert 'label="deduction"' in s_line


def test_to_dot_light_operator_label_keeps_type_name():
    """Light theme keeps `symbol type` operator labels."""
    dot = to_dot(_make_stellaris_fixture(), theme="light")
    contra_line = _node_line(dot, "op_contra")
    assert "⊗ contradiction" in contra_line


def test_inject_legend_adds_block_before_svg_close():
    """Legend builder injects a `<g id="legend">` before `</svg>`."""
    from gaia.cli.commands._stellaris_svg import inject_legend

    minimal = '<svg xmlns="http://www.w3.org/2000/svg"><polygon/></svg>'
    out = inject_legend(minimal)
    assert '<g id="legend"' in out
    assert "节点角色" in out
    # Legend appears before </svg>.
    assert out.index('id="legend"') < out.index("</svg>")


def test_inject_legend_includes_all_node_role_rows():
    """Legend lists premise, derived, root, deduction, support, all 6 operator types."""
    from gaia.cli.commands._stellaris_svg import inject_legend

    out = inject_legend('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    # Knowledge boxes
    assert "premise" in out
    assert "derived" in out
    assert "root claim" in out
    # Strategies
    assert "deduction" in out
    assert "support" in out
    # All 6 operator types by symbol + name
    for sym in ("⊗", "⊙", "⊃", "¬", "∨", "∧"):
        assert sym in out
    for tname in (
        "contradiction",
        "equivalence",
        "implication",
        "complement",
        "disjunction",
        "conjunction",
    ):
        assert tname in out


def test_inject_legend_idempotent():
    """A second `inject_legend` call is a no-op."""
    from gaia.cli.commands._stellaris_svg import inject_legend

    once = inject_legend('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    twice = inject_legend(once)
    assert once == twice
    # And only one legend group ends up in the output.
    assert twice.count('id="legend"') == 1


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_stellaris_includes_legend(tmp_path):
    """End-to-end: `--format svg --theme stellaris` produces an SVG carrying the legend."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_legend")
    out = "the.svg"
    result = runner.invoke(
        app,
        [
            "inspect",
            "starmap",
            str(pkg_dir),
            "--format",
            "svg",
            "--theme",
            "stellaris",
            "--out",
            out,
        ],
    )
    assert result.exit_code == 0, result.output
    svg = (pkg_dir / out).read_text(encoding="utf-8")
    assert '<g id="legend"' in svg
    assert "节点角色" in svg


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_light_no_legend(tmp_path):
    """Light theme SVG does not include the stellaris legend block."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_light_no_legend")
    out = "the.svg"
    result = runner.invoke(
        app,
        ["inspect", "starmap", str(pkg_dir), "--format", "svg", "--theme", "light", "--out", out],
    )
    assert result.exit_code == 0, result.output
    svg = (pkg_dir / out).read_text(encoding="utf-8")
    assert 'id="legend"' not in svg


# ── starmap-replay smoke tests (lift codecov patch coverage on PR #536) ─────


def test_replay_load_template_carries_placeholder():
    """The shipped HTML template includes the timeline-data placeholder marker."""
    from gaia.cli.commands.starmap_replay import TIMELINE_PLACEHOLDER, _load_template

    template = _load_template()
    assert TIMELINE_PLACEHOLDER in template


def test_replay_render_html_injects_payload():
    """`_render_html` substitutes the placeholder with a window.TIMELINE_DATA assignment."""
    from gaia.cli.commands.starmap_replay import _render_html

    template = "<html><body><!--__TIMELINE_DATA__--></body></html>"
    out = _render_html(template, '{"hello": "world"}')
    assert "<!--__TIMELINE_DATA__-->" not in out
    assert 'window.TIMELINE_DATA = {"hello": "world"};' in out


def test_replay_render_html_raises_when_placeholder_missing():
    """Verify replay render html raises when placeholder missing.

    Templates without the placeholder are rejected loudly — silent failure would leave the
    frontend with no timeline data.
    """
    from gaia.cli.commands.starmap_replay import _render_html

    with pytest.raises(RuntimeError, match="placeholder"):
        _render_html("<html>no marker</html>", "{}")


def test_replay_read_jsonl_skips_blank_lines(tmp_path):
    """`_read_jsonl` returns one dict per non-blank line."""
    from gaia.cli.commands.starmap_replay import _read_jsonl

    p = tmp_path / "log.jsonl"
    p.write_text('{"a": 1}\n\n   \n{"b": 2}\n', encoding="utf-8")
    events = _read_jsonl(p)
    assert events == [{"a": 1}, {"b": 2}]


def test_replay_read_jsonl_raises_on_invalid_json(tmp_path):
    """A malformed JSONL line surfaces as a typer.BadParameter with the line number."""
    import typer

    from gaia.cli.commands.starmap_replay import _read_jsonl

    p = tmp_path / "bad.jsonl"
    p.write_text('{"ok": 1}\n{not json\n', encoding="utf-8")
    with pytest.raises(typer.BadParameter, match="line 2"):
        _read_jsonl(p)


def test_replay_is_replayable_filters_retries_and_failures():
    """Replay drops retry / failed-retrieval events, keeps normal ones."""
    from gaia.cli.commands.starmap_replay import _is_replayable

    assert _is_replayable({"event_id": "e1"}) is True
    assert _is_replayable({"retry_of_event_id": "e0"}) is False
    assert _is_replayable({"decision": "retry"}) is False
    assert _is_replayable({"response_code": 500}) is False
    # response_code 0 / None are healthy.
    assert _is_replayable({"response_code": 0}) is True
    assert _is_replayable({"response_code": None}) is True


def test_replay_validate_schema_warns_on_version_mismatch():
    """Events whose schema_version != "1" each produce a warning."""
    from gaia.cli.commands.starmap_replay import _validate_schema

    events = [
        {"event_id": "ok", "schema_version": "1"},
        {"event_id": "old", "schema_version": "0"},
        {"event_id": "missing"},
    ]
    warnings = _validate_schema(events, "src.jsonl")
    # Two events deviate from "1"; one matches.
    assert len(warnings) == 2
    assert any("'old'" in w or "old" in w for w in warnings)


def test_replay_merge_events_tags_and_sorts():
    """`merge_events` tags each event with `event_kind` and sorts stably."""
    from gaia.cli.commands.starmap_replay import merge_events

    retrievals = [
        {"actor_id": "a", "seq": 1, "timestamp_utc": "2026-05-05T00:00:01.000Z"},
    ]
    growths = [
        {"actor_id": "a", "seq": 0, "timestamp_utc": "2026-05-05T00:00:00.000Z"},
    ]
    merged = merge_events(retrievals, growths)
    assert [e["event_kind"] for e in merged] == ["growth", "retrieval"]
    assert [e["timestamp_utc"] for e in merged] == [
        "2026-05-05T00:00:00.000Z",
        "2026-05-05T00:00:01.000Z",
    ]
    # Caller's lists must not be mutated (shallow-copy contract).
    assert "event_kind" not in retrievals[0]
    assert "event_kind" not in growths[0]


def test_replay_parse_pos_and_bb_helpers():
    """`_parse_pos`/`_parse_bb` accept canonical Graphviz strings, reject junk."""
    from gaia.cli.commands._replay_build import _parse_bb, _parse_pos

    assert _parse_pos("1.5,2.0") == (1.5, 2.0)
    # Pinned positions carry a trailing `!`.
    assert _parse_pos("3.0,4.0!") == (3.0, 4.0)
    assert _parse_pos("") is None
    assert _parse_pos("only-one") is None
    assert _parse_pos("a,b") is None

    assert _parse_bb("0,0,100,200") == (0.0, 0.0, 100.0, 200.0)
    assert _parse_bb("") is None
    assert _parse_bb("0,0,100") is None
    assert _parse_bb("a,b,c,d") is None


def test_replay_compute_round_beliefs_empty_ir_returns_empty():
    """`compute_round_beliefs` short-circuits to {} when the IR has no knowledges."""
    from gaia.cli.commands._replay_build import compute_round_beliefs

    assert compute_round_beliefs({}, [{"round_id": "r0"}]) == {}
    assert compute_round_beliefs({"knowledges": []}, [{"round_id": "r0"}]) == {}


def test_replay_compute_dot_layout_parses_canned_json(monkeypatch):
    """Verify replay compute dot layout parses canned json.

    `compute_dot_layout` consumes Graphviz `-Tjson0` output: nodes get y-flipped cluster
    bounding boxes flatten into the clusters list.
    """
    import subprocess as _subprocess

    from gaia.cli.commands import _replay_build as rb

    canned = {
        "bb": "0,0,400,200",
        "objects": [
            # A cluster carries a `nodes` list (indices into objects).
            {
                "name": "cluster_pkg_module",
                "label": "module",
                "bb": "10,10,90,90",
                "lp": "50,50",
                "nodes": [1],
            },
            # Plain node.
            {"name": "ns:pkg::node", "pos": "30,180"},
            # Another node, no `nodes` key, default-named.
            {"name": "strat_0", "pos": "100,150!"},
        ],
    }

    class _FakeProc:
        def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
            self.stdout = stdout
            self.returncode = returncode
            self.stderr = stderr

    def _fake_run(cmd, **kwargs):
        del cmd
        # Caller passes the dot source via stdin.
        assert kwargs.get("input")
        return _FakeProc(json.dumps(canned))

    monkeypatch.setattr(rb.shutil, "which", lambda _: "/usr/bin/dot")
    monkeypatch.setattr(_subprocess, "run", _fake_run)
    monkeypatch.setattr(rb.subprocess, "run", _fake_run)

    layout = rb.compute_dot_layout("digraph { a -> b }")
    assert layout["viewport"] == {"width": 400.0, "height": 200.0}
    # y-flip: y' = bb_y_max - y → 200 - 180 = 20, 200 - 150 = 50.
    assert layout["nodes"]["ns:pkg::node"] == {"x": 30.0, "y": 20.0}
    assert layout["nodes"]["strat_0"] == {"x": 100.0, "y": 50.0}
    # One cluster, with flipped bb.
    assert len(layout["clusters"]) == 1
    cluster = layout["clusters"][0]
    assert cluster["name"] == "cluster_pkg_module"
    assert cluster["w"] == 80.0 and cluster["h"] == 80.0


def test_replay_compute_dot_layout_raises_when_dot_missing(monkeypatch):
    """Without the `dot` binary on PATH, `compute_dot_layout` raises FileNotFoundError."""
    from gaia.cli.commands import _replay_build as rb

    monkeypatch.setattr(rb.shutil, "which", lambda _: None)
    with pytest.raises(FileNotFoundError, match="Graphviz"):
        rb.compute_dot_layout("digraph { a -> b }")


# ── starmap-replay CLI smoke tests against the bundled fixture ──────────────


_STARMAP_REPLAY_FIXTURE = (
    __import__("pathlib").Path(__file__).resolve().parents[1]
    / "fixtures"
    / "starmap_replay"
    / "mendelian_inheritance"
)


def test_starmap_replay_cli_smoke(tmp_path):
    """End-to-end: the bundled fixture renders to a self-contained HTML file."""
    if not _STARMAP_REPLAY_FIXTURE.is_dir():
        pytest.skip(f"replay fixture not present at {_STARMAP_REPLAY_FIXTURE}")
    out_path = tmp_path / "replay.html"
    result = runner.invoke(
        app,
        ["inspect", "starmap-replay", str(_STARMAP_REPLAY_FIXTURE), "--out", str(out_path)],
    )
    assert result.exit_code == 0, result.output
    html = out_path.read_text(encoding="utf-8")
    assert "window.TIMELINE_DATA" in html
    # Schema version baked into the payload.
    payload_match = re.search(r"window\.TIMELINE_DATA = (.*?);</script>", html, re.DOTALL)
    assert payload_match is not None
    payload = json.loads(payload_match.group(1))
    assert payload["schema_version"] == "1"
    assert payload["retrieval_count"] == 7
    assert payload["growth_count"] == 35


def test_starmap_replay_cli_rejects_non_directory(tmp_path):
    """Replaying against a file (not a package directory) fails with exit code 1."""
    f = tmp_path / "not_a_dir"
    f.write_text("hello", encoding="utf-8")
    result = runner.invoke(app, ["inspect", "starmap-replay", str(f)])
    assert result.exit_code == 1
    assert "is not a directory" in result.output


def test_starmap_replay_cli_reports_missing_logs(tmp_path):
    """Replaying a directory missing its lkm-discovery JSONL logs surfaces both paths."""
    pkg_dir = tmp_path / "empty_pkg"
    pkg_dir.mkdir()
    result = runner.invoke(app, ["inspect", "starmap-replay", str(pkg_dir)])
    assert result.exit_code == 1
    assert "missing timeline log" in result.output
    assert "graph_growth_log.jsonl" in result.output
    assert "retrieval_log.jsonl" in result.output


def test_replay_compute_round_beliefs_runs_inference_on_synthetic_ir():
    """Verify replay compute round beliefs runs inference on synthetic ir.

    Two-claim IR + lkm-driven events: each round's truncation runs through the BP engine and
    beliefs land at the priors (no edges).
    """
    from gaia.cli.commands._replay_build import compute_round_beliefs

    ir = {
        "namespace": "test",
        "package_name": "replay_smoke",
        "scope": "local",
        "knowledges": [
            {
                "id": "test:replay_smoke::a",
                "type": "claim",
                "metadata": {"lkm_id": "gcn_a", "prior": 0.5},
            },
            {
                # No lkm_id → always-present.
                "id": "test:replay_smoke::b",
                "type": "claim",
                "metadata": {"prior": 0.3},
            },
        ],
        "operators": [],
        "strategies": [],
    }
    events = [
        {"round_id": "r0", "graph_delta": {"nodes_added": [{"lkm_id": "gcn_a"}]}},
    ]
    beliefs = compute_round_beliefs(ir, events)
    assert "r0" in beliefs
    # Always-present + admitted-this-round both surface in the round table.
    assert "test:replay_smoke::a" in beliefs["r0"]
    assert "test:replay_smoke::b" in beliefs["r0"]
    # Disconnected priors → beliefs equal priors.
    assert abs(beliefs["r0"]["test:replay_smoke::a"] - 0.5) < 1e-6
    assert abs(beliefs["r0"]["test:replay_smoke::b"] - 0.3) < 1e-6


def test_replay_annotate_ticks_with_survival_no_layout_marks_all_true():
    """Without IR / layout context, every tick defaults to survives_to_final=True."""
    from gaia.cli.commands._replay_build import annotate_ticks_with_survival

    ticks = [
        {"action": {"action": "claim", "symbol": "x"}, "tick_index": 0, "event_id": "e1"},
        {"action": {"action": "deduction", "symbol": "y"}, "tick_index": 1, "event_id": "e2"},
    ]
    out, warns = annotate_ticks_with_survival(ticks, [], None, None)
    assert all(t["survives_to_final"] is True for t in out)
    assert warns == []


def test_replay_topo_reorder_short_circuits_without_context():
    """`topo_reorder_ticks` returns ticks untouched when layout / ir is missing."""
    from gaia.cli.commands._replay_build import topo_reorder_ticks

    ticks = [
        {"tick_index": 0, "action": {"action": "claim", "symbol": "x"}},
        {"tick_index": 1, "action": {"action": "claim", "symbol": "y"}},
    ]
    out, warns = topo_reorder_ticks(list(ticks), [], None, None)
    assert out == ticks
    assert warns == []


def test_replay_collect_round_order_dedup_preserves_first_appearance():
    """`collect_round_order` returns each round_id once, in arrival order."""
    from gaia.cli.commands._replay_build import collect_round_order

    events = [
        {"round_id": "r0"},
        {"round_id": "r1"},
        {"round_id": "r0"},
        {},  # No round_id — ignored.
        {"round_id": "r2"},
        {"round_id": "r1"},
    ]
    assert collect_round_order(events) == ["r0", "r1", "r2"]


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_replay_cli_with_real_package_triggers_layout_pipeline(tmp_path):
    """Verify starmap replay cli with real package triggers layout pipeline.

    End-to-end: a compiled package + the bundled fixture's logs exercises the full pipeline (dot
    layout, IR-side annotation, round beliefs).

    This is a smoke test — we don't assert the layout *contents* (those depend
    on the package's specific IR), only that the pipeline emits a payload with
    a non-None final_layout when graphviz is available.
    """
    import shutil as _shutil

    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_replay_real")

    # Splat the bundled fixture's logs into the package's expected artifacts dir.
    artifacts = pkg_dir / "artifacts" / "lkm-discovery"
    artifacts.mkdir(parents=True, exist_ok=True)
    fixture = _STARMAP_REPLAY_FIXTURE / "artifacts" / "lkm-discovery"
    if not fixture.is_dir():
        pytest.skip(f"replay fixture not present at {fixture}")
    _shutil.copy(fixture / "graph_growth_log.jsonl", artifacts / "graph_growth_log.jsonl")
    _shutil.copy(fixture / "retrieval_log.jsonl", artifacts / "retrieval_log.jsonl")

    out_path = tmp_path / "real_replay.html"
    result = runner.invoke(
        app,
        ["inspect", "starmap-replay", str(pkg_dir), "--out", str(out_path)],
    )
    assert result.exit_code == 0, result.output
    html = out_path.read_text(encoding="utf-8")
    payload_match = re.search(r"window\.TIMELINE_DATA = (.*?);</script>", html, re.DOTALL)
    assert payload_match is not None
    payload = json.loads(payload_match.group(1))
    # With graphviz + a compiled IR, final_layout pins are populated.
    assert payload["final_layout"] is not None
    assert "viewport" in payload["final_layout"]
    assert isinstance(payload["final_layout"].get("nodes"), dict)
    # round_beliefs is a dict keyed by round_id (may be empty per round if the
    # fixture's lkm_ids don't intersect the demo package's IR).
    assert isinstance(payload["round_beliefs"], dict)


# ── starmap CLI error-branch tests (lift codecov patch coverage on PR #536) ──


def test_starmap_invalid_format_rejects_with_exit_2(tmp_path):
    """`--format` outside the allow-list exits 2 with a helpful message."""
    pkg_dir = tmp_path / "starmap_bad_fmt"
    _write_base_package(pkg_dir, name="starmap_bad_fmt")
    _write_minimal_source(pkg_dir, "starmap_bad_fmt")

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--format", "pdf"])
    assert result.exit_code == 2
    assert "--format must be one of" in result.output


def test_starmap_invalid_theme_rejects_with_exit_2(tmp_path):
    """`--theme` outside the allow-list exits 2 with a helpful message."""
    pkg_dir = tmp_path / "starmap_bad_theme"
    _write_base_package(pkg_dir, name="starmap_bad_theme")
    _write_minimal_source(pkg_dir, "starmap_bad_theme")

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir), "--theme", "neon"])
    assert result.exit_code == 2
    assert "--theme must be one of" in result.output


def test_starmap_stale_ir_hash_errors(tmp_path):
    """A mismatching `.gaia/ir_hash` triggers a stale-artifacts error."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_stale_hash")
    # Corrupt the recorded ir_hash so the freshness gate fires.
    (pkg_dir / ".gaia" / "ir_hash").write_text("not-the-real-hash\n")

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code == 1
    assert "stale" in result.output


def test_starmap_corrupt_ir_json_errors(tmp_path):
    """An ir.json file with invalid JSON surfaces a clear error message."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_bad_ir_json")
    (pkg_dir / ".gaia" / "ir.json").write_text("{ this is not json")

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code == 1
    assert "ir.json is not valid JSON" in result.output


def test_starmap_corrupt_beliefs_json_errors(tmp_path):
    """An invalid beliefs.json surfaces the parse error and exits non-zero."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_bad_beliefs_json")
    (pkg_dir / ".gaia" / "beliefs.json").write_text("{ broken")

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code == 1
    assert "beliefs.json" in result.output and "not valid JSON" in result.output


def test_starmap_stale_beliefs_errors(tmp_path):
    """Beliefs whose ir_hash doesn't match compile output prompt `gaia infer` again."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_stale_beliefs")
    beliefs_path = pkg_dir / ".gaia" / "beliefs.json"
    data = json.loads(beliefs_path.read_text())
    data["ir_hash"] = "wrong-hash"
    beliefs_path.write_text(json.dumps(data))

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code == 1
    assert "beliefs are stale" in result.output


def test_starmap_render_html_missing_placeholder_via_monkeypatch(tmp_path, monkeypatch):
    """When the template lacks the GRAPH_DATA placeholder, starmap exits 1."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_bad_template")
    from gaia.cli.commands import starmap as starmap_mod

    monkeypatch.setattr(starmap_mod, "_load_template", lambda: "<html>no marker</html>")
    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code == 1
    assert "placeholder" in result.output


# ── starmap-replay error-branch tests ──────────────────────────────────────


def test_starmap_replay_missing_template_exits_1(tmp_path, monkeypatch):
    """A template with no placeholder triggers the RuntimeError → exit 1 path."""
    from gaia.cli.commands import starmap_replay as sr

    monkeypatch.setattr(sr, "_load_template", lambda: "<html>no marker</html>")

    result = runner.invoke(
        app,
        [
            "inspect",
            "starmap-replay",
            str(_STARMAP_REPLAY_FIXTURE),
            "--out",
            str(tmp_path / "x.html"),
        ],
    )
    assert result.exit_code == 1
    assert "placeholder" in result.output


def test_starmap_replay_validates_schema_warning_lines(tmp_path):
    """Schema-version warnings surface to stdout when fixture events deviate."""
    pkg_dir = tmp_path / "schema_warn_pkg"
    pkg_dir.mkdir()
    artifacts = pkg_dir / "artifacts" / "lkm-discovery"
    artifacts.mkdir(parents=True)
    # One event with non-"1" schema_version per log → two `Warning:` lines.
    (artifacts / "graph_growth_log.jsonl").write_text(
        '{"event_id": "e1", "schema_version": "2"}\n', encoding="utf-8"
    )
    (artifacts / "retrieval_log.jsonl").write_text(
        '{"event_id": "r1", "schema_version": "0"}\n', encoding="utf-8"
    )

    out_path = tmp_path / "out.html"
    result = runner.invoke(app, ["inspect", "starmap-replay", str(pkg_dir), "--out", str(out_path)])
    assert result.exit_code == 0, result.output
    assert "Warning:" in result.output
    assert "schema_version" in result.output


# ── _replay_build helper unit tests ────────────────────────────────────────


def test_replay_split_into_ir_ticks_filters_non_ir_actions():
    """`split_into_ir_ticks` keeps only IR-relevant actions and stamps lkm_driven."""
    from gaia.cli.commands._replay_build import split_into_ir_ticks

    events = [
        # Two IR-relevant actions + one non-IR (`metadata_update`) inside the
        # same event. `retrieval_event_ids` populated → `lkm_driven=True`.
        {
            "event_id": "e0",
            "round_id": "r0",
            "retrieval_event_ids": ["ret_1"],
            "gaia_actions": [
                {"action": "claim", "symbol": "gcn_a"},
                {"action": "metadata_update", "symbol": "gcn_a"},
                {"action": "deduction", "symbol": "gfac_x"},
            ],
        },
        # Empty actions → contributes zero ticks.
        {"event_id": "e1", "gaia_actions": []},
        # Non-list actions value → skipped.
        {"event_id": "e2", "gaia_actions": "not-a-list"},
        # Non-dict action entries → skipped.
        {"event_id": "e3", "gaia_actions": ["not a dict", {"action": "claim", "symbol": "gcn_b"}]},
    ]
    ticks = split_into_ir_ticks(events)
    assert [t["action_index"] for t in ticks] == [0, 2, 1]
    assert [t["action"]["action"] for t in ticks] == ["claim", "deduction", "claim"]
    assert ticks[0]["lkm_driven"] is True
    assert ticks[0]["round_id"] == "r0"
    assert ticks[2]["lkm_driven"] is False  # event e3 had no retrieval_event_ids
    # Global tick_index runs 0..N-1.
    assert [t["tick_index"] for t in ticks] == [0, 1, 2]


def test_replay_rekey_layout_to_lkm_ids_remaps_and_warns_on_duplicates():
    """`rekey_layout_to_lkm_ids` moves entries by lkm_id; collisions warn."""
    from gaia.cli.commands._replay_build import rekey_layout_to_lkm_ids

    layout = {
        "nodes": {
            "ns:pkg::a": {"x": 1.0, "y": 2.0},
            "ns:pkg::b": {"x": 3.0, "y": 4.0},
            "ns:pkg::c": {"x": 5.0, "y": 6.0},  # No lkm_id → key kept.
            "strat_0": {"x": 7.0, "y": 8.0},  # Strategy keys untouched.
        }
    }
    ir = {
        "knowledges": [
            {"id": "ns:pkg::a", "metadata": {"lkm_id": "gcn_a"}},
            # Two IR ids claim the same lkm_id → one warning, second ignored.
            {"id": "ns:pkg::b", "metadata": {"lkm_id": "gcn_dup"}},
            {"id": "ns:pkg::other", "metadata": {"lkm_id": "gcn_dup"}},
            {"id": "ns:pkg::c", "metadata": {}},  # No lkm_id → fall through.
        ]
    }
    out, warns = rekey_layout_to_lkm_ids(layout, ir)
    nodes = out["nodes"]
    assert nodes["gcn_a"] == {"x": 1.0, "y": 2.0}
    assert nodes["gcn_dup"] == {"x": 3.0, "y": 4.0}
    # No-lkm and strategy keys preserved.
    assert nodes["ns:pkg::c"] == {"x": 5.0, "y": 6.0}
    assert nodes["strat_0"] == {"x": 7.0, "y": 8.0}
    assert any("duplicate lkm_id" in w for w in warns)


def test_replay_rekey_layout_returns_early_on_empty_inputs():
    """Empty layout / ir / non-dict nodes short-circuit cleanly."""
    from gaia.cli.commands._replay_build import rekey_layout_to_lkm_ids

    assert rekey_layout_to_lkm_ids({}, {}) == ({}, [])
    out, warns = rekey_layout_to_lkm_ids({"nodes": "not-a-dict"}, {"knowledges": []})
    assert out == {"nodes": "not-a-dict"}
    assert warns == []


def test_replay_annotate_layout_with_kinds_decorates_strategy_operator_knowledge():
    """`annotate_layout_with_kinds` stamps `kind`, `label`, conclusion/premise refs."""
    from gaia.cli.commands._replay_build import annotate_layout_with_kinds

    layout = {
        "nodes": {
            "gcn_premise": {"x": 1.0, "y": 1.0},
            "gcn_concl": {"x": 2.0, "y": 2.0},
            "strat_0": {"x": 3.0, "y": 3.0},
            "oper_0": {"x": 4.0, "y": 4.0},
            "oper_99": {"x": 5.0, "y": 5.0},  # Out-of-range index → skipped.
            "strat_bogus": {"x": 6.0, "y": 6.0},  # Non-int suffix → skipped.
            "non_dict_value": "scalar",  # Not a dict → skipped.
        }
    }
    ir = {
        "knowledges": [
            {
                "id": "ns:pkg::premise",
                "title": "premise label",
                "metadata": {"lkm_id": "gcn_premise", "prior": 0.6},
                "module": "m",
            },
            {
                "id": "ns:pkg::concl",
                "title": "conclusion",
                "metadata": {"lkm_id": "gcn_concl"},
                "exported": True,
                "module": "m",
            },
        ],
        "strategies": [
            {
                "type": "deduction",
                "premises": ["ns:pkg::premise"],
                "conclusion": "ns:pkg::concl",
            }
        ],
        "operators": [
            {
                "operator": "contradiction",
                "variables": ["ns:pkg::premise"],
                "conclusion": "ns:pkg::concl",
            }
        ],
    }
    out = annotate_layout_with_kinds(layout, ir)
    nodes = out["nodes"]
    # Strategy decoration.
    assert nodes["strat_0"]["kind"] == "strategy"
    assert nodes["strat_0"]["strategy_type"] == "deduction"
    assert nodes["strat_0"]["conclusion_id"] == "gcn_concl"
    assert nodes["strat_0"]["premise_ids"] == ["gcn_premise"]
    # Operator decoration with contradiction label.
    assert nodes["oper_0"]["kind"] == "operator"
    assert "contradiction" in nodes["oper_0"]["label"]
    assert nodes["oper_0"]["conclusion_id"] == "gcn_concl"
    assert nodes["oper_0"]["variable_ids"] == ["gcn_premise"]
    # Knowledge decoration: post-rekey lookup via lkm_id.
    assert nodes["gcn_premise"]["kind"] == "knowledge"
    assert nodes["gcn_premise"]["sub_kind"] == "claim"
    assert nodes["gcn_premise"]["prior"] == 0.6
    # Exported knowledge → ★ prefix in label, sub_kind = exported.
    assert nodes["gcn_concl"]["sub_kind"] == "exported"
    assert nodes["gcn_concl"]["label"].startswith("★ ")
    # Out-of-range / non-int strategy / non-dict entries left untouched (no
    # `kind` stamp).
    assert "kind" not in nodes["oper_99"]
    assert "kind" not in nodes["strat_bogus"]


def test_replay_annotate_layout_with_kinds_returns_early_on_empty_inputs():
    """Empty layout / ir / non-dict nodes short-circuit cleanly."""
    from gaia.cli.commands._replay_build import annotate_layout_with_kinds

    assert annotate_layout_with_kinds({}, {"knowledges": []}) == {}
    assert annotate_layout_with_kinds({"nodes": "scalar"}, {"knowledges": []}) == {
        "nodes": "scalar"
    }


def test_replay_collect_round_lkm_membership_is_cumulative():
    """`collect_round_lkm_membership` returns a monotone-by-round cumulative set."""
    from gaia.cli.commands._replay_build import collect_round_lkm_membership

    events = [
        {"round_id": "r0", "graph_delta": {"nodes_added": [{"lkm_id": "gcn_a"}]}},
        {"round_id": "r0", "graph_delta": {"nodes_added": [{"lkm_id": "gcn_b"}]}},
        # Helper claim with no lkm_id — does not contribute.
        {"round_id": "r0", "graph_delta": {"nodes_added": [{"id": "__impl_x"}]}},
        {"round_id": "r1", "graph_delta": {"nodes_added": [{"lkm_id": "gcn_c"}]}},
        # An event without round_id (orchestrator marker) — ignored.
        {"graph_delta": {"nodes_added": [{"lkm_id": "gcn_orphan"}]}},
        {"round_id": "r2"},  # No graph_delta — closes round monotonically.
    ]
    out = collect_round_lkm_membership(events)
    assert out["r0"] == {"gcn_a", "gcn_b"}
    assert out["r1"] == {"gcn_a", "gcn_b", "gcn_c"}
    assert out["r2"] == {"gcn_a", "gcn_b", "gcn_c"}


def test_replay_truncated_canonical_graph_filters_to_kept_ids():
    """Verify replay truncated canonical graph filters to kept ids.

    `_truncated_canonical_graph` returns None when the kept set is empty or the result fails
    Pydantic validation; happy path keeps survivors.
    """
    from gaia.cli.commands._replay_build import _truncated_canonical_graph

    # Knowledge-only IR (no strategies / operators) avoids pydantic surface
    # area and exercises the drop-when-not-in-keep filter directly.
    ir = {
        "namespace": "test",
        "package_name": "trunc",
        "scope": "local",
        "knowledges": [
            {"id": "test:trunc::a", "type": "claim", "metadata": {"prior": 0.5}},
            {"id": "test:trunc::b", "type": "claim", "metadata": {"prior": 0.5}},
            {"id": "test:trunc::c", "type": "claim", "metadata": {"prior": 0.5}},
        ],
        "operators": [],
        "strategies": [],
    }
    keep = {"test:trunc::a", "test:trunc::b"}
    canonical = _truncated_canonical_graph(ir, keep)
    assert canonical is not None
    # Only the kept knowledges land in the truncated graph (c is dropped).
    kept_ids = {k.id for k in canonical.knowledges}
    assert kept_ids == keep

    # Empty keep set → None (no claim survives).
    assert _truncated_canonical_graph(ir, set()) is None

    # Pydantic-failure path: a malformed knowledge dict that survives the
    # filter but fails LocalCanonicalGraph validation → returns None.
    bad_ir = {
        "namespace": "test",
        "package_name": "bad",
        "scope": "local",
        "knowledges": [{"id": "test:bad::a"}],  # Missing required fields.
        "operators": [],
        "strategies": [],
    }
    assert _truncated_canonical_graph(bad_ir, {"test:bad::a"}) is None


def test_replay_annotate_ticks_with_survival_marks_orphans():
    """Verify replay annotate ticks with survival marks orphans.

    Ticks whose `action.symbol` doesn't resolve to the final IR get `survives_to_final=False`
    plus a warning.
    """
    from gaia.cli.commands._replay_build import annotate_ticks_with_survival

    layout = {
        "nodes": {
            "gcn_a": {"x": 1.0, "y": 1.0, "kind": "knowledge"},
            "strat_0": {"x": 2.0, "y": 2.0, "kind": "strategy"},
        }
    }
    ir = {
        "knowledges": [{"id": "ns:pkg::a", "metadata": {"lkm_id": "gcn_a"}}],
        "strategies": [{"type": "deduction", "premises": ["ns:pkg::a"], "conclusion": "ns:pkg::a"}],
        "operators": [],
    }
    ticks = [
        # Surviving claim (gcn_a is in the IR).
        {
            "tick_index": 0,
            "event_index": 0,
            "event_id": "e0",
            "action": {"action": "claim", "symbol": "gcn_a"},
        },
        # Orphan claim — symbol not in IR.
        {
            "tick_index": 1,
            "event_index": 0,
            "event_id": "e0",
            "action": {"action": "claim", "symbol": "gcn_phantom"},
        },
        # Surviving deduction (strat_0 is in layout).
        {
            "tick_index": 2,
            "event_index": 0,
            "event_id": "e0",
            "action": {"action": "deduction", "symbol": "strat_0"},
        },
        # Orphan deduction — symbol not bridged to any strategy.
        {
            "tick_index": 3,
            "event_index": 0,
            "event_id": "e0",
            "action": {"action": "deduction", "symbol": "gfac_phantom"},
        },
        # Symbol-less deduction → defaults to surviving.
        {
            "tick_index": 4,
            "event_index": 0,
            "event_id": "e0",
            "action": {"action": "deduction"},
        },
        # `prior` action with no payload candidates → surviving (no targets).
        {
            "tick_index": 5,
            "event_index": 0,
            "event_id": "e0",
            "action": {"action": "prior"},
        },
        # `metadata_update` is non-IR but if it slips in still defaults True.
        {
            "tick_index": 6,
            "event_index": 0,
            "event_id": "e0",
            "action": {"action": "metadata_update", "symbol": "anything"},
        },
    ]
    events = [{"event_id": "e0", "graph_delta": {"edges_added": []}, "payload": {}}]
    out, warns = annotate_ticks_with_survival(ticks, events, layout, ir)
    survives = {t["tick_index"]: t["survives_to_final"] for t in out}
    assert survives[0] is True
    assert survives[1] is False
    assert survives[2] is True
    assert survives[3] is False
    assert survives[4] is True
    assert survives[5] is True
    assert survives[6] is True
    # One warning per orphan tick (two here).
    assert len(warns) == 2
    assert all("orphan IR-tick" in w for w in warns)


def test_replay_annotate_ticks_with_survival_skips_when_layout_nodes_not_dict():
    """A malformed layout (`nodes` not a dict) defaults every tick to surviving."""
    from gaia.cli.commands._replay_build import annotate_ticks_with_survival

    ticks = [{"tick_index": 0, "action": {"action": "claim", "symbol": "x"}}]
    out, warns = annotate_ticks_with_survival(ticks, [], {"nodes": "scalar"}, {"knowledges": []})
    assert out[0]["survives_to_final"] is True
    assert warns == []


def test_replay_bridge_event_symbols_to_layout_aliases_strat_via_edge_signature():
    """Verify replay bridge event symbols to layout aliases strat via edge signature.

    An event whose deduction edge matches an IR strategy's lkm-id signature aliases ``gfac_*``
    to ``strat_<i>`` and stamps `canonical_id`.
    """
    from gaia.cli.commands._replay_build import bridge_event_symbols_to_layout

    layout = {
        "nodes": {
            "gcn_premise": {"x": 1.0, "y": 1.0},
            "gcn_concl": {"x": 2.0, "y": 2.0},
            "strat_0": {"x": 3.0, "y": 3.0},
        }
    }
    ir = {
        "knowledges": [
            {"id": "ns:pkg::premise", "metadata": {"lkm_id": "gcn_premise"}},
            {"id": "ns:pkg::concl", "metadata": {"lkm_id": "gcn_concl"}},
        ],
        "strategies": [
            {
                "type": "deduction",
                "premises": ["ns:pkg::premise"],
                "conclusion": "ns:pkg::concl",
            }
        ],
        "operators": [],
    }
    events = [
        {
            "event_id": "e0",
            "gaia_actions": [{"action": "deduction", "symbol": "gfac_x"}],
            "graph_delta": {
                "edges_added": [
                    {"kind": "deduction", "from": "gcn_premise", "to": "gcn_concl"},
                ]
            },
        }
    ]
    out, _warns = bridge_event_symbols_to_layout(layout, ir, events)
    nodes = out["nodes"]
    # The event-side gfac_x now has a layout entry aliased from strat_0.
    assert "gfac_x" in nodes
    assert nodes["gfac_x"]["canonical_id"] == "strat_0"
    # The original strat_0 entry got stamped too, so dedupe works.
    assert nodes["strat_0"]["canonical_id"] == "strat_0"


def test_replay_bridge_event_symbols_to_layout_returns_early_on_empties():
    """Empty layout / ir / events all short-circuit to (layout, [])."""
    from gaia.cli.commands._replay_build import bridge_event_symbols_to_layout

    out, warns = bridge_event_symbols_to_layout({}, {}, [])
    assert out == {} and warns == []
    out, warns = bridge_event_symbols_to_layout({"nodes": "scalar"}, {"x": 1}, [{"e": 1}])
    assert out == {"nodes": "scalar"} and warns == []


def test_replay_topo_reorder_ticks_preserves_chronology_when_no_dep_pressure():
    """With no IR / layout dependency pressure, reorder is a no-op."""
    from gaia.cli.commands._replay_build import topo_reorder_ticks

    ticks = [
        {
            "tick_index": 0,
            "action": {"action": "claim", "symbol": "x"},
            "survives_to_final": True,
        },
        {
            "tick_index": 1,
            "action": {"action": "claim", "symbol": "y"},
            "survives_to_final": True,
        },
    ]
    layout = {"nodes": {"x": {"kind": "knowledge"}, "y": {"kind": "knowledge"}}}
    ir = {"knowledges": [], "strategies": [], "operators": []}
    out, warns = topo_reorder_ticks(list(ticks), [], layout, ir)
    # Two pure claims with no deps — order is preserved.
    assert [t["action"]["symbol"] for t in out] == ["x", "y"]
    assert warns == []


def test_replay_topo_reorder_ticks_swaps_premature_strategy():
    """Verify replay topo reorder ticks swaps premature strategy.

    A strategy tick fired before its premise/conclusion claims should be moved past those claims
    by the topo reorder.
    """
    from gaia.cli.commands._replay_build import topo_reorder_ticks

    layout = {
        "nodes": {
            "gcn_p": {"x": 0.0, "y": 0.0, "kind": "knowledge"},
            "gcn_c": {"x": 1.0, "y": 0.0, "kind": "knowledge"},
            "strat_0": {"x": 2.0, "y": 0.0, "kind": "strategy"},
        }
    }
    ir = {
        "knowledges": [
            {"id": "ns:pkg::p", "metadata": {"lkm_id": "gcn_p"}},
            {"id": "ns:pkg::c", "metadata": {"lkm_id": "gcn_c"}},
        ],
        "strategies": [
            {
                "type": "deduction",
                "premises": ["ns:pkg::p"],
                "conclusion": "ns:pkg::c",
            }
        ],
        "operators": [],
    }
    # Chronological order: strategy fires before either claim is admitted.
    ticks = [
        {
            "tick_index": 0,
            "event_index": 0,
            "action": {"action": "deduction", "symbol": "strat_0"},
            "survives_to_final": True,
        },
        {
            "tick_index": 1,
            "event_index": 1,
            "action": {"action": "claim", "symbol": "gcn_p"},
            "survives_to_final": True,
        },
        {
            "tick_index": 2,
            "event_index": 2,
            "action": {"action": "claim", "symbol": "gcn_c"},
            "survives_to_final": True,
        },
    ]
    out, warns = topo_reorder_ticks(ticks, [], layout, ir)
    symbols = [t["action"]["symbol"] for t in out]
    # The strategy must land *after* both its dep claims are admitted.
    assert symbols.index("strat_0") > symbols.index("gcn_p")
    assert symbols.index("strat_0") > symbols.index("gcn_c")
    # tick_index re-stamped 0..N-1.
    assert [t["tick_index"] for t in out] == [0, 1, 2]
    # Reorder warning emitted because at least one tick moved.
    assert any("topo_reorder" in w and "moved" in w for w in warns)


def test_replay_topo_reorder_ticks_keeps_orphans_in_place():
    """Verify replay topo reorder ticks keeps orphans in place.

    Orphan ticks (`survives_to_final=False`) stay in their original slot while surviving ticks
    pour through the reordered slots.
    """
    from gaia.cli.commands._replay_build import topo_reorder_ticks

    layout = {"nodes": {"gcn_a": {"kind": "knowledge"}, "gcn_b": {"kind": "knowledge"}}}
    ir = {
        "knowledges": [
            {"id": "ns:pkg::a", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:pkg::b", "metadata": {"lkm_id": "gcn_b"}},
        ],
        "strategies": [],
        "operators": [],
    }
    ticks = [
        {
            "tick_index": 0,
            "event_index": 0,
            "action": {"action": "claim", "symbol": "gcn_a"},
            "survives_to_final": True,
        },
        {
            "tick_index": 1,
            "event_index": 1,
            "action": {"action": "claim", "symbol": "gcn_orphan"},
            "survives_to_final": False,
        },
        {
            "tick_index": 2,
            "event_index": 2,
            "action": {"action": "claim", "symbol": "gcn_b"},
            "survives_to_final": True,
        },
    ]
    out, _warns = topo_reorder_ticks(ticks, [], layout, ir)
    # Slot 1 must still hold the orphan; survivors fill slots 0 and 2.
    assert out[1]["action"]["symbol"] == "gcn_orphan"
    assert out[1]["survives_to_final"] is False


def test_replay_bridge_event_symbols_to_layout_pair_signature_match():
    """Verify replay bridge event symbols to layout pair signature match.

    `pair_signatures` route bridges support / contradiction / equivalence events whose two-
    endpoint edge matches an IR operator's variable set.
    """
    from gaia.cli.commands._replay_build import bridge_event_symbols_to_layout

    layout = {
        "nodes": {
            "gcn_a": {"x": 0.0, "y": 0.0},
            "gcn_b": {"x": 1.0, "y": 1.0},
            "oper_0": {"x": 2.0, "y": 2.0},
        }
    }
    ir = {
        "knowledges": [
            {"id": "ns:pkg::a", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:pkg::b", "metadata": {"lkm_id": "gcn_b"}},
        ],
        "strategies": [],
        "operators": [
            {
                "operator": "contradiction",
                "variables": ["ns:pkg::a", "ns:pkg::b"],
                "conclusion": "ns:pkg::a",
            }
        ],
    }
    events = [
        {
            "event_id": "e0",
            "gaia_actions": [{"action": "contradiction", "symbol": "older_vs_newer"}],
            "graph_delta": {
                "edges_added": [
                    {"kind": "contradiction", "from": "gcn_a", "to": "gcn_b"},
                ]
            },
        }
    ]
    out, _warns = bridge_event_symbols_to_layout(layout, ir, events)
    # The event's symbol now aliases the IR operator's coords.
    assert "older_vs_newer" in out["nodes"]
    assert out["nodes"]["older_vs_newer"]["canonical_id"] == "oper_0"


def test_replay_bridge_event_symbols_skips_when_already_in_layout():
    """A symbol that already has its own layout entry should not be re-bridged."""
    from gaia.cli.commands._replay_build import bridge_event_symbols_to_layout

    layout = {
        "nodes": {
            "gcn_a": {"x": 0.0, "y": 0.0},
            "gcn_b": {"x": 1.0, "y": 1.0},
            "strat_0": {"x": 2.0, "y": 2.0},
            # Symbol already keyed in layout — bridge should leave alone.
            "gfac_x": {"x": 3.0, "y": 3.0},
        }
    }
    ir = {
        "knowledges": [
            {"id": "ns:pkg::a", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:pkg::b", "metadata": {"lkm_id": "gcn_b"}},
        ],
        "strategies": [{"type": "deduction", "premises": ["ns:pkg::a"], "conclusion": "ns:pkg::b"}],
        "operators": [],
    }
    events = [
        {
            "event_id": "e0",
            "gaia_actions": [{"action": "deduction", "symbol": "gfac_x"}],
            "graph_delta": {"edges_added": [{"kind": "deduction", "from": "gcn_a", "to": "gcn_b"}]},
        }
    ]
    out, _warns = bridge_event_symbols_to_layout(layout, ir, events)
    # Original gfac_x entry preserved; no canonical_id stamped on it.
    assert out["nodes"]["gfac_x"] == {"x": 3.0, "y": 3.0}


def test_replay_compute_dot_layout_real_graphviz_smoke(tmp_path):
    """End-to-end against a real graphviz dot binary: produces nodes + viewport."""
    del tmp_path
    if not _has_graphviz():
        pytest.skip("graphviz not on PATH")
    from gaia.cli.commands._replay_build import compute_dot_layout

    dot = 'digraph G {\n  "n_a" [pos="10,20"];\n  "n_b" [pos="30,40"];\n  "n_a" -> "n_b";\n}\n'
    layout = compute_dot_layout(dot)
    assert "viewport" in layout
    assert isinstance(layout["nodes"], dict)
    # Both nodes show up in the layout.
    assert "n_a" in layout["nodes"]
    assert "n_b" in layout["nodes"]


def test_replay_compute_dot_layout_raises_on_dot_failure(monkeypatch):
    """A non-zero `dot` exit raises RuntimeError with the stderr text."""
    from gaia.cli.commands import _replay_build as rb

    monkeypatch.setattr(rb.shutil, "which", lambda _: "/usr/bin/dot")

    class _FakeProc:
        returncode = 1
        stdout = ""
        stderr = "syntax error near token foo"

    monkeypatch.setattr(rb.subprocess, "run", lambda *_args, **_kwargs: _FakeProc())
    with pytest.raises(RuntimeError, match="dot -Tjson0"):
        rb.compute_dot_layout("digraph { a }")


# ── starmap.py validation-error branches ────────────────────────────────────


def test_starmap_validation_error_exits_1(tmp_path, monkeypatch):
    """A graph_validation result with errors triggers Exit(1) and `Error:` lines."""
    from gaia.cli.commands import starmap as starmap_mod

    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_validate_err")

    class _Result:
        warnings: ClassVar[list[str]] = ["a soft note"]
        errors: ClassVar[list[str]] = ["something is broken"]

    monkeypatch.setattr(starmap_mod, "validate_local_graph", lambda _g: _Result())
    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code == 1
    assert "Warning:" in result.output
    assert "something is broken" in result.output


def test_starmap_load_failure_exits_1(tmp_path, monkeypatch):
    """A GaiaPackagingError raised by `load_gaia_package` is captured + exit 1."""
    from gaia.cli.commands import starmap as starmap_mod
    from gaia.engine.packaging import GaiaPackagingError

    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_load_fail")

    def _boom(_path):
        raise GaiaPackagingError("simulated load failure")

    monkeypatch.setattr(starmap_mod, "load_gaia_package", _boom)
    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code == 1
    assert "simulated load failure" in result.output


def test_starmap_stored_ir_mismatches_compiled_ir(tmp_path):
    """When stored ir.json hash differs from compile output, exit with stale msg."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_stored_diff")
    # Tamper stored ir.json so the equality check at line 227 trips.
    ir_path = pkg_dir / ".gaia" / "ir.json"
    data = json.loads(ir_path.read_text())
    # Keep the hash matching ir_hash (so freshness gate passes), but mutate
    # the dict body so `stored_ir != ir` fires.
    data["package_name"] = "TAMPERED"
    ir_path.write_text(json.dumps(data))

    result = runner.invoke(app, ["inspect", "starmap", str(pkg_dir)])
    assert result.exit_code == 1
    assert "stale" in result.output


# ── _replay_build deeper coverage: bridge fallbacks + topo ops + beliefs ────


def test_replay_bridge_event_symbols_file_symbol_name_fallback():
    """Verify replay bridge event symbols file symbol name fallback.

    Step B fallback: when no edge signature matches, action.file + symbol name (matching the IR
    conclusion slug) bridges the symbol.
    """
    from gaia.cli.commands._replay_build import bridge_event_symbols_to_layout

    layout = {
        "nodes": {
            "ns:pkg::a": {"x": 0.0, "y": 0.0},
            "ns:pkg::concl_target": {"x": 1.0, "y": 0.0},
            "oper_0": {"x": 2.0, "y": 0.0},
        }
    }
    ir = {
        "knowledges": [
            {"id": "ns:pkg::a", "module": "mymod"},
            {"id": "ns:pkg::concl_target", "module": "mymod"},
        ],
        "strategies": [],
        "operators": [
            # Variables list intentionally matches no edges so step A misses;
            # Step B finds the operator by file + conclusion slug name.
            {
                "operator": "contradiction",
                "variables": ["ns:pkg::a"],
                "conclusion": "ns:pkg::concl_target",
            }
        ],
    }
    events = [
        {
            "event_id": "e0",
            "gaia_actions": [
                {
                    "action": "contradiction",
                    "symbol": "concl_target",
                    "file": "src/pkg/mymod.py",
                }
            ],
            "graph_delta": {"edges_added": []},  # No edges → step A fails.
        }
    ]
    out, warns = bridge_event_symbols_to_layout(layout, ir, events)
    # The symbol got bridged via the symbol-name fallback (Step B).
    assert "concl_target" in out["nodes"]
    assert out["nodes"]["concl_target"]["canonical_id"] == "oper_0"
    assert any("symbol-name fallback" in w for w in warns)


def test_replay_bridge_event_symbols_file_kind_uniqueness_fallback():
    """Verify replay bridge event symbols file kind uniqueness fallback.

    Step C fallback: when no edge / name match, the sole IR strat/oper of the right kind in the
    right module gets claimed.
    """
    from gaia.cli.commands._replay_build import bridge_event_symbols_to_layout

    layout = {
        "nodes": {
            "ns:pkg::premise": {"x": 0.0, "y": 0.0},
            "ns:pkg::concl": {"x": 1.0, "y": 0.0},
            "strat_0": {"x": 2.0, "y": 0.0},
        }
    }
    ir = {
        "knowledges": [
            {"id": "ns:pkg::premise", "module": "alpha"},
            {"id": "ns:pkg::concl", "module": "alpha"},
        ],
        "strategies": [
            {
                "type": "deduction",
                "premises": ["ns:pkg::premise"],
                "conclusion": "ns:pkg::concl",
            }
        ],
        "operators": [],
    }
    events = [
        {
            "event_id": "e0",
            "gaia_actions": [
                {
                    "action": "deduction",
                    "symbol": "gfac_unrelated",  # No name match.
                    "file": "src/pkg/alpha.py",
                }
            ],
            "graph_delta": {"edges_added": []},  # No edge match.
        }
    ]
    out, warns = bridge_event_symbols_to_layout(layout, ir, events)
    assert "gfac_unrelated" in out["nodes"]
    assert out["nodes"]["gfac_unrelated"]["canonical_id"] == "strat_0"
    assert any("file-uniqueness fallback" in w for w in warns)


def test_replay_topo_reorder_with_operator_dependency():
    """Verify replay topo reorder with operator dependency.

    A contradiction operator tick depends on its variable claims; if it fires before them, topo
    reorder pushes it past.
    """
    from gaia.cli.commands._replay_build import topo_reorder_ticks

    layout = {
        "nodes": {
            "gcn_v1": {"x": 0.0, "y": 0.0, "kind": "knowledge"},
            "gcn_v2": {"x": 1.0, "y": 0.0, "kind": "knowledge"},
            "oper_0": {"x": 2.0, "y": 0.0, "kind": "operator"},
        }
    }
    ir = {
        "knowledges": [
            {"id": "ns:pkg::v1", "metadata": {"lkm_id": "gcn_v1"}},
            {"id": "ns:pkg::v2", "metadata": {"lkm_id": "gcn_v2"}},
        ],
        "strategies": [],
        "operators": [
            {
                "operator": "contradiction",
                "variables": ["ns:pkg::v1", "ns:pkg::v2"],
                "conclusion": "ns:pkg::v1",
            }
        ],
    }
    ticks = [
        {
            "tick_index": 0,
            "event_index": 0,
            "action": {"action": "contradiction", "symbol": "oper_0"},
            "survives_to_final": True,
        },
        {
            "tick_index": 1,
            "event_index": 1,
            "action": {"action": "claim", "symbol": "gcn_v1"},
            "survives_to_final": True,
        },
        {
            "tick_index": 2,
            "event_index": 2,
            "action": {"action": "claim", "symbol": "gcn_v2"},
            "survives_to_final": True,
        },
    ]
    out, _warns = topo_reorder_ticks(ticks, [], layout, ir)
    # Operator must end up after both variable claims.
    symbols = [t["action"]["symbol"] for t in out]
    assert symbols.index("oper_0") > symbols.index("gcn_v1")
    assert symbols.index("oper_0") > symbols.index("gcn_v2")


def test_replay_topo_reorder_prior_dep_keys_resolution():
    """Verify replay topo reorder prior dep keys resolution.

    A `prior` action's dependency comes from its event's payload — the `_prior_dep_keys` helper
    should pull `target_lkm_id` / `priors` / `claim_ids` / prior edges correctly.
    """
    from gaia.cli.commands._replay_build import topo_reorder_ticks

    layout = {
        "nodes": {
            "gcn_a": {"x": 0.0, "y": 0.0, "kind": "knowledge"},
            "gcn_b": {"x": 1.0, "y": 0.0, "kind": "knowledge"},
        }
    }
    ir = {
        "knowledges": [
            {"id": "ns:pkg::a", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:pkg::b", "metadata": {"lkm_id": "gcn_b"}},
        ],
        "strategies": [],
        "operators": [],
    }
    # Event 0 carries a prior on gcn_a; event 1 admits gcn_a; event 2 admits gcn_b.
    events = [
        {
            "event_id": "e0",
            "payload": {"target_lkm_id": "gcn_a"},
            "graph_delta": {
                "edges_added": [{"kind": "prior", "to": "gcn_b"}],
            },
        },
        {"event_id": "e1"},
        {"event_id": "e2"},
    ]
    ticks = [
        {
            "tick_index": 0,
            "event_index": 0,
            "action": {"action": "prior", "symbol": "gcn_a"},
            "survives_to_final": True,
        },
        {
            "tick_index": 1,
            "event_index": 1,
            "action": {"action": "claim", "symbol": "gcn_a"},
            "survives_to_final": True,
        },
        {
            "tick_index": 2,
            "event_index": 2,
            "action": {"action": "claim", "symbol": "gcn_b"},
            "survives_to_final": True,
        },
    ]
    out, _warns = topo_reorder_ticks(ticks, events, layout, ir)
    symbols = [(t["action"]["action"], t["action"].get("symbol")) for t in out]
    # The prior tick must land after both target_lkm_id (gcn_a) and the
    # prior edge target (gcn_b) are admitted.
    prior_pos = next(i for i, s in enumerate(symbols) if s[0] == "prior")
    a_pos = next(i for i, s in enumerate(symbols) if s == ("claim", "gcn_a"))
    b_pos = next(i for i, s in enumerate(symbols) if s == ("claim", "gcn_b"))
    assert prior_pos > a_pos
    assert prior_pos > b_pos


def test_replay_compute_round_beliefs_full_engine_path():
    """Verify replay compute round beliefs full engine path.

    `compute_round_beliefs` runs the BP engine on an IR with a deduction edge. Each round's
    truncated graph yields a beliefs dict containing the admitted claims.
    """
    from gaia.cli.commands._replay_build import compute_round_beliefs

    ir = {
        "namespace": "test",
        "package_name": "rbeliefs",
        "scope": "local",
        "knowledges": [
            {
                "id": "test:rbeliefs::premise",
                "type": "claim",
                "metadata": {"lkm_id": "gcn_p", "prior": 0.7},
            },
            {
                "id": "test:rbeliefs::concl",
                "type": "claim",
                "metadata": {"lkm_id": "gcn_c", "prior": 0.4},
            },
            # No lkm_id → always-present.
            {
                "id": "test:rbeliefs::ap",
                "type": "claim",
                "metadata": {"prior": 0.3},
            },
        ],
        "operators": [],
        "strategies": [],
    }
    events = [
        {"round_id": "r0", "graph_delta": {"nodes_added": [{"lkm_id": "gcn_p"}]}},
        {"round_id": "r1", "graph_delta": {"nodes_added": [{"lkm_id": "gcn_c"}]}},
    ]
    beliefs = compute_round_beliefs(ir, events)
    # Each round materializes a beliefs table.
    assert "r0" in beliefs and "r1" in beliefs
    # r0 has premise + always-present.
    assert "test:rbeliefs::premise" in beliefs["r0"]
    assert "test:rbeliefs::ap" in beliefs["r0"]
    # r1 cumulatively adds concl.
    assert "test:rbeliefs::concl" in beliefs["r1"]
    # Beliefs land at priors (no edges in IR).
    assert abs(beliefs["r0"]["test:rbeliefs::premise"] - 0.7) < 1e-6
    assert abs(beliefs["r1"]["test:rbeliefs::concl"] - 0.4) < 1e-6


def test_replay_compute_round_beliefs_returns_empty_when_membership_empty():
    """Verify replay compute round beliefs returns empty when membership empty.

    When no events have lkm_id-bearing nodes_added entries, every IR claim is "always-present"
    and `cumulative` is empty → returns {}.
    """
    from gaia.cli.commands._replay_build import compute_round_beliefs

    ir = {
        "knowledges": [{"id": "ns:pkg::a", "type": "claim", "metadata": {"prior": 0.5}}],
        "operators": [],
        "strategies": [],
    }
    # No events with round_id → cumulative stays empty.
    assert compute_round_beliefs(ir, []) == {}
