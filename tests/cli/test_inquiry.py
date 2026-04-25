import json

from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.ir import ReviewManifest, ReviewStatus
from gaia.lang import Claim, depends_on, derive, observe
from gaia.lang.compiler import compile_package_artifact
from gaia.lang.review.manifest import generate_review_manifest
from gaia.lang.runtime.package import CollectedPackage

runner = CliRunner()


def _write_inquiry_package(pkg_dir) -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "inquiry-demo-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "inquiry_demo"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, derive\n\n"
        'a = claim("A.")\n'
        'b = claim("B.")\n'
        'c = derive("C.", given=(a, b), rationale="A and B imply C.", label="derive_c")\n'
        'hole = claim("Unwarranted exported claim.")\n'
        '__all__ = ["c", "hole"]\n'
    )


def test_inquiry_shows_exported_goals_and_holes(tmp_path):
    pkg_dir = tmp_path / "inquiry_demo"
    _write_inquiry_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", "--inquiry", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Goal 1:" in result.output
    assert "Goal 2:" in result.output
    assert "hole [hole]" in result.output
    assert "Structural holes:" in result.output


def test_inquiry_shows_warrant_status():
    from gaia.cli.commands._inquiry import build_goal_trees, render_inquiry

    with CollectedPackage("inquiry_pkg") as pkg:
        a = Claim("A.")
        a.label = "a"
        data = observe("Observation.", rationale="Measured.", label="observe_data")
        data.label = "data"
        c = derive("C.", given=(a, data), rationale="A and data imply C.", label="derive_c")
        c.label = "c"
        pkg._exported_labels = {"c"}

    compiled = compile_package_artifact(pkg)
    generated = generate_review_manifest(compiled)
    accepted = generated.reviews[0].model_copy(update={"status": ReviewStatus.ACCEPTED, "round": 2})
    manifest = ReviewManifest(reviews=[*generated.reviews, accepted])

    trees = build_goal_trees(compiled.to_json(), manifest)
    output = render_inquiry(trees)

    assert "[accepted]" in output
    assert "[unreviewed]" in output


def test_inquiry_shows_support_tree(tmp_path):
    pkg_dir = tmp_path / "inquiry_demo"
    _write_inquiry_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", "--inquiry", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "derive_c [unreviewed]" in result.output
    assert "- a [hole]" in result.output
    assert "- b [hole]" in result.output


def test_check_inquiry_flag(tmp_path):
    pkg_dir = tmp_path / "inquiry_demo"
    _write_inquiry_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", str(pkg_dir), "--inquiry"])
    assert result.exit_code == 0, result.output
    assert "Inquiry" in result.output
    assert "Summary" in result.output


def test_inquiry_shows_unformalized_scaffold_dependencies(tmp_path):
    pkg_dir = tmp_path / "inquiry_demo"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "inquiry-demo-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "inquiry_demo"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, depends_on\n\n"
        'a = claim("A.")\n'
        'b = claim("B.")\n'
        'c = claim("C.")\n'
        'depends_on(c, given=(a, b), rationale="Scaffold.", label="c_depends_on_a_b")\n'
        '__all__ = ["c"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output
    formalization_manifest = json.loads(
        (pkg_dir / ".gaia" / "formalization_manifest.json").read_text()
    )
    assert formalization_manifest["dependencies"][0]["label"] == "c_depends_on_a_b"

    result = runner.invoke(app, ["check", "--inquiry", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Goal 1: c" in result.output
    assert "c_depends_on_a_b [unformalized]" in result.output
    assert "Goal 1: c [hole]" not in result.output
    assert "- a [hole]" in result.output
    assert "- b [hole]" in result.output
    assert "    - a  no external prior (MaxEnt)" in result.output
    assert "    - b  no external prior (MaxEnt)" in result.output
    assert "    - c  no external prior (MaxEnt)" not in result.output
    assert "Scaffolded (unformalized): 1" in result.output
    assert "    - c" in result.output
    assert "Orphaned claims" not in result.output


def test_build_goal_trees_accepts_formalization_manifest():
    from gaia.cli.commands._inquiry import build_goal_trees, render_inquiry

    with CollectedPackage("inquiry_pkg") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        c = Claim("C.")
        c.label = "c"
        depends_on(c, given=(a, b), rationale="Scaffold.", label="c_depends_on_a_b")
        pkg._exported_labels = {"c"}

    compiled = compile_package_artifact(pkg)
    trees = build_goal_trees(
        compiled.to_json(),
        ReviewManifest(reviews=[]),
        formalization_manifest=compiled.formalization_manifest,
    )
    output = render_inquiry(trees)

    assert "c_depends_on_a_b [unformalized]" in output
    assert "Goal 1: c [hole]" not in output
