"""Tests for the `gaia starmap` command."""

from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from gaia.cli.commands._dot import to_dot
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


def test_starmap_dot_cross_paper_module_unboxed():
    """``cross_paper`` module renders as floating nodes, not a cluster.

    Convention in Gaia knowledge packages: each paper lives in
    ``paper_<name>.py`` and cross-paper deductions/supports/contradictions
    live in ``cross_paper.py``. The DOT emitter wraps every paper module in a
    ``cluster_*`` subgraph, but the cross-paper bridge module should NOT be
    boxed — its content (knowledge nodes plus any strategy/operator that
    only anchors to it) must float at top-level scope alongside other
    cross-module bridges.
    """
    graph_json = json.dumps(
        {
            "nodes": [
                # paper_x: a tiny premise → conclusion via a deduction.
                {
                    "id": "p:paper_x::a",
                    "type": "knowledge",
                    "label": "a",
                    "title": "a",
                    "module": "paper_x",
                },
                {
                    "id": "p:paper_x::b",
                    "type": "knowledge",
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
                # cross_paper: a knowledge node and a strategy that anchors
                # to a paper_x node + a cross_paper node (so it touches more
                # than one module → already floats today).
                {
                    "id": "p:cross_paper::c",
                    "type": "knowledge",
                    "label": "c",
                    "title": "c",
                    "module": "cross_paper",
                },
                {
                    "id": "p:cross_paper::s",
                    "type": "strategy",
                    "strategy_type": "deduction",
                    "module": "cross_paper",
                },
                # Cross-paper-only strategy: anchors only to cross_paper
                # knowledge nodes. Should also float (treated as _FLOAT).
                {
                    "id": "p:cross_paper::c2",
                    "type": "knowledge",
                    "label": "c2",
                    "title": "c2",
                    "module": "cross_paper",
                },
                {
                    "id": "p:cross_paper::s_local",
                    "type": "strategy",
                    "strategy_type": "deduction",
                    "module": "cross_paper",
                },
            ],
            "edges": [
                # paper_x: a -> s -> b (so s anchors entirely inside paper_x).
                {"source": "p:paper_x::a", "target": "p:paper_x::s"},
                {"source": "p:paper_x::s", "target": "p:paper_x::b"},
                # cross_paper bridge strategy: paper_x::b -> s -> cross_paper::c.
                {"source": "p:paper_x::b", "target": "p:cross_paper::s"},
                {"source": "p:cross_paper::s", "target": "p:cross_paper::c"},
                # cross_paper-only strategy: c -> s_local -> c2.
                {"source": "p:cross_paper::c", "target": "p:cross_paper::s_local"},
                {"source": "p:cross_paper::s_local", "target": "p:cross_paper::c2"},
            ],
        }
    )

    dot = to_dot(graph_json)

    # No cluster_cross_paper subgraph — the whole point of this change.
    assert "cluster_cross_paper" not in dot, dot
    # paper_x is still boxed.
    assert "subgraph cluster_paper_x" in dot, dot

    # cross_paper knowledge nodes appear in the floating block.
    floating_marker = "// cross-module strategy/operator nodes (outside clusters)"
    assert floating_marker in dot, dot
    after_marker = dot.split(floating_marker, 1)[1]
    # End the floating block at the // edges marker.
    floating_block = after_marker.split("// edges", 1)[0]
    assert '"p:cross_paper::c"' in floating_block, floating_block
    assert '"p:cross_paper::c2"' in floating_block, floating_block
    # And the cross_paper-only strategy (touches only cross_paper) also floats.
    assert '"p:cross_paper::s_local"' in floating_block, floating_block
    # The truly cross-module bridge strategy still floats.
    assert '"p:cross_paper::s"' in floating_block, floating_block

    # paper_x knowledge stays inside its cluster (sanity check).
    paper_x_block = dot.split("subgraph cluster_paper_x", 1)[1].split("}", 1)[0]
    assert '"p:paper_x::a"' in paper_x_block
    assert '"p:paper_x::b"' in paper_x_block
    # And the paper_x-local strategy stays inside it.
    assert '"p:paper_x::s"' in paper_x_block

    # All edges still emit, including those to/from floating nodes.
    assert '"p:paper_x::b" -> "p:cross_paper::s"' in dot
    assert '"p:cross_paper::s" -> "p:cross_paper::c"' in dot
    assert '"p:cross_paper::c" -> "p:cross_paper::s_local"' in dot
    assert '"p:cross_paper::s_local" -> "p:cross_paper::c2"' in dot
