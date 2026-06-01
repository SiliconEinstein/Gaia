"""CLI tests for the package-native ``gaia research`` M1 skeleton."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _write_research_package(pkg_dir: Path) -> Path:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "research-demo-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "research_demo"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / "src" / "research_demo"
    src.mkdir(parents=True)
    init_py = src / "__init__.py"
    init_py.write_text(
        "from gaia.engine.lang import claim\n\n"
        'seed = claim("Seed claim for research actions.")\n'
        '__all__ = ["seed"]\n',
        encoding="utf-8",
    )
    return init_py


def _read_events(pkg_dir: Path) -> list[dict[str, object]]:
    events_path = pkg_dir / ".gaia" / "research" / "events.jsonl"
    assert events_path.exists()
    return [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_research_group_is_help_visible() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "research" in result.output


def test_research_status_creates_manifest_and_suggests_inquiry_commands(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")

    result = runner.invoke(app, ["research", "status", str(pkg_dir)])

    assert result.exit_code == 0, result.output
    assert "Research status" in result.output
    assert "gaia inquiry obligation add" in result.output
    assert init_py.read_text(encoding="utf-8") == source_before

    manifest = json.loads(
        (pkg_dir / ".gaia" / "research" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == 1
    assert manifest["package"]["project_name"] == "research-demo-gaia"
    assert manifest["package"]["import_name"] == "research_demo"
    assert manifest["inquiry"]["open_obligations"] == 0
    assert "obligations.json" not in {
        path.name for path in (pkg_dir / ".gaia" / "research").iterdir()
    }

    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "status.checked"


def test_research_scan_dry_run_writes_events_without_pulls_or_source_edits(
    tmp_path: Path,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")

    result = runner.invoke(
        app,
        ["research", "explore", str(pkg_dir), "--mode", "scan", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert "mode: scan" in result.output
    assert "pull_budget: 0" in result.output
    assert "gaia inquiry obligation add" in result.output
    assert init_py.read_text(encoding="utf-8") == source_before
    assert not (pkg_dir / ".gaia" / "lkm_packages").exists()
    assert not (pkg_dir / ".gaia" / "exploration").exists()
    assert not (pkg_dir / ".gaia" / "research" / "obligations.json").exists()

    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "explore.scan.planned"
    assert events[-1]["payload"]["dry_run"] is True
    assert events[-1]["payload"]["pull_budget"] == 0


def test_research_assess_artifact_only_records_planning_event(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")

    result = runner.invoke(
        app,
        ["research", "assess", str(pkg_dir), "--focus", "seed", "--artifact-only"],
    )

    assert result.exit_code == 0, result.output
    assert "artifact_only: true" in result.output
    assert init_py.read_text(encoding="utf-8") == source_before

    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "assess.planned"
    assert events[-1]["payload"]["artifact_only"] is True
    assert events[-1]["payload"]["focus"] == "seed"


def test_research_rejects_non_package_without_creating_layout(tmp_path: Path) -> None:
    target = tmp_path / "not-yet-gaia"

    result = runner.invoke(app, ["research", "status", str(target)])

    assert result.exit_code != 0
    assert "gaia pkg scaffold --target" in result.output
    assert not (target / ".gaia" / "research").exists()


def test_research_commands_preserve_build_check_path(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)

    scan = runner.invoke(
        app,
        ["research", "explore", str(pkg_dir), "--mode", "scan", "--dry-run"],
    )
    assert scan.exit_code == 0, scan.output

    check = runner.invoke(app, ["build", "check", str(pkg_dir)])
    assert check.exit_code == 0, check.output
