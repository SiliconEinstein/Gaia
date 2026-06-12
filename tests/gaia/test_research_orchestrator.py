"""Unit tests for engine-level research workflow orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gaia.engine.research import (
    ResearchOrchestratorPaused,
    ResearchPackage,
    ResearchSyncResult,
    append_research_event,
    write_research_artifact,
)
from gaia.engine.research.orchestrator import execute_file_provider_run
from gaia.engine.research.run import ResearchRunStart, start_research_run


def _write_research_package(pkg_dir: Path) -> ResearchPackage:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "research-demo-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "research_demo"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / "src" / "research_demo"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import claim\n\n"
        'seed = claim("Seed claim for research orchestrator tests.")\n'
        '__all__ = ["seed"]\n',
        encoding="utf-8",
    )
    return ResearchPackage(
        path=pkg_dir,
        project_name="research-demo-gaia",
        import_name="research_demo",
        namespace="research_demo",
    )


def _search_json(path: Path) -> Path:
    payload = {
        "schema_version": 1,
        "query": {"text": "aspirin evidence", "provider": "lkm", "kind": "knowledge"},
        "results": [
            {
                "id": "lkm:bohrium:var_aspree",
                "kind": "claim",
                "title": "Claim from ASPREE",
                "content": "ASPREE reported no cardiovascular benefit.",
                "gaia": {"qid": None},
                "source": {
                    "provider_id": "var_aspree",
                    "paper_id": "P_ASPREE",
                    "paper_title": "ASPREE trial",
                    "doi": "10.1/aspree",
                    "index_id": "bohrium",
                },
                "rank": {"score": 0.9},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _focus_analysis_json(path: Path) -> Path:
    payload = {
        "focuses": [
            {
                "id": "aspree_net_benefit",
                "kind": "research_focus",
                "status": "candidate",
                "question": "Does aspirin primary prevention show net benefit in older adults?",
                "rationale": "ASPREE evidence raises a net-benefit uncertainty.",
                "priority": "high",
                "readiness": "ready_for_assess",
                "scope": {"population": "older adults"},
                "coverage": {"items": 1, "missing": []},
                "evidence_refs": [{"kind": "variable", "id": "var_aspree"}],
                "suggested_queries": [],
            }
        ],
        "coverage_gaps": [],
        "notes": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class _Runtime:
    def update_run_state(self, run: ResearchRunStart, payload: dict[str, object]) -> None:
        state = json.loads(run.state_path.read_text(encoding="utf-8"))
        state.update(payload)
        run.state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def read_search_json(self, ref: str) -> tuple[dict[str, object], str]:
        path = Path(ref)
        return json.loads(path.read_text(encoding="utf-8")), str(path)

    def read_json_object_ref(self, ref: str, *, label: str) -> dict[str, object]:
        _ = label
        payload = json.loads(Path(ref).read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        return payload

    def write_json_file(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def write_text_file(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_artifact(
        self,
        research_pkg: ResearchPackage,
        category: str,
        stem: str,
        payload: dict[str, Any],
    ) -> Path:
        return write_research_artifact(research_pkg, category, stem, payload)

    def append_research_event(
        self,
        research_pkg: ResearchPackage,
        event: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return append_research_event(research_pkg, event, payload)

    def emit_run_event(
        self,
        run: ResearchRunStart,
        *,
        event_type: str,
        phase: str,
        json_stream: bool,
        payload: dict[str, object],
    ) -> None:
        _ = json_stream
        with run.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"type": event_type, "phase": phase, **payload}) + "\n")

    def record_trace(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        start: float,
        name: str,
        kind: str,
        mode: str,
        inputs: list[str],
        outputs: list[str],
        metrics: dict[str, object] | None = None,
        status: str = "ok",
    ) -> None:
        _ = research_pkg, start, kind, mode, inputs, outputs, metrics, status
        trace_dir = run.run_dir / "trace"
        trace_dir.mkdir(parents=True, exist_ok=True)
        with (trace_dir / "trace.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"name": name, "status": status}) + "\n")

    def record_cli_trace(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        start: float,
        name: str,
        mode: str,
        inputs: list[str],
        outputs: list[str],
        metrics: dict[str, object] | None = None,
    ) -> None:
        self.record_trace(
            research_pkg,
            run,
            start=start,
            name=name,
            kind="cli",
            mode=mode,
            inputs=inputs,
            outputs=outputs,
            metrics=metrics,
        )

    def sync_landscape_artifact(
        self,
        research_pkg: ResearchPackage,
        landscape: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        _ = research_pkg, landscape
        return ResearchSyncResult(dry_run=dry_run)

    def sync_focus_artifact(
        self,
        research_pkg: ResearchPackage,
        focus_artifact: dict[str, Any],
        *,
        max_questions: int,
        dry_run: bool,
    ) -> ResearchSyncResult:
        _ = research_pkg, focus_artifact, max_questions
        return ResearchSyncResult(dry_run=dry_run)

    def sync_assessment_artifact(
        self,
        research_pkg: ResearchPackage,
        assessment: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        _ = research_pkg, assessment
        return ResearchSyncResult(dry_run=dry_run)

    def write_benchmark_summary(self, research_pkg: ResearchPackage, trace_dir: Path) -> Path:
        _ = research_pkg
        path = trace_dir / "summary.json"
        self.write_json_file(path, {"schema_version": 1})
        return path

    def resolve_litellm_model(self, model: str | None) -> str:
        return model or "test-model"

    def maybe_run_sectioned_report_writing(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        topic: str,
        language: str,
        analysis_provider: str,
        research_mode: str,
        model: str | None,
        assess_model: str | None,
        focus: str,
        field_map_path: Path | None,
        focus_path: Path,
        landscape_paths: list[Path],
        selected_evidence_paths: list[Path],
        assessment_paths: list[Path],
        llm_temperature: float,
        llm_timeout: float,
        llm_max_retries: int,
        llm_max_tokens: int | None,
        report_section_concurrency: int,
        json_stream: bool,
    ) -> tuple[str | None, list[str]]:
        _ = (
            research_pkg,
            run,
            topic,
            language,
            analysis_provider,
            research_mode,
            model,
            assess_model,
            focus,
            field_map_path,
            focus_path,
            landscape_paths,
            selected_evidence_paths,
            assessment_paths,
            llm_temperature,
            llm_timeout,
            llm_max_retries,
            llm_max_tokens,
            report_section_concurrency,
            json_stream,
        )
        return None, []

    def search_lkm(
        self,
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        _ = query, index, limit, reasoning_only
        return {"schema_version": 1, "results": []}

    def run_command_provider(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("command provider should not run")

    def run_litellm_provider(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("litellm provider should not run")

    def materialize_landscape_sources(
        self,
        research_pkg: ResearchPackage,
        landscape: dict[str, Any],
        *,
        landscape_artifact: Path,
        dry_run: bool,
    ) -> dict[str, object]:
        _ = research_pkg, landscape, landscape_artifact, dry_run
        return {"source_packages_added": [], "source_packages_skipped": []}

    def materialize_lkm_deep_evidence(
        self,
        research_pkg: ResearchPackage,
        *,
        paper_ids: list[str],
        claim_ids: list[str],
        chain_claim_ids: list[str],
        lkm_index: str,
        dry_run: bool,
    ) -> dict[str, object]:
        _ = research_pkg, paper_ids, claim_ids, chain_claim_ids, lkm_index, dry_run
        return {
            "lkm_materialize_requests": [],
            "lkm_packages_materialized": [],
            "lkm_chains_materialized": [],
        }


def test_checkpoint_assess_pause_uses_typed_engine_signal(tmp_path: Path) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="review",
        run_id="typed-pause",
        wait_for_query_plan=False,
    )

    with pytest.raises(ResearchOrchestratorPaused) as exc_info:
        execute_file_provider_run(
            research_pkg,
            run,
            topic="aspirin evidence",
            mode="fast-package-native",
            language="en",
            search_json=[str(_search_json(tmp_path / "search.json"))],
            focus_analysis_json=str(_focus_analysis_json(tmp_path / "focus.json")),
            targeted_search_json=[],
            targeted_query=[],
            focus=None,
            focus_count=1,
            assess_analysis_json=None,
            analysis_provider="checkpoint",
            model=None,
            focus_model=None,
            assess_model=None,
            llm_temperature=0.0,
            llm_timeout=30.0,
            llm_max_retries=0,
            llm_max_tokens=None,
            report_section_concurrency=1,
            search_index="bohrium",
            search_limit=20,
            reasoning_only=True,
            evidence_selection_mode="off",
            evidence_max_items=8,
            evidence_max_papers=5,
            evidence_max_chains=3,
            focus_analysis_command=None,
            assess_analysis_command=None,
            json_stream=False,
            runtime=_Runtime(),
        )

    assert exc_info.value.phase == "assess_analysis"
    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    assert state["status"] == "waiting_for_input"
    assert state["phase"] == "assess_analysis"
    assert "error" not in state
