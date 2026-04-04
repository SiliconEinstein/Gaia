"""Tests for module narrative fields in compiled IR."""

import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def test_compile_single_file_declaration_index(tmp_path):
    """Single-file package: module=None, declaration_index tracks order."""
    pkg_dir = tmp_path / "single_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "single-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "single_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, setting\n\n"
        'env = setting("Environment.")\n'
        'a = claim("First.")\n'
        'b = claim("Second.")\n'
        '__all__ = ["b"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    by_label = {k["label"]: k for k in ir["knowledges"] if "label" in k}

    assert by_label["env"].get("module") is None  # None excluded from JSON
    assert by_label["env"]["declaration_index"] == 0
    assert by_label["a"]["declaration_index"] == 1
    assert by_label["b"]["declaration_index"] == 2
    assert by_label["b"]["exported"] is True
    assert by_label["a"].get("exported", False) is False
    assert ir.get("module_order") is None


def test_compile_multi_file_module_order(tmp_path):
    """Multi-file package: module and module_order populated."""
    pkg_dir = tmp_path / "multi_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "multi-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "multi_pkg"
    pkg_src.mkdir()
    (pkg_src / "sec_a.py").write_text(
        "from gaia.lang import claim\n\n"
        'x = claim("X from section A.")\n'
        'y = claim("Y from section A.")\n'
    )
    (pkg_src / "sec_b.py").write_text(
        'from gaia.lang import claim\n\nz = claim("Z from section B.")\n'
    )
    (pkg_src / "__init__.py").write_text(
        'from .sec_a import *\nfrom .sec_b import *\n\n__all__ = ["z"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    by_label = {k["label"]: k for k in ir["knowledges"] if "label" in k}

    assert by_label["x"]["module"] == "sec_a"
    assert by_label["y"]["module"] == "sec_a"
    assert by_label["z"]["module"] == "sec_b"
    assert by_label["x"]["declaration_index"] == 0
    assert by_label["y"]["declaration_index"] == 1
    assert by_label["z"]["declaration_index"] == 0
    assert by_label["z"]["exported"] is True
    assert by_label["x"]["exported"] is False
    assert ir["module_order"] == ["sec_a", "sec_b"]
