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
    versions_text = (package_dir / "Versions.toml").read_text()
    assert 'git_tag = "v1.2.0"' in versions_text
    # gaia_lang_version is recorded so downstream consumers know which
    # BP engine produced the registered beliefs. Must be a concrete PEP 440
    # version from importlib.metadata, not the 'unknown' fallback.
    import re as _re

    _match = _re.search(r'gaia_lang_version = "([^"]+)"', versions_text)
    assert _match is not None, f"gaia_lang_version missing from Versions.toml:\n{versions_text}"
    assert _match.group(1) != "unknown", (
        "gaia_lang_version fell back to 'unknown' — importlib.metadata should "
        "resolve it in this test environment"
    )
    assert _re.match(r"^\d+\.\d+", _match.group(1)), f"unexpected version format: {_match.group(1)}"
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


def test_render_versions_toml_emits_gaia_lang_version_when_present():
    """New entries with gaia_lang_version emit it in canonical order; older entries
    lacking the field render unchanged (forward compat when appending)."""
    from gaia.cli.commands.register import _render_versions_toml

    versions = {
        "1.0.0": {
            "ir_hash": "sha256:aaa",
            "git_tag": "v1.0.0",
            "git_sha": "deadbeef",
            "registered_at": "2026-01-01T00:00:00Z",
            # Missing gaia_lang_version — simulates a legacy Versions.toml entry
        },
        "1.1.0": {
            "ir_hash": "sha256:bbb",
            "git_tag": "v1.1.0",
            "git_sha": "cafebabe",
            "registered_at": "2026-04-09T12:00:00Z",
            "gaia_lang_version": "0.2.7",
        },
    }
    rendered = _render_versions_toml(versions)

    # 1.0.0 is untouched — no gaia_lang_version emitted
    assert '[versions."1.0.0"]' in rendered
    # 1.1.0 emits the new field in canonical order (after registered_at)
    assert '[versions."1.1.0"]' in rendered
    assert 'gaia_lang_version = "0.2.7"' in rendered
    # Canonical order: registered_at comes immediately before gaia_lang_version
    pos_registered = rendered.find('registered_at = "2026-04-09T12:00:00Z"')
    pos_gaia = rendered.find('gaia_lang_version = "0.2.7"')
    assert pos_registered < pos_gaia
    # Legacy entry at 1.0.0 has NO gaia_lang_version line
    v1_block = rendered.split('[versions."1.0.0"]')[1].split('[versions."1.1.0"]')[0]
    assert "gaia_lang_version" not in v1_block


def test_render_versions_toml_preserves_unknown_keys_with_types():
    """Forward-compat: keys not in the canonical list are preserved AND their
    native TOML type is respected (not silently coerced to strings). This
    guards against the corruption mode where an older gaia reads a
    Versions.toml with a bool/int field added by a newer gaia and re-emits it
    as a quoted string.

    Regression test for Codex adversarial review Finding 3 (medium).
    """
    from gaia.cli.commands.register import _render_versions_toml

    versions = {
        "2.0.0": {
            "ir_hash": "sha256:xyz",
            "git_tag": "v2.0.0",
            "git_sha": "1234abcd",
            "registered_at": "2027-01-01T00:00:00Z",
            "gaia_lang_version": "0.3.0",
            # Hypothetical future fields with different types
            "needs_rebuild": True,
            "retry_count": 3,
            "freshness_score": 0.85,
            "some_future_field": "forward-compat-value",
        },
    }
    rendered = _render_versions_toml(versions)

    # Canonical fields emitted first in canonical order
    assert 'ir_hash = "sha256:xyz"' in rendered
    assert 'gaia_lang_version = "0.3.0"' in rendered

    # Non-string extras emitted as native TOML literals — the critical fix
    assert "needs_rebuild = true" in rendered  # bool, NOT "true"
    assert "retry_count = 3" in rendered  # int, NOT "3"
    assert "freshness_score = 0.85" in rendered  # float, NOT "0.85"
    # String extras still quoted
    assert 'some_future_field = "forward-compat-value"' in rendered

    # Unknown fields come AFTER canonical fields, alphabetically sorted
    pos_canonical = rendered.find('gaia_lang_version = "0.3.0"')
    pos_freshness = rendered.find("freshness_score")
    pos_needs = rendered.find("needs_rebuild")
    pos_retry = rendered.find("retry_count")
    pos_some = rendered.find("some_future_field")
    assert pos_canonical < pos_freshness
    assert pos_freshness < pos_needs
    assert pos_needs < pos_retry
    assert pos_retry < pos_some


def test_render_versions_toml_rejects_complex_types():
    """Unsupported types (arrays, dicts, None) must raise ValueError rather
    than silently corrupting the output. Explicit failure beats silent data
    loss for the forward-compat path."""
    import pytest as _pytest

    from gaia.cli.commands.register import _render_versions_toml

    for bad_value in ([1, 2, 3], {"nested": "dict"}, None):
        versions = {
            "1.0.0": {
                "ir_hash": "sha256:aaa",
                "git_tag": "v1.0.0",
                "git_sha": "deadbeef",
                "registered_at": "2026-01-01T00:00:00Z",
                "gaia_lang_version": "0.2.7",
                "weird_field": bad_value,
            },
        }
        with _pytest.raises(ValueError, match="Cannot render Versions.toml value of type"):
            _render_versions_toml(versions)


def test_read_gaia_lang_version_from_compile_metadata(tmp_path):
    """Register reads gaia_lang_version from `.gaia/compile_metadata.json`
    rather than from the live process environment. This makes registration
    reproducible from a committed package state regardless of which gaia-lang
    the operator has installed at register time.

    Covers all three branches of the helper:
    1. File present and well-formed → returns the recorded version
    2. File missing → returns "unknown"
    3. File present but malformed / missing field → returns "unknown"
    """
    from gaia.cli.commands.register import _read_gaia_lang_version_from_compile_metadata

    # Case 1: file present, concrete version
    pkg_dir = tmp_path / "with_metadata"
    (pkg_dir / ".gaia").mkdir(parents=True)
    (pkg_dir / ".gaia" / "compile_metadata.json").write_text(
        json.dumps(
            {
                "gaia_lang_version": "0.3.1",
                "compiled_at": "2026-05-01T00:00:00Z",
                "ir_hash": "sha256:fake",
            }
        )
    )
    assert _read_gaia_lang_version_from_compile_metadata(pkg_dir) == "0.3.1"

    # Case 2: file missing
    pkg_dir_missing = tmp_path / "no_metadata"
    pkg_dir_missing.mkdir()
    assert _read_gaia_lang_version_from_compile_metadata(pkg_dir_missing) == "unknown"

    # Case 3: file present but malformed
    pkg_dir_bad = tmp_path / "malformed_metadata"
    (pkg_dir_bad / ".gaia").mkdir(parents=True)
    (pkg_dir_bad / ".gaia" / "compile_metadata.json").write_text("not-valid-json {{{")
    assert _read_gaia_lang_version_from_compile_metadata(pkg_dir_bad) == "unknown"

    # Case 4: file present and valid JSON but missing the field
    pkg_dir_noField = tmp_path / "no_field_metadata"
    (pkg_dir_noField / ".gaia").mkdir(parents=True)
    (pkg_dir_noField / ".gaia" / "compile_metadata.json").write_text(
        json.dumps({"compiled_at": "2026-05-01T00:00:00Z"})
    )
    assert _read_gaia_lang_version_from_compile_metadata(pkg_dir_noField) == "unknown"
