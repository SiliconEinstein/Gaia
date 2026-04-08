"""Tests for gaia check command."""

from __future__ import annotations

import json
import shutil

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


def _write_hole_fill_package(pkg_dir) -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "check-hole-fill-gaia"\nversion = "1.2.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "check_hole_fill"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, fills, hole\n\n"
        'result = claim("A supporting theorem.")\n'
        'missing = hole("A missing premise.")\n'
        'fills(source=result, hole=missing, reason="The theorem establishes the hole.")\n'
        '__all__ = ["result", "missing"]\n'
    )


def test_check_passes_with_fresh_artifacts(tmp_path):
    pkg_dir = tmp_path / "check_demo"
    _write_package(pkg_dir)

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


def test_check_fails_when_manifest_is_missing(tmp_path):
    pkg_dir = tmp_path / "check_demo"
    _write_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    (pkg_dir / ".gaia" / "manifests" / "exports.json").unlink()

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code != 0
    assert "missing compiled manifest" in result.output.lower()


def test_check_fails_when_manifest_directory_is_missing(tmp_path):
    pkg_dir = tmp_path / "check_demo"
    _write_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    shutil.rmtree(pkg_dir / ".gaia" / "manifests")

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code != 0
    assert "missing .gaia/manifests" in result.output.lower()


def test_check_fails_when_holes_manifest_is_tampered(tmp_path):
    pkg_dir = tmp_path / "check_hole_fill"
    _write_hole_fill_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    holes_path = pkg_dir / ".gaia" / "manifests" / "holes.json"
    holes = json.loads(holes_path.read_text())
    holes["holes"][0]["content"] = "tampered"
    holes_path.write_text(json.dumps(holes, indent=2, sort_keys=True))

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code != 0
    assert "holes.json" in result.output
    assert "does not match current source" in result.output


def test_check_fails_when_bridges_manifest_is_tampered(tmp_path):
    pkg_dir = tmp_path / "check_hole_fill"
    _write_hole_fill_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    bridges_path = pkg_dir / ".gaia" / "manifests" / "bridges.json"
    bridges = json.loads(bridges_path.read_text())
    bridges["bridges"][0]["mode"] = "infer"
    bridges_path.write_text(json.dumps(bridges, indent=2, sort_keys=True))

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code != 0
    assert "bridges.json" in result.output
    assert "does not match current source" in result.output


def test_check_warns_for_unused_exported_hole(tmp_path):
    pkg_dir = tmp_path / "hole_demo"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "hole-demo-gaia"\nversion = "1.2.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "hole_demo"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import hole\n\n"
        'key_missing_lemma = hole("A missing premise.")\n'
        '__all__ = ["key_missing_lemma"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "has no downstream local use" in result.output
