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
        "from gaia.engine.lang import claim, setting\n\n"
        'env = setting("Environment.")\n'
        'a = claim("First.")\n'
        'b = claim("Second.")\n'
        '__all__ = ["b"]\n'
    )

    result = runner.invoke(app, ["build", "compile", str(pkg_dir)])
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
        "from gaia.engine.lang import claim\n\n"
        'x = claim("X from section A.")\n'
        'y = claim("Y from section A.")\n'
    )
    (pkg_src / "sec_b.py").write_text(
        'from gaia.engine.lang import claim\n\nz = claim("Z from section B.")\n'
    )
    (pkg_src / "__init__.py").write_text(
        'from .sec_a import *\nfrom .sec_b import *\n\n__all__ = ["z"]\n'
    )

    result = runner.invoke(app, ["build", "compile", str(pkg_dir)])
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


def test_compile_discovers_source_modules_without_root_imports(tmp_path):
    """Source modules are declarations, not a byproduct of __init__ re-exports."""
    pkg_dir = tmp_path / "discovery_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "discovery-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "discovery_pkg"
    pkg_src.mkdir()
    (pkg_src / "claims.py").write_text(
        "from gaia.engine.lang import claim, support\n\n"
        'evidence = claim("Evidence from an unimported module.")\n'
        'result = claim("Result from an unimported module.")\n'
        "_strat_result = support(\n"
        '    [evidence], result, reason="Evidence supports result.", prior=0.9\n'
        ")\n"
    )
    (pkg_src / "__init__.py").write_text('__all__ = ["result"]\n')

    result = runner.invoke(app, ["build", "compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    by_label = {k["label"]: k for k in ir["knowledges"] if "label" in k}

    assert by_label["evidence"]["module"] == "claims"
    assert by_label["result"]["module"] == "claims"
    assert by_label["result"]["exported"] is True
    assert ir["module_order"] == ["claims"]


def test_load_labels_private_strategy_names_from_declaring_module(tmp_path):
    """Underscore-prefixed strategy variables still get stable internal labels."""
    from gaia.engine.packaging import load_gaia_package

    pkg_dir = tmp_path / "private_strategy_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "private-strategy-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "private_strategy_pkg"
    pkg_src.mkdir()
    (pkg_src / "logic.py").write_text(
        "from gaia.engine.lang import claim, support\n\n"
        'premise = claim("Premise.")\n'
        'result = claim("Result.")\n'
        '_strat_result = support([premise], result, reason="Premise entails result.", prior=0.9)\n'
    )
    (pkg_src / "__init__.py").write_text('from .logic import result\n__all__ = ["result"]\n')

    loaded = load_gaia_package(pkg_dir)

    assert len(loaded.package.strategies) == 1
    assert loaded.package.strategies[0].label == "_strat_result"
