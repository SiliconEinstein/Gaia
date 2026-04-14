"""Tests for gaia init command."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from gaia.cli.main import app

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

runner = CliRunner()


def _fake_uv_init(args, *, cwd, text, capture_output):
    """Simulate `uv init --lib <name>`: create the directory tree that uv would create."""
    # args: ["uv", "init", "--lib", "<name>"]
    name = args[3]
    uv_import_name = name.replace("-", "_")
    pkg_dir = Path(cwd) / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
        f'description = "Add your description here"\n'
    )
    src_dir = pkg_dir / "src" / uv_import_name
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text(
        f'def hello() -> str:\n    return "Hello from {uv_import_name}!"\n'
    )
    (pkg_dir / ".gitignore").write_text("# uv default gitignore\n")
    return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


def _fake_uv_add_ok(args, *, cwd, text, capture_output):
    """Simulate a successful `uv add gaia-lang`."""
    return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


def _fake_uv_add_fail(args, *, cwd, text, capture_output):
    """Simulate a failing `uv add gaia-lang`."""
    return subprocess.CompletedProcess(args, 1, stdout="", stderr="package not found")


def _fake_subprocess_run(args, *, cwd, text, capture_output):
    """Dispatch to the correct fake based on the command."""
    if args[:3] == ["uv", "init", "--lib"]:
        return _fake_uv_init(args, cwd=cwd, text=text, capture_output=capture_output)
    if args[:2] == ["uv", "add"]:
        return _fake_uv_add_ok(args, cwd=cwd, text=text, capture_output=capture_output)
    return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected command")


def _fake_subprocess_run_uv_add_fails(args, *, cwd, text, capture_output):
    """Dispatch where uv add fails."""
    if args[:3] == ["uv", "init", "--lib"]:
        return _fake_uv_init(args, cwd=cwd, text=text, capture_output=capture_output)
    if args[:2] == ["uv", "add"]:
        return _fake_uv_add_fail(args, cwd=cwd, text=text, capture_output=capture_output)
    return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected command")


def test_init_rejects_name_without_gaia_suffix():
    """Package name must end with '-gaia'."""
    result = runner.invoke(app, ["init", "my-package"])
    assert result.exit_code != 0
    assert "must end with '-gaia'" in result.output
    assert "my-package-gaia" in result.output


def test_init_creates_package(tmp_path, monkeypatch):
    """Successful init scaffolds the expected files."""
    monkeypatch.chdir(tmp_path)
    with patch("gaia.cli.commands.init.subprocess.run", side_effect=_fake_subprocess_run):
        result = runner.invoke(app, ["init", "my-research-gaia"])

    assert result.exit_code == 0, f"Failed: {result.output}"
    assert "Created Gaia knowledge package" in result.output

    pkg_dir = tmp_path / "my-research-gaia"
    assert pkg_dir.exists()

    # pyproject.toml has [tool.hatch] wheel config and [tool.gaia] section
    pyproject = pkg_dir / "pyproject.toml"
    config = tomllib.loads(pyproject.read_text())
    # Regression for #349: hatch wheel packages must be present
    assert config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/my_research"]
    assert config["tool"]["gaia"]["type"] == "knowledge-package"
    assert "uuid" in config["tool"]["gaia"]
    # uuid should be a valid UUID string
    import uuid

    uuid.UUID(config["tool"]["gaia"]["uuid"])

    # src directory was renamed: my_research_gaia → my_research
    import_dir = pkg_dir / "src" / "my_research"
    assert import_dir.exists()
    uv_default_dir = pkg_dir / "src" / "my_research_gaia"
    assert not uv_default_dir.exists()

    # __init__.py has DSL template
    init_py = import_dir / "__init__.py"
    content = init_py.read_text()
    assert "from gaia.lang import claim, setting" in content
    assert "context = setting(" in content
    assert "hypothesis = claim(" in content
    assert "evidence = claim(" in content
    assert '__all__ = ["context", "hypothesis", "evidence"]' in content

    # .gitignore includes .gaia/
    gitignore = pkg_dir / ".gitignore"
    assert ".gaia/" in gitignore.read_text()


def test_init_simple_name(tmp_path, monkeypatch):
    """A simple name like 'foo-gaia' removes the -gaia suffix for the import name."""
    monkeypatch.chdir(tmp_path)
    with patch("gaia.cli.commands.init.subprocess.run", side_effect=_fake_subprocess_run):
        result = runner.invoke(app, ["init", "foo-gaia"])

    assert result.exit_code == 0, f"Failed: {result.output}"

    pkg_dir = tmp_path / "foo-gaia"
    # src/foo_gaia → src/foo
    assert (pkg_dir / "src" / "foo").exists()
    assert not (pkg_dir / "src" / "foo_gaia").exists()


def test_init_uv_add_failure_warns_but_succeeds(tmp_path, monkeypatch):
    """If 'uv add gaia-lang' fails, the command warns but exits 0."""
    monkeypatch.chdir(tmp_path)
    with patch(
        "gaia.cli.commands.init.subprocess.run",
        side_effect=_fake_subprocess_run_uv_add_fails,
    ):
        result = runner.invoke(app, ["init", "warn-gaia"])

    assert result.exit_code == 0, f"Failed: {result.output}"
    assert "Warning" in result.output or "could not add gaia-lang" in result.output
    # Package was still created
    assert (tmp_path / "warn-gaia" / "pyproject.toml").exists()


def test_init_gitignore_not_duplicated(tmp_path, monkeypatch):
    """If .gaia patterns are already in .gitignore, don't add them again."""
    monkeypatch.chdir(tmp_path)
    with patch("gaia.cli.commands.init.subprocess.run", side_effect=_fake_subprocess_run):
        result = runner.invoke(app, ["init", "dedup-gaia"])

    assert result.exit_code == 0
    gitignore = (tmp_path / "dedup-gaia" / ".gitignore").read_text()
    assert gitignore.count(".gaia/reviews/") == 1
    assert gitignore.count(".gaia/beliefs.json") == 1
    assert gitignore.count(".gaia/dep_beliefs/") == 1


def test_init_gitignore_adds_missing_patterns_to_existing(tmp_path, monkeypatch):
    """Re-running init on a project with old .gitignore adds new patterns."""
    monkeypatch.chdir(tmp_path)
    pkg_dir = tmp_path / "migrate-gaia"
    pkg_dir.mkdir()
    # Simulate old .gitignore that only has .gaia/reviews/
    (pkg_dir / ".gitignore").write_text("# old patterns\n.gaia/reviews/\n")
    with patch("gaia.cli.commands.init.subprocess.run", side_effect=_fake_subprocess_run):
        result = runner.invoke(app, ["init", "migrate-gaia"])

    assert result.exit_code == 0
    gitignore = (pkg_dir / ".gitignore").read_text()
    assert ".gaia/reviews/" in gitignore
    assert ".gaia/beliefs.json" in gitignore
    assert ".gaia/dep_beliefs/" in gitignore
    # Old pattern not duplicated
    assert gitignore.count(".gaia/reviews/") == 1


def test_init_gitignore_replaces_broad_gaia_ignore(tmp_path, monkeypatch):
    """If .gitignore has overly broad '.gaia/', it is replaced with specific patterns."""
    monkeypatch.chdir(tmp_path)
    pkg_dir = tmp_path / "broad-gaia"
    pkg_dir.mkdir()
    # Simulate .gitignore with the overly broad .gaia/ pattern
    (pkg_dir / ".gitignore").write_text("# uv default\n.gaia/\n")
    with patch("gaia.cli.commands.init.subprocess.run", side_effect=_fake_subprocess_run):
        result = runner.invoke(app, ["init", "broad-gaia"])

    assert result.exit_code == 0
    gitignore = (pkg_dir / ".gitignore").read_text()
    # Broad pattern removed
    assert ".gaia/\n" not in gitignore
    # Specific patterns added
    assert ".gaia/reviews/" in gitignore
    assert ".gaia/beliefs.json" in gitignore
    assert ".gaia/dep_beliefs/" in gitignore


def test_init_missing_uv_shows_install_hint(tmp_path, monkeypatch):
    """Missing uv binary gives a helpful error message."""
    monkeypatch.chdir(tmp_path)
    with patch(
        "gaia.cli.commands.init.subprocess.run",
        side_effect=FileNotFoundError("uv"),
    ):
        result = runner.invoke(app, ["init", "missing-uv-gaia"])

    assert result.exit_code != 0
    assert "uv is not installed" in result.output
