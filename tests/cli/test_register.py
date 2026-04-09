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


def _write_dependency_with_local_hole(dep_dir) -> None:
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "dep-bridge-gaia"\n'
        'version = "0.4.0"\n'
        "dependencies = [\n"
        '  "gaia-lang>=0.1.0",\n'
        "]\n\n"
        "[tool.gaia]\n"
        'namespace = "github"\n'
        'type = "knowledge-package"\n'
    )
    dep_src = dep_dir / "src" / "dep_bridge"
    dep_src.mkdir(parents=True)
    (dep_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'missing_lemma = claim("A missing lemma.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[missing_lemma], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )


def _write_package_with_local_hole_and_bridge(pkg_dir) -> None:
    pkg_dir.mkdir()
    (pkg_dir / ".gitignore").write_text(".gaia/\n")
    (pkg_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "register-bridge-gaia"\n'
        'version = "1.2.0"\n'
        'description = "Registration demo with public premises and bridges"\n'
        "dependencies = [\n"
        '  "gaia-lang>=0.1.0",\n'
        '  "dep-bridge-gaia >= 0.4.0",\n'
        "]\n\n"
        "[tool.gaia]\n"
        'namespace = "github"\n'
        'type = "knowledge-package"\n'
        'uuid = "08e78748-e1d5-5881-b72a-af9cc22550ac"\n'
    )
    pkg_src = pkg_dir / "register_bridge"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction, fills\n"
        "from dep_bridge import missing_lemma\n\n"
        'local_premise = claim("A local missing lemma.")\n'
        'main_claim = claim("A release-ready claim.")\n'
        'bridge_claim = claim("A bridge claim.")\n'
        "deduction(premises=[local_premise], conclusion=main_claim)\n"
        'fills(source=bridge_claim, target=missing_lemma, reason="Theorem 3 establishes A.")\n'
        '__all__ = ["main_claim", "bridge_claim"]\n'
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
    release_dir = "packages/register-demo/releases/1.2.0"
    assert f"{release_dir}/exports.json" in plan["files"]
    assert f"{release_dir}/premises.json" in plan["files"]
    assert f"{release_dir}/holes.json" in plan["files"]
    assert f"{release_dir}/bridges.json" in plan["files"]
    exports_manifest = json.loads(plan["files"][f"{release_dir}/exports.json"])
    premises_manifest = json.loads(plan["files"][f"{release_dir}/premises.json"])
    assert exports_manifest["manifest_schema_version"] == 1
    assert exports_manifest["exports"][0]["label"] == "exported_claim"
    assert premises_manifest["premises"] == []


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
    release_dir = package_dir / "releases" / "1.2.0"
    assert (release_dir / "exports.json").exists()
    assert (release_dir / "premises.json").exists()
    assert (release_dir / "holes.json").exists()
    assert (release_dir / "bridges.json").exists()
    assert (release_dir / "exports.json").read_text().endswith("\n")
    assert 'name = "register-demo"' in (package_dir / "Package.toml").read_text()
    assert 'git_tag = "v1.2.0"' in (package_dir / "Versions.toml").read_text()
    assert '"aristotle-mechanics-gaia" = ">= 1.0.0"' in (package_dir / "Deps.toml").read_text()
    exports_manifest = json.loads((release_dir / "exports.json").read_text())
    premises_manifest = json.loads((release_dir / "premises.json").read_text())
    holes_manifest = json.loads((release_dir / "holes.json").read_text())
    bridges_manifest = json.loads((release_dir / "bridges.json").read_text())
    assert exports_manifest["exports"][0]["qid"] == "github:register_demo::exported_claim"
    assert premises_manifest["premises"] == []
    assert holes_manifest["holes"] == []
    assert bridges_manifest["bridges"] == []
    assert (
        _run(["git", "branch", "--show-current"], cwd=registry_dir)
        == "register/register-demo-1.2.0"
    )


def test_register_dry_run_emits_nonempty_release_manifests(tmp_path, monkeypatch):
    dep_dir = tmp_path / "dep_bridge"
    pkg_dir = tmp_path / "register_bridge"
    remote_dir = tmp_path / "register_bridge_remote.git"
    _write_dependency_with_local_hole(dep_dir)
    _write_package_with_local_hole_and_bridge(pkg_dir)
    monkeypatch.syspath_prepend(str(dep_dir / "src"))

    dep_compile = runner.invoke(app, ["compile", str(dep_dir)])
    assert dep_compile.exit_code == 0, dep_compile.output

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
            "https://github.com/example/RegisterBridge.gaia",
        ],
    )
    assert result.exit_code == 0, result.output

    plan = json.loads(result.output)
    release_dir = "packages/register-bridge/releases/1.2.0"
    premises_manifest = json.loads(plan["files"][f"{release_dir}/premises.json"])
    holes_manifest = json.loads(plan["files"][f"{release_dir}/holes.json"])
    bridges_manifest = json.loads(plan["files"][f"{release_dir}/bridges.json"])

    assert premises_manifest["premises"][0]["role"] == "local_hole"
    assert premises_manifest["premises"][0]["required_by"] == ["github:register_bridge::main_claim"]
    assert holes_manifest["holes"][0]["qid"] == "github:register_bridge::local_premise"
    assert bridges_manifest["bridges"][0]["target_qid"] == "github:dep_bridge::missing_lemma"
    assert bridges_manifest["bridges"][0]["target_interface_hash"].startswith("sha256:")
    assert bridges_manifest["bridges"][0]["declared_by_owner_of_source"] is True


def test_register_writes_nonempty_release_manifests_to_local_checkout(tmp_path, monkeypatch):
    dep_dir = tmp_path / "dep_bridge"
    pkg_dir = tmp_path / "register_bridge"
    remote_dir = tmp_path / "register_bridge_remote.git"
    registry_dir = tmp_path / "gaia-registry"
    _write_dependency_with_local_hole(dep_dir)
    _write_package_with_local_hole_and_bridge(pkg_dir)
    monkeypatch.syspath_prepend(str(dep_dir / "src"))

    dep_compile = runner.invoke(app, ["compile", str(dep_dir)])
    assert dep_compile.exit_code == 0, dep_compile.output

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
            "https://github.com/example/RegisterBridge.gaia",
            "--registry-dir",
            str(registry_dir),
        ],
    )
    assert result.exit_code == 0, result.output

    release_dir = registry_dir / "packages" / "register-bridge" / "releases" / "1.2.0"
    premises_manifest = json.loads((release_dir / "premises.json").read_text())
    holes_manifest = json.loads((release_dir / "holes.json").read_text())
    bridges_manifest = json.loads((release_dir / "bridges.json").read_text())

    assert premises_manifest["premises"][0]["qid"] == "github:register_bridge::local_premise"
    assert holes_manifest["holes"][0]["required_by"] == ["github:register_bridge::main_claim"]
    assert bridges_manifest["bridges"][0]["target_package"] == "dep-bridge"
    assert bridges_manifest["bridges"][0]["target_dependency_req"] == ">=0.4.0"
    assert bridges_manifest["bridges"][0]["justification"] == "Theorem 3 establishes A."


def test_register_fails_when_release_dir_already_exists(tmp_path):
    pkg_dir = tmp_path / "register_demo"
    remote_dir = tmp_path / "register_demo_remote.git"
    registry_dir = tmp_path / "gaia-registry"
    _write_package(pkg_dir)
    _init_git_repo(pkg_dir, remote_dir)
    _init_registry_repo(registry_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    package_dir = registry_dir / "packages" / "register-demo"
    release_dir = package_dir / "releases" / "1.2.0"
    release_dir.mkdir(parents=True)
    (release_dir / "exports.json").write_text("{}\n")
    _run(["git", "add", "."], cwd=registry_dir)
    _run(["git", "commit", "-m", "precreate release dir"], cwd=registry_dir)

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
    assert result.exit_code != 0
    assert "release metadata already exists in registry checkout" in result.output


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
