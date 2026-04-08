"""Tests for gaia compile command."""

import json

from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph

runner = CliRunner()


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

    ir = json.loads((gaia_dir / "ir.json").read_text())
    assert ir["package_name"] == "test_pkg"
    assert len(ir["knowledges"]) >= 1
    assert ir["ir_hash"] is not None
    result = validate_local_graph(LocalCanonicalGraph(**ir))
    assert result.valid, result.errors

    exports_manifest = json.loads((gaia_dir / "manifests" / "exports.json").read_text())
    premises_manifest = json.loads((gaia_dir / "manifests" / "premises.json").read_text())
    assert exports_manifest["manifest_schema_version"] == 1
    assert premises_manifest["manifest_schema_version"] == 1
    assert exports_manifest["package"] == "test-pkg"
    assert exports_manifest["version"] == "1.0.0"
    assert exports_manifest["exports"] == [
        {
            "content": "A test claim.",
            "content_hash": ir["knowledges"][0]["content_hash"],
            "label": "my_claim",
            "qid": "github:test_pkg::my_claim",
            "type": "claim",
        }
    ]
    assert premises_manifest["premises"] == []


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


def test_compile_emits_public_premise_manifest_for_local_hole(tmp_path):
    pkg_dir = tmp_path / "premise_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "premise-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "premise_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'missing_lemma = claim("A missing lemma.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[missing_lemma], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    premises_manifest = json.loads((pkg_dir / ".gaia" / "manifests" / "premises.json").read_text())
    assert premises_manifest["manifest_schema_version"] == 1
    assert premises_manifest["package"] == "premise-pkg"
    assert premises_manifest["version"] == "1.0.0"
    assert len(premises_manifest["premises"]) == 1
    premise = premises_manifest["premises"][0]
    assert premise["qid"] == "github:premise_pkg::missing_lemma"
    assert premise["label"] == "missing_lemma"
    assert premise["role"] == "local_hole"
    assert premise["exported"] is False
    assert premise["required_by"] == ["github:premise_pkg::main_theorem"]
    assert premise["interface_hash"].startswith("sha256:")


def test_compile_marks_foreign_dependency_public_premise(tmp_path, monkeypatch):
    dep_dir = tmp_path / "dep_pkg_root"
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        '[project]\nname = "dep-pkg-gaia"\nversion = "0.4.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    dep_src = dep_dir / "src" / "dep_pkg"
    dep_src.mkdir(parents=True)
    (dep_src / "__init__.py").write_text(
        'from gaia.lang import claim\n\n'
        'dep_result = claim("Dependency theorem.")\n'
        '__all__ = ["dep_result"]\n'
    )
    monkeypatch.syspath_prepend(str(dep_dir / "src"))

    pkg_dir = tmp_path / "consumer_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "consumer-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "consumer_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n"
        "from dep_pkg import dep_result\n\n"
        'main_theorem = claim("Consumer theorem.")\n'
        "deduction(premises=[dep_result], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    premises_manifest = json.loads((pkg_dir / ".gaia" / "manifests" / "premises.json").read_text())
    assert len(premises_manifest["premises"]) == 1
    premise = premises_manifest["premises"][0]
    assert premise["qid"] == "github:dep_pkg::dep_result"
    assert premise["role"] == "foreign_dependency"
    assert premise["required_by"] == ["github:consumer_pkg::main_theorem"]


def test_compile_public_premise_required_by_uses_nearest_exported_claim(tmp_path):
    pkg_dir = tmp_path / "nearest_root_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "nearest-root-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "nearest_root_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'shared_premise = claim("Shared premise.")\n'
        'helper_claim = claim("Helper claim.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[shared_premise], conclusion=helper_claim)\n"
        "deduction(premises=[helper_claim], conclusion=main_theorem)\n"
        '__all__ = ["helper_claim", "main_theorem"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    premises_manifest = json.loads((pkg_dir / ".gaia" / "manifests" / "premises.json").read_text())
    assert len(premises_manifest["premises"]) == 1
    premise = premises_manifest["premises"][0]
    assert premise["qid"] == "github:nearest_root_pkg::shared_premise"
    assert premise["required_by"] == ["github:nearest_root_pkg::helper_claim"]


def test_compile_exported_public_premise_lists_other_exported_roots(tmp_path):
    pkg_dir = tmp_path / "exp_premise_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "exp-premise-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "exp_premise_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'shared_premise = claim("Shared premise.")\n'
        'theorem_a = claim("Theorem A.")\n'
        'theorem_b = claim("Theorem B.")\n'
        "deduction(premises=[shared_premise], conclusion=theorem_a)\n"
        "deduction(premises=[shared_premise], conclusion=theorem_b)\n"
        '__all__ = ["shared_premise", "theorem_a", "theorem_b"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    premises_manifest = json.loads((pkg_dir / ".gaia" / "manifests" / "premises.json").read_text())
    assert len(premises_manifest["premises"]) == 1
    premise = premises_manifest["premises"][0]
    assert premise["qid"] == "github:exp_premise_pkg::shared_premise"
    assert premise["exported"] is True
    assert premise["required_by"] == [
        "github:exp_premise_pkg::theorem_a",
        "github:exp_premise_pkg::theorem_b",
    ]


def test_compile_interface_hash_is_deterministic(tmp_path):
    pkg_dir = tmp_path / "deterministic_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "deterministic-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "deterministic_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'missing_lemma = claim("A missing lemma.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[missing_lemma], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )

    first = runner.invoke(app, ["compile", str(pkg_dir)])
    assert first.exit_code == 0, first.output
    first_manifest = json.loads((pkg_dir / ".gaia" / "manifests" / "premises.json").read_text())
    first_hash = first_manifest["premises"][0]["interface_hash"]

    second = runner.invoke(app, ["compile", str(pkg_dir)])
    assert second.exit_code == 0, second.output
    second_manifest = json.loads((pkg_dir / ".gaia" / "manifests" / "premises.json").read_text())
    second_hash = second_manifest["premises"][0]["interface_hash"]

    assert first_hash == second_hash


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
