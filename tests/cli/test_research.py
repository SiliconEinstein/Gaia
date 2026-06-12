"""CLI tests for the package-native ``gaia research`` M1 skeleton."""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

import gaia.cli.commands.research_orchestrator as research_orchestrator
import gaia.cli.commands.research_providers as research_providers
from gaia.cli.main import app
from gaia.engine.research import load_research_package
from gaia.engine.research.benchmark import (
    append_research_trace_step,
    write_research_benchmark_summary,
)
from gaia.engine.research.run import start_research_run

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI color/style escape sequences from Typer rich help output."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


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


def _patch_deep_materialization(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def fake_materialize(
        research_pkg: Any,
        *,
        paper_ids: list[str],
        claim_ids: list[str],
        chain_claim_ids: list[str],
        lkm_index: str,
        dry_run: bool,
    ) -> dict[str, object]:
        calls.append(
            {
                "paper_ids": paper_ids,
                "claim_ids": claim_ids,
                "chain_claim_ids": chain_claim_ids,
                "lkm_index": lkm_index,
                "dry_run": dry_run,
                "pkg": research_pkg.path,
            }
        )
        return {
            "lkm_materialize_requests": [*paper_ids, *claim_ids, *chain_claim_ids],
            "lkm_packages_materialized": [],
            "lkm_chains_materialized": [],
        }

    monkeypatch.setattr(
        research_orchestrator,
        "_materialize_lkm_papers_or_exit",
        fake_materialize,
    )
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
    output = _strip_ansi(result.output)

    assert result.exit_code == 0, result.output
    assert "--materialize-paper" in output
    assert "--materialize-chain" in output
    assert "backing paper" in output
    assert "--pull-paper" not in output
    assert "--pull-claim" not in output


def test_research_run_help_is_visible() -> None:
    result = runner.invoke(app, ["research", "run", "--help"])
    output = _strip_ansi(result.output)

    assert result.exit_code == 0, result.output
    assert "Start a UI-observable research run" in output
    assert "--topic" in output
    assert "--config" in output
    assert "--focus-count" in output
    assert "Evidence selection" in output
    assert "--json-stream" in output


def test_research_run_start_writes_state_events_and_checkpoint(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "DQCP evidence assessment",
            "--mode",
            "fast-package-native",
            "--language",
            "zh",
            "--profile",
            "evidence-assessment",
            "--run-id",
            "dqcp-test-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Research run: " in result.output
    run_dir = pkg_dir / ".gaia" / "research" / "runs" / "dqcp-test-run"
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["schema_version"] == 1
    assert state["run_id"] == "dqcp-test-run"
    assert state["status"] == "waiting_for_input"
    assert state["phase"] == "query_plan"
    assert state["mode"] == "fast-package-native"
    assert state["profile"] == "evidence-assessment"
    assert state["language"] == "zh"
    assert state["topic"] == "DQCP evidence assessment"
    assert state["package"]["project_name"] == "research-demo-gaia"
    assert state["run_dir"] == str(run_dir)
    assert state["trace_dir"] == str(run_dir / "trace")
    assert state["pending_checkpoint"] == str(run_dir / "checkpoints" / "query_plan.request.json")
    assert state["artifacts"] == {}
    assert state["metrics"] == {}

    checkpoint = json.loads(
        (run_dir / "checkpoints" / "query_plan.request.json").read_text(encoding="utf-8")
    )
    assert checkpoint["schema_version"] == 1
    assert checkpoint["type"] == "checkpoint.query_plan"
    assert checkpoint["phase"] == "query_plan"
    assert checkpoint["default_action"]["action"] == "continue"
    assert checkpoint["default_action"]["queries"] == []

    events = [
        json.loads(line)
        for line in (run_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["type"] for event in events] == [
        "run.created",
        "checkpoint.created",
        "run.waiting_for_input",
    ]
    assert {event["run_id"] for event in events} == {"dqcp-test-run"}
    assert (run_dir / "searches").is_dir()
    assert (run_dir / "analysis").is_dir()
    assert (run_dir / "trace").is_dir()


def test_research_run_rejects_unsafe_run_id(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "DQCP evidence assessment",
            "--run-id",
            "../escape",
        ],
    )

    assert result.exit_code == 2
    assert "run_id must contain only lowercase ASCII letters" in result.output
    assert not (tmp_path / "escape").exists()


def test_research_run_json_stream_emits_persisted_events(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "DQCP evidence assessment",
            "--run-id",
            "stream-test-run",
            "--json-stream",
        ],
    )

    assert result.exit_code == 0, result.output
    streamed = [json.loads(line) for line in result.output.splitlines() if line.strip()]
    assert [event["type"] for event in streamed] == [
        "run.created",
        "checkpoint.created",
        "run.waiting_for_input",
    ]
    events_path = pkg_dir / ".gaia" / "research" / "runs" / "stream-test-run" / "events.ndjson"
    persisted = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    assert streamed == persisted


def test_orchestrator_live_search_uses_runtime_ports(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    research_pkg = load_research_package(pkg_dir)
    run = start_research_run(
        research_pkg,
        topic="runtime ports",
        mode="fast-package-native",
        language="zh",
        profile="evidence-assessment",
        run_id="runtime-ports-run",
        wait_for_query_plan=False,
    )
    calls: list[tuple[str, object]] = []

    class FakeRuntime(research_orchestrator.CliResearchOrchestratorRuntime):
        def emit_run_event(
            self,
            run: object,
            *,
            event_type: str,
            phase: str,
            json_stream: bool,
            payload: dict[str, object],
        ) -> None:
            _ = run, phase, json_stream, payload
            calls.append(("event", event_type))

        def update_run_state(self, run: object, payload: dict[str, object]) -> None:
            _ = run
            calls.append(("state", payload))

        def record_trace(
            self,
            research_pkg: object,
            run: object,
            *,
            start: float,
            name: str,
            kind: str,
            mode: str,
            inputs: list[str],
            outputs: list[str],
            metrics: dict[str, object] | None = None,
        ) -> None:
            _ = research_pkg, run, start, kind, mode, inputs, outputs, metrics
            calls.append(("trace", name))

        def search_lkm(
            self,
            query: str,
            *,
            index: str,
            limit: int,
            reasoning_only: bool,
        ) -> dict[str, object]:
            _ = index, limit, reasoning_only
            calls.append(("search", query))
            return _search(
                query,
                [
                    _lkm_row(
                        "P_RUNTIME",
                        "claim_runtime",
                        0.9,
                        paper_title="Runtime port paper",
                    )
                ],
            )

    refs = research_orchestrator.execute_live_searches(
        research_pkg,
        run,
        queries=["runtime query"],
        prefix="broad",
        search_index="bohrium",
        search_limit=5,
        reasoning_only=True,
        json_stream=False,
        runtime=FakeRuntime(),
    )

    assert [Path(ref).name for ref in refs] == ["broad-01.json"]
    assert ("search", "runtime query") in calls
    assert ("trace", "search.lkm.broad") in calls
    assert ("event", "search.started") in calls
    assert ("event", "search.completed") in calls


def test_research_run_executes_fast_package_native_file_provider_loop(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    broad_search = tmp_path / "broad-search.json"
    broad_search.write_text(
        json.dumps(
            _search(
                "aspirin elderly primary prevention",
                [
                    _lkm_row(
                        "P_ASPREE",
                        "aspree",
                        0.9,
                        paper_title="ASPREE trial",
                        content="ASPREE reported no cardiovascular benefit and more bleeding.",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    targeted_search = tmp_path / "targeted-search.json"
    targeted_search.write_text(
        json.dumps(
            _search(
                "aspirin elderly bleeding",
                [
                    _lkm_row(
                        "P_BLEED",
                        "bleed",
                        0.8,
                        paper_title="Bleeding risk study",
                        content="Bleeding risk qualifies primary prevention net benefit.",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    focus_analysis = tmp_path / "focus-analysis.json"
    focus_analysis.write_text(
        json.dumps(
            {
                "focuses": [
                    {
                        "id": "elderly_net_benefit",
                        "kind": "research_focus",
                        "status": "accepted",
                        "question": "老年人阿司匹林一级预防是否有净获益？",
                        "rationale": "ASPREE 同时涉及心血管获益和出血风险。",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {"population": "older adults"},
                        "coverage": {"items": 1, "paper_leads": 1, "missing": []},
                        "evidence_refs": [{"kind": "variable", "id": "aspree"}],
                        "suggested_queries": [],
                    }
                ],
                "coverage_gaps": [],
                "notes": ["Ready for assessment."],
            }
        ),
        encoding="utf-8",
    )
    assess_analysis = tmp_path / "assess-analysis.json"
    assess_analysis.write_text(
        json.dumps(
            {
                "relations": [
                    {
                        "type": "opposes",
                        "claim": (
                            "ASPREE opposes routine aspirin primary prevention in older adults."
                        ),
                        "rationale": "The retrieved claim reports no cardiovascular benefit.",
                        "epistemic_status": "candidate",
                        "promotion_hint": "none",
                        "source_refs": [{"kind": "variable", "id": "aspree"}],
                    }
                ],
                "review": {
                    "language": "zh",
                    "depth": "review",
                    "summary": "老年人常规一级预防净获益不足。[variable:aspree]",
                    "sections": [
                        {
                            "title": "老年人证据",
                            "body": "ASPREE 指向无获益且出血风险需要谨慎权衡。[variable:aspree]",
                        }
                    ],
                    "limitations": ["需要核对原始终点定义。"],
                    "next_queries": ["aspirin elderly bleeding net benefit"],
                },
                "candidate_obligations": [],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "aspirin primary prevention evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "closed-loop-run",
            "--search-json",
            str(broad_search),
            "--focus-analysis-json",
            str(focus_analysis),
            "--targeted-search-json",
            str(targeted_search),
            "--focus",
            "elderly_net_benefit",
            "--assess-analysis-json",
            str(assess_analysis),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "status: completed" in result.output
    run_dir = pkg_dir / ".gaia" / "research" / "runs" / "closed-loop-run"
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["phase"] == "complete"
    assert state["artifacts"]["benchmark"].endswith("/trace/benchmark.json")
    assert state["artifacts"]["stop"].endswith("/trace/stop.json")
    assert state["artifacts"]["final_report"].endswith("/trace/final_report.md")
    assert "focus_report" not in state["artifacts"]
    assert "assessment_report" not in state["artifacts"]
    assert "stop_report" not in state["artifacts"]
    assert state["metrics"]["searches"] == 2

    events = [
        json.loads(line)
        for line in (run_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    ]
    event_types = [event["type"] for event in events]
    assert "phase.completed" in event_types
    assert "run.completed" in event_types
    assert any(event.get("phase") == "assess_sync" for event in events)
    assert (run_dir / "trace" / "final_report.md").exists()
    assert not (run_dir / "trace" / "assessment_report.md").exists()
    assert not (run_dir / "trace" / "focus_report.md").exists()
    assert not (run_dir / "trace" / "stop_report.md").exists()
    final_report = (run_dir / "trace" / "final_report.md").read_text(encoding="utf-8")
    assert "一级预防" in final_report
    assert "stop recommendation" not in final_report
    assert "total tokens" not in final_report
    benchmark = json.loads((run_dir / "trace" / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["summary"]["steps"] >= 6


def test_research_run_assesses_multiple_focuses_and_aggregates_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    broad_search = tmp_path / "broad-search.json"
    broad_search.write_text(
        json.dumps(
            _search(
                "dqcp evidence",
                [
                    _lkm_row(
                        "P_A",
                        "claim_a",
                        0.9,
                        paper_title="First focus paper",
                        content="First focus evidence supports the question.",
                    ),
                    _lkm_row(
                        "P_B",
                        "claim_b",
                        0.8,
                        paper_title="Second focus paper",
                        content="Second focus evidence qualifies the question.",
                    ),
                ],
            )
        ),
        encoding="utf-8",
    )
    focus_analysis = tmp_path / "focus-analysis.json"
    focus_analysis.write_text(
        json.dumps(
            {
                "focuses": [
                    {
                        "id": "focus_a",
                        "kind": "research_focus",
                        "status": "accepted",
                        "question": "First focus?",
                        "rationale": "Grounded in claim_a.",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {},
                        "coverage": {"items": 1, "paper_leads": 1, "missing": []},
                        "evidence_refs": [{"kind": "variable", "id": "claim_a"}],
                        "suggested_queries": ["focus a targeted"],
                    },
                    {
                        "id": "focus_b",
                        "kind": "research_focus",
                        "status": "accepted",
                        "question": "Second focus?",
                        "rationale": "Grounded in claim_b.",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {},
                        "coverage": {"items": 1, "paper_leads": 1, "missing": []},
                        "evidence_refs": [{"kind": "variable", "id": "claim_b"}],
                        "suggested_queries": ["focus b targeted"],
                    },
                ],
                "coverage_gaps": [],
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    _patch_deep_materialization(monkeypatch)
    searched_queries: list[str] = []

    def fake_lkm_search(
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        _ = index, limit, reasoning_only
        searched_queries.append(query)
        variable_id = "claim_a" if "a targeted" in query else "claim_b"
        paper_id = "P_A_TARGETED" if variable_id == "claim_a" else "P_B_TARGETED"
        return _search(
            query,
            [
                _lkm_row(
                    paper_id,
                    variable_id,
                    0.7,
                    paper_title=f"{variable_id} targeted paper",
                    content=f"{query} targeted evidence.",
                )
            ],
        )

    monkeypatch.setattr(research_orchestrator, "_run_lkm_knowledge_search", fake_lkm_search)

    def fake_provider(
        research_pkg: object,
        run: object,
        *,
        phase: str,
        command: str,
        input_payload: dict[str, object],
        output_name: str,
        json_stream: bool,
    ) -> str:
        _ = research_pkg, command, json_stream
        assert phase == "assess_analysis"
        focus = input_payload["focus"]
        variable_id = "claim_a" if focus == "focus_a" else "claim_b"
        relation_type = "supports" if focus == "focus_a" else "qualifies"
        payload = {
            "relations": [
                {
                    "type": relation_type,
                    "claim": f"{focus} relation is grounded.",
                    "rationale": f"{focus} uses its selected evidence packet.",
                    "epistemic_status": "candidate",
                    "promotion_hint": "none",
                    "source_refs": [{"kind": "variable", "id": variable_id}],
                }
            ],
            "limitations": [f"{focus} needs source-level review."],
            "next_queries": [],
            "candidate_obligations": [],
        }
        output_path = run.run_dir / "analysis" / f"{output_name}.output.json"
        output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return str(output_path)

    monkeypatch.setattr(research_orchestrator, "_run_analysis_provider_command", fake_provider)

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "multi focus evidence assessment",
            "--mode",
            "fast-package-native",
            "--run-id",
            "multi-focus-run",
            "--search-json",
            str(broad_search),
            "--focus-analysis-json",
            str(focus_analysis),
            "--analysis-provider",
            "command",
            "--assess-analysis-command",
            "fake-provider",
            "--focus-count",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = pkg_dir / ".gaia" / "research" / "runs" / "multi-focus-run"
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["metrics"]["focuses_assessed"] == 2
    assert state["metrics"]["relations"] == 2
    assert len(state["artifacts"]["assessments"]) == 2
    assert (run_dir / "analysis" / "assess_analysis_focus_a.output.json").exists()
    assert (run_dir / "analysis" / "assess_analysis_focus_b.output.json").exists()
    assert searched_queries == ["focus a targeted", "focus b targeted"]
    assert sorted(path.name for path in (run_dir / "searches").glob("targeted-*.json")) == [
        "targeted-focus_a-01.json",
        "targeted-focus_b-01.json",
    ]
    assessment_payloads = [
        json.loads(path.read_text(encoding="utf-8")) for path in _assessment_artifacts(pkg_dir)
    ]
    assert {payload["focus"]["id"] for payload in assessment_payloads} == {
        "focus_a",
        "focus_b",
    }
    final_report = (run_dir / "trace" / "final_report.md").read_text(encoding="utf-8")
    assert "focus_a relation is grounded" in final_report
    assert "focus_b relation is grounded" in final_report


def test_research_run_executes_search_and_command_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)

    def fake_lkm_search(
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        assert index == "bohrium"
        assert limit == 7
        assert reasoning_only is True
        row_id = "aspree" if "primary" in query else "bleed"
        return _search(
            query,
            [
                _lkm_row(
                    f"P_{row_id.upper()}",
                    row_id,
                    0.9,
                    paper_title=f"{row_id.upper()} paper",
                    content=f"{query} retrieved evidence.",
                )
            ],
        )

    monkeypatch.setattr(research_orchestrator, "_run_lkm_knowledge_search", fake_lkm_search)
    _patch_deep_materialization(monkeypatch)

    provider = tmp_path / "provider.py"
    provider.write_text(
        """
import json
import os
from pathlib import Path

phase = os.environ["GAIA_RESEARCH_PHASE"]
output = Path(os.environ["GAIA_RESEARCH_OUTPUT"])
if phase == "focus_analysis":
    payload = {
        "focuses": [
            {
                "id": "elderly_net_benefit",
                "kind": "research_focus",
                "status": "accepted",
                "question": "老年人阿司匹林一级预防是否有净获益？",
                "rationale": "自动 search 已找到获益和出血风险线索。",
                "priority": "high",
                "readiness": "ready_for_assess",
                "scope": {"population": "older adults"},
                "coverage": {"items": 1, "paper_leads": 1, "missing": []},
                "evidence_refs": [{"kind": "variable", "id": "aspree"}],
                "suggested_queries": [],
            }
        ],
        "coverage_gaps": [],
        "notes": ["Command provider selected the assessment focus."],
    }
else:
    payload = {
        "relations": [
            {
                "type": "opposes",
                "claim": "ASPREE opposes routine primary-prevention aspirin in older adults.",
                "rationale": "The retrieved evidence reports limited benefit and bleeding risk.",
                "epistemic_status": "candidate",
                "promotion_hint": "none",
                "source_refs": [{"kind": "variable", "id": "aspree"}],
            }
        ],
        "review": {
            "language": "zh",
            "depth": "review",
            "summary": "老年人常规一级预防证据偏反对。[variable:aspree]",
            "sections": [
                {
                    "title": "证据权衡",
                    "body": "自动流程保留了 search 和 provider 的输入输出。[variable:aspree]",
                }
            ],
            "limitations": ["仍需人工审阅原文。"],
            "next_queries": [],
        },
        "candidate_obligations": [],
    }
output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "aspirin primary prevention evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "auto-provider-run",
            "--query",
            "aspirin elderly primary prevention",
            "--targeted-query",
            "aspirin elderly bleeding",
            "--search-limit",
            "7",
            "--analysis-provider",
            "command",
            "--focus-analysis-command",
            f"{sys.executable} {provider}",
            "--assess-analysis-command",
            f"{sys.executable} {provider}",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "status: completed" in result.output
    run_dir = pkg_dir / ".gaia" / "research" / "runs" / "auto-provider-run"
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["metrics"]["searches"] == 2
    assert sorted(path.name for path in (run_dir / "searches").glob("*.json")) == [
        "broad-01.json",
        "targeted-01.json",
    ]
    assert (run_dir / "analysis" / "focus_analysis.input.json").exists()
    assert (run_dir / "analysis" / "focus_analysis.output.json").exists()
    assert (run_dir / "analysis" / "assess_analysis.input.json").exists()
    assert (run_dir / "analysis" / "assess_analysis.output.json").exists()

    events = [
        json.loads(line)
        for line in (run_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    ]
    event_types = [event["type"] for event in events]
    assert event_types.count("search.completed") == 2
    assert event_types.count("provider.completed") == 2

    benchmark = json.loads((run_dir / "trace" / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["summary"]["kind_counts"]["search"] == 2
    assert benchmark["summary"]["kind_counts"]["llm"] == 2


def test_research_run_marks_state_failed_when_orchestrator_fails(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "aspirin elderly primary prevention",
                [
                    _lkm_row(
                        "P_ASPREE",
                        "paper:P_ASPREE::claim_1",
                        0.92,
                        paper_title="ASPREE trial",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "aspirin primary prevention evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "failed-provider-run",
            "--search-json",
            str(search_path),
            "--analysis-provider",
            "command",
        ],
    )

    assert result.exit_code == 2
    assert "--focus-analysis-command" in result.output
    run_dir = pkg_dir / ".gaia" / "research" / "runs" / "failed-provider-run"
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert state["error"]
    events = [
        json.loads(line)
        for line in (run_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["type"] == "run.failed"
    assert events[-1]["error"] == state["error"]


def test_research_run_executes_litellm_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    broad_search = tmp_path / "broad-search.json"
    broad_search.write_text(
        json.dumps(
            _search(
                "aspirin elderly primary prevention",
                [
                    _lkm_row(
                        "P_ASPREE",
                        "aspree",
                        0.9,
                        paper_title="ASPREE trial",
                        content="ASPREE reported no cardiovascular benefit.",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    async def fake_acompletion(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        messages = kwargs["messages"]
        assert isinstance(messages, list)
        user_content = str(messages[-1]["content"])
        payload: dict[str, Any]
        if '"phase": "field_map_analysis"' in user_content:
            payload = {
                "domain_thesis": "一级预防证据需要先按人群、获益和危害建立地图。",
                "buckets": [
                    {
                        "id": "trial_evidence",
                        "title": "Trial evidence",
                        "role": "main evidence base",
                        "required_for_review": True,
                        "coverage_status": "covered",
                        "evidence_refs": [{"kind": "variable", "id": "aspree"}],
                        "recommended_queries": [],
                    }
                ],
                "controversy_axes": ["benefit versus bleeding"],
                "coverage_gaps": [],
                "recommended_expansions": [],
                "synthesis_notes": [],
            }
        elif '"phase": "focus_analysis"' in user_content:
            payload = {
                "focuses": [
                    {
                        "id": "elderly_net_benefit",
                        "kind": "research_focus",
                        "status": "accepted",
                        "question": "老年人阿司匹林一级预防是否有净获益？",
                        "rationale": "LiteLLM provider selected a grounded focus.",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {"population": "older adults"},
                        "coverage": {"items": 1, "paper_leads": 1, "missing": []},
                        "evidence_refs": [{"kind": "variable", "id": "aspree"}],
                        "suggested_queries": [],
                    }
                ],
                "coverage_gaps": [],
                "notes": ["litellm focus output"],
            }
        else:
            payload = {
                "relations": [
                    {
                        "type": "opposes",
                        "claim": "ASPREE opposes routine primary prevention aspirin.",
                        "rationale": "The retrieved evidence reports limited benefit.",
                        "epistemic_status": "candidate",
                        "promotion_hint": "none",
                        "source_refs": [{"kind": "variable", "id": "aspree"}],
                    }
                ],
                "review": {
                    "language": "zh",
                    "depth": "review",
                    "summary": "LiteLLM 评估输出。[variable:aspree]",
                    "sections": [
                        {
                            "title": "证据",
                            "body": "证据偏反对常规一级预防。[variable:aspree]",
                        }
                    ],
                    "limitations": [],
                    "next_queries": [],
                },
                "candidate_obligations": [],
            }
        return {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "id": "litellm-test-request",
        }

    fake_litellm = SimpleNamespace(
        acompletion=fake_acompletion,
        suppress_debug_info=False,
        disable_cost_calc=False,
    )
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    _patch_deep_materialization(monkeypatch)

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "aspirin primary prevention evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "litellm-provider-run",
            "--search-json",
            str(broad_search),
            "--analysis-provider",
            "litellm",
            "--model",
            "litellm_proxy/test-model",
            "--llm-timeout",
            "9",
            "--llm-max-retries",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "status: completed" in result.output
    assert len(calls) == 5
    assert {call["model"] for call in calls} == {"litellm_proxy/test-model"}
    assert {call["timeout"] for call in calls} == {9.0}
    assert {call["max_retries"] for call in calls} == {1}
    assert all(call["response_format"] == {"type": "json_object"} for call in calls)
    run_dir = pkg_dir / ".gaia" / "research" / "runs" / "litellm-provider-run"
    assert (run_dir / "analysis" / "field_map_analysis.output.json").exists()
    assert (run_dir / "analysis" / "focus_analysis.output.json").exists()
    assert (run_dir / "analysis" / "assess_analysis.output.json").exists()
    assert (run_dir / "analysis" / "report_plan.output.json").exists()
    assert (run_dir / "analysis" / "report_stitch.output.json").exists()
    benchmark = json.loads((run_dir / "trace" / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["summary"]["kind_counts"]["llm"] == 5
    assert benchmark["summary"]["total_input_tokens"] == 50
    assert benchmark["summary"]["total_output_tokens"] == 100
    assert benchmark["summary"]["total_tokens"] == 150


def test_research_run_litellm_auto_plans_queries_and_focus_suggestions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    searched_queries: list[str] = []

    def fake_lkm_search(
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        searched_queries.append(query)
        assert index == "bohrium"
        assert limit == 3
        assert reasoning_only is True
        row_id = "aspree" if "primary" in query else "bleed"
        return _search(
            query,
            [
                _lkm_row(
                    f"P_{row_id.upper()}",
                    row_id,
                    0.9,
                    paper_title=f"{row_id.upper()} paper",
                    content=f"{query} retrieved evidence.",
                )
            ],
        )

    monkeypatch.setattr(research_orchestrator, "_run_lkm_knowledge_search", fake_lkm_search)
    _patch_deep_materialization(monkeypatch)

    calls: list[str] = []

    async def fake_acompletion(**kwargs: object) -> dict[str, object]:
        messages = kwargs["messages"]
        assert isinstance(messages, list)
        user_content = str(messages[-1]["content"])
        payload: dict[str, Any]
        if '"phase": "query_plan"' in user_content:
            calls.append("query_plan")
            payload = {
                "queries": [
                    {
                        "query": "aspirin elderly primary prevention",
                        "rationale": "broad evidence scan",
                    }
                ]
            }
        elif '"phase": "field_map_analysis"' in user_content:
            calls.append("field_map_analysis")
            payload = {
                "domain_thesis": "一级预防综述需要覆盖试验证据和指南/风险分层。",
                "buckets": [
                    {
                        "id": "trial_evidence",
                        "title": "Trial evidence",
                        "role": "main evidence base",
                        "required_for_review": True,
                        "coverage_status": "covered",
                        "evidence_refs": [{"kind": "variable", "id": "aspree"}],
                        "recommended_queries": [],
                    },
                    {
                        "id": "risk_stratification",
                        "title": "Risk stratification",
                        "role": "review coverage gap",
                        "required_for_review": True,
                        "coverage_status": "thin",
                        "evidence_refs": [{"kind": "query", "query_index": 0}],
                        "recommended_queries": ["aspirin guideline risk stratification"],
                    },
                ],
                "controversy_axes": ["benefit versus bleeding"],
                "coverage_gaps": [],
                "recommended_expansions": [],
                "synthesis_notes": [],
            }
        elif '"phase": "focus_analysis"' in user_content:
            calls.append("focus_analysis")
            assert "field_map" in user_content
            payload = {
                "focuses": [
                    {
                        "id": "elderly_net_benefit",
                        "kind": "research_focus",
                        "status": "accepted",
                        "question": "老年人阿司匹林一级预防是否有净获益？",
                        "rationale": "Focus suggests targeted bleeding search.",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {"population": "older adults"},
                        "coverage": {"items": 1, "paper_leads": 1, "missing": []},
                        "evidence_refs": [{"kind": "variable", "id": "aspree"}],
                        "suggested_queries": ["aspirin elderly bleeding"],
                    }
                ],
                "coverage_gaps": [],
                "notes": [],
            }
        else:
            calls.append("assess_analysis")
            payload = {
                "relations": [
                    {
                        "type": "opposes",
                        "claim": "ASPREE opposes routine primary prevention aspirin.",
                        "rationale": "The retrieved evidence reports limited benefit.",
                        "epistemic_status": "candidate",
                        "promotion_hint": "none",
                        "source_refs": [{"kind": "variable", "id": "aspree"}],
                    }
                ],
                "review": {
                    "language": "zh",
                    "depth": "review",
                    "summary": "自动 query plan 与 suggested query 均已执行。[variable:aspree]",
                    "sections": [{"title": "证据", "body": "证据偏反对。[variable:aspree]"}],
                    "limitations": [],
                    "next_queries": [],
                },
                "candidate_obligations": [],
            }
        return {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "id": f"litellm-{calls[-1]}",
        }

    fake_litellm = SimpleNamespace(
        acompletion=fake_acompletion,
        suppress_debug_info=False,
        disable_cost_calc=False,
    )
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "aspirin primary prevention evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "litellm-auto-plan-run",
            "--analysis-provider",
            "litellm",
            "--model",
            "litellm_proxy/test-model",
            "--search-limit",
            "3",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[:4] == [
        "query_plan",
        "field_map_analysis",
        "focus_analysis",
        "assess_analysis",
    ]
    assert len(calls) == 6
    assert searched_queries == [
        "aspirin elderly primary prevention",
        "aspirin guideline risk stratification",
        "aspirin elderly bleeding",
    ]
    run_dir = pkg_dir / ".gaia" / "research" / "runs" / "litellm-auto-plan-run"
    assert (run_dir / "analysis" / "query_plan.output.json").exists()
    assert (run_dir / "analysis" / "field_map_analysis.output.json").exists()
    assert len(list((pkg_dir / ".gaia" / "research" / "field_maps").glob("*.json"))) == 1
    selected_evidence_paths = sorted(
        (pkg_dir / ".gaia" / "research" / "evidence").glob("selected-evidence-*.json")
    )
    assert len(selected_evidence_paths) == 1
    assess_input = json.loads(
        (run_dir / "analysis" / "assess_analysis.input.json").read_text(encoding="utf-8")
    )
    assert assess_input["artifact_payloads"][0]["json"]["kind"] == "selected_evidence"
    assert assess_input["artifact_payloads"][0]["path"] == str(selected_evidence_paths[0])
    assert sorted(path.name for path in (run_dir / "searches").glob("*.json")) == [
        "broad-01.json",
        "coverage-01.json",
        "targeted-elderly_net_benefit-01.json",
    ]
    events = [
        json.loads(line)
        for line in (run_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        event["type"] == "provider.completed" and event["phase"] == "query_plan" for event in events
    )
    benchmark = json.loads((run_dir / "trace" / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["summary"]["kind_counts"]["llm"] == 6
    assert benchmark["summary"]["kind_counts"]["search"] == 3


def test_research_run_fast_mode_deep_expands_selected_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    config_path = tmp_path / "research.json"
    config_path.write_text(
        json.dumps(
            {
                "profile": "review",
                "evidence": {"max_items": 4, "max_papers": 3, "max_chains": 2},
            }
        ),
        encoding="utf-8",
    )

    def fake_lkm_search(
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        assert index == "bohrium"
        assert limit == 2
        assert reasoning_only is True
        return _search(
            query,
            [
                _lkm_row(
                    "P_DEEP",
                    "claim_deep",
                    0.9,
                    paper_title="Deep evidence paper",
                    content="Selected focus evidence about weak first-order behavior.",
                )
            ],
        )

    monkeypatch.setattr(research_orchestrator, "_run_lkm_knowledge_search", fake_lkm_search)

    materialize_calls: list[dict[str, object]] = []

    def fake_materialize(
        research_pkg: Any,
        *,
        paper_ids: list[str],
        claim_ids: list[str],
        chain_claim_ids: list[str],
        lkm_index: str,
        dry_run: bool,
    ) -> dict[str, object]:
        materialize_calls.append(
            {
                "paper_ids": paper_ids,
                "claim_ids": claim_ids,
                "chain_claim_ids": chain_claim_ids,
                "lkm_index": lkm_index,
                "dry_run": dry_run,
                "pkg": research_pkg.path,
            }
        )
        return {
            "lkm_materialize_requests": [*paper_ids, *claim_ids, *chain_claim_ids],
            "lkm_packages_materialized": [{"source_ref": "lkm:bohrium:paper:P_DEEP"}],
            "lkm_chains_materialized": [{"source_ref": "lkm:bohrium:chain:claim_deep"}],
        }

    monkeypatch.setattr(
        research_orchestrator,
        "_materialize_lkm_papers_or_exit",
        fake_materialize,
    )

    calls: list[str] = []

    async def fake_acompletion(**kwargs: object) -> dict[str, object]:
        user_content = str(kwargs["messages"][-1]["content"])
        payload: dict[str, Any]
        if '"phase": "query_plan"' in user_content:
            calls.append("query_plan")
            payload = {"queries": [{"query": "weak first order evidence", "rationale": "broad"}]}
        elif '"phase": "field_map_analysis"' in user_content:
            calls.append("field_map_analysis")
            payload = {
                "domain_thesis": "Review map.",
                "buckets": [
                    {
                        "id": "weak_first_order",
                        "title": "Weak first order",
                        "role": "core controversy",
                        "required_for_review": True,
                        "coverage_status": "covered",
                        "evidence_refs": [{"kind": "variable", "id": "claim_deep"}],
                        "recommended_queries": [],
                    }
                ],
                "controversy_axes": ["continuous versus weak first order"],
                "coverage_gaps": [],
                "recommended_expansions": [],
                "synthesis_notes": [],
            }
        elif '"phase": "focus_analysis"' in user_content:
            calls.append("focus_analysis")
            payload = {
                "focuses": [
                    {
                        "id": "weak_first_order_focus",
                        "kind": "research_focus",
                        "status": "accepted",
                        "question": "Does evidence favor weak first-order behavior?",
                        "rationale": "Grounded in selected claim.",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {},
                        "coverage": {"items": 1, "paper_leads": 1, "missing": []},
                        "evidence_refs": [{"kind": "variable", "id": "claim_deep"}],
                        "suggested_queries": [],
                    }
                ],
                "coverage_gaps": [],
                "notes": [],
            }
        elif '"phase": "assess_analysis"' in user_content:
            calls.append("assess_analysis")
            assert '"kind": "selected_evidence"' in user_content
            assert '"materialization_plan"' in user_content
            payload = {
                "relations": [
                    {
                        "type": "supports",
                        "claim": "Selected evidence supports the weak first-order focus.",
                        "rationale": "The selected packet contains the directly relevant claim.",
                        "epistemic_status": "candidate",
                        "promotion_hint": "none",
                        "source_refs": [{"kind": "variable", "id": "claim_deep"}],
                    }
                ],
                "candidate_obligations": [],
            }
        elif '"phase": "report_plan"' in user_content:
            calls.append("report_plan")
            payload = {
                "title": "Weak first order report",
                "abstract": "Sectioned report.",
                "thesis": "Selected evidence supports the focus.",
                "sections": [
                    {
                        "id": "judgment",
                        "title": "Judgment",
                        "purpose": "Summarize assessment judgment.",
                        "evidence_refs": [{"kind": "variable", "id": "claim_deep"}],
                    }
                ],
                "conclusion_prompt": "Conclude cautiously.",
            }
        elif '"phase": "report_section"' in user_content:
            calls.append("report_section:judgment")
            payload = {
                "section_id": "judgment",
                "title": "Judgment",
                "markdown": "## Judgment\n\nSelected evidence supports the focus.",
                "used_refs": [{"kind": "variable", "id": "claim_deep"}],
            }
        else:
            calls.append("report_stitch")
            payload = {
                "markdown": (
                    "# Weak first order report\n\n"
                    "## Judgment\n\nSelected evidence supports the focus.\n"
                )
            }
        return {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "id": f"litellm-{calls[-1]}",
        }

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(
            acompletion=fake_acompletion,
            suppress_debug_info=False,
            disable_cost_calc=False,
        ),
    )

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "weak first order evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "deep-expand-run",
            "--config",
            str(config_path),
            "--analysis-provider",
            "litellm",
            "--model",
            "litellm_proxy/test-model",
            "--search-limit",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        "query_plan",
        "field_map_analysis",
        "focus_analysis",
        "assess_analysis",
        "report_plan",
        "report_section:judgment",
        "report_stitch",
    ]
    assert materialize_calls == [
        {
            "paper_ids": ["P_DEEP"],
            "claim_ids": [],
            "chain_claim_ids": ["claim_deep"],
            "lkm_index": "bohrium",
            "dry_run": False,
            "pkg": pkg_dir,
        }
    ]
    selected_evidence_path = next(
        (pkg_dir / ".gaia" / "research" / "evidence").glob("selected-evidence-*.json")
    )
    selected_evidence = json.loads(selected_evidence_path.read_text(encoding="utf-8"))
    assert selected_evidence["selection_policy"] == {
        "mode": "review",
        "max_items": 4,
        "max_papers": 3,
        "max_chains": 2,
        "max_omitted": 20,
    }
    assert selected_evidence["selection"]["unique_items_considered"] == 1
    assert selected_evidence["coverage_audit"]["focus_refs_selected"] == 1
    assert selected_evidence["materialization_result"]["lkm_packages_materialized"] == [
        {"source_ref": "lkm:bohrium:paper:P_DEEP"}
    ]


def test_research_run_litellm_writes_report_in_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)

    def fake_lkm_search(
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        assert index == "bohrium"
        assert limit == 2
        assert reasoning_only is True
        filler_rows = [
            _lkm_row(
                f"P_FILLER_{index}",
                f"claim_filler_{index}",
                0.1,
                paper_title=f"Filler paper {index}",
                content=f"Filler evidence {index}.",
            )
            for index in range(11)
        ]
        return _search(
            query,
            [
                _lkm_row(
                    "P_REPORT",
                    "claim_report",
                    0.9,
                    paper_title="Report evidence paper",
                    content="Evidence supports a cautious conclusion.",
                ),
                *filler_rows,
                _lkm_row(
                    "P_EXTRA",
                    "claim_extra",
                    0.05,
                    paper_title="Landscape-only paper",
                    content="Landscape-only evidence should still reach its report section.",
                ),
            ],
        )

    monkeypatch.setattr(research_orchestrator, "_run_lkm_knowledge_search", fake_lkm_search)

    def fake_no_materialize(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "lkm_materialize_requests": [],
            "lkm_packages_materialized": [],
            "lkm_chains_materialized": [],
        }

    monkeypatch.setattr(
        research_orchestrator,
        "_materialize_lkm_papers_or_exit",
        fake_no_materialize,
    )

    calls: list[str] = []
    section_inputs: dict[str, dict[str, object]] = {}
    stitch_inputs: list[dict[str, object]] = []

    async def fake_acompletion(**kwargs: object) -> dict[str, object]:
        user_content = str(kwargs["messages"][-1]["content"])
        payload: dict[str, Any]
        if '"phase": "query_plan"' in user_content:
            calls.append("query_plan")
            payload = {"queries": [{"query": "report evidence", "rationale": "broad"}]}
        elif '"phase": "field_map_analysis"' in user_content:
            calls.append("field_map_analysis")
            payload = {
                "domain_thesis": "Report field map.",
                "buckets": [
                    {
                        "id": "evidence_base",
                        "title": "Evidence base",
                        "role": "main evidence",
                        "required_for_review": True,
                        "coverage_status": "covered",
                        "evidence_refs": [{"kind": "variable", "id": "claim_report"}],
                        "recommended_queries": [],
                    }
                ],
                "controversy_axes": ["support versus caution"],
                "coverage_gaps": [],
                "recommended_expansions": [],
                "synthesis_notes": [],
            }
        elif '"phase": "focus_analysis"' in user_content:
            calls.append("focus_analysis")
            payload = {
                "focuses": [
                    {
                        "id": "report_focus",
                        "kind": "research_focus",
                        "status": "accepted",
                        "question": "What does the evidence show?",
                        "rationale": "Grounded in report claim.",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {},
                        "coverage": {"items": 1, "paper_leads": 1, "missing": []},
                        "evidence_refs": [{"kind": "variable", "id": "claim_report"}],
                        "suggested_queries": [],
                    }
                ],
                "coverage_gaps": [],
                "notes": [],
            }
        elif '"phase": "assess_analysis"' in user_content:
            calls.append("assess_analysis")
            payload = {
                "relations": [
                    {
                        "type": "qualifies",
                        "claim": "The selected evidence supports a cautious conclusion.",
                        "rationale": "The selected evidence packet contains the relevant claim.",
                        "epistemic_status": "candidate",
                        "promotion_hint": "none",
                        "source_refs": [{"kind": "variable", "id": "claim_report"}],
                    }
                ],
                "candidate_obligations": [],
            }
        elif '"phase": "report_plan"' in user_content:
            calls.append("report_plan")
            payload = {
                "title": "分章节循证报告",
                "abstract": "报告应分章节呈现证据。",
                "thesis": "证据支持谨慎结论。",
                "sections": [
                    {
                        "id": "evidence_base",
                        "title": "证据基础",
                        "purpose": "解释核心证据。",
                        "evidence_refs": [{"kind": "variable", "id": "claim_report"}],
                    },
                    {
                        "id": "evidence:base",
                        "title": "局限性",
                        "purpose": "说明不确定性。",
                        "evidence_refs": [{"kind": "variable", "id": "claim_extra"}],
                    },
                ],
                "conclusion_prompt": "给出审慎结论。",
            }
        elif '"phase": "report_section"' in user_content:
            section_id = (
                "evidence_base"
                if '"section_id": "evidence_base"' in user_content
                else "evidence:base"
            )
            request = json.loads(user_content)["input"]
            section_inputs[section_id] = request
            calls.append(f"report_section:{section_id}")
            payload = {
                "section_id": section_id,
                "title": "证据基础" if section_id == "evidence_base" else "局限性",
                "markdown": (
                    "## 证据基础\n\n核心证据支持审慎判断。[variable:claim_report]\n"
                    if section_id == "evidence_base"
                    else "## 局限性\n\n仍需更多深读证据。[variable:claim_extra]\n"
                ),
                "used_refs": [
                    {
                        "kind": "variable",
                        "id": "claim_report" if section_id == "evidence_base" else "claim_extra",
                    }
                ],
            }
        else:
            request = json.loads(user_content)["input"]
            stitch_inputs.append(request)
            calls.append("report_stitch")
            payload = {
                "markdown": (
                    "# 分章节循证报告\n\n"
                    "## 摘要\n\n报告应分章节呈现证据。\n\n"
                    "## 证据基础\n\n核心证据支持审慎判断（claim_report）。\n\n"
                    "## 局限性\n\n仍需更多深读证据（claim_extra）。\n"
                )
            }
        return {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "id": f"litellm-{calls[-1]}",
        }

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(
            acompletion=fake_acompletion,
            suppress_debug_info=False,
            disable_cost_calc=False,
        ),
    )

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "report evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "section-report-run",
            "--analysis-provider",
            "litellm",
            "--model",
            "litellm_proxy/test-model",
            "--search-limit",
            "2",
            "--report-section-concurrency",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        "query_plan",
        "field_map_analysis",
        "focus_analysis",
        "assess_analysis",
        "report_plan",
        "report_section:evidence_base",
        "report_section:evidence:base",
        "report_stitch",
    ]
    assert len(stitch_inputs) == 1
    draft_markdown = stitch_inputs[0]["draft_markdown"]
    assert isinstance(draft_markdown, str)
    assert "## 证据基础" in draft_markdown
    assert "## 局限性" in draft_markdown
    run_dir = pkg_dir / ".gaia" / "research" / "runs" / "section-report-run"
    assert (run_dir / "analysis" / "report_plan.output.json").exists()
    assert (run_dir / "analysis" / "report_section_01_evidence_base.output.json").exists()
    assert (run_dir / "analysis" / "report_section_02_evidence_base.output.json").exists()
    assert (run_dir / "analysis" / "report_stitch.output.json").exists()
    evidence_base_context = section_inputs["evidence_base"]["section_evidence"]
    assert isinstance(evidence_base_context, dict)
    evidence_items = evidence_base_context["items"]
    assert isinstance(evidence_items, list)
    assert len(evidence_items) == 1
    evidence_item = evidence_items[0]
    assert isinstance(evidence_item, dict)
    assert evidence_item["kind"] == "variable"
    assert evidence_item["id"] == "claim_report"
    assert evidence_item["content"] == "Evidence supports a cautious conclusion."
    source = evidence_item["source"]
    assert isinstance(source, dict)
    assert source["paper_id"] == "P_REPORT"
    assert source["paper_title"] == "Report evidence paper"
    assert evidence_base_context["missing_refs"] == []
    limitations_context = section_inputs["evidence:base"]["section_evidence"]
    assert isinstance(limitations_context, dict)
    limitation_items = limitations_context["items"]
    assert isinstance(limitation_items, list)
    assert len(limitation_items) == 1
    limitation_item = limitation_items[0]
    assert isinstance(limitation_item, dict)
    assert limitation_item["id"] == "claim_extra"
    limitation_source = limitation_item["source"]
    assert isinstance(limitation_source, dict)
    assert limitation_source["paper_title"] == "Landscape-only paper"
    assert limitations_context["missing_refs"] == []
    final_report = (run_dir / "trace" / "final_report.md").read_text(encoding="utf-8")
    assert final_report.startswith("# 分章节循证报告")
    assert "## 证据基础" in final_report
    assert "## 局限性" in final_report
    assert "[variable:claim_report]" not in final_report
    assert "[variable:claim_extra]" not in final_report
    assert "claim_report" not in final_report
    assert "claim_extra" not in final_report
    assert "[1]" in final_report
    assert "[2]" in final_report
    assert "## 参考文献" in final_report
    assert "Report evidence paper" in final_report
    assert "Landscape-only paper" in final_report


def test_sectioned_report_citations_fallback_to_refs_and_relations() -> None:
    from gaia.cli.commands.research_report_writing import (
        _normalize_rendered_report_citation_wrappers,
        _normalize_report_citation_refs,
        _sectioned_report_citations,
    )
    from gaia.engine.research import render_markdown_with_research_citations

    section_contexts: list[dict[str, object]] = [
        {
            "refs": ["claim_from_plan", "123456789"],
            "items": [],
            "paper_leads": [],
            "relations": [
                {
                    "source_refs": [
                        {"kind": "variable", "id": "claim_from_relation"},
                    ],
                }
            ],
            "citations": [],
            "missing_refs": [],
        }
    ]
    citations = _sectioned_report_citations(section_contexts)
    markdown = _normalize_report_citation_refs(
        "计划引用（[claim_from_plan, 123456789]），关系引用([claim_from_relation])。",
        citations,
    )
    rendered = render_markdown_with_research_citations(
        markdown,
        citations=citations,
        language="zh",
    )
    rendered = _normalize_rendered_report_citation_wrappers(rendered)

    assert "claim_from_plan" not in rendered
    assert "123456789" not in rendered
    assert "claim_from_relation" not in rendered
    assert "[1]" in rendered
    assert "[2]" in rendered
    assert "[3]" in rendered
    assert "[[" not in rendered
    assert "（[" not in rendered
    assert "([" not in rendered
    assert "## 参考文献" in rendered
    wrapped = _normalize_rendered_report_citation_wrappers("复杂引用（[1][2]、）和英文([3], [4])。")
    assert wrapped == "复杂引用[1], [2]和英文[3], [4]。"


def test_research_run_parallelizes_report_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "pkg"
    _write_research_package(pkg_dir)

    def fake_lkm_search(
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        assert index == "bohrium"
        assert limit == 2
        assert reasoning_only is True
        return _search(
            query,
            [
                _lkm_row(
                    "P_PARALLEL",
                    "claim_parallel",
                    0.9,
                    paper_title="Parallel report paper",
                    content="Parallel section evidence.",
                )
            ],
        )

    monkeypatch.setattr(research_orchestrator, "_run_lkm_knowledge_search", fake_lkm_search)
    monkeypatch.setattr(
        research_orchestrator,
        "_materialize_lkm_papers_or_exit",
        lambda *_args, **_kwargs: {
            "lkm_materialize_requests": [],
            "lkm_packages_materialized": [],
            "lkm_chains_materialized": [],
        },
    )

    active_sections = 0
    max_active_sections = 0
    active_lock = threading.Lock()

    async def fake_acompletion(**kwargs: object) -> dict[str, object]:
        nonlocal active_sections, max_active_sections
        user_content = str(kwargs["messages"][-1]["content"])
        payload: dict[str, Any]
        if '"phase": "query_plan"' in user_content:
            payload = {"queries": [{"query": "parallel evidence", "rationale": "broad"}]}
        elif '"phase": "field_map_analysis"' in user_content:
            payload = {
                "domain_thesis": "Parallel field map.",
                "buckets": [
                    {
                        "id": "parallel",
                        "title": "Parallel",
                        "role": "evidence",
                        "required_for_review": True,
                        "coverage_status": "covered",
                        "evidence_refs": [{"kind": "variable", "id": "claim_parallel"}],
                        "recommended_queries": [],
                    }
                ],
                "controversy_axes": [],
                "coverage_gaps": [],
                "recommended_expansions": [],
                "synthesis_notes": [],
            }
        elif '"phase": "focus_analysis"' in user_content:
            payload = {
                "focuses": [
                    {
                        "id": "parallel_focus",
                        "kind": "research_focus",
                        "status": "accepted",
                        "question": "Can sections run concurrently?",
                        "rationale": "Grounded in parallel evidence.",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {},
                        "coverage": {"items": 1, "paper_leads": 1, "missing": []},
                        "evidence_refs": [{"kind": "variable", "id": "claim_parallel"}],
                        "suggested_queries": [],
                    }
                ],
                "coverage_gaps": [],
                "notes": [],
            }
        elif '"phase": "assess_analysis"' in user_content:
            payload = {
                "relations": [
                    {
                        "type": "supports",
                        "claim": "Parallel evidence supports the focus.",
                        "rationale": "The selected packet contains the claim.",
                        "epistemic_status": "candidate",
                        "promotion_hint": "none",
                        "source_refs": [{"kind": "variable", "id": "claim_parallel"}],
                    }
                ],
                "candidate_obligations": [],
            }
        elif '"phase": "report_plan"' in user_content:
            payload = {
                "title": "Parallel report",
                "abstract": "Sections can run concurrently.",
                "thesis": "Parallel section writing is independent.",
                "sections": [
                    {
                        "id": "one",
                        "title": "One",
                        "purpose": "First section.",
                        "evidence_refs": [{"kind": "variable", "id": "claim_parallel"}],
                    },
                    {
                        "id": "two",
                        "title": "Two",
                        "purpose": "Second section.",
                        "evidence_refs": [{"kind": "variable", "id": "claim_parallel"}],
                    },
                    {
                        "id": "three",
                        "title": "Three",
                        "purpose": "Third section.",
                        "evidence_refs": [{"kind": "variable", "id": "claim_parallel"}],
                    },
                ],
                "conclusion_prompt": "Conclude.",
            }
        elif '"phase": "report_section"' in user_content:
            request = json.loads(user_content)["input"]
            section_id = str(request["section_id"])
            with active_lock:
                active_sections += 1
                max_active_sections = max(max_active_sections, active_sections)
            await asyncio.sleep(0.05)
            with active_lock:
                active_sections -= 1
            payload = {
                "section_id": section_id,
                "title": section_id.title(),
                "markdown": (
                    f"## {section_id.title()}\n\nParallel evidence.[variable:claim_parallel]\n"
                ),
                "used_refs": [{"kind": "variable", "id": "claim_parallel"}],
            }
        else:
            payload = {
                "markdown": (
                    "# Parallel report\n\n"
                    "## One\n\nParallel evidence.[variable:claim_parallel]\n\n"
                    "## Two\n\nParallel evidence.[variable:claim_parallel]\n\n"
                    "## Three\n\nParallel evidence.[variable:claim_parallel]\n"
                )
            }
        return {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "id": "litellm-test",
        }

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(
            acompletion=fake_acompletion,
            suppress_debug_info=False,
            disable_cost_calc=False,
        ),
    )

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "parallel evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "parallel-section-run",
            "--analysis-provider",
            "litellm",
            "--model",
            "litellm_proxy/test-model",
            "--search-limit",
            "2",
            "--report-section-concurrency",
            "3",
        ],
    )

    assert result.exit_code == 0, result.output
    assert max_active_sections > 1


def test_litellm_json_parser_repairs_latex_backslashes() -> None:
    payload = research_providers._json_object_from_llm_content(
        '{"review":{"summary":"弱一级标度 $T^{**}-T^*\\propto q^2$"}}'
    )

    assert payload == {"review": {"summary": "弱一级标度 $T^{**}-T^*\\propto q^2$"}}


def test_research_run_litellm_provider_loads_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    broad_search = tmp_path / "broad-search.json"
    broad_search.write_text(
        json.dumps(
            _search(
                "aspirin elderly primary prevention",
                [
                    _lkm_row(
                        "P_ASPREE",
                        "aspree",
                        0.9,
                        paper_title="ASPREE trial",
                        content="ASPREE reported no cardiovascular benefit.",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "GAIA_RESEARCH_LLM_MODEL=litellm_proxy/env-model",
                "OPENAI_API_BASE=https://gateway.example/v1",
                "OPENAI_API_KEY=test-env-key",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for key in ("GAIA_RESEARCH_LLM_MODEL", "OPENAI_API_BASE", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    calls: list[dict[str, object]] = []

    async def fake_acompletion(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        assert os.environ["OPENAI_API_BASE"] == "https://gateway.example/v1"
        assert os.environ["OPENAI_API_KEY"] == "test-env-key"
        messages = kwargs["messages"]
        assert isinstance(messages, list)
        user_content = str(messages[-1]["content"])
        payload: dict[str, Any]
        if '"phase": "field_map_analysis"' in user_content:
            payload = {
                "domain_thesis": "Env file run builds a review field map first.",
                "buckets": [
                    {
                        "id": "trial_evidence",
                        "title": "Trial evidence",
                        "role": "main evidence base",
                        "required_for_review": True,
                        "coverage_status": "covered",
                        "evidence_refs": [{"kind": "variable", "id": "aspree"}],
                        "recommended_queries": [],
                    }
                ],
                "controversy_axes": ["benefit versus bleeding"],
                "coverage_gaps": [],
                "recommended_expansions": [],
                "synthesis_notes": [],
            }
        elif '"phase": "focus_analysis"' in user_content:
            payload = {
                "focuses": [
                    {
                        "id": "elderly_net_benefit",
                        "kind": "research_focus",
                        "status": "accepted",
                        "question": "老年人阿司匹林一级预防是否有净获益？",
                        "rationale": "Env-file model selected a grounded focus.",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "scope": {"population": "older adults"},
                        "coverage": {"items": 1, "paper_leads": 1, "missing": []},
                        "evidence_refs": [{"kind": "variable", "id": "aspree"}],
                        "suggested_queries": [],
                    }
                ],
                "coverage_gaps": [],
                "notes": [],
            }
        else:
            payload = {
                "relations": [
                    {
                        "type": "opposes",
                        "claim": "ASPREE opposes routine primary prevention aspirin.",
                        "rationale": "The retrieved evidence reports limited benefit.",
                        "epistemic_status": "candidate",
                        "promotion_hint": "none",
                        "source_refs": [{"kind": "variable", "id": "aspree"}],
                    }
                ],
                "review": {
                    "language": "zh",
                    "depth": "review",
                    "summary": "Env file 评估输出。[variable:aspree]",
                    "sections": [{"title": "证据", "body": "证据偏反对。[variable:aspree]"}],
                    "limitations": [],
                    "next_queries": [],
                },
                "candidate_obligations": [],
            }
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    fake_litellm = SimpleNamespace(
        acompletion=fake_acompletion,
        suppress_debug_info=False,
        disable_cost_calc=False,
    )
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    _patch_deep_materialization(monkeypatch)

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "aspirin primary prevention evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "litellm-env-file-run",
            "--search-json",
            str(broad_search),
            "--analysis-provider",
            "litellm",
            "--env-file",
            str(env_file),
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(calls) == 5
    assert {call["model"] for call in calls} == {"litellm_proxy/env-model"}


def test_research_run_litellm_provider_records_raw_and_failed_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    broad_search = tmp_path / "broad-search.json"
    broad_search.write_text(
        json.dumps(
            _search(
                "aspirin elderly primary prevention",
                [
                    _lkm_row(
                        "P_ASPREE",
                        "aspree",
                        0.9,
                        paper_title="ASPREE trial",
                        content="ASPREE reported no cardiovascular benefit.",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )

    async def fake_acompletion(**kwargs: object) -> dict[str, object]:
        assert kwargs["response_format"] == {"type": "json_object"}
        return {
            "choices": [{"message": {"content": "Here is the JSON: {}"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            "id": "litellm-invalid-json",
        }

    fake_litellm = SimpleNamespace(
        acompletion=fake_acompletion,
        suppress_debug_info=False,
        disable_cost_calc=False,
    )
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "aspirin primary prevention evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "litellm-invalid-json-run",
            "--search-json",
            str(broad_search),
            "--analysis-provider",
            "litellm",
            "--model",
            "litellm_proxy/test-model",
        ],
    )

    assert result.exit_code == 2, result.output
    run_dir = pkg_dir / ".gaia" / "research" / "runs" / "litellm-invalid-json-run"
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert state["phase"] == "field_map_analysis"
    raw_path = run_dir / "analysis" / "field_map_analysis.raw.txt"
    assert raw_path.read_text(encoding="utf-8") == "Here is the JSON: {}"
    assert not (run_dir / "analysis" / "field_map_analysis.output.json").exists()
    trace = [
        json.loads(line)
        for line in (run_dir / "trace" / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    failed = trace[-1]
    assert failed["step"] == "provider.litellm.field_map_analysis"
    assert failed["kind"] == "llm"
    assert failed["status"] == "failed"
    assert failed["outputs"] == [str(raw_path)]
    assert failed["token_usage"] == {"input_tokens": 11, "output_tokens": 7}
    assert failed["metrics"]["error_type"] == "ValueError"
    assert failed["metrics"]["raw_path"] == str(raw_path)


def test_research_run_waits_for_focus_analysis_when_missing(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    broad_search = tmp_path / "broad-search.json"
    broad_search.write_text(
        json.dumps(
            _search(
                "aspirin elderly primary prevention",
                [
                    _lkm_row(
                        "P_ASPREE",
                        "aspree",
                        0.9,
                        paper_title="ASPREE trial",
                        content="ASPREE reported no cardiovascular benefit.",
                    )
                ],
            )
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            str(pkg_dir),
            "--topic",
            "aspirin primary prevention evidence",
            "--mode",
            "fast-package-native",
            "--run-id",
            "checkpoint-run",
            "--search-json",
            str(broad_search),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = pkg_dir / ".gaia" / "research" / "runs" / "checkpoint-run"
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "waiting_for_input"
    assert state["phase"] == "focus_analysis"
    checkpoint_path = Path(state["pending_checkpoint"])
    assert checkpoint_path.name == "focus_analysis.request.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["type"] == "checkpoint.focus_analysis"
    assert _landscape_artifacts(pkg_dir)


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


def test_research_scan_consumes_search_json_and_writes_landscape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uv_add(monkeypatch)
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
    assert events[-1]["payload"]["obligations_added"] == []
    assert len(events[-1]["payload"]["obligations_deferred"]) == 1

    state = _read_inquiry_state(pkg_dir)
    assert len(state["synthetic_hypotheses"]) == 1
    assert state["synthetic_obligations"] == []


def test_research_scan_records_trace_then_summarizes_benchmark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uv_add(monkeypatch)
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "benchmark query",
                [_lkm_row("P_BENCH", "lkm:bohrium:bench", 0.8, paper_title="Benchmark Paper")],
            )
        ),
        encoding="utf-8",
    )
    trace_dir = tmp_path / "trace"

    result = runner.invoke(
        app,
        [
            "research",
            "explore",
            str(pkg_dir),
            "--mode",
            "scan",
            "--search-json",
            str(search_path),
            "--trace-dir",
            str(trace_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "trace:" in result.output
    assert "benchmark_summary:" not in result.output
    benchmark_path = trace_dir / "benchmark.json"
    assert not benchmark_path.exists()

    summary = runner.invoke(
        app,
        [
            "research",
            "trace",
            "summarize",
            str(pkg_dir),
            "--trace-dir",
            str(trace_dir),
        ],
    )

    assert summary.exit_code == 0, summary.output
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["run"]["package"]["project_name"] == "research-demo-gaia"
    assert payload["summary"]["steps"] == 1
    assert payload["summary"]["mode_counts"] == {"fast_package_native": 1}
    step = payload["steps"][0]
    assert step["name"] == "explore.scan"
    assert step["kind"] == "cli"
    assert step["mode"] == "fast_package_native"
    assert step["wall_seconds"] >= 0
    assert step["metrics"]["query_batches"] == 1
    assert step["metrics"]["raw_results"] == 1
    assert step["metrics"]["paper_leads"] == 1
    assert step["metrics"]["source_packages_added"] == 1
    assert step["outputs"][0].endswith(".json")


def test_research_scan_defaults_trace_to_package_run_trace(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "default run trace query",
                [_lkm_row("P_TRACE", "lkm:bohrium:trace", 0.7, paper_title="Trace Paper")],
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
            "scan",
            "--search-json",
            str(search_path),
        ],
    )

    assert result.exit_code == 0, result.output
    trace_dir = pkg_dir / ".gaia" / "research" / "runs" / "current" / "trace"
    trace_lines = (trace_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(trace_lines) == 1
    trace = json.loads(trace_lines[0])
    assert trace["actor"] == "gaia_cli"
    assert trace["step"] == "explore.scan"
    assert trace["status"] == "ok"
    assert trace["ts_start"] <= trace["ts_end"]
    assert not (trace_dir / "benchmark.json").exists()

    summary = runner.invoke(app, ["research", "trace", "summarize", str(pkg_dir)])

    assert summary.exit_code == 0, summary.output
    benchmark = json.loads((trace_dir / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["summary"]["steps"] == 1
    assert benchmark["steps"][0]["name"] == "explore.scan"
    assert trace["outputs"] == benchmark["steps"][0]["outputs"]


def test_research_trace_record_appends_llm_token_step(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    trace_dir = tmp_path / "trace"
    prompt_path = tmp_path / "prompt.md"
    output_path = tmp_path / "focus-analysis.json"
    prompt_path.write_text("Prompt text", encoding="utf-8")
    output_path.write_text('{"focuses": []}', encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "research",
            "trace",
            "record",
            str(pkg_dir),
            "--trace-dir",
            str(trace_dir),
            "--step",
            "llm.focus_analysis",
            "--kind",
            "llm",
            "--mode",
            "fast_package_native",
            "--model",
            "gpt-5",
            "--input-tokens",
            "1200",
            "--output-tokens",
            "300",
            "--wall-seconds",
            "12.5",
            "--input-file",
            str(prompt_path),
            "--output-file",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Trace:" in result.output
    benchmark_path = trace_dir / "benchmark.json"
    assert not benchmark_path.exists()

    summary = runner.invoke(
        app,
        [
            "research",
            "trace",
            "summarize",
            str(pkg_dir),
            "--trace-dir",
            str(trace_dir),
        ],
    )

    assert summary.exit_code == 0, summary.output
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    assert payload["summary"]["steps"] == 1
    assert payload["summary"]["total_input_tokens"] == 1200
    assert payload["summary"]["total_output_tokens"] == 300
    assert payload["summary"]["total_tokens"] == 1500
    step = payload["steps"][0]
    assert step["name"] == "llm.focus_analysis"
    assert step["kind"] == "llm"
    assert step["model"] == "gpt-5"
    assert step["token_usage"] == {
        "input_tokens": 1200,
        "output_tokens": 300,
        "total_tokens": 1500,
    }
    assert step["inputs"] == [str(prompt_path)]
    assert step["outputs"] == [str(output_path)]
    trace_path = trace_dir / "trace.jsonl"
    trace = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert trace["actor"] == "llm"
    assert trace["step"] == "llm.focus_analysis"
    assert trace["model"] == "gpt-5"
    assert trace["token_usage"]["total_tokens"] == 1500


def test_research_trace_summarize_rebuilds_benchmark_from_trace(
    tmp_path: Path,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    trace_dir = tmp_path / "trace"

    first = runner.invoke(
        app,
        [
            "research",
            "trace",
            "record",
            str(pkg_dir),
            "--trace-dir",
            str(trace_dir),
            "--step",
            "search.lkm.first",
            "--kind",
            "search",
            "--mode",
            "external",
            "--wall-seconds",
            "1.25",
        ],
    )
    assert first.exit_code == 0, first.output
    second = runner.invoke(
        app,
        [
            "research",
            "trace",
            "record",
            str(pkg_dir),
            "--trace-dir",
            str(trace_dir),
            "--step",
            "llm.focus",
            "--kind",
            "llm",
            "--mode",
            "fast_package_native",
            "--input-tokens",
            "10",
            "--output-tokens",
            "5",
        ],
    )
    assert second.exit_code == 0, second.output

    benchmark_path = trace_dir / "benchmark.json"
    assert not benchmark_path.exists()

    result = runner.invoke(
        app,
        [
            "research",
            "trace",
            "summarize",
            str(pkg_dir),
            "--trace-dir",
            str(trace_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "benchmark_summary:" in result.output
    trace_lines = (trace_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    assert benchmark["summary"]["steps"] == len(trace_lines) == 2
    assert benchmark["summary"]["total_wall_seconds"] == 1.25
    assert benchmark["summary"]["total_tokens"] == 15
    assert [step["name"] for step in benchmark["steps"]] == [
        "search.lkm.first",
        "llm.focus",
    ]


def test_research_trace_concurrent_appends_summarize_once(
    tmp_path: Path,
) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    research_pkg = load_research_package(pkg_dir)
    trace_dir = tmp_path / "trace"

    def record_step(index: int) -> None:
        append_research_trace_step(
            research_pkg,
            trace_dir,
            name=f"search.lkm.parallel_{index}",
            kind="search",
            mode="external",
            wall_seconds=1.0,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(record_step, range(40)))

    benchmark_path = trace_dir / "benchmark.json"
    assert not benchmark_path.exists()
    benchmark_path = write_research_benchmark_summary(research_pkg, trace_dir)

    trace_lines = (trace_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(trace_lines) == 40
    assert all(json.loads(line)["kind"] == "search" for line in trace_lines)
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    assert benchmark["summary"]["steps"] == 40
    assert benchmark["summary"]["kind_counts"] == {"search": 40}
    assert benchmark["summary"]["total_wall_seconds"] == 40.0


def test_research_benchmark_command_is_not_registered() -> None:
    result = runner.invoke(app, ["research", "benchmark", "--help"])

    assert result.exit_code != 0
    assert "No such command" in result.output


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


def test_research_scan_reads_search_json_from_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uv_add(monkeypatch)
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


def test_research_expand_writes_targeted_landscape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uv_add(monkeypatch)
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
    assert state["synthetic_obligations"] == []
    assert events[-1]["payload"]["obligations_added"] == []
    assert events[-1]["payload"]["obligations_deferred"][0]["target_qid"] == "seed"


def test_research_focus_writes_synthesis_from_analysis_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uv_add(monkeypatch)
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
    assert events[-1]["payload"]["obligations_added"] == []
    assert len(events[-1]["payload"]["obligations_deferred"]) == 1

    state = _read_inquiry_state(pkg_dir)
    assert str(state["focus"]).startswith("rq_elderly_net_benefit_")
    assert state["focus_kind"] == "question"
    assert state["synthetic_obligations"] == []

    check = runner.invoke(app, ["build", "check", str(pkg_dir)])
    assert check.exit_code == 0, check.output


def test_research_assess_records_planning_event(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "research-demo-gaia"
    init_py = _write_research_package(pkg_dir)
    source_before = init_py.read_text(encoding="utf-8")

    result = runner.invoke(
        app,
        ["research", "assess", str(pkg_dir), "--focus", "seed"],
    )

    assert result.exit_code == 0, result.output
    assert init_py.read_text(encoding="utf-8") == source_before

    events = _read_events(pkg_dir)
    assert events[-1]["event"] == "assess.planned"
    assert events[-1]["payload"]["focus"] == "seed"


def test_research_assess_writes_grounded_assessment_from_landscape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uv_add(monkeypatch)
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
        ],
    )
    assert scan.exit_code == 0, scan.output
    landscape_path = _landscape_artifacts(pkg_dir)[0]
    trace_dir = tmp_path / "trace"

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
            "--trace-dir",
            str(trace_dir),
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
    summary = runner.invoke(
        app,
        [
            "research",
            "trace",
            "summarize",
            str(pkg_dir),
            "--trace-dir",
            str(trace_dir),
        ],
    )

    assert summary.exit_code == 0, summary.output
    benchmark = json.loads((trace_dir / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["summary"]["mode_counts"] == {"deep": 1}
    assert benchmark["steps"][0]["name"] == "assess"
    assert benchmark["steps"][0]["metrics"]["lkm_chains_materialized"] == 1


def test_research_assess_accepts_analysis_json_with_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uv_add(monkeypatch)
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
    assert events[-1]["payload"]["obligations_added"] == []
    assert len(events[-1]["payload"]["obligations_deferred"]) == 1
    assert len(events[-1]["payload"]["hypotheses_added"]) == 1

    state = _read_inquiry_state(pkg_dir)
    assert state["synthetic_obligations"] == []
    assert any(item["scope_qid"] == "elderly_net_benefit" for item in state["synthetic_hypotheses"])

    check = runner.invoke(app, ["build", "check", str(pkg_dir)])
    assert check.exit_code == 0, check.output


def test_research_assess_infers_candidate_relation_from_package_ref_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uv_add(monkeypatch)
    pkg_dir = tmp_path / "research-demo-gaia"
    _write_research_package(pkg_dir)
    search_path = tmp_path / "search.json"
    search_path.write_text(
        json.dumps(
            _search(
                "relation source package refs",
                [
                    _lkm_row(
                        "P_REL_A",
                        "lkm:bohrium:rel_a",
                        0.91,
                        paper_title="Relation Paper A",
                        content="Claim A supports one side of the relation.",
                    ),
                    _lkm_row(
                        "P_REL_B",
                        "lkm:bohrium:rel_b",
                        0.89,
                        paper_title="Relation Paper B",
                        content="Claim B supports the other side of the relation.",
                    ),
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
    landscape = json.loads(landscape_path.read_text(encoding="utf-8"))
    package_refs = [item["package_ref"] for item in landscape["items"]]
    assert [ref["value_type"] for ref in package_refs] == ["claim", "claim"]
    analysis_path = tmp_path / "assess-analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "relations": [
                    {
                        "type": "opposes",
                        "claim": "Two package claim refs are in tension.",
                        "rationale": "Both source refs are concrete shallow package claims.",
                        "epistemic_status": "candidate",
                        "promotion_hint": "none",
                        "source_refs": [
                            {"kind": "package_ref", "id": package_refs[0]["ref"]},
                            {"kind": "package_ref", "id": package_refs[1]["ref"]},
                        ],
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
            "package_ref_tension",
            "--landscape",
            str(landscape_path),
            "--analysis-json",
            str(analysis_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "candidate_relations_written: 1" in result.output
    authored = pkg_dir / "src" / "research_demo" / "authored" / "__init__.py"
    authored_source = authored.read_text(encoding="utf-8")
    assert "candidate_relation(" in authored_source
    assert "pattern='contradict'" in authored_source
    assert package_refs[0]["symbol"] in authored_source
    assert package_refs[1]["symbol"] in authored_source


def test_research_assess_skips_candidate_relation_for_non_claim_package_ref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uv_add(monkeypatch)
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
                        "source_refs": [
                            {"kind": "package_ref", "id": source_ref["ref"]},
                            {"kind": "variable", "id": "open_question"},
                        ],
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
    assert "candidate_relations_skipped: 1" in result.output
    events = _read_events(pkg_dir)
    assert events[-1]["payload"]["candidate_relations_written"] == []
    assert events[-1]["payload"]["candidate_relations_skipped"]
    assert source_ref["ref"] in events[-1]["payload"]["candidate_relations_skipped"][0]
    assert "value_type=question" in events[-1]["payload"]["candidate_relations_skipped"][0]
    authored = pkg_dir / "src" / "research_demo" / "authored" / "__init__.py"
    if authored.exists():
        assert "candidate_relation(" not in authored.read_text(encoding="utf-8")
    check = runner.invoke(app, ["build", "check", str(pkg_dir)])
    assert check.exit_code == 0, check.output


def test_research_assess_reports_schema_errors_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uv_add(monkeypatch)
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
    assert "# Evidence Assessment" in result.output
    assert "## Evidence Grading And Tensions" in result.output
    assert "当前证据不足。 没有可用 items。" in result.output
    assert "evidence packet" not in result.output
    assert "needs_more_evidence: 1" not in result.output
    assert "## Citations" not in result.output


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
