"""Engine-level ports for fixed research workflow orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from gaia.engine.research.artifacts import ResearchPackage
from gaia.engine.research.run import ResearchRunStart
from gaia.engine.research.sync import ResearchSyncResult


class ResearchOrchestratorError(RuntimeError):
    """Raised when fixed research workflow orchestration cannot continue."""

    def __init__(self, message: str = "", *, exit_code: int = 2) -> None:
        """Initialize the error with a CLI-compatible exit code."""
        super().__init__(message)
        self.exit_code = exit_code


class ResearchOrchestratorRuntime(Protocol):
    """Runtime services required by the fixed research workflow."""

    def update_run_state(self, run: ResearchRunStart, payload: dict[str, object]) -> None:
        """Update persisted run state."""

    def read_search_json(self, ref: str) -> tuple[dict[str, object], str]:
        """Read one normalized search JSON reference and return payload plus label."""

    def read_json_object_ref(self, ref: str, *, label: str) -> dict[str, object]:
        """Read one JSON object from a workflow reference."""

    def write_json_file(self, path: Path, payload: dict[str, Any]) -> None:
        """Write one JSON file."""

    def write_text_file(self, path: Path, text: str) -> None:
        """Write one text file."""

    def write_artifact(
        self,
        research_pkg: ResearchPackage,
        category: str,
        stem: str,
        payload: dict[str, Any],
    ) -> Path:
        """Write one package-local research artifact."""

    def append_research_event(
        self,
        research_pkg: ResearchPackage,
        event: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Append a package-local research event."""

    def emit_run_event(
        self,
        run: ResearchRunStart,
        *,
        event_type: str,
        phase: str,
        json_stream: bool,
        payload: dict[str, object],
    ) -> None:
        """Emit a UI-observable run event."""

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
        """Record a generic trace step."""

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
        """Record a CLI workflow trace step."""

    def sync_landscape_artifact(
        self,
        research_pkg: ResearchPackage,
        landscape: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        """Sync one landscape artifact into package state."""

    def sync_focus_artifact(
        self,
        research_pkg: ResearchPackage,
        focus_artifact: dict[str, Any],
        *,
        max_questions: int,
        dry_run: bool,
    ) -> ResearchSyncResult:
        """Sync one focus artifact into package state."""

    def sync_assessment_artifact(
        self,
        research_pkg: ResearchPackage,
        assessment: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        """Sync one assessment artifact into package state."""

    def write_benchmark_summary(
        self,
        research_pkg: ResearchPackage,
        trace_dir: Path,
    ) -> Path:
        """Write a benchmark summary from the run trace."""

    def resolve_litellm_model(self, model: str | None) -> str:
        """Resolve the effective LiteLLM model for provider calls."""

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
        """Optionally run sectioned final report writing."""

    def search_lkm(
        self,
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        """Run one LKM search and return normalized search results."""

    def run_command_provider(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        phase: str,
        command: str,
        input_payload: dict[str, object],
        output_name: str,
        json_stream: bool,
    ) -> str:
        """Run command-backed analysis provider."""

    def run_litellm_provider(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        phase: str,
        model: str,
        input_payload: dict[str, object],
        output_name: str,
        temperature: float,
        timeout: float,
        max_retries: int,
        max_tokens: int | None,
        json_stream: bool,
    ) -> str:
        """Run LiteLLM-backed analysis provider."""

    def materialize_landscape_sources(
        self,
        research_pkg: ResearchPackage,
        landscape: dict[str, Any],
        *,
        landscape_artifact: Path,
        dry_run: bool,
    ) -> dict[str, object]:
        """Materialize shallow source packages for a landscape artifact."""

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
        """Materialize selected LKM paper graphs or reasoning chains."""


__all__ = ["ResearchOrchestratorError", "ResearchOrchestratorRuntime"]
