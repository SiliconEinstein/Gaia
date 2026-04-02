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
        '[tool.gaia]\nnamespace = "reg"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "test_pkg"
    pkg_src.mkdir()
    # Note: need __init__.py for Python to treat as package
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import Package, claim\n\n"
        'with Package("test_pkg", namespace="test") as pkg:\n'
        '    my_claim = claim("A test claim.")\n'
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
        '[tool.gaia]\nnamespace = "reg"\ntype = "knowledge-package"\n'
    )
    result = runner.invoke(app, ["compile", str(tmp_path)])
    assert result.exit_code != 0


def test_compile_labels_assigned(tmp_path):
    """Variable names become labels in the IR."""
    pkg_dir = tmp_path / "label_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "label-pkg-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "reg"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "label_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import Package, claim, setting\n\n"
        'with Package("label_pkg", namespace="reg") as pkg:\n'
        '    bg = setting("Background context.")\n'
        '    hypothesis = claim("Main hypothesis.")\n'
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
        '[tool.gaia]\nnamespace = "reg"\ntype = "knowledge-package"\n'
    )
    src_root = pkg_dir / "src"
    src_root.mkdir()
    pkg_src = src_root / "ver_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import Package, claim\n\n"
        'with Package("ver_pkg", namespace="reg", version="0.0.0") as pkg:\n'
        '    c = claim("A claim.")\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Failed: {result.output}"

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    assert ir["package"]["version"] == "2.3.4"
    assert ir["package_name"] == "ver_pkg"
