import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def test_quality_gate_default_config():
    from gaia.cli.commands._quality_gate import load_quality_config

    config = load_quality_config({})
    assert config.allow_holes is False
    assert config.min_posterior is None


def test_quality_gate_custom_config():
    from gaia.cli.commands._quality_gate import load_quality_config

    config = load_quality_config({"min_posterior": 0.7})
    assert config.min_posterior == 0.7
    assert config.allow_holes is False


def _write_gate_package(pkg_dir, source: str, *, quality: str = "") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "gate-demo-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
        f"{quality}"
    )
    pkg_src = pkg_dir / "gate_demo"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(source)


def _accept_all_reviews(pkg_dir) -> None:
    from gaia.cli._packages import compile_loaded_package_artifact, load_gaia_package
    from gaia.ir import ReviewManifest, ReviewStatus

    loaded = load_gaia_package(pkg_dir)
    compiled = compile_loaded_package_artifact(loaded)
    assert compiled.review is not None
    accepted = [
        review.model_copy(update={"status": ReviewStatus.ACCEPTED, "round": 2})
        for review in compiled.review.reviews
    ]
    (pkg_dir / ".gaia" / "review_manifest.json").write_text(
        json.dumps(ReviewManifest(reviews=accepted).model_dump(mode="json"), indent=2)
    )


def _accept_reviews_except(pkg_dir, action_label_fragment: str) -> None:
    from gaia.cli._packages import compile_loaded_package_artifact, load_gaia_package
    from gaia.ir import ReviewManifest, ReviewStatus

    loaded = load_gaia_package(pkg_dir)
    compiled = compile_loaded_package_artifact(loaded)
    assert compiled.review is not None
    reviews = [
        review.model_copy(
            update={
                "status": (
                    ReviewStatus.UNREVIEWED
                    if action_label_fragment in review.action_label
                    else ReviewStatus.ACCEPTED
                ),
                "round": 2,
            }
        )
        for review in compiled.review.reviews
    ]
    (pkg_dir / ".gaia" / "review_manifest.json").write_text(
        json.dumps(ReviewManifest(reviews=reviews).model_dump(mode="json"), indent=2)
    )


def test_gate_fails_on_structural_hole(tmp_path):
    pkg_dir = tmp_path / "gate_demo"
    _write_gate_package(
        pkg_dir,
        "from gaia.lang import claim\n\n"
        'hole = claim("Unwarranted exported claim.")\n'
        '__all__ = ["hole"]\n',
    )

    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code != 0
    assert "structural hole" in result.output.lower()


def test_gate_fails_on_unreviewed(tmp_path):
    pkg_dir = tmp_path / "gate_demo"
    _write_gate_package(
        pkg_dir,
        "from gaia.lang import derive, observe\n\n"
        'data = observe("Data.", rationale="Measured.", label="observe_data")\n'
        'conclusion = derive("Conclusion.", given=data, rationale="Data implies conclusion.", label="derive_c")\n'
        '__all__ = ["conclusion"]\n',
    )

    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code != 0
    assert "unreviewed" in result.output.lower()


def test_gate_fails_on_unreviewed_compose(tmp_path):
    pkg_dir = tmp_path / "gate_demo"
    _write_gate_package(
        pkg_dir,
        "from gaia.lang import Claim, compose, derive\n\n"
        'premise = Claim("A.")\n'
        'premise.label = "premise"\n\n'
        '@compose(name="test:workflow", version="1.0", label="workflow")\n'
        "def workflow(a: Claim) -> Claim:\n"
        '    result = derive("C.", given=a, rationale="A implies C.", label="derive_c")\n'
        '    result.label = "c"\n'
        "    return result\n\n"
        "c = workflow(premise)\n"
        '__all__ = ["c"]\n',
        quality="\n[tool.gaia.quality]\nallow_holes = true\n",
    )
    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output
    _accept_reviews_except(pkg_dir, "workflow")

    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])

    assert result.exit_code != 0
    assert "workflow" in result.output


def test_gate_fails_on_unreviewed_exported_infer_helper(tmp_path):
    pkg_dir = tmp_path / "gate_demo"
    _write_gate_package(
        pkg_dir,
        "from gaia.lang import Claim, infer\n\n"
        'h = Claim("H.")\n'
        'h.label = "h"\n'
        'e = Claim("E.")\n'
        'e.label = "e"\n\n'
        "support = infer(\n"
        "    e,\n"
        "    hypothesis=h,\n"
        "    p_e_given_h=0.9,\n"
        "    p_e_given_not_h=0.1,\n"
        '    label="infer_h",\n'
        ")\n"
        'support.label = "support"\n'
        '__all__ = ["support"]\n',
        quality="\n[tool.gaia.quality]\nallow_holes = true\n",
    )

    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])

    assert result.exit_code != 0
    assert "infer_h" in result.output


def test_gate_still_runs_with_blind_warrant_report(tmp_path):
    pkg_dir = tmp_path / "gate_demo"
    _write_gate_package(
        pkg_dir,
        "from gaia.lang import observe\n\n"
        'root = observe("Root fact.", rationale="Measured.", label="root_obs")\n'
        '__all__ = ["root"]\n',
    )

    result = runner.invoke(app, ["check", str(pkg_dir), "--warrants", "--blind", "--gate"])
    assert result.exit_code != 0
    assert "quality gate failed" in result.output.lower()
    assert "root_obs" in result.output


def test_gate_fails_on_unreviewed_root_observe(tmp_path):
    pkg_dir = tmp_path / "gate_demo"
    _write_gate_package(
        pkg_dir,
        "from gaia.lang import observe\n\n"
        'root = observe("Root fact.", rationale="Measured.", label="root_obs")\n'
        '__all__ = ["root"]\n',
    )

    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code != 0
    assert "unreviewed" in result.output.lower()


def test_gate_fails_on_low_posterior(tmp_path):
    pkg_dir = tmp_path / "gate_demo"
    _write_gate_package(
        pkg_dir,
        "from gaia.lang import observe\n\n"
        'root = observe("Root fact.", rationale="Measured.", label="root_obs")\n'
        '__all__ = ["root"]\n',
        quality="\n[tool.gaia.quality]\nmin_posterior = 0.9\n",
    )
    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output
    _accept_all_reviews(pkg_dir)
    (pkg_dir / ".gaia" / "beliefs.json").write_text(
        json.dumps(
            {
                "beliefs": [
                    {
                        "knowledge_id": "github:gate_demo::root",
                        "label": "root",
                        "belief": 0.7,
                    }
                ]
            },
            indent=2,
        )
    )

    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code != 0
    assert "low posterior" in result.output.lower()


def test_gate_passes_when_all_met(tmp_path):
    pkg_dir = tmp_path / "gate_demo"
    _write_gate_package(
        pkg_dir,
        "from gaia.lang import derive, observe\n\n"
        'data = observe("Data.", rationale="Measured.", label="observe_data")\n'
        'conclusion = derive("Conclusion.", given=data, rationale="Data implies conclusion.", label="derive_c")\n'
        '__all__ = ["conclusion"]\n',
    )
    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output
    _accept_all_reviews(pkg_dir)

    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code == 0, result.output
    assert "Quality gate passed" in result.output


def test_gate_ignores_unexported_unreachable_draft_actions(tmp_path):
    pkg_dir = tmp_path / "gate_demo"
    _write_gate_package(
        pkg_dir,
        "from gaia.lang import derive, observe\n\n"
        'data = observe("Data.", rationale="Measured.", label="observe_data")\n'
        'conclusion = derive("Conclusion.", given=data, rationale="Data implies conclusion.", label="derive_c")\n'
        'draft = observe("Unrelated draft measurement.", rationale="Draft.", label="draft_obs")\n'
        '__all__ = ["conclusion"]\n',
    )
    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output
    _accept_reviews_except(pkg_dir, "draft_obs")

    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code == 0, result.output
    assert "Quality gate passed" in result.output
