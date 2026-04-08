"""Tests for gaia compile command."""

import json
from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph

runner = CliRunner()


def _write_package(
    root,
    *,
    project_name: str,
    body: str,
    dependencies: list[str] | None = None,
    src_layout: bool = True,
):
    root.mkdir()
    deps_block = ""
    if dependencies:
        deps_lines = ",\n".join(f'  "{dep}"' for dep in dependencies)
        deps_block = f"dependencies = [\n{deps_lines}\n]\n\n"
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{project_name}"\nversion = "1.0.0"\n{deps_block}'
        '\n[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    import_name = project_name.removesuffix("-gaia").replace("-", "_")
    package_root = root / ("src" if src_layout else "")
    if src_layout:
        package_root.mkdir()
    pkg_src = package_root / import_name
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(body)
    return root, pkg_src


def _read_manifest(pkg_dir, name: str) -> dict:
    return json.loads((pkg_dir / ".gaia" / "manifests" / name).read_text())


def test_compile_creates_ir_json(tmp_path):
    """Create a minimal package and compile it."""
    pkg_dir = tmp_path / "test_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "test-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "test_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        'from gaia.lang import claim\n\nmy_claim = claim("A test claim.")\n__all__ = ["my_claim"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    gaia_dir = pkg_dir / ".gaia"
    assert (gaia_dir / "ir.json").exists()
    assert (gaia_dir / "ir_hash").exists()
    assert (gaia_dir / "manifests" / "exports.json").exists()
    assert (gaia_dir / "manifests" / "holes.json").exists()
    assert (gaia_dir / "manifests" / "bridges.json").exists()

    ir = json.loads((gaia_dir / "ir.json").read_text())
    exports = _read_manifest(pkg_dir, "exports.json")
    holes = _read_manifest(pkg_dir, "holes.json")
    bridges = _read_manifest(pkg_dir, "bridges.json")
    assert ir["package_name"] == "test_pkg"
    assert len(ir["knowledges"]) >= 1
    assert ir["ir_hash"] is not None
    assert exports["package"] == "test-pkg"
    assert exports["exports"][0]["label"] == "my_claim"
    assert holes["holes"] == []
    assert bridges["bridges"] == []
    result = validate_local_graph(LocalCanonicalGraph(**ir))
    assert result.valid, result.errors


def test_compile_no_pyproject(tmp_path):
    """Error when no pyproject.toml exists."""
    result = runner.invoke(app, ["compile", str(tmp_path)])
    assert result.exit_code != 0


def test_compile_not_knowledge_package(tmp_path):
    """Error when [tool.gaia].type is not knowledge-package."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "foo"\nversion = "1.0.0"\n\n[tool.gaia]\ntype = "something-else"\n'
    )
    result = runner.invoke(app, ["compile", str(tmp_path)])
    assert result.exit_code != 0


def test_compile_missing_source_dir(tmp_path):
    """Error when derived source directory does not exist."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "missing-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    result = runner.invoke(app, ["compile", str(tmp_path)])
    assert result.exit_code != 0


def test_compile_fails_on_invalid_ir_validation(tmp_path):
    """Compile should fail before writing artifacts when IR validator rejects the graph."""
    pkg_dir = tmp_path / "invalid_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "invalid-pkg-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "invalid_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, contradiction, setting\n\n"
        'context = setting("Background context.")\n'
        'hypothesis = claim("Main hypothesis.")\n'
        "conflict = contradiction(context, hypothesis)\n"
        '__all__ = ["context", "hypothesis", "conflict"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code != 0
    assert "must be claim" in result.output
    assert not (pkg_dir / ".gaia" / "ir.json").exists()


def test_compile_labels_assigned(tmp_path):
    """Variable names become labels in the IR."""
    pkg_dir = tmp_path / "label_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "label-pkg-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "label_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, setting\n\n"
        'bg = setting("Background context.")\n'
        'hypothesis = claim("Main hypothesis.")\n'
        '__all__ = ["bg", "hypothesis"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    labels = [k["label"] for k in ir["knowledges"]]
    assert "bg" in labels
    assert "hypothesis" in labels


def test_compile_supports_src_layout(tmp_path):
    """uv-style src/ layout packages compile successfully."""
    pkg_dir = tmp_path / "ver_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "ver-pkg-gaia"\nversion = "2.3.4"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    src_root = pkg_dir / "src"
    src_root.mkdir()
    pkg_src = src_root / "ver_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        'from gaia.lang import claim\n\nc = claim("A claim.")\n__all__ = ["c"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    assert ir["package_name"] == "ver_pkg"
    assert "package" not in ir


def test_compile_preserves_structured_steps_and_provenance(tmp_path):
    pkg_dir = tmp_path / "step_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "step-pkg-gaia"\nversion = "0.3.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "step_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import Step, claim, noisy_and\n\n"
        'evidence_a = claim("Evidence A.", provenance=[{"package_id": "paper:alpha", "version": "1.0.0"}])\n'
        'evidence_b = claim("Evidence B.")\n'
        'hypothesis = claim("Hypothesis.")\n'
        "support = noisy_and(\n"
        "    premises=[evidence_a, evidence_b],\n"
        "    conclusion=hypothesis,\n"
        '    reason=[Step(reason="Combine both evidence lines.", premises=[evidence_a, evidence_b])],\n'
        ")\n"
        '__all__ = ["evidence_a", "evidence_b", "hypothesis", "support"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    evidence_a = next(
        knowledge for knowledge in ir["knowledges"] if knowledge["label"] == "evidence_a"
    )
    assert evidence_a["provenance"] == [{"package_id": "paper:alpha", "version": "1.0.0"}]

    strategy = ir["strategies"][0]
    assert strategy["steps"] == [
        {
            "reasoning": "Combine both evidence lines.",
            "premises": ["github:step_pkg::evidence_a", "github:step_pkg::evidence_b"],
        }
    ]


def test_compile_named_strategy_uses_ir_canonical_formalization(tmp_path):
    """Named strategies should be formalized through gaia.ir.formalize during compile."""
    pkg_dir = tmp_path / "abduction_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "abduction-pkg-gaia"\nversion = "0.2.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "abduction_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import abduction, claim\n\n"
        'observation = claim("Observation.")\n'
        'hypothesis = claim("Hypothesis.")\n'
        'best_explanation = abduction(observation=observation, hypothesis=hypothesis, reason="fit")\n'
        '__all__ = ["observation", "hypothesis", "best_explanation"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    assert len(ir["strategies"]) == 1
    strategy = ir["strategies"][0]
    assert strategy["type"] == "abduction"
    assert strategy["metadata"]["reason"] == "fit"
    assert strategy["metadata"]["generated_formal_expr"] is True
    assert strategy["metadata"]["formalization_template"] == "abduction"
    assert "alternative_explanation" in strategy["metadata"]["interface_roles"]
    assert len(strategy["premises"]) == 2
    assert [op["operator"] for op in strategy["formal_expr"]["operators"]] == [
        "disjunction",
        "equivalence",
    ]

    interface_claims = [
        knowledge
        for knowledge in ir["knowledges"]
        if knowledge.get("metadata", {}).get("generated_kind") == "interface_claim"
    ]
    assert len(interface_claims) == 1
    assert "is_input" not in interface_claims[0]


def test_compile_emits_pure_local_canonical_graph(tmp_path):
    pkg_dir = tmp_path / "pure_ir_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "pure-ir-pkg-gaia"\nversion = "0.4.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "pure_ir_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, noisy_and\n\n"
        'premise = claim("Premise.")\n'
        'conclusion = claim("Conclusion.")\n'
        "support = noisy_and(premises=[premise], conclusion=conclusion)\n"
        '__all__ = ["premise", "conclusion", "support"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    assert "package" not in ir
    assert all("is_input" not in knowledge for knowledge in ir["knowledges"])
    result = validate_local_graph(LocalCanonicalGraph(**ir))
    assert result.valid, result.errors


def test_compile_elimination_strategy_uses_ir_canonical_formalization(tmp_path):
    """New named strategy wrappers should compile through the IR formalizer."""
    pkg_dir = tmp_path / "elimination_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "elimination-pkg-gaia"\nversion = "0.2.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "elimination_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, elimination\n\n"
        'exhaustive = claim("The candidates are exhaustive.")\n'
        'bacterial = claim("Bacterial cause.")\n'
        'antibiotics_neg = claim("Antibiotics test is negative.")\n'
        'viral = claim("Viral cause.")\n'
        'viral_test_neg = claim("Viral test is negative.")\n'
        'autoimmune = claim("Autoimmune cause.")\n'
        "argument = elimination(\n"
        "    exhaustiveness=exhaustive,\n"
        "    excluded=[(bacterial, antibiotics_neg), (viral, viral_test_neg)],\n"
        "    survivor=autoimmune,\n"
        '    reason="All alternative causes were excluded.",\n'
        ")\n"
        '__all__ = ["exhaustive", "bacterial", "antibiotics_neg", "viral", "viral_test_neg", "autoimmune", "argument"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    assert len(ir["strategies"]) == 1
    strategy = ir["strategies"][0]
    assert strategy["type"] == "elimination"
    assert strategy["metadata"]["formalization_template"] == "elimination"
    assert strategy["metadata"]["interface_roles"] == {
        "eliminated_candidate": [
            "github:elimination_pkg::bacterial",
            "github:elimination_pkg::viral",
        ],
        "elimination_evidence": [
            "github:elimination_pkg::antibiotics_neg",
            "github:elimination_pkg::viral_test_neg",
        ],
        "exhaustiveness": ["github:elimination_pkg::exhaustive"],
    }
    assert [op["operator"] for op in strategy["formal_expr"]["operators"]] == [
        "disjunction",
        "equivalence",
        "contradiction",
        "contradiction",
        "conjunction",
        "implication",
    ]


def test_compile_composite_strategy_preserves_sub_strategy_references(tmp_path):
    pkg_dir = tmp_path / "composite_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "composite-pkg-gaia"\nversion = "0.2.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "composite_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import abduction, claim, composite, noisy_and\n\n"
        'observation = claim("Observation.")\n'
        'hypothesis = claim("Hypothesis.")\n'
        'final_claim = claim("Final claim.")\n'
        "best_explanation = abduction(observation=observation, hypothesis=hypothesis)\n"
        "support = noisy_and(premises=[hypothesis], conclusion=final_claim)\n"
        "argument = composite(\n"
        "    premises=[observation],\n"
        "    conclusion=final_claim,\n"
        "    sub_strategies=[best_explanation, support],\n"
        '    reason="Compose the abductive and support sub-arguments.",\n'
        ")\n"
        '__all__ = ["observation", "hypothesis", "final_claim", "best_explanation", "support", "argument"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    strategy_ids = {strategy["strategy_id"] for strategy in ir["strategies"]}
    composite_strategy = next(
        strategy for strategy in ir["strategies"] if strategy.get("sub_strategies") is not None
    )
    assert composite_strategy["type"] == "infer"
    assert composite_strategy["premises"] == ["github:composite_pkg::observation"]
    assert composite_strategy["conclusion"] == "github:composite_pkg::final_claim"
    assert len(composite_strategy["sub_strategies"]) == 2
    for child_id in composite_strategy["sub_strategies"]:
        assert child_id in strategy_ids

    result = validate_local_graph(LocalCanonicalGraph(**ir))
    assert result.valid, result.errors


def test_compile_nested_composite_strategy_collects_recursive_knowledge(tmp_path):
    pkg_dir = tmp_path / "nested_composite_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "nested-composite-pkg-gaia"\nversion = "0.2.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "nested_composite_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import abduction, claim, composite, noisy_and\n\n"
        'observation = claim("Observation.")\n'
        'hypothesis = claim("Hypothesis.")\n'
        'intermediate = claim("Intermediate.")\n'
        'final_claim = claim("Final claim.")\n'
        "best_explanation = abduction(observation=observation, hypothesis=hypothesis)\n"
        "support = noisy_and(premises=[hypothesis], conclusion=intermediate)\n"
        "inner = composite(\n"
        "    premises=[observation],\n"
        "    conclusion=intermediate,\n"
        "    sub_strategies=[best_explanation, support],\n"
        ")\n"
        "final_support = noisy_and(premises=[intermediate], conclusion=final_claim)\n"
        "argument = composite(\n"
        "    premises=[observation],\n"
        "    conclusion=final_claim,\n"
        "    sub_strategies=[inner, final_support],\n"
        ")\n"
        '__all__ = ["observation", "hypothesis", "intermediate", "final_claim", "best_explanation", "support", "inner", "final_support", "argument"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    knowledge_ids = {knowledge["id"] for knowledge in ir["knowledges"]}
    assert "github:nested_composite_pkg::hypothesis" in knowledge_ids
    result = validate_local_graph(LocalCanonicalGraph(**ir))
    assert result.valid, result.errors


def test_compile_emits_holes_manifest_with_required_by(tmp_path):
    pkg_dir, _ = _write_package(
        tmp_path / "hole_pkg",
        project_name="hole-pkg-gaia",
        body=(
            "from gaia.lang import claim, deduction, hole\n\n"
            'main_theorem = claim("Main theorem.")\n'
            'key_missing_lemma = hole("A missing lemma.")\n'
            "deduction(premises=[key_missing_lemma], conclusion=main_theorem)\n"
            '__all__ = ["main_theorem", "key_missing_lemma"]\n'
        ),
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    exports = _read_manifest(pkg_dir, "exports.json")
    holes = _read_manifest(pkg_dir, "holes.json")
    assert [item["label"] for item in exports["exports"]] == ["main_theorem", "key_missing_lemma"]
    assert holes["holes"] == [
        {
            "qid": "github:hole_pkg::key_missing_lemma",
            "label": "key_missing_lemma",
            "content": "A missing lemma.",
            "content_hash": holes["holes"][0]["content_hash"],
            "required_by": ["github:hole_pkg::main_theorem"],
        }
    ]


def test_compile_emits_bridge_manifest_for_direct_fill(tmp_path, monkeypatch):
    dep_dir, _ = _write_package(
        tmp_path / "dep_hole_pkg",
        project_name="dep-hole-pkg-gaia",
        body=(
            "from gaia.lang import hole\n\n"
            'key_missing_lemma = hole("A missing premise.")\n'
            '__all__ = ["key_missing_lemma"]\n'
        ),
    )
    pkg_dir, _ = _write_package(
        tmp_path / "fill_pkg",
        project_name="fill-pkg-gaia",
        dependencies=["dep-hole-pkg-gaia>=1.4.0,<2.0.0"],
        body=(
            "from gaia.lang import claim, fills\n"
            "from dep_hole_pkg import key_missing_lemma\n\n"
            'b_result = claim("B theorem.")\n'
            'fills(source=b_result, hole=key_missing_lemma, reason="Theorem 3 proves the missing lemma.")\n'
            '__all__ = ["b_result"]\n'
        ),
    )

    monkeypatch.syspath_prepend(str(dep_dir / "src"))
    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    bridges = _read_manifest(pkg_dir, "bridges.json")
    exports = _read_manifest(pkg_dir, "exports.json")
    assert [item["label"] for item in exports["exports"]] == ["b_result"]
    assert len(bridges["bridges"]) == 1
    bridge = bridges["bridges"][0]
    assert bridge["relation_id"].startswith("bridge_")
    assert bridge["relation_type"] == "fills"
    assert bridge["source_qid"] == "github:fill_pkg::b_result"
    assert bridge["target_hole_qid"] == "github:dep_hole_pkg::key_missing_lemma"
    assert bridge["target_package"] == "dep-hole-pkg"
    assert bridge["target_version_req"] == ">=1.4.0,<2.0.0"
    assert bridge["declared_by_owner_of_source"] is True
    assert bridge["justification"] == "Theorem 3 proves the missing lemma."


def test_compile_emits_bridge_manifest_for_zero_local_bridge_package(tmp_path, monkeypatch):
    dep_a_dir, _ = _write_package(
        tmp_path / "bridge_dep_a",
        project_name="bridge-dep-a-gaia",
        body=(
            "from gaia.lang import hole\n\n"
            'key_missing_lemma = hole("A missing premise.")\n'
            '__all__ = ["key_missing_lemma"]\n'
        ),
    )
    dep_b_dir, _ = _write_package(
        tmp_path / "bridge_dep_b",
        project_name="bridge-dep-b-gaia",
        body=(
            "from gaia.lang import claim\n\n"
            'b_result = claim("B theorem.")\n'
            '__all__ = ["b_result"]\n'
        ),
    )
    pkg_dir, _ = _write_package(
        tmp_path / "bridge_pkg",
        project_name="bridge-pkg-gaia",
        dependencies=[
            "bridge-dep-a-gaia>=1.4.0,<2.0.0",
            "bridge-dep-b-gaia>=2.1.0,<3.0.0",
        ],
        body=(
            "from gaia.lang import fills\n"
            "from bridge_dep_a import key_missing_lemma\n"
            "from bridge_dep_b import b_result\n\n"
            'fills(source=b_result, hole=key_missing_lemma, reason="Bridge package links B to A.")\n'
        ),
    )

    monkeypatch.syspath_prepend(str(dep_a_dir / "src"))
    monkeypatch.syspath_prepend(str(dep_b_dir / "src"))
    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    exports = _read_manifest(pkg_dir, "exports.json")
    holes = _read_manifest(pkg_dir, "holes.json")
    bridges = _read_manifest(pkg_dir, "bridges.json")
    assert exports["exports"] == []
    assert holes["holes"] == []
    assert len(bridges["bridges"]) == 1
    bridge = bridges["bridges"][0]
    assert bridge["source_qid"] == "github:bridge_dep_b::b_result"
    assert bridge["target_hole_qid"] == "github:bridge_dep_a::key_missing_lemma"
    assert bridge["declared_by_owner_of_source"] is False
    assert bridge["target_version_req"] == ">=1.4.0,<2.0.0"


def test_compile_rejects_foreign_fill_without_dependency_constraint(tmp_path, monkeypatch):
    dep_dir, _ = _write_package(
        tmp_path / "missing_dep_hole_pkg",
        project_name="missing-dep-hole-pkg-gaia",
        body=(
            "from gaia.lang import hole\n\n"
            'key_missing_lemma = hole("A missing premise.")\n'
            '__all__ = ["key_missing_lemma"]\n'
        ),
    )
    pkg_dir, _ = _write_package(
        tmp_path / "bad_fill_pkg",
        project_name="bad-fill-pkg-gaia",
        body=(
            "from gaia.lang import claim, fills\n"
            "from missing_dep_hole_pkg import key_missing_lemma\n\n"
            'b_result = claim("B theorem.")\n'
            "fills(source=b_result, hole=key_missing_lemma)\n"
            '__all__ = ["b_result"]\n'
        ),
    )

    monkeypatch.syspath_prepend(str(dep_dir / "src"))
    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code != 0
    assert "requires a Gaia dependency constraint" in result.output
