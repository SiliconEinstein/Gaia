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

pytestmark = pytest.mark.pr_gate

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
    """Without `gaia run infer`, starmap still produces HTML; beliefs are absent."""
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
    """Without `gaia build compile`, starmap exits non-zero with a clear message."""
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
    """Without `gaia run infer`, dot still renders and skips trend arrows."""
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


def test_to_dot_knowledge_content_fallback_when_unnamed():
    """A claim with empty title+label falls back to its (truncated) content."""
    graph_json = json.dumps(
        {
            "nodes": [
                {
                    "id": "p:m::_anon_001",
                    "type": "claim",
                    "label": "",
                    "title": None,
                    "module": "m",
                    "content": "derive warrants The muon g-2 anomaly provides a sensitive test "
                    "of the Standard Model and beyond",
                    "belief": 0.5,
                }
            ],
            "edges": [],
        }
    )
    for theme in ("stellaris", "light"):
        dot = to_dot(graph_json, theme=theme)
        line = _node_line(dot, "p:m::_anon_001")
        m = re.search(r'label="([^"]*)"', line)
        assert m, line
        label = m.group(1)
        # "derive warrants " prefix stripped; substantive text shown.
        assert label.startswith("The muon g-2 anomaly"), f"{theme}: {label!r}"
        assert "derive warrants" not in label, f"{theme}: {label!r}"
        # Truncated with an ellipsis (content is longer than the cap), then the
        # belief annotation trails it.
        assert "…" in label, f"{theme}: {label!r}"
        assert label.endswith("(0.50)"), f"{theme}: {label!r}"


def test_to_dot_knowledge_title_wins_over_content():
    """When a title is present it is used; content is only a last-resort fallback."""
    graph_json = json.dumps(
        {
            "nodes": [
                {
                    "id": "p:m::named",
                    "type": "claim",
                    "label": "named",
                    "title": "A Named Claim",
                    "module": "m",
                    "content": "derive warrants some other text",
                }
            ],
            "edges": [],
        }
    )
    line = _node_line(to_dot(graph_json, theme="stellaris"), "p:m::named")
    assert 'label="A Named Claim"' in line


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
    """`gaia inspect starmap --format dot --theme stellaris` produces dot with sfdp layout."""
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


def _multi_contradiction_graph_json(n: int) -> str:
    """Graph JSON with *n* contradiction operators, each on its own conclusion."""
    nodes: list[dict] = []
    edges: list[dict] = []
    for i in range(n):
        kid = f"p:m::c{i}"
        nodes.append({"id": kid, "type": "claim", "label": f"c{i}", "module": "m"})
        nodes.append(
            {"id": f"oper_{i}", "type": "operator", "operator_type": "contradiction", "module": "m"}
        )
        edges.append({"source": f"oper_{i}", "target": kid, "role": "conclusion"})
    return json.dumps({"nodes": nodes, "edges": edges})


def _count_contradiction_node_groups(svg: str) -> int:
    """Count SVG node ``<g>`` groups whose class carries the contradiction token."""
    count = 0
    for m in re.finditer(r'<g\s+id="[^"]*"\s+class="([^"]*)"[^>]*>\s*<title>([^<]*)</title>', svg):
        cls, title = m.groups()
        if "contradiction" in cls.split() and title.startswith("oper_"):
            count += 1
    return count


def test_ensure_contradiction_classes_restamps_dropped_marker():
    """When Graphviz drops the per-node class, all N markers are re-injected.

    Simulates Graphviz 2.43, which emits operator groups as ``class="node"`` with
    the dot ``class="contradiction"`` dropped. The post-process keyed off the dot
    source must restore the token on every contradiction node group.
    """
    from gaia.cli.commands._stellaris_svg import (
        _contradiction_node_ids_from_dot,
        ensure_contradiction_classes,
    )

    dot = to_dot(_multi_contradiction_graph_json(3), theme="stellaris")
    contra_ids = _contradiction_node_ids_from_dot(dot)
    assert contra_ids == {"oper_0", "oper_1", "oper_2"}

    # Graphviz-2.43-style SVG: contradiction class dropped to a bare node class.
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g id="node1" class="node"><title>oper_0</title></g>'
        '<g id="node2" class="node"><title>oper_1</title></g>'
        '<g id="node3" class="node"><title>oper_2</title></g>'
        "</svg>"
    )
    assert _count_contradiction_node_groups(svg) == 0
    out = ensure_contradiction_classes(svg, contra_ids)
    assert _count_contradiction_node_groups(out) == 3
    # Idempotent.
    assert _count_contradiction_node_groups(ensure_contradiction_classes(out, contra_ids)) == 3


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
def test_post_process_styles_all_contradiction_nodes_end_to_end():
    """All N contradiction operators are styled, not just 1, through sfdp + post.

    Regression: a 3-operator graph previously surfaced a single contradiction
    marker downstream because Graphviz emission dropped/merged the per-node
    class. Driving the real pipeline (to_dot → sfdp → post_process with the dot
    source) must leave all 3 contradiction node groups carrying the token.
    """
    import subprocess

    dot = to_dot(_multi_contradiction_graph_json(3), theme="stellaris")
    svg = subprocess.run(
        ["sfdp", "-Tsvg"], input=dot, capture_output=True, text=True, check=True
    ).stdout
    out = post_process_stellaris_svg(svg, dot_source=dot)
    assert _count_contradiction_node_groups(out) == 3


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


def test_to_dot_stellaris_strategy_labels_carry_glyph():
    """In stellaris, strategy nodes are glyph-coded (∴ deduction / ⊕ support)."""
    dot = to_dot(_make_stellaris_fixture(), theme="stellaris")
    expectations = {"strat_ded": "∴", "strat_sup": "⊕"}
    for nid, glyph in expectations.items():
        line = _node_line(dot, nid)
        m = re.search(r'label="([^"]*)"', line)
        assert m and m.group(1) == glyph, f"{nid} expected {glyph!r}, got line: {line}"


def test_to_dot_stellaris_unknown_strategy_falls_back_to_type_text():
    """A strategy with an unmapped type renders its type text, not a blank label."""
    graph_json = json.dumps(
        {
            "nodes": [{"id": "strat_x", "type": "strategy", "strategy_type": "mystery"}],
            "edges": [],
        }
    )
    dot = to_dot(graph_json, theme="stellaris")
    line = _node_line(dot, "strat_x")
    assert 'label="mystery"' in line


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
    assert "Stellaris starmap" in out
    # Legend text is English-only — no CJK leaks into the figure.
    assert not re.search(r"[一-鿿]", out)
    # Legend appears before </svg>.
    assert out.index('id="legend"') < out.index("</svg>")


def test_inject_legend_includes_all_node_role_rows():
    """Legend lists premise, derived, root, deduction, support, all 6 operator types."""
    from gaia.cli.commands._stellaris_svg import inject_legend

    out = inject_legend('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    # Knowledge boxes — English-only labels.
    assert "premise · no upstream strategy/operator" in out
    assert "derived · ≥1 upstream strategy/operator" in out
    assert "★ root claim · belief-prop seed" in out
    assert "⊕ support (independent evidence)" in out
    assert "box numbers:" in out
    # Strategies — now glyph-coded (mirrors the dot node labels).
    assert "∴ deduction" in out
    assert "⊕ support" in out
    # The strategy glyphs render as their own <text> nodes (icon labels), not
    # just inside the row-label text.
    assert out.count("∴") >= 2
    assert out.count("⊕") >= 2
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


def test_inject_legend_frontier_row_off_by_default():
    """Without `include_frontier`, the legend has no fog row (starmap unchanged)."""
    from gaia.cli.commands._stellaris_svg import inject_legend

    out = inject_legend('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    assert "frontier · unexplored (fog)" not in out
    assert "stroke-dasharray" not in out


def test_inject_legend_frontier_row_added_when_requested():
    """With `include_frontier=True`, a dashed fog row + label appear."""
    from gaia.cli.commands._stellaris_svg import inject_legend

    out = inject_legend('<svg xmlns="http://www.w3.org/2000/svg"></svg>', include_frontier=True)
    assert "frontier · unexplored (fog)" in out
    # The fog icon is a dashed rounded rect in the question palette.
    assert 'stroke-dasharray="4,2"' in out
    assert "#332416" in out
    assert "#caa84a" in out
    # The other node-role rows still render.
    assert "premise · no upstream strategy/operator" in out


def test_build_legend_svg_frontier_flag_controls_fog_row():
    """`_build_legend_svg` gates the fog row on its flag."""
    from gaia.cli.commands._stellaris_svg import _build_legend_svg

    assert "frontier · unexplored (fog)" not in _build_legend_svg()
    assert "frontier · unexplored (fog)" in _build_legend_svg(include_frontier=True)


def test_post_process_stellaris_svg_frontier_flag_gates_fog_row():
    """`post_process_stellaris_svg` only emits the fog row when `include_frontier`."""
    from gaia.cli.commands._stellaris_svg import post_process_stellaris_svg

    svg = '<svg xmlns="http://www.w3.org/2000/svg"><polygon fill="#05060f"/></svg>'
    # Default (starmap path) — no fog row.
    assert "frontier · unexplored (fog)" not in post_process_stellaris_svg(svg)
    # Explorer path — fog row present.
    assert "frontier · unexplored (fog)" in post_process_stellaris_svg(svg, include_frontier=True)


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
    assert "Stellaris starmap" in svg
    # No CJK leaks into the rendered stellaris figure.
    assert not re.search(r"[一-鿿]", svg)
    # Plain starmap has no fog nodes, so the frontier legend row must be absent.
    assert "frontier · unexplored (fog)" not in svg


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
    """Beliefs whose ir_hash doesn't match compile output prompt `gaia run infer` again."""
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
