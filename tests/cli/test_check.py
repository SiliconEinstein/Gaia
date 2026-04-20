"""Tests for gaia check command."""

from __future__ import annotations

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_package(pkg_dir, *, content: str = "A test claim.") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "check-demo-gaia"\nversion = "1.2.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "check_demo"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        f'main_claim = claim("{content}")\n'
        '__all__ = ["main_claim"]\n'
    )


def test_check_passes_with_fresh_artifacts(tmp_path):
    pkg_dir = tmp_path / "check_demo"
    _write_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Check passed" in result.output


def test_check_applies_priors_py_before_stale_check(tmp_path):
    pkg_dir = tmp_path / "check_demo"
    _write_package(pkg_dir)
    (pkg_dir / "check_demo" / "priors.py").write_text(
        'from . import main_claim\n\nPRIORS = {main_claim: (0.8, "Reviewed premise.")}\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Check passed" in result.output


def test_check_fails_when_compiled_artifacts_are_stale(tmp_path):
    pkg_dir = tmp_path / "check_demo"
    _write_package(pkg_dir, content="Original claim.")

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    (pkg_dir / "check_demo" / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'main_claim = claim("Updated claim.")\n'
        '__all__ = ["main_claim"]\n'
    )

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower()


def test_check_fails_on_invalid_fills_target(tmp_path, monkeypatch):
    dep_dir = tmp_path / "dep_check_missing_root"
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        '[project]\nname = "dep-check-missing-gaia"\nversion = "0.4.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    dep_src = dep_dir / "src" / "dep_check_missing"
    dep_src.mkdir(parents=True)
    (dep_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'missing_lemma = claim("A missing lemma.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[missing_lemma], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )
    monkeypatch.syspath_prepend(str(dep_dir / "src"))

    pkg_dir = tmp_path / "check_demo"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "check-demo-gaia"\n'
        'version = "1.2.0"\n'
        'dependencies = ["dep-check-missing-gaia>=0.4.0"]\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "check_demo"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, fills\n"
        "from dep_check_missing import missing_lemma\n\n"
        'main_claim = claim("A test claim.")\n'
        "fills(source=main_claim, target=missing_lemma)\n"
        '__all__ = ["main_claim"]\n'
    )

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code != 0
    assert "missing .gaia/manifests/premises.json" in result.output


def _write_multi_claim_package(pkg_dir, *, with_priors: bool = False) -> None:
    """Create a test package with two independent premises and one derived claim."""
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "check-holes-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "check_holes"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'premise_a = claim("Evidence A is observed.")\n'
        'premise_b = claim("Evidence B is observed.")\n'
        'conclusion = claim("Therefore, hypothesis H holds.")\n'
        "deduction(premises=[premise_a, premise_b], conclusion=conclusion)\n"
        '__all__ = ["premise_a", "premise_b", "conclusion"]\n'
    )
    if with_priors:
        (pkg_src / "priors.py").write_text(
            "from . import premise_a\n\n"
            'PRIORS = {premise_a: (0.85, "Strong experimental evidence.")}\n'
        )


def test_check_shows_prior_on_independent_claims(tmp_path):
    """Independent claims with priors show prior=X; without show warning."""
    pkg_dir = tmp_path / "check_holes"
    _write_multi_claim_package(pkg_dir, with_priors=True)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "prior=0.85" in result.output
    assert "no prior (defaults to 0.5)" in result.output


def test_check_shows_hole_count_in_summary(tmp_path):
    """Summary shows hole count when some independent claims lack priors."""
    pkg_dir = tmp_path / "check_holes"
    _write_multi_claim_package(pkg_dir, with_priors=True)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    # premise_a has prior, premise_b does not → 1 hole
    assert "Holes (no prior set):   1" in result.output


def test_check_hides_generated_helper_claims_from_diagnostics(tmp_path):
    """Generated formal helper claims should not pollute check diagnostics."""
    pkg_dir = tmp_path / "check_holes"
    _write_multi_claim_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Generated helper claims:" in result.output
    assert "__conjunction_result" not in result.output
    assert "__implication_result" not in result.output
    assert "_anon_" not in result.output


def test_check_no_hole_count_when_all_covered(tmp_path):
    """Summary omits hole count when all independent claims have priors."""
    pkg_dir = tmp_path / "check_holes"
    _write_multi_claim_package(pkg_dir)

    pkg_src = pkg_dir / "check_holes"
    (pkg_src / "priors.py").write_text(
        "from . import premise_a, premise_b\n\n"
        "PRIORS = {\n"
        '    premise_a: (0.85, "Strong evidence."),\n'
        '    premise_b: (0.70, "Moderate evidence."),\n'
        "}\n"
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Holes (no prior set)" not in result.output


def test_check_hole_flag_lists_details(tmp_path):
    """--hole flag shows detailed report with content and prior status."""
    pkg_dir = tmp_path / "check_holes"
    _write_multi_claim_package(pkg_dir, with_priors=True)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", "--hole", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Hole analysis:" in result.output
    assert "NOT SET (defaults to 0.5)" in result.output
    # premise_b is the hole
    assert "premise_b" in result.output
    assert "Evidence B is observed." in result.output
    # premise_a is covered
    assert "Covered" in result.output
    assert "prior=0.85" in result.output
    assert "Strong experimental evidence." in result.output


def test_check_hole_flag_all_covered(tmp_path):
    """--hole with all priors set shows 'all assigned' message."""
    pkg_dir = tmp_path / "check_holes"
    _write_multi_claim_package(pkg_dir)

    pkg_src = pkg_dir / "check_holes"
    (pkg_src / "priors.py").write_text(
        "from . import premise_a, premise_b\n\n"
        "PRIORS = {\n"
        '    premise_a: (0.85, "Strong evidence."),\n'
        '    premise_b: (0.70, "Moderate evidence."),\n'
        "}\n"
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", "--hole", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "All independent claims have priors assigned." in result.output
    assert "0 hole(s)" in result.output
