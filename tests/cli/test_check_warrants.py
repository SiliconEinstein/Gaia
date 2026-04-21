from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_v6_warrant_package(pkg_dir, *, with_prior: bool = False) -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "check-warrants-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "check_warrants"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, derive, equal\n\n"
        'premise = claim("Evidence A is reliable.")\n'
        'evidence = claim("Evidence B matches Evidence A.")\n'
        'same = equal(premise, evidence, rationale="The two evidence records match.", label="same_evidence")\n'
        "conclusion = derive(\n"
        '    "The hypothesis is supported.",\n'
        "    given=(premise, same),\n"
        '    rationale="The matched evidence supports the hypothesis.",\n'
        '    label="derive_conclusion",\n'
        ")\n"
        '__all__ = ["conclusion"]\n'
    )
    if with_prior:
        (pkg_src / "priors.py").write_text(
            "from . import premise\n\n"
            'PRIORS = {premise: (0.83, "Author confidence in the observed evidence.")}\n'
        )


def test_check_warrants_outputs_review_list(tmp_path):
    pkg_dir = tmp_path / "check_warrants"
    _write_v6_warrant_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", "--warrants", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Review warrants:" in result.output
    assert "github:check_warrants::action::derive_conclusion" in result.output
    assert "github:check_warrants::action::same_evidence" in result.output
    assert "Do the listed premises suffice" in result.output
    assert "Are [@premise] and [@evidence] truly equivalent?" in result.output
    assert "status: unreviewed" in result.output


def test_check_warrants_blind_omits_author_priors_and_status_values(tmp_path):
    pkg_dir = tmp_path / "check_warrants"
    _write_v6_warrant_package(pkg_dir, with_prior=True)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", "--warrants", "--blind", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Review warrants:" in result.output
    assert "github:check_warrants::action::derive_conclusion" in result.output
    assert "Do the listed premises suffice" in result.output
    assert "status:" in result.output
    assert "status: unreviewed" not in result.output
    assert "0.83" not in result.output
    assert "prior=" not in result.output
