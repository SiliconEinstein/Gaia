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


def _search(query: str, rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "query": {"text": query, "provider": "lkm", "kind": "knowledge"},
        "results": rows,
    }


def _lkm_row(
    paper_id: str,
    node_id: str,
    score: float,
    *,
    paper_title: str,
    doi: str | None = None,
) -> dict[str, object]:
    return {
        "id": node_id,
        "provider": "lkm",
        "kind": "claim",
        "title": f"Claim surfaced from {paper_title}",
        "source": {
            "paper_id": paper_id,
            "paper_title": paper_title,
            "doi": doi,
            "index_id": "bohrium",
        },
        "rank": {"score": score, "score_kind": "retrieval"},
        "gaia": {"qid": None},
    }


def _landscape_artifacts(pkg_dir: Path, stem: str = "scan") -> list[Path]:
    return sorted((pkg_dir / ".gaia" / "research" / "landscapes").glob(f"{stem}-*.json"))


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


def test_research_scan_consumes_search_json_and_writes_landscape(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "free fall",
                [
                    _lkm_row(
                        "P1",
                        "lkm:bohrium:n1",
                        0.7,
                        paper_title="Paper One",
                        doi="10.1/example",
                    ),
                    _lkm_row("P1", "lkm:bohrium:n2", 0.9, paper_title="Paper One"),
                    _lkm_row("P2", "lkm:bohrium:n3", 0.4, paper_title="Paper Two"),
                ],
            )
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["research", "explore", str(pkg_dir), "--mode", "scan", "--search-json", str(search_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Landscape:" in result.output
    assert "pull_budget: 0" in result.output
    assert init_py.read_text(encoding="utf-8") == source_before
    assert not (pkg_dir / ".gaia" / "lkm_packages").exists()

    artifacts = _landscape_artifacts(pkg_dir)
    assert len(artifacts) == 1
    payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert payload["kind"] == "research_landscape"
    assert payload["action"] == "explore.scan"
    assert payload["pull_budget"] == 0
    assert payload["stats"]["query_batches"] == 1
    assert payload["stats"]["paper_leads"] == 2
    assert payload["query_provenance"][0]["query"] == "free fall"
    assert payload["query_provenance"][0]["path"] == str(search_path)
    assert [lead["paper_id"] for lead in payload["paper_leads"]] == ["P1", "P2"]
    assert payload["paper_leads"][0]["lkm_node_ids"] == ["lkm:bohrium:n1", "lkm:bohrium:n2"]
    assert payload["pull_candidates"][0]["command"] == (
        "gaia pkg add --lkm-index bohrium --lkm-paper P1"
    )
    assert payload["coverage_map"]["query_families"][0]["paper_leads"] == 2
    assert payload["candidate_focuses"][0]["status"] == "candidate"

    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "explore.scan.completed"
    assert events[-1]["payload"]["artifact"].endswith(artifacts[0].name)
    assert events[-1]["payload"]["stats"]["paper_leads"] == 2


def test_research_scan_reads_search_json_from_stdin(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    envelope = _search(
        "stdin query",
        [_lkm_row("P3", "lkm:bohrium:n4", 0.5, paper_title="Paper Three")],
    )

    result = runner.invoke(
        app,
        ["research", "explore", str(pkg_dir), "--mode", "scan", "--search-json", "-"],
        input=json.dumps(envelope),
    )

    assert result.exit_code == 0, result.output
    artifacts = _landscape_artifacts(pkg_dir)
    assert len(artifacts) == 1
    payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert payload["query_provenance"][0]["path"] == "<stdin>"
    assert payload["paper_leads"][0]["paper_id"] == "P3"


def test_research_expand_requires_focus_or_obligation(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "targeted query",
                [_lkm_row("P4", "lkm:bohrium:n5", 0.8, paper_title="Paper Four")],
            )
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "explore",
            str(pkg_dir),
            "--mode",
            "expand",
            "--search-json",
            str(search_path),
        ],
    )

    assert result.exit_code != 0
    assert "requires --focus or --obligation" in result.output
    assert not _landscape_artifacts(pkg_dir, "expand")


def test_research_expand_writes_targeted_landscape(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "targeted query",
                [_lkm_row("P4", "lkm:bohrium:n5", 0.8, paper_title="Paper Four")],
            )
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "explore",
            str(pkg_dir),
            "--mode",
            "expand",
            "--focus",
            "seed",
            "--search-json",
            str(search_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Target: focus seed" in result.output
    assert "pull_budget: 0" in result.output
    assert init_py.read_text(encoding="utf-8") == source_before
    assert not (pkg_dir / ".gaia" / "lkm_packages").exists()

    artifacts = _landscape_artifacts(pkg_dir, "expand")
    assert len(artifacts) == 1
    payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert payload["action"] == "explore.expand"
    assert payload["target"] == {"kind": "focus", "id": "seed"}
    assert payload["pull_budget"] == 0
    assert payload["paper_leads"][0]["paper_id"] == "P4"

    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "explore.expand.completed"
    assert events[-1]["payload"]["target"] == {"kind": "focus", "id": "seed"}


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
