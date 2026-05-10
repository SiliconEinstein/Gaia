"""Tests for the `gaia starmap` command."""

from __future__ import annotations

import json
import re

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
        "from gaia.lang import claim, deduction\n\n"
        'evidence_a = claim("Observed evidence A.")\n'
        'evidence_b = claim("Observed evidence B.")\n'
        'hypothesis = claim("Main hypothesis.")\n'
        "s = deduction(premises=[evidence_a, evidence_b], conclusion=hypothesis,"
        " reason='test', prior=0.9)\n"
        '__all__ = ["evidence_a", "evidence_b", "hypothesis", "s"]\n'
    )


def _write_priors(pkg_dir, name: str) -> None:
    (pkg_dir / name / "priors.py").write_text(
        "from . import evidence_a, evidence_b, hypothesis\n\n"
        "PRIORS = {\n"
        '    evidence_a: (0.9, "Direct observation."),\n'
        '    evidence_b: (0.8, "Supporting observation."),\n'
        '    hypothesis: (0.4, "Base rate."),\n'
        "}\n"
    )


def _prepare_inferred_package(tmp_path, name: str = "starmap_demo"):
    """Create, compile, and infer a package. Returns pkg_dir."""
    pkg_dir = tmp_path / name
    _write_base_package(pkg_dir, name=name)
    _write_minimal_source(pkg_dir, name)
    _write_priors(pkg_dir, name)
    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0
    assert runner.invoke(app, ["infer", str(pkg_dir)]).exit_code == 0
    return pkg_dir


def _extract_graph_data(html: str) -> dict:
    """Parse the JSON payload injected by `gaia starmap` out of the HTML."""
    match = re.search(r"window\.GRAPH_DATA = (.*?);</script>", html, re.DOTALL)
    assert match is not None, "window.GRAPH_DATA assignment not found in starmap HTML"
    return json.loads(match.group(1))


def test_starmap_default_output(tmp_path):
    """Happy path: writes .gaia/starmap.html with a parseable graph payload."""
    pkg_dir = _prepare_inferred_package(tmp_path)

    result = runner.invoke(app, ["starmap", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    out_path = pkg_dir / ".gaia" / "starmap.html"
    assert out_path.exists()
    html = out_path.read_text()
    assert "window.GRAPH_DATA" in html

    data = _extract_graph_data(html)
    knowledge_nodes = [n for n in data["nodes"] if n["type"] not in ("strategy", "operator")]
    # 3 knowledge nodes: evidence_a, evidence_b, hypothesis.
    assert len(knowledge_nodes) == 3
    labels = {n["label"] for n in knowledge_nodes}
    assert labels == {"evidence_a", "evidence_b", "hypothesis"}

    # Beliefs and priors should be threaded through.
    assert any(n.get("belief") is not None for n in knowledge_nodes)
    assert any(n.get("prior") is not None for n in knowledge_nodes)

    # Success message reports counts.
    assert "Wrote starmap to" in result.output
    assert "nodes" in result.output and "edges" in result.output


def test_starmap_custom_output(tmp_path):
    """`--out` overrides the default path (relative to package dir)."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_custom")
    custom = "build/star.html"

    result = runner.invoke(app, ["starmap", str(pkg_dir), "--out", custom])
    assert result.exit_code == 0, result.output

    expected = pkg_dir / custom
    assert expected.exists()
    assert not (pkg_dir / ".gaia" / "starmap.html").exists()


def test_starmap_creates_parent_dirs(tmp_path):
    """`--out` honors nested paths and creates parent directories."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_nested")
    nested = "nested/dir/foo.html"

    result = runner.invoke(app, ["starmap", str(pkg_dir), "--out", nested])
    assert result.exit_code == 0, result.output

    out_path = pkg_dir / nested
    assert out_path.exists()
    assert out_path.parent.is_dir()


def test_starmap_absolute_out_path(tmp_path):
    """Absolute `--out` is honored as-is, ignoring the package directory."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_abs")
    abs_out = tmp_path / "elsewhere" / "starmap.html"

    result = runner.invoke(app, ["starmap", str(pkg_dir), "--out", str(abs_out)])
    assert result.exit_code == 0, result.output
    assert abs_out.exists()


def test_starmap_without_beliefs(tmp_path):
    """Without `gaia infer`, starmap still produces HTML; beliefs are absent."""
    pkg_dir = tmp_path / "starmap_no_infer"
    _write_base_package(pkg_dir, name="starmap_no_infer")
    _write_minimal_source(pkg_dir, "starmap_no_infer")
    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["starmap", str(pkg_dir)])
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

    result = runner.invoke(app, ["starmap", str(pkg_dir)])
    assert result.exit_code != 0
    assert "missing compiled artifacts" in result.output


# ── DOT format ──────────────────────────────────────────────────────────────


def test_starmap_dot_default_output(tmp_path):
    """`--format dot` writes `.gaia/starmap.dot` with paper-ready Graphviz content."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_dot")

    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "dot"])
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

    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "dot", "--out", custom])
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

    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "dot"])
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
    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "dot"])
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
        app, ["starmap", str(pkg_dir), "--format", "dot", "--theme", "stellaris"]
    )
    assert result.exit_code == 0, result.output
    content = (pkg_dir / ".gaia" / "starmap.dot").read_text()
    assert "layout=sfdp" in content
    assert 'bgcolor="#05060f"' in content


def test_starmap_cli_theme_default_is_light(tmp_path):
    """Without `--theme`, output stays on the light/TB layout (regression guard)."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_default_theme")
    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "dot"])
    assert result.exit_code == 0, result.output
    content = (pkg_dir / ".gaia" / "starmap.dot").read_text()
    assert "layout=sfdp" not in content
    assert 'bgcolor="#05060f"' not in content
    assert "rankdir=TB" in content


def test_starmap_cli_theme_dark_alias(tmp_path):
    """`--theme dark` is accepted and produces stellaris output."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_dark")
    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "dot", "--theme", "dark"])
    assert result.exit_code == 0, result.output
    content = (pkg_dir / ".gaia" / "starmap.dot").read_text()
    assert "layout=sfdp" in content


def test_starmap_cli_theme_invalid(tmp_path):
    """Unknown theme exits non-zero with a clear message."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_bad_theme")
    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "dot", "--theme", "bogus"])
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
    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "garbage"])
    assert result.exit_code != 0
    assert "format" in result.output.lower()


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_stellaris_end_to_end(tmp_path):
    """`--format svg --theme stellaris` writes a paper-ready glowing SVG."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_stellaris")
    result = runner.invoke(
        app, ["starmap", str(pkg_dir), "--format", "svg", "--theme", "stellaris"]
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
        app, ["starmap", str(pkg_dir), "--format", "svg", "--theme", "stellaris"]
    )
    assert result.exit_code == 0, result.output

    out_path = pkg_dir / ".gaia" / "starmap.svg"
    # ET.parse raises on malformed XML — that's the assertion.
    ET.parse(out_path)


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_dark_alias(tmp_path):
    """`--theme dark` produces the same stellaris SVG output."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_dark")
    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "svg", "--theme", "dark"])
    assert result.exit_code == 0, result.output
    svg = (pkg_dir / ".gaia" / "starmap.svg").read_text(encoding="utf-8")
    assert "<defs>" in svg
    assert 'id="contra-glow"' in svg
    assert 'fill="url(#space-bg)"' in svg


@pytest.mark.skipif(not _has_graphviz(), reason="graphviz binaries not on PATH")
def test_starmap_svg_light_no_defs(tmp_path):
    """Light theme SVG goes through `dot` and skips the stellaris post-process."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="starmap_svg_light")
    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "svg", "--theme", "light"])
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
    result = runner.invoke(app, ["starmap", str(pkg_dir), "--format", "svg"])
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
        app, ["starmap", str(pkg_dir), "--format", "svg", "--theme", "stellaris"]
    )
    assert result.exit_code != 0
    msg = result.output.lower()
    assert "graphviz" in msg
    # The error names the missing binary so users know what to install.
    assert "sfdp" in result.output or "dot" in result.output
