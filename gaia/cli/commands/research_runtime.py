"""Runtime helpers for the package-native research CLI."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

import typer

from gaia.engine.research import ResearchPackage
from gaia.engine.research.benchmark import append_research_trace_step
from gaia.engine.research.run import ResearchRunStart, append_run_event, write_run_state


def _read_json_object_path(path: Path) -> dict[str, object]:
    if not path.exists():
        typer.echo(f"Error: file not found: {path}", err=True)
        raise typer.Exit(2)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"Error: file is not valid JSON: {path}: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not isinstance(payload, dict):
        typer.echo(f"Error: file must contain a JSON object: {path}", err=True)
        raise typer.Exit(2)
    return payload


def _run_state(run: ResearchRunStart) -> dict[str, Any]:
    return _read_json_object_path(run.state_path)


def _update_run_state(run: ResearchRunStart, updates: dict[str, Any]) -> dict[str, Any]:
    state = _run_state(run)
    state.update(updates)
    write_run_state(run.state_path, state)
    return state


def _emit_run_event(
    run: ResearchRunStart,
    *,
    event_type: str,
    phase: str,
    json_stream: bool,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = append_run_event(
        run.events_path,
        run_id=run.run_id,
        event_type=event_type,
        phase=phase,
        payload=payload,
    )
    if json_stream:
        typer.echo(json.dumps(event, ensure_ascii=False))
    return event


def _record_run_cli_trace(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    start: float,
    name: str,
    mode: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    metrics: dict[str, object] | None = None,
    model: str | None = None,
    token_usage: dict[str, int] | None = None,
    status: str = "ok",
) -> None:
    append_research_trace_step(
        research_pkg,
        run.run_dir / "trace",
        name=name,
        kind="cli",
        mode=mode,
        wall_seconds=perf_counter() - start,
        inputs=inputs,
        outputs=outputs,
        metrics=metrics,
        model=model,
        token_usage=token_usage,
        status=status,
    )


def _record_run_trace(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    start: float,
    name: str,
    kind: str,
    mode: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    metrics: dict[str, object] | None = None,
    model: str | None = None,
    token_usage: dict[str, int] | None = None,
    status: str = "ok",
) -> None:
    append_research_trace_step(
        research_pkg,
        run.run_dir / "trace",
        name=name,
        kind=kind,
        mode=mode,
        wall_seconds=perf_counter() - start,
        inputs=inputs,
        outputs=outputs,
        metrics=metrics,
        model=model,
        token_usage=token_usage,
        status=status,
    )
