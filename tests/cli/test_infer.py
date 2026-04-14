"""Tests for gaia infer command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_base_package(pkg_dir, *, name: str, version: str = "1.0.0") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "{version}"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / name).mkdir()


def test_infer_with_priors_py(tmp_path):
    """Package with priors.py — infer reads metadata priors from compiled IR."""
    pkg_dir = tmp_path / "priors_infer"
    _write_base_package(pkg_dir, name="priors_infer")
    (pkg_dir / "priors_infer" / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'evidence = claim("Evidence.")\n'
        'hypothesis = claim("Hypothesis.")\n'
        "s = deduction(premises=[evidence], conclusion=hypothesis, reason='deduction', prior=0.9)\n"
        '__all__ = ["evidence", "hypothesis", "s"]\n'
    )
    (pkg_dir / "priors_infer" / "priors.py").write_text(
        "from . import evidence, hypothesis\n\n"
        "PRIORS = {\n"
        '    evidence: (0.9, "Direct observation."),\n'
        '    hypothesis: (0.4, "Base rate."),\n'
        "}\n"
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Method:" in result.output

    beliefs = json.loads((pkg_dir / ".gaia" / "beliefs.json").read_text())
    belief_by_label = {item["label"]: item["belief"] for item in beliefs["beliefs"]}
    assert belief_by_label["hypothesis"] > 0.4


def test_infer_without_priors_py(tmp_path):
    """Package without priors.py — infer uses default 0.5 priors."""
    pkg_dir = tmp_path / "no_priors_infer"
    _write_base_package(pkg_dir, name="no_priors_infer")
    (pkg_dir / "no_priors_infer" / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'evidence = claim("Evidence.")\n'
        'hypothesis = claim("Hypothesis.")\n'
        "s = deduction(premises=[evidence], conclusion=hypothesis, reason='deduction', prior=0.9)\n"
        '__all__ = ["evidence", "hypothesis", "s"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    beliefs = json.loads((pkg_dir / ".gaia" / "beliefs.json").read_text())
    assert len(beliefs["beliefs"]) >= 2


def test_infer_fails_when_compiled_artifacts_are_stale(tmp_path):
    pkg_dir = tmp_path / "infer_demo"
    _write_base_package(pkg_dir, name="infer_demo")
    (pkg_dir / "infer_demo" / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'main_claim = claim("Original claim.")\n'
        '__all__ = ["main_claim"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    (pkg_dir / "infer_demo" / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'main_claim = claim("Updated claim.")\n'
        '__all__ = ["main_claim"]\n'
    )

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower()


def test_infer_with_deduction_strategy(tmp_path):
    """Deduction strategy auto-formalizes and runs BP successfully."""
    pkg_dir = tmp_path / "deduction_demo"
    _write_base_package(pkg_dir, name="deduction_demo")
    (pkg_dir / "deduction_demo" / "__init__.py").write_text(
        "from gaia.lang import deduction, claim\n\n"
        'law = claim("forall x. P(x)")\n'
        'instance = claim("P(a)")\n'
        "proof = deduction(premises=[law], conclusion=instance, reason='instantiate', prior=0.9)\n"
        '__all__ = ["law", "instance", "proof"]\n'
    )
    (pkg_dir / "deduction_demo" / "priors.py").write_text(
        "from . import law, instance\n\n"
        "PRIORS = {\n"
        '    law: (0.9, "Well established."),\n'
        '    instance: (0.5, "Follows from law."),\n'
        "}\n"
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output


def test_infer_loads_upstream_beliefs_for_foreign_nodes(tmp_path, monkeypatch):
    """When dep_beliefs are present, foreign nodes use upstream beliefs as priors."""
    # Create upstream dependency package
    dep_dir = tmp_path / "upstream_dep"
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        '[project]\nname = "upstream-dep-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    dep_src = dep_dir / "upstream_dep"
    dep_src.mkdir()
    (dep_src / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'upstream_claim = claim("Upstream conclusion.")\n'
        '__all__ = ["upstream_claim"]\n'
    )
    monkeypatch.syspath_prepend(str(dep_dir))

    # Create local package that imports from upstream
    pkg_dir = tmp_path / "local_pkg"
    _write_base_package(pkg_dir, name="local_pkg")
    (pkg_dir / "local_pkg" / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n"
        "from upstream_dep import upstream_claim\n\n"
        'local_obs = claim("Local observation.")\n'
        "deduction(premises=[upstream_claim, local_obs], conclusion=claim('Result.'), "
        "reason='apply upstream', prior=0.9)\n"
        '__all__ = ["local_obs"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    # Write dep_beliefs with high upstream belief
    dep_beliefs_dir = pkg_dir / ".gaia" / "dep_beliefs"
    dep_beliefs_dir.mkdir(parents=True)
    (dep_beliefs_dir / "upstream_dep.json").write_text(
        json.dumps(
            {
                "manifest_schema_version": 1,
                "package": "upstream-dep",
                "version": "1.0.0",
                "ir_hash": "sha256:fake",
                "beliefs": [
                    {
                        "knowledge_id": "github:upstream_dep::upstream_claim",
                        "label": "upstream_claim",
                        "belief": 0.85,
                    }
                ],
            }
        )
    )

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "upstream belief" in result.output.lower()

    beliefs = json.loads((pkg_dir / ".gaia" / "beliefs.json").read_text())
    belief_by_id = {b["knowledge_id"]: b["belief"] for b in beliefs["beliefs"]}
    # The upstream claim should NOT be at 0.5 default — it should reflect the upstream prior
    upstream_belief = belief_by_id.get("github:upstream_dep::upstream_claim")
    assert upstream_belief is not None
    assert upstream_belief != 0.5, "Foreign node should not use default 0.5 when dep_beliefs exist"


def test_collect_foreign_node_priors_unit(tmp_path):
    """Unit test for collect_foreign_node_priors — no inference, just file parsing."""
    from types import SimpleNamespace

    from gaia.cli._packages import collect_foreign_node_priors

    pkg_path = tmp_path / "test_pkg"
    pkg_path.mkdir()

    # No dep_beliefs dir → empty dict
    result = collect_foreign_node_priors(
        SimpleNamespace(
            namespace="github",
            package_name="test_pkg",
            knowledges=[],
        ),
        pkg_path,
    )
    assert result == {}

    # Create dep_beliefs with upstream data
    dep_beliefs_dir = pkg_path / ".gaia" / "dep_beliefs"
    dep_beliefs_dir.mkdir(parents=True)
    (dep_beliefs_dir / "upstream_a.json").write_text(
        json.dumps(
            {
                "beliefs": [
                    {"knowledge_id": "github:upstream_a::claim_x", "belief": 0.9},
                    {"knowledge_id": "github:upstream_a::claim_y", "belief": 0.3},
                ]
            }
        )
    )
    (dep_beliefs_dir / "upstream_b.json").write_text(
        json.dumps(
            {
                "beliefs": [
                    {"knowledge_id": "github:upstream_b::claim_z", "belief": 0.7},
                ]
            }
        )
    )
    # Also add a malformed file to verify graceful handling
    (dep_beliefs_dir / "bad.json").write_text("not valid json")

    # Mock graph with local + foreign nodes
    local_node = SimpleNamespace(id="github:test_pkg::local_claim")
    foreign_a = SimpleNamespace(id="github:upstream_a::claim_x")
    foreign_b = SimpleNamespace(id="github:upstream_b::claim_z")
    foreign_missing = SimpleNamespace(id="github:upstream_c::no_data")

    graph = SimpleNamespace(
        namespace="github",
        package_name="test_pkg",
        knowledges=[local_node, foreign_a, foreign_b, foreign_missing],
    )

    result = collect_foreign_node_priors(graph, pkg_path)
    # Only foreign nodes with matching upstream beliefs
    assert result == {
        "github:upstream_a::claim_x": 0.9,
        "github:upstream_b::claim_z": 0.7,
    }
    # Local node and unmatched foreign node are excluded
    assert "github:test_pkg::local_claim" not in result
    assert "github:upstream_c::no_data" not in result


# --- Tests for gaia infer --depth (joint cross-package inference) ---


def _write_dep_package(dep_dir, *, name: str, monkeypatch):
    """Create a compilable dependency package and put it on sys.path."""
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    import_name = name.replace("-", "_")
    src = dep_dir / import_name
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'evidence = claim("Strong evidence for upstream.", title="evidence")\n'
        'upstream_conclusion = claim("Upstream conclusion.", title="conclusion")\n'
        "deduction(premises=[evidence], conclusion=upstream_conclusion, "
        "reason='evidence supports conclusion', prior=0.9)\n"
        '__all__ = ["evidence", "upstream_conclusion"]\n'
    )
    # Write priors.py to give evidence a high prior
    (src / "priors.py").write_text(
        'from . import evidence\n\nPRIORS = {evidence: (0.85, "Strong evidence")}\n'
    )
    monkeypatch.syspath_prepend(str(dep_dir))


def test_infer_depth_0_unchanged(tmp_path, monkeypatch):
    """--depth 0 (default) uses flat prior injection, same as no flag."""
    pkg_dir = tmp_path / "depth0"
    _write_base_package(pkg_dir, name="depth0")
    (pkg_dir / "depth0" / "__init__.py").write_text(
        'from gaia.lang import claim\n\nh = claim("Hypothesis.")\n__all__ = ["h"]\n'
    )
    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", "--depth", "0", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    # No merge messages
    assert "merged graph" not in result.output.lower()


def test_infer_depth_1_no_deps_falls_back(tmp_path, monkeypatch):
    """--depth 1 with no deps falls back to local inference."""
    pkg_dir = tmp_path / "nodeps"
    _write_base_package(pkg_dir, name="nodeps")
    (pkg_dir / "nodeps" / "__init__.py").write_text(
        'from gaia.lang import claim\n\nh = claim("Hypothesis.")\n__all__ = ["h"]\n'
    )
    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", "--depth", "1", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "no -gaia dependencies" in result.output.lower()


def test_infer_depth_1_merges_dep_graphs(tmp_path, monkeypatch):
    """--depth 1 merges dependency factor graphs for joint inference."""
    from unittest.mock import patch

    # Create upstream dep
    dep_dir = tmp_path / "upstream_dep"
    _write_dep_package(dep_dir, name="upstream_dep", monkeypatch=monkeypatch)

    # Compile the dep so it has .gaia/ir.json
    dep_compile = runner.invoke(app, ["compile", str(dep_dir)])
    assert dep_compile.exit_code == 0, dep_compile.output

    # Create local package that imports from upstream
    pkg_dir = tmp_path / "local_pkg"
    _write_base_package(pkg_dir, name="local_pkg")
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "local-pkg-gaia"\nversion = "1.0.0"\n'
        'dependencies = ["upstream-dep-gaia"]\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / "local_pkg" / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n"
        "from upstream_dep import upstream_conclusion\n\n"
        'local_obs = claim("Local observation.")\n'
        "local_result = claim('Local result.')\n"
        "deduction(premises=[upstream_conclusion, local_obs], conclusion=local_result, "
        "reason='apply upstream', prior=0.9)\n"
        '__all__ = ["local_obs", "local_result"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    # Mock _locate_dependency_manifest_root to point to our dep
    with patch(
        "gaia.cli._packages._locate_dependency_manifest_root",
        return_value=dep_dir,
    ):
        result = runner.invoke(app, ["infer", "--depth", "1", str(pkg_dir)])

    assert result.exit_code == 0, result.output
    assert "merged graph" in result.output.lower()
    assert "upstream_dep" in result.output.lower()

    # Verify beliefs.json was written with local knowledge nodes
    beliefs = json.loads((pkg_dir / ".gaia" / "beliefs.json").read_text())
    belief_ids = {b["knowledge_id"] for b in beliefs["beliefs"]}
    # Local nodes should be present
    assert any("local_pkg" in kid for kid in belief_ids)


def test_infer_depth_1_beliefs_differ_from_flat_priors(tmp_path, monkeypatch):
    """Joint inference produces different beliefs than flat prior injection."""
    from unittest.mock import patch

    # Create upstream dep with reasoning structure
    dep_dir = tmp_path / "upstream_dep"
    _write_dep_package(dep_dir, name="upstream_dep", monkeypatch=monkeypatch)

    dep_compile = runner.invoke(app, ["compile", str(dep_dir)])
    assert dep_compile.exit_code == 0, dep_compile.output

    # Create local package referencing upstream
    pkg_dir = tmp_path / "local_pkg"
    _write_base_package(pkg_dir, name="local_pkg")
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "local-pkg-gaia"\nversion = "1.0.0"\n'
        'dependencies = ["upstream-dep-gaia"]\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / "local_pkg" / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n"
        "from upstream_dep import upstream_conclusion\n\n"
        'local_obs = claim("Local observation.")\n'
        "local_result = claim('Local result.')\n"
        "deduction(premises=[upstream_conclusion, local_obs], conclusion=local_result, "
        "reason='apply upstream', prior=0.9)\n"
        '__all__ = ["local_obs", "local_result"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    # Run with --depth 0 (flat priors)
    result_flat = runner.invoke(app, ["infer", "--depth", "0", str(pkg_dir)])
    assert result_flat.exit_code == 0, result_flat.output
    beliefs_flat = json.loads((pkg_dir / ".gaia" / "beliefs.json").read_text())
    beliefs_flat_by_id = {b["knowledge_id"]: b["belief"] for b in beliefs_flat["beliefs"]}

    # Run with --depth 1 (joint inference)
    with patch(
        "gaia.cli._packages._locate_dependency_manifest_root",
        return_value=dep_dir,
    ):
        result_joint = runner.invoke(app, ["infer", "--depth", "1", str(pkg_dir)])
    assert result_joint.exit_code == 0, result_joint.output
    beliefs_joint = json.loads((pkg_dir / ".gaia" / "beliefs.json").read_text())
    beliefs_joint_by_id = {b["knowledge_id"]: b["belief"] for b in beliefs_joint["beliefs"]}

    # The foreign node should get different treatment: --depth 1 has full dep reasoning
    # structure while --depth 0 uses 0.5 default (no dep_beliefs written here)
    upstream_kid = "github:upstream_dep::upstream_conclusion"
    flat_upstream = beliefs_flat_by_id.get(upstream_kid, 0.5)
    joint_upstream = beliefs_joint_by_id.get(upstream_kid)
    # Joint inference should give a meaningfully different result
    # (dep's deduction + evidence prior 0.85 should push upstream_conclusion higher)
    if joint_upstream is not None:
        assert joint_upstream != flat_upstream, (
            f"Joint and flat beliefs should differ for the foreign node: "
            f"joint={joint_upstream}, flat={flat_upstream}"
        )
