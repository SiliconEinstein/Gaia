"""CLI tests for the package-native ``gaia research`` M1 skeleton."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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
        'seed_alt = claim("Second seed claim for research actions.")\n'
        '__all__ = ["seed", "seed_alt"]\n',
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


def _read_inquiry_state(pkg_dir: Path) -> dict[str, object]:
    state_path = pkg_dir / ".gaia" / "inquiry" / "state.json"
    assert state_path.exists()
    return json.loads(state_path.read_text(encoding="utf-8"))


def _patch_uv_add(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def fake_run_uv(
        args: list[str],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        calls.append({"args": list(args), "cwd": kwargs.get("cwd")})
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("gaia.cli.commands.add._run_uv", fake_run_uv)
    return calls


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
    content: str | None = None,
) -> dict[str, object]:
    return {
        "id": node_id,
        "provider": "lkm",
        "kind": "claim",
        "title": f"Claim surfaced from {paper_title}",
        "content": content or f"Retrieved content item from {paper_title}.",
        "source": {
            "provider_id": node_id.rsplit(":", 1)[-1],
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


def _assessment_artifacts(pkg_dir: Path) -> list[Path]:
    return sorted((pkg_dir / ".gaia" / "research" / "assessments").glob("assessment-*.json"))


def _proposal_artifacts(pkg_dir: Path) -> list[Path]:
    return sorted((pkg_dir / ".gaia" / "research" / "proposals").glob("proposal-*.json"))


def _stop_artifacts(pkg_dir: Path) -> list[Path]:
    return sorted((pkg_dir / ".gaia" / "research" / "stops").glob("stop-*.json"))


def test_research_group_is_help_visible() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "research" in result.output


def test_research_contract_commands_emit_json() -> None:
    focus = runner.invoke(app, ["research", "contract", "focus"])
    assess = runner.invoke(app, ["research", "contract", "assess"])
    propose = runner.invoke(app, ["research", "contract", "propose"])

    assert focus.exit_code == 0, focus.output
    assert assess.exit_code == 0, assess.output
    assert propose.exit_code == 0, propose.output
    focus_payload = json.loads(focus.output)
    assess_payload = json.loads(assess.output)
    propose_payload = json.loads(propose.output)
    assert focus_payload["contract"] == "gaia.research.focus_synthesis"
    assert assess_payload["contract"] == "gaia.research.assessment_analysis"
    assert propose_payload["contract"] == "gaia.research.proposal_analysis"
    assert "ready_for_assess" in focus_payload["focus_fields"]["readiness"]
    assert "supports" in assess_payload["relation_fields"]["type"]
    assert "claim_refs" in assess_payload["relation_fields"]
    assert "package_ref" in assess_payload["input"]["evidence_packet"]
    assert "stable truth claims" in propose_payload["forbidden_outputs"][0]


def test_research_assess_help_uses_materialize_names() -> None:
    result = runner.invoke(app, ["research", "assess", "--help"])

    assert result.exit_code == 0, result.output
    assert "--materialize-paper" in result.output
    assert "--materialize-chain" in result.output
    assert "backing paper" in result.output
    assert "--pull-paper" not in result.output
    assert "--pull-claim" not in result.output


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
                        content="Snippet about the first paper.",
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
    assert "writes_inquiry: true" in result.output
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
    assert payload["paper_leads"][0]["variable_ids"] == ["n1", "n2"]
    assert payload["items"][0]["kind"] == "variable"
    assert payload["items"][0]["id"] == "n1"
    assert payload["items"][0]["variable_type"] == "claim"
    assert payload["items"][0]["content"] == "Snippet about the first paper."
    assert payload["pull_candidates"][0]["command"] == (
        "gaia pkg add --lkm-index bohrium --lkm-paper P1"
    )
    assert payload["pull_candidates"][0]["evidence_refs"] == [
        {"kind": "variable", "id": "n1"},
        {"kind": "variable", "id": "n2"},
    ]
    assert payload["coverage_map"]["query_families"][0]["paper_leads"] == 2
    assert payload["candidate_focuses"][0]["status"] == "candidate"

    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "explore.scan.completed"
    assert events[-1]["payload"]["artifact"].endswith(artifacts[0].name)
    assert events[-1]["payload"]["stats"]["paper_leads"] == 2
    assert events[-1]["payload"]["writes_source"] is False
    assert events[-1]["payload"]["writes_inquiry"] is True
    assert len(events[-1]["payload"]["hypotheses_added"]) == 1
    assert len(events[-1]["payload"]["obligations_added"]) == 1

    state = _read_inquiry_state(pkg_dir)
    assert len(state["synthetic_hypotheses"]) == 1
    assert len(state["synthetic_obligations"]) == 1


def test_research_scan_materializes_items_as_local_source_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uv_calls = _patch_uv_add(monkeypatch)
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "hubble tension",
                [
                    _lkm_row(
                        "P_H0",
                        "lkm:bohrium:claim_1",
                        0.92,
                        paper_title="H0 tension review",
                        doi="10.1000/h0",
                        content="Local distance-ladder measurements prefer a higher H0.",
                    )
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
    assert "source_packages_added: 1" in result.output
    assert init_py.read_text(encoding="utf-8") == source_before
    source_roots = sorted((pkg_dir / ".gaia" / "research" / "source_packages").glob("*-gaia"))
    assert len(source_roots) == 1
    source_root = source_roots[0]
    assert (source_root / "pyproject.toml").exists()
    generated_sources = list((source_root / "src").glob("*/__init__.py"))
    assert len(generated_sources) == 1
    generated = generated_sources[0].read_text(encoding="utf-8")
    assert "claim(" in generated
    assert "Local distance-ladder measurements prefer a higher H0." in generated
    assert '"variable_id": "claim_1"' in generated
    assert '"paper_id": "P_H0"' in generated
    assert '"landscape_artifact"' in generated
    assert uv_calls == [
        {
            "args": ["uv", "add", "--editable", str(source_root)],
            "cwd": pkg_dir,
        }
    ]

    events = _read_events(pkg_dir)
    source_payload = events[-1]["payload"]["source_packages_added"]
    assert len(source_payload) == 1
    assert source_payload[0]["path"] == str(source_root)
    assert source_payload[0]["claim_count"] == 1

    landscape = json.loads(_landscape_artifacts(pkg_dir)[0].read_text(encoding="utf-8"))
    source_ref = landscape["items"][0]["package_ref"]
    assert source_ref["kind"] == "package_ref"
    assert source_ref["value_type"] == "claim"
    assert source_ref["package"] == source_root.name
    assert source_ref["symbol"] == "source_claim_1"
    assert source_ref["ref"].endswith("::source_claim_1")

    check = runner.invoke(app, ["build", "check", str(source_root)])
    assert check.exit_code == 0, check.output


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
            "expand",
            str(pkg_dir),
            "--focus",
            "seed",
            "--search-json",
            str(search_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Target: focus seed" in result.output
    assert "pull_budget: 0" in result.output
    assert "writes_inquiry: true" in result.output
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
    assert events[-1]["payload"]["writes_source"] is False
    assert events[-1]["payload"]["writes_inquiry"] is True

    state = _read_inquiry_state(pkg_dir)
    assert state["synthetic_hypotheses"][0]["scope_qid"] == "seed"
    assert state["synthetic_obligations"][0]["target_qid"] == "seed"


def test_research_focus_writes_synthesis_from_analysis_json(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "aspirin elderly",
                [
                    _lkm_row(
                        "P_ASPREE",
                        "lkm:bohrium:aspree",
                        0.9,
                        paper_title="ASPREE trial",
                        content=(
                            "ASPREE reported no cardiovascular benefit and more major hemorrhage."
                        ),
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    scan = runner.invoke(
        app,
        ["research", "explore", str(pkg_dir), "--mode", "scan", "--search-json", str(search_path)],
    )
    assert scan.exit_code == 0, scan.output
    landscape_path = _landscape_artifacts(pkg_dir)[0]
    analysis_path = tmp_path / "focus-analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "focuses": [
                    {
                        "id": "elderly_net_benefit",
                        "kind": "research_focus",
                        "status": "accepted",
                        "question": "70岁及以上人群中，阿司匹林一级预防的净获益是否为正？",
                        "rationale": "ASPREE 证据直接涉及老年人无获益和出血增加。",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {"population": "older adults"},
                        "coverage": {"items": 1, "paper_leads": 1},
                        "evidence_refs": [{"kind": "variable", "id": "aspree"}],
                        "suggested_queries": [],
                    }
                ],
                "coverage_gaps": [
                    {
                        "kind": "missing_absolute_effect",
                        "description": "补充老年人绝对风险差和出血绝对风险。",
                        "evidence_refs": [{"kind": "variable", "id": "aspree"}],
                    }
                ],
                "notes": ["agent synthesis"],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "focus",
            str(pkg_dir),
            "--landscape",
            str(landscape_path),
            "--analysis-json",
            str(analysis_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Focus synthesis:" in result.output
    assert "focuses: 1" in result.output
    assert "questions_written: 1" in result.output
    assert init_py.read_text(encoding="utf-8") != source_before
    authored = pkg_dir / "src" / "research_demo" / "authored" / "__init__.py"
    authored_source = authored.read_text(encoding="utf-8")
    assert "rq_elderly_net_benefit_" in authored_source
    assert "question(" in authored_source
    artifacts = sorted((pkg_dir / ".gaia" / "research" / "focuses").glob("focuses-*.json"))
    assert len(artifacts) == 1
    payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert payload["focuses"][0]["id"] == "elderly_net_benefit"
    assert payload["focuses"][0]["readiness"] == "ready_for_assess"
    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "focus.synthesis.completed"
    assert events[-1]["payload"]["analysis_json"] is True
    assert len(events[-1]["payload"]["questions_written"]) == 1
    assert len(events[-1]["payload"]["obligations_added"]) == 1

    state = _read_inquiry_state(pkg_dir)
    assert str(state["focus"]).startswith("rq_elderly_net_benefit_")
    assert state["focus_kind"] == "question"

    check = runner.invoke(app, ["build", "check", str(pkg_dir)])
    assert check.exit_code == 0, check.output


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


def test_research_assess_writes_grounded_assessment_from_landscape(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "assessment query",
                [
                    _lkm_row(
                        "P5",
                        "lkm:bohrium:n6",
                        0.9,
                        paper_title="Assessment Paper",
                        content="A retrieved claim-level item relevant to the focus.",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    scan = runner.invoke(
        app,
        ["research", "explore", str(pkg_dir), "--mode", "scan", "--search-json", str(search_path)],
    )
    assert scan.exit_code == 0, scan.output
    landscape_path = _landscape_artifacts(pkg_dir)[0]

    result = runner.invoke(
        app,
        [
            "research",
            "assess",
            str(pkg_dir),
            "--focus",
            "seed",
            "--artifact-only",
            "--landscape",
            str(landscape_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Assessment:" in result.output
    assert "gaia inquiry obligation add" in result.output
    assert init_py.read_text(encoding="utf-8") == source_before

    artifacts = _assessment_artifacts(pkg_dir)
    assert len(artifacts) == 1
    assessment = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert assessment["kind"] == "assessment"
    assert assessment["focus"] == {"kind": "focus", "id": "seed"}
    assert assessment["evidence_packet"]["items"][0]["content"] == (
        "A retrieved claim-level item relevant to the focus."
    )
    assert assessment["relations"][0]["type"] == "background_for"
    assert assessment["relations"][0]["epistemic_status"] == "candidate"
    assert assessment["relations"][0]["promotion_hint"] == "none"
    assert assessment["relations"][0]["source_refs"][0]["id"] == "n6"
    assert assessment["candidate_obligations"]

    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "assess.completed"
    assert events[-1]["payload"]["artifact"].endswith(artifacts[0].name)


def test_research_assess_materializes_selected_lkm_paper_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "deep assessment query",
                [
                    _lkm_row(
                        "P_DEEP",
                        "lkm:bohrium:deep_claim",
                        0.95,
                        paper_title="Deep Evidence Paper",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    scan = runner.invoke(
        app,
        [
            "research",
            "explore",
            str(pkg_dir),
            "--mode",
            "scan",
            "--search-json",
            str(search_path),
            "--no-materialize-sources",
        ],
    )
    assert scan.exit_code == 0, scan.output
    landscape_path = _landscape_artifacts(pkg_dir)[0]

    pull_calls: list[dict[str, object]] = []

    def fake_add_lkm_paper_dependency(ref: Any, *, package_root: Path) -> Any:
        pull_calls.append({"ref": ref.ref, "package_root": package_root})
        return SimpleNamespace(
            source_ref=ref.ref,
            root=pkg_dir / ".gaia" / "lkm_packages" / "deep-paper-gaia",
            dist_name="deep-paper-gaia",
            import_name="deep_paper",
            claim_count=2,
            question_count=0,
            dependency_count=1,
        )

    monkeypatch.setattr(
        "gaia.cli.commands.research.add_lkm_paper_dependency",
        fake_add_lkm_paper_dependency,
        raising=False,
    )

    result = runner.invoke(
        app,
        [
            "research",
            "assess",
            str(pkg_dir),
            "--focus",
            "seed",
            "--landscape",
            str(landscape_path),
            "--materialize-paper",
            "P_DEEP",
            "--lkm-index",
            "bohrium",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "lkm_packages_materialized: 1" in result.output
    assert pull_calls == [{"ref": "lkm:bohrium:paper:P_DEEP", "package_root": pkg_dir}]
    events = _read_events(pkg_dir)
    materialized = events[-1]["payload"]["lkm_packages_materialized"]
    assert materialized[0]["source_ref"] == "lkm:bohrium:paper:P_DEEP"
    assert materialized[0]["claim_count"] == 2


def test_research_assess_materializes_lkm_paper_from_claim_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "claim deep assessment query",
                [
                    _lkm_row(
                        "P_FROM_CLAIM",
                        "lkm:bohrium:claim_from_reasoning",
                        0.95,
                        paper_title="Claim Backing Paper",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    scan = runner.invoke(
        app,
        [
            "research",
            "explore",
            str(pkg_dir),
            "--mode",
            "scan",
            "--search-json",
            str(search_path),
            "--no-materialize-sources",
        ],
    )
    assert scan.exit_code == 0, scan.output
    landscape_path = _landscape_artifacts(pkg_dir)[0]

    pull_calls: list[dict[str, object]] = []

    def fake_add_lkm_claim_dependency(ref: Any, *, package_root: Path) -> Any:
        pull_calls.append({"ref": ref.ref, "package_root": package_root})
        return SimpleNamespace(
            source_ref="lkm:bohrium:paper:P_FROM_CLAIM",
            root=pkg_dir / ".gaia" / "lkm_packages" / "claim-paper-gaia",
            dist_name="claim-paper-gaia",
            import_name="claim_paper",
            claim_count=3,
            question_count=1,
            dependency_count=0,
        )

    monkeypatch.setattr(
        "gaia.cli.commands.research.add_lkm_claim_dependency",
        fake_add_lkm_claim_dependency,
        raising=False,
    )

    result = runner.invoke(
        app,
        [
            "research",
            "assess",
            str(pkg_dir),
            "--focus",
            "seed",
            "--landscape",
            str(landscape_path),
            "--materialize-paper-from-claim",
            "claim_from_reasoning",
            "--lkm-index",
            "bohrium",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "lkm_packages_materialized: 1" in result.output
    assert pull_calls == [
        {"ref": "lkm:bohrium:claim:claim_from_reasoning", "package_root": pkg_dir}
    ]
    events = _read_events(pkg_dir)
    materialized = events[-1]["payload"]["lkm_packages_materialized"]
    assert materialized[0]["requested_source_ref"] == "lkm:bohrium:claim:claim_from_reasoning"
    assert materialized[0]["source_ref"] == "lkm:bohrium:paper:P_FROM_CLAIM"


def test_research_assess_materializes_lkm_reasoning_chain_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "chain-level assessment query",
                [
                    _lkm_row(
                        "P_CHAIN",
                        "lkm:bohrium:chain_target_claim",
                        0.95,
                        paper_title="Chain Backing Paper",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    scan = runner.invoke(
        app,
        [
            "research",
            "explore",
            str(pkg_dir),
            "--mode",
            "scan",
            "--search-json",
            str(search_path),
            "--no-materialize-sources",
        ],
    )
    assert scan.exit_code == 0, scan.output
    landscape_path = _landscape_artifacts(pkg_dir)[0]

    materialize_calls: list[dict[str, object]] = []

    def fake_add_lkm_chain_dependency(ref: Any, *, package_root: Path) -> Any:
        materialize_calls.append({"ref": ref.ref, "package_root": package_root})
        return SimpleNamespace(
            source_ref="lkm:bohrium:chain:chain_target_claim",
            root=pkg_dir / ".gaia" / "lkm_packages" / "claim-chain-gaia",
            dist_name="claim-chain-gaia",
            import_name="claim_chain",
            claim_count=4,
            question_count=1,
            dependency_count=3,
            chain_count=2,
            total_chains=5,
        )

    monkeypatch.setattr(
        "gaia.cli.commands.research.add_lkm_chain_dependency",
        fake_add_lkm_chain_dependency,
        raising=False,
    )

    result = runner.invoke(
        app,
        [
            "research",
            "assess",
            str(pkg_dir),
            "--focus",
            "seed",
            "--landscape",
            str(landscape_path),
            "--materialize-chain",
            "chain_target_claim",
            "--lkm-index",
            "bohrium",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "lkm_chains_materialized: 1" in result.output
    assert materialize_calls == [
        {"ref": "lkm:bohrium:claim:chain_target_claim", "package_root": pkg_dir}
    ]
    events = _read_events(pkg_dir)
    materialized = events[-1]["payload"]["lkm_chains_materialized"]
    assert materialized[0]["requested_source_ref"] == "lkm:bohrium:claim:chain_target_claim"
    assert materialized[0]["source_ref"] == "lkm:bohrium:chain:chain_target_claim"
    assert materialized[0]["chain_count"] == 2


def test_research_assess_accepts_analysis_json_with_review(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "aspirin elderly assessment",
                [
                    _lkm_row(
                        "P_ASPREE",
                        "lkm:bohrium:aspree",
                        0.9,
                        paper_title="ASPREE trial",
                        content=(
                            "ASPREE reported no cardiovascular benefit and more major hemorrhage."
                        ),
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    scan = runner.invoke(
        app,
        ["research", "explore", str(pkg_dir), "--mode", "scan", "--search-json", str(search_path)],
    )
    assert scan.exit_code == 0, scan.output
    landscape_path = _landscape_artifacts(pkg_dir)[0]
    analysis_path = tmp_path / "assess-analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "relations": [
                    {
                        "type": "opposes",
                        "claim": (
                            "ASPREE opposes routine aspirin primary prevention in older adults."
                        ),
                        "rationale": (
                            "The retrieved item reports no cardiovascular benefit "
                            "and more major hemorrhage."
                        ),
                        "epistemic_status": "candidate",
                        "promotion_hint": "none",
                        "source_refs": [{"kind": "variable", "id": "aspree"}],
                        "claim_refs": ["seed", "seed_alt"],
                    }
                ],
                "review": {
                    "language": "zh",
                    "depth": "review",
                    "summary": "老年人常规一级预防净获益不足。",
                    "sections": [{"title": "老年人", "body": "ASPREE 指向无获益且出血增加。"}],
                    "limitations": ["需要核对原始试验终点定义。"],
                    "next_queries": ["aspirin primary prevention elderly NNH"],
                },
                "candidate_obligations": [
                    {
                        "kind": "needs_more_evidence",
                        "content": "补充老年人绝对风险差。",
                        "source_refs": [{"kind": "variable", "id": "aspree"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "assess",
            str(pkg_dir),
            "--focus",
            "elderly_net_benefit",
            "--landscape",
            str(landscape_path),
            "--analysis-json",
            str(analysis_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "relation_type_counts" in result.output
    assert "review: true" in result.output
    assert "notes_written: 1" in result.output
    assert "candidate_relations_written: 1" in result.output
    assert init_py.read_text(encoding="utf-8") != source_before
    authored = pkg_dir / "src" / "research_demo" / "authored" / "__init__.py"
    authored_source = authored.read_text(encoding="utf-8")
    assert "note(" in authored_source
    assert "candidate_relation(" in authored_source
    artifacts = _assessment_artifacts(pkg_dir)
    assessment = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert assessment["relations"][0]["type"] == "opposes"
    assert assessment["review"]["summary"] == "老年人常规一级预防净获益不足。"
    events = _read_events(pkg_dir)
    assert events[-1]["payload"]["relation_type_counts"] == {"opposes": 1}
    assert events[-1]["payload"]["review"] is True
    assert len(events[-1]["payload"]["notes_written"]) == 1
    assert len(events[-1]["payload"]["candidate_relations_written"]) == 1
    assert len(events[-1]["payload"]["obligations_added"]) == 1
    assert len(events[-1]["payload"]["hypotheses_added"]) == 1

    state = _read_inquiry_state(pkg_dir)
    assert any(
        item["target_qid"] == "elderly_net_benefit" for item in state["synthetic_obligations"]
    )
    assert any(item["scope_qid"] == "elderly_net_benefit" for item in state["synthetic_hypotheses"])

    check = runner.invoke(app, ["build", "check", str(pkg_dir)])
    assert check.exit_code == 0, check.output


def test_research_assess_skips_candidate_relation_for_non_claim_package_ref(
    tmp_path: Path,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    search_path = tmp_path / "search.json"
    question_row = _lkm_row(
        "P_QUESTION",
        "lkm:bohrium:open_question",
        0.91,
        paper_title="Open Question Paper",
        content="What unresolved issue should be studied next?",
    )
    question_row["kind"] = "question"
    search_path.write_text(
        json.dumps(_search("open question query", [question_row])),
        encoding="utf-8",
    )
    scan = runner.invoke(
        app,
        ["research", "explore", str(pkg_dir), "--mode", "scan", "--search-json", str(search_path)],
    )
    assert scan.exit_code == 0, scan.output
    landscape_path = _landscape_artifacts(pkg_dir)[0]
    landscape = json.loads(landscape_path.read_text(encoding="utf-8"))
    source_ref = landscape["items"][0]["package_ref"]
    assert source_ref["value_type"] == "question"
    analysis_path = tmp_path / "assess-analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "relations": [
                    {
                        "type": "opposes",
                        "claim": "A question ref must not be used as a candidate relation claim.",
                        "rationale": "candidate_relation requires claim-compatible inputs.",
                        "epistemic_status": "candidate",
                        "promotion_hint": "contradict",
                        "source_refs": [{"kind": "variable", "id": "open_question"}],
                        "claim_refs": ["seed", source_ref["ref"]],
                    }
                ],
                "candidate_obligations": [],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "assess",
            str(pkg_dir),
            "--focus",
            "seed",
            "--landscape",
            str(landscape_path),
            "--analysis-json",
            str(analysis_path),
        ],
    )

    assert result.exit_code == 0, result.output
    events = _read_events(pkg_dir)
    assert events[-1]["payload"]["candidate_relations_written"] == []
    assert events[-1]["payload"]["candidate_relations_skipped"]
    authored = pkg_dir / "src" / "research_demo" / "authored" / "__init__.py"
    if authored.exists():
        assert "candidate_relation(" not in authored.read_text(encoding="utf-8")
    check = runner.invoke(app, ["build", "check", str(pkg_dir)])
    assert check.exit_code == 0, check.output


def test_research_assess_reports_schema_errors_without_traceback(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "assessment query",
                [
                    _lkm_row(
                        "P_SCHEMA",
                        "lkm:bohrium:schema_claim",
                        0.9,
                        paper_title="Schema Paper",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    scan = runner.invoke(
        app,
        ["research", "explore", str(pkg_dir), "--mode", "scan", "--search-json", str(search_path)],
    )
    assert scan.exit_code == 0, scan.output
    analysis_path = tmp_path / "bad-assess-analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "relations": [
                    {
                        "type": "qualifies",
                        "claim": "The evidence qualifies the focus.",
                        "rationale": "Bad promotion hint for this relation type.",
                        "epistemic_status": "candidate",
                        "promotion_hint": "candidate_relation",
                        "source_refs": [{"kind": "variable", "id": "schema_claim"}],
                    }
                ],
                "candidate_obligations": [],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "assess",
            str(pkg_dir),
            "--focus",
            "seed",
            "--landscape",
            str(_landscape_artifacts(pkg_dir)[0]),
            "--analysis-json",
            str(analysis_path),
        ],
    )

    assert result.exit_code == 2, result.output
    assert "Error: invalid assessment artifact:" in result.output
    assert "promotion_hint" in result.output
    assert "Traceback" not in result.output


def test_research_propose_writes_artifact_without_accepting(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")
    assessment_path = tmp_path / "assessment.json"
    assessment_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "assessment",
                "focus": {"kind": "focus", "id": "h0_tension"},
                "evidence_packet": {"items": [], "paper_leads": []},
                "relations": [],
                "candidate_obligations": [
                    {
                        "kind": "needs_more_evidence",
                        "content": "补充 TRGB 与 Cepheid 共同定标系统误差的证据。",
                        "source_refs": [{"kind": "assessment", "id": "h0_tension"}],
                    }
                ],
                "review": {
                    "language": "zh",
                    "depth": "review",
                    "summary": "H0 张力需要继续区分系统误差与新物理。",
                    "sections": [],
                    "limitations": [],
                    "next_queries": ["TRGB Cepheid calibration systematics H0 tension"],
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["research", "propose", str(pkg_dir), "--from-assessment", str(assessment_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Proposal:" in result.output
    assert "proposals: 1" in result.output
    assert "accepted: false" in result.output
    assert "writes_source: false" in result.output
    assert "writes_inquiry: false" in result.output
    assert init_py.read_text(encoding="utf-8") == source_before

    artifacts = _proposal_artifacts(pkg_dir)
    assert len(artifacts) == 1
    payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert payload["kind"] == "research_proposal"
    assert payload["source_assessment"]["focus_id"] == "h0_tension"
    assert payload["proposals"][0]["question"] == (
        "TRGB Cepheid calibration systematics H0 tension"
    )
    assert payload["candidate_obligations"][0]["content"] == (
        "补充 TRGB 与 Cepheid 共同定标系统误差的证据。"
    )

    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "propose.completed"
    assert events[-1]["payload"]["accepted"] is False
    assert events[-1]["payload"]["writes_source"] is False
    assert events[-1]["payload"]["writes_inquiry"] is False


def test_research_propose_accepts_questions_hypotheses_and_obligations(
    tmp_path: Path,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")
    assessment_path = tmp_path / "assessment.json"
    assessment_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "assessment",
                "focus": {"kind": "focus", "id": "h0_tension"},
                "evidence_packet": {"items": [], "paper_leads": []},
                "relations": [],
                "candidate_obligations": [],
                "review": {
                    "language": "zh",
                    "depth": "review",
                    "summary": "H0 张力仍有未解决方向。",
                    "sections": [],
                    "limitations": [],
                    "next_queries": [],
                },
            }
        ),
        encoding="utf-8",
    )
    analysis_path = tmp_path / "proposal-analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "proposals": [
                    {
                        "id": "rq_calibration_systematics",
                        "kind": "research_question",
                        "status": "accepted",
                        "question": "TRGB 与 Cepheid 定标是否共享导致高 H0 的系统误差？",
                        "rationale": "assessment 指出距离阶梯内部系统误差是核心未决方向。",
                        "priority": "high",
                        "source_refs": [{"kind": "assessment", "id": "h0_tension"}],
                    }
                ],
                "hypotheses": [
                    {
                        "content": "TRGB 与 SH0ES 可能共享部分定标系统误差。",
                        "source_refs": [{"kind": "assessment", "id": "h0_tension"}],
                    }
                ],
                "candidate_obligations": [
                    {
                        "kind": "needs_more_evidence",
                        "content": (
                            "核查 Cepheid 零点、TRGB 零点和 SNIa 绝对星等传递的不确定度协方差。"
                        ),
                        "source_refs": [{"kind": "assessment", "id": "h0_tension"}],
                    }
                ],
                "notes": ["agent proposal"],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "propose",
            str(pkg_dir),
            "--from-assessment",
            str(assessment_path),
            "--analysis-json",
            str(analysis_path),
            "--accept",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "accepted: true" in result.output
    assert "questions_written: 1" in result.output
    assert "obligations_added: 1" in result.output
    assert "hypotheses_added: 1" in result.output
    assert init_py.read_text(encoding="utf-8") != source_before
    authored = pkg_dir / "src" / "research_demo" / "authored" / "__init__.py"
    authored_source = authored.read_text(encoding="utf-8")
    assert "rq_rq_calibration_systematics_" in authored_source
    assert "question(" in authored_source

    state = _read_inquiry_state(pkg_dir)
    assert state["focus_kind"] == "question"
    assert str(state["focus"]).startswith("rq_rq_calibration_systematics_")
    assert len(state["synthetic_hypotheses"]) == 1
    assert len(state["synthetic_obligations"]) == 1

    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "propose.completed"
    assert events[-1]["payload"]["accepted"] is True
    assert len(events[-1]["payload"]["questions_written"]) == 1
    assert len(events[-1]["payload"]["obligations_added"]) == 1
    assert len(events[-1]["payload"]["hypotheses_added"]) == 1

    check = runner.invoke(app, ["build", "check", str(pkg_dir)])
    assert check.exit_code == 0, check.output


def test_research_promote_writes_materialization_scaffold(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "research",
            "promote",
            str(pkg_dir),
            "--scaffold",
            "candidate_relation_demo",
            "--by",
            "seed",
            "--rationale",
            "Human-reviewed formalization.",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Research promote" in result.output
    assert "materializations_written: 1" in result.output
    assert init_py.read_text(encoding="utf-8") != source_before
    authored = pkg_dir / "src" / "research_demo" / "authored" / "__init__.py"
    authored_source = authored.read_text(encoding="utf-8")
    assert "materialize(candidate_relation_demo" in authored_source
    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "promote.completed"
    assert len(events[-1]["payload"]["materializations_written"]) == 1


def test_research_report_renders_artifact_to_markdown_file(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")
    artifact_path = tmp_path / "focuses.json"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "focus_synthesis",
                "language": "zh",
                "source_landscapes": [],
                "focuses": [
                    {
                        "id": "core_tension",
                        "kind": "research_focus",
                        "status": "candidate",
                        "question": "核心矛盾是什么？",
                        "rationale": "检索结果显示存在可评估的证据张力。",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {"topic": "demo"},
                        "coverage": {"items": 2},
                        "evidence_refs": [{"kind": "paper", "paper_id": "P1"}],
                        "suggested_queries": ["core tension follow up"],
                    }
                ],
                "coverage_gaps": [],
                "notes": ["agent synthesis"],
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "focus_report.md"

    result = runner.invoke(
        app,
        [
            "research",
            "report",
            str(pkg_dir),
            "--artifact",
            str(artifact_path),
            "--out",
            str(report_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Report:" in result.output
    assert init_py.read_text(encoding="utf-8") == source_before
    markdown = report_path.read_text(encoding="utf-8")
    assert "# Research Focus Synthesis" in markdown
    assert "core_tension" in markdown
    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "report.rendered"
    assert events[-1]["payload"]["writes_source"] is False


def test_research_report_renders_proposal_artifact(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    artifact_path = tmp_path / "proposal.json"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "research_proposal",
                "source_assessment": {"kind": "assessment", "focus_id": "h0_tension"},
                "proposals": [
                    {
                        "id": "rq_calibration_systematics",
                        "kind": "research_question",
                        "status": "accepted",
                        "question": "TRGB 与 Cepheid 定标是否共享导致高 H0 的系统误差？",
                        "rationale": "assessment 指出距离阶梯内部系统误差是核心未决方向。",
                        "priority": "high",
                        "source_refs": [{"kind": "assessment", "id": "h0_tension"}],
                    }
                ],
                "hypotheses": [{"content": "TRGB 与 SH0ES 可能共享系统误差。"}],
                "candidate_obligations": [{"content": "核查协方差报告完整性。"}],
                "notes": ["agent proposal"],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["research", "report", str(pkg_dir), "--artifact", str(artifact_path)],
    )

    assert result.exit_code == 0, result.output
    assert "# Research Proposal" in result.output
    assert "rq_calibration_systematics" in result.output
    assert "TRGB 与 Cepheid 定标是否共享" in result.output
    assert "## Hypotheses" in result.output
    assert "## Candidate Obligations" in result.output


def test_research_report_prints_markdown_to_stdout(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    artifact_path = tmp_path / "assessment.json"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "assessment",
                "focus": {"kind": "focus", "id": "core_tension"},
                "evidence_packet": {"items": [], "paper_leads": []},
                "relations": [
                    {
                        "type": "needs_more_evidence",
                        "claim": "当前证据不足。",
                        "rationale": "没有可用 items。",
                        "epistemic_status": "candidate",
                        "promotion_hint": "obligation",
                        "source_refs": [{"kind": "focus", "id": "core_tension"}],
                    }
                ],
                "candidate_obligations": [],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["research", "report", str(pkg_dir), "--artifact", str(artifact_path)],
    )

    assert result.exit_code == 0, result.output
    assert "# Research Assessment" in result.output
    assert "Focus `core_tension` is evaluated using 0 retrieved evidence record(s)" in result.output
    assert "evidence packet" not in result.output
    assert "needs_more_evidence: 1" not in result.output
    assert "## Citations" in result.output


def test_research_stop_writes_stop_criteria_artifact(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")
    focus_path = tmp_path / "focuses.json"
    focus_path.write_text(
        json.dumps(
            {
                "kind": "focus_synthesis",
                "focuses": [{"id": "core_tension", "readiness": "ready_for_assess"}],
                "coverage_gaps": [],
            }
        ),
        encoding="utf-8",
    )
    assessment_path = tmp_path / "assessment.json"
    assessment_path.write_text(
        json.dumps(
            {
                "kind": "assessment",
                "relations": [
                    {"type": "supports"},
                    {"type": "opposes"},
                    {"type": "qualifies"},
                ],
                "candidate_obligations": [],
            }
        ),
        encoding="utf-8",
    )
    current_landscape = tmp_path / "current.json"
    current_landscape.write_text(
        json.dumps(
            {
                "kind": "research_landscape",
                "paper_leads": [{"paper_id": "P1"}, {"paper_id": "P2"}],
            }
        ),
        encoding="utf-8",
    )
    previous_landscape = tmp_path / "previous.json"
    previous_landscape.write_text(
        json.dumps({"kind": "research_landscape", "paper_leads": [{"paper_id": "P0"}]}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "stop",
            str(pkg_dir),
            "--focus-artifact",
            str(focus_path),
            "--assessment",
            str(assessment_path),
            "--landscape",
            str(current_landscape),
            "--previous-landscape",
            str(previous_landscape),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "recommendation: ready_for_human_review" in result.output
    assert "coverage: sufficient" in result.output
    assert init_py.read_text(encoding="utf-8") == source_before
    artifacts = _stop_artifacts(pkg_dir)
    assert len(artifacts) == 1
    stop_payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert stop_payload["kind"] == "research_stop"
    assert stop_payload["should_stop"] is True
    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "stop.evaluated"
    assert events[-1]["payload"]["writes_source"] is False


def test_research_report_renders_stop_artifact(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    stop_path = tmp_path / "stop.json"
    stop_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "research_stop",
                "recommendation": "ready_for_assess",
                "should_stop": True,
                "dimensions": {
                    "coverage": {
                        "status": "sufficient",
                        "score": 1.0,
                        "reason": "1 focus is ready.",
                    }
                },
                "reasons": ["coverage: 1 focus is ready."],
                "metrics": {"new_paper_lead_ratio": 0.5},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["research", "report", str(pkg_dir), "--artifact", str(stop_path)],
    )

    assert result.exit_code == 0, result.output
    assert "# Research Stop Criteria" in result.output
    assert "ready_for_assess" in result.output
    assert "new_paper_lead_ratio" in result.output


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
