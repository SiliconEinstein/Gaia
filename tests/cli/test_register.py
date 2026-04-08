"""Tests for gaia register command."""

from __future__ import annotations

import json
import subprocess

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _run(args: list[str], *, cwd) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def _write_package(pkg_dir) -> None:
    pkg_dir.mkdir()
    (pkg_dir / ".gitignore").write_text(".gaia/\n")
    (pkg_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "register-demo-gaia"\n'
        'version = "1.2.0"\n'
        'description = "Registration demo"\n'
        "dependencies = [\n"
        '  "gaia-lang>=0.1.0",\n'
        '  "aristotle-mechanics-gaia >= 1.0.0",\n'
        "]\n\n"
        "[tool.gaia]\n"
        'namespace = "github"\n'
        'type = "knowledge-package"\n'
        'uuid = "336ed68f-0bac-5ca0-87d4-7b16caf5d00b"\n'
    )
    pkg_src = pkg_dir / "register_demo"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'exported_claim = claim("A release-ready claim.")\n'
        '__all__ = ["exported_claim"]\n'
    )


def _init_git_repo(pkg_dir, remote_dir) -> None:
    _run(["git", "init"], cwd=pkg_dir)
    _run(["git", "config", "user.name", "Gaia Test"], cwd=pkg_dir)
    _run(["git", "config", "user.email", "gaia@example.com"], cwd=pkg_dir)
    _run(["git", "add", "."], cwd=pkg_dir)
    _run(["git", "commit", "-m", "init"], cwd=pkg_dir)
    _run(["git", "branch", "-M", "main"], cwd=pkg_dir)

    _run(["git", "init", "--bare", str(remote_dir)], cwd=pkg_dir.parent)
    _run(["git", "remote", "add", "origin", str(remote_dir)], cwd=pkg_dir)
    _run(["git", "push", "-u", "origin", "main"], cwd=pkg_dir)


def _init_registry_repo(registry_dir) -> None:
    registry_dir.mkdir()
    _run(["git", "init"], cwd=registry_dir)
    _run(["git", "config", "user.name", "Gaia Registry"], cwd=registry_dir)
    _run(["git", "config", "user.email", "registry@example.com"], cwd=registry_dir)
    (registry_dir / "README.md").write_text("# Registry\n")
    _run(["git", "add", "README.md"], cwd=registry_dir)
    _run(["git", "commit", "-m", "init registry"], cwd=registry_dir)
    _run(["git", "branch", "-M", "main"], cwd=registry_dir)


def test_register_dry_run_emits_registration_plan(tmp_path):
    pkg_dir = tmp_path / "register_demo"
    remote_dir = tmp_path / "register_demo_remote.git"
    _write_package(pkg_dir)
    _init_git_repo(pkg_dir, remote_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    _run(["git", "tag", "v1.2.0"], cwd=pkg_dir)
    _run(["git", "push", "origin", "v1.2.0"], cwd=pkg_dir)

    result = runner.invoke(
        app,
        [
            "register",
            str(pkg_dir),
            "--repo",
            "https://github.com/example/RegisterDemo.gaia",
        ],
    )
    assert result.exit_code == 0, result.output

    plan = json.loads(result.output)
    assert plan["package"]["name"] == "register-demo"
    assert plan["package"]["pypi_name"] == "register-demo-gaia"
    assert plan["version"]["git_tag"] == "v1.2.0"
    assert plan["version"]["ir_hash"].startswith("sha256:")
    assert plan["deps"] == {"aristotle-mechanics-gaia": ">= 1.0.0"}


def test_register_writes_registry_metadata_to_local_checkout(tmp_path):
    pkg_dir = tmp_path / "register_demo"
    remote_dir = tmp_path / "register_demo_remote.git"
    registry_dir = tmp_path / "gaia-registry"
    _write_package(pkg_dir)
    _init_git_repo(pkg_dir, remote_dir)
    _init_registry_repo(registry_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    _run(["git", "tag", "v1.2.0"], cwd=pkg_dir)
    _run(["git", "push", "origin", "v1.2.0"], cwd=pkg_dir)

    result = runner.invoke(
        app,
        [
            "register",
            str(pkg_dir),
            "--repo",
            "https://github.com/example/RegisterDemo.gaia",
            "--registry-dir",
            str(registry_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Prepared registry branch" in result.output

    package_dir = registry_dir / "packages" / "register-demo"
    assert (package_dir / "Package.toml").exists()
    assert (package_dir / "Versions.toml").exists()
    assert (package_dir / "Deps.toml").exists()
    assert 'name = "register-demo"' in (package_dir / "Package.toml").read_text()
    assert 'git_tag = "v1.2.0"' in (package_dir / "Versions.toml").read_text()
    assert '"aristotle-mechanics-gaia" = ">= 1.0.0"' in (package_dir / "Deps.toml").read_text()
    assert (
        _run(["git", "branch", "--show-current"], cwd=registry_dir)
        == "register/register-demo-1.2.0"
    )


def test_register_fails_on_invalid_fills_target(tmp_path, monkeypatch):
    dep_dir = tmp_path / "dep_register_missing_root"
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        '[project]\nname = "dep-register-missing-gaia"\nversion = "0.4.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    dep_src = dep_dir / "src" / "dep_register_missing"
    dep_src.mkdir(parents=True)
    (dep_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'missing_lemma = claim("A missing lemma.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[missing_lemma], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )
    monkeypatch.syspath_prepend(str(dep_dir / "src"))

    pkg_dir = tmp_path / "register_demo"
    remote_dir = tmp_path / "register_demo_remote.git"
    _write_package(pkg_dir)
    (pkg_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "register-demo-gaia"\n'
        'version = "1.2.0"\n'
        'description = "Registration demo"\n'
        "dependencies = [\n"
        '  "gaia-lang>=0.1.0",\n'
        '  "dep-register-missing-gaia >= 0.4.0",\n'
        "]\n\n"
        "[tool.gaia]\n"
        'namespace = "github"\n'
        'type = "knowledge-package"\n'
        'uuid = "336ed68f-0bac-5ca0-87d4-7b16caf5d00b"\n'
    )
    (pkg_dir / "register_demo" / "__init__.py").write_text(
        "from gaia.lang import claim, fills\n"
        "from dep_register_missing import missing_lemma\n\n"
        'exported_claim = claim("A release-ready claim.")\n'
        "fills(source=exported_claim, target=missing_lemma)\n"
        '__all__ = ["exported_claim"]\n'
    )
    _init_git_repo(pkg_dir, remote_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code != 0
    assert "missing .gaia/manifests/premises.json" in compile_result.output

    _run(["git", "tag", "v1.2.0"], cwd=pkg_dir)
    _run(["git", "push", "origin", "v1.2.0"], cwd=pkg_dir)

    result = runner.invoke(
        app,
        [
            "register",
            str(pkg_dir),
            "--repo",
            "https://github.com/example/RegisterDemo.gaia",
        ],
    )
    assert result.exit_code != 0
    assert "missing .gaia/manifests/premises.json" in result.output
