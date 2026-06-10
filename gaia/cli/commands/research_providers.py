"""Analysis provider helpers for the package-native research CLI."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from time import perf_counter, sleep

import typer

from gaia.cli.commands.research_runtime import (
    _emit_run_event,
    _read_json_object_path,
    _record_run_trace,
    _update_run_state,
)
from gaia.engine.research import ResearchPackage
from gaia.engine.research.run import ResearchRunStart


def _load_research_env_files_or_exit(env_file: list[str] | None) -> None:
    refs = _research_env_file_refs(env_file)
    for ref in refs:
        path = Path(ref).expanduser()
        if not path.exists():
            typer.echo(f"Error: --env-file not found: {ref}", err=True)
            raise typer.Exit(2)
        if not path.is_file():
            typer.echo(f"Error: --env-file is not a file: {ref}", err=True)
            raise typer.Exit(2)
        try:
            assignments = _parse_research_env_file(path)
        except ValueError as exc:
            typer.echo(f"Error: invalid --env-file {ref}: {exc}", err=True)
            raise typer.Exit(2) from exc
        for key, value in assignments.items():
            os.environ.setdefault(key, value)


def _research_env_file_refs(env_file: list[str] | None) -> list[str]:
    refs = [ref for ref in (env_file or []) if ref.strip()]
    if refs:
        return refs
    configured = os.environ.get("GAIA_RESEARCH_ENV_FILE")
    if configured:
        return [ref for ref in configured.split(os.pathsep) if ref.strip()]
    return []


def _parse_research_env_file(path: Path) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            raise ValueError(f"line {line_number} must be KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"line {line_number} has invalid key {key!r}")
        assignments[key] = _parse_env_value(value.strip())
    return assignments


def _parse_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    comment_index = value.find(" #")
    if comment_index != -1:
        value = value[:comment_index].rstrip()
    return value


def _run_analysis_provider_command(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    phase: str,
    command: str,
    input_payload: dict[str, object],
    output_name: str,
    json_stream: bool,
) -> str:
    analysis_dir = run.run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    input_path = analysis_dir / f"{output_name}.input.json"
    output_path = analysis_dir / f"{output_name}.output.json"
    input_path.write_text(
        json.dumps(input_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _emit_run_event(
        run,
        event_type="provider.started",
        phase=phase,
        json_stream=json_stream,
        payload={"provider": "command", "input": str(input_path), "output": str(output_path)},
    )
    args = shlex.split(command)
    if not args:
        typer.echo(f"Error: empty provider command for {phase}.", err=True)
        raise typer.Exit(2)
    env = {
        **os.environ,
        "GAIA_RESEARCH_PHASE": phase,
        "GAIA_RESEARCH_INPUT": str(input_path),
        "GAIA_RESEARCH_OUTPUT": str(output_path),
        "GAIA_RESEARCH_RUN_DIR": str(run.run_dir),
    }
    start = perf_counter()
    completed = subprocess.run(
        args,
        cwd=research_pkg.path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout or "").strip()
        _update_run_state(
            run,
            {
                "status": "failed",
                "phase": phase,
                "error": error or f"provider command exited {completed.returncode}",
            },
        )
        _emit_run_event(
            run,
            event_type="run.failed",
            phase=phase,
            json_stream=json_stream,
            payload={"provider": "command", "returncode": completed.returncode, "error": error},
        )
        typer.echo(
            f"Error: provider command failed for {phase} with exit code "
            f"{completed.returncode}: {error}",
            err=True,
        )
        raise typer.Exit(2)
    if not output_path.exists():
        typer.echo(
            f"Error: provider command for {phase} did not write {output_path}.",
            err=True,
        )
        raise typer.Exit(2)
    _read_json_object_path(output_path)
    _record_run_trace(
        research_pkg,
        run,
        start=start,
        name=f"provider.command.{phase}",
        kind="llm",
        mode="command",
        inputs=[str(input_path)],
        outputs=[str(output_path)],
        metrics={
            "provider": "command",
            "phase": phase,
            "returncode": completed.returncode,
            "stdout_chars": len(completed.stdout or ""),
            "stderr_chars": len(completed.stderr or ""),
        },
    )
    _emit_run_event(
        run,
        event_type="provider.completed",
        phase=phase,
        json_stream=json_stream,
        payload={"provider": "command", "input": str(input_path), "output": str(output_path)},
    )
    return str(output_path)


def _run_analysis_provider_litellm(
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
    rate_limit_retry_count = 2
    rate_limit_retry_delay_seconds = 75.0
    analysis_dir = run.run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    input_path = analysis_dir / f"{output_name}.input.json"
    output_path = analysis_dir / f"{output_name}.output.json"
    raw_path = analysis_dir / f"{output_name}.raw.txt"
    hydrated_payload = _hydrate_analysis_provider_input(input_payload)
    input_path.write_text(
        json.dumps(hydrated_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _emit_run_event(
        run,
        event_type="provider.started",
        phase=phase,
        json_stream=json_stream,
        payload={
            "provider": "litellm",
            "model": model,
            "input": str(input_path),
            "output": str(output_path),
        },
    )
    start = perf_counter()
    response: object | None = None
    retry_count = 0
    retry_wait_seconds = 0.0
    try:
        while True:
            try:
                response = asyncio.run(
                    _litellm_completion(
                        model=model,
                        phase=phase,
                        input_payload=hydrated_payload,
                        temperature=temperature,
                        timeout=timeout,
                        max_retries=max_retries,
                        max_tokens=max_tokens,
                    )
                )
                break
            except Exception as exc:
                if not _is_litellm_rate_limit_error(exc) or retry_count >= rate_limit_retry_count:
                    raise
                retry_count += 1
                retry_wait_seconds += rate_limit_retry_delay_seconds
                _emit_run_event(
                    run,
                    event_type="provider.retrying",
                    phase=phase,
                    json_stream=json_stream,
                    payload={
                        "provider": "litellm",
                        "model": model,
                        "reason": "rate_limit",
                        "attempt": retry_count,
                        "max_attempts": rate_limit_retry_count + 1,
                        "wait_seconds": rate_limit_retry_delay_seconds,
                        "error": str(exc),
                    },
                )
                sleep(rate_limit_retry_delay_seconds)
        content = _litellm_response_content(response)
        raw_path.write_text(content, encoding="utf-8")
        output_payload = _json_object_from_llm_content(content)
    except Exception as exc:
        usage = _litellm_usage_dict(response)
        prompt_tokens = _int_metric(usage.get("prompt_tokens"))
        completion_tokens = _int_metric(usage.get("completion_tokens"))
        _record_run_trace(
            research_pkg,
            run,
            start=start,
            name=f"provider.litellm.{phase}",
            kind="llm",
            mode="litellm",
            inputs=[str(input_path)],
            outputs=[str(raw_path)] if raw_path.exists() else [],
            metrics={
                "provider": "litellm",
                "phase": phase,
                "model": model,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "raw_path": str(raw_path) if raw_path.exists() else None,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": _int_metric(usage.get("total_tokens")),
                "request_id": _litellm_request_id(response),
                "retry_count": retry_count,
                "retry_wait_seconds": retry_wait_seconds,
            },
            model=model,
            token_usage={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            },
            status="failed",
        )
        _update_run_state(run, {"status": "failed", "phase": phase, "error": str(exc)})
        _emit_run_event(
            run,
            event_type="run.failed",
            phase=phase,
            json_stream=json_stream,
            payload={"provider": "litellm", "model": model, "error": str(exc)},
        )
        typer.echo(f"Error: LiteLLM provider failed for {phase}: {exc}", err=True)
        raise typer.Exit(2) from exc
    output_path.write_text(
        json.dumps(output_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    usage = _litellm_usage_dict(response)
    prompt_tokens = _int_metric(usage.get("prompt_tokens"))
    completion_tokens = _int_metric(usage.get("completion_tokens"))
    _record_run_trace(
        research_pkg,
        run,
        start=start,
        name=f"provider.litellm.{phase}",
        kind="llm",
        mode="litellm",
        inputs=[str(input_path)],
        outputs=[str(output_path)],
        metrics={
            "provider": "litellm",
            "phase": phase,
            "model": model,
            "raw_path": str(raw_path),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": _int_metric(usage.get("total_tokens")),
            "request_id": _litellm_request_id(response),
            "retry_count": retry_count,
            "retry_wait_seconds": retry_wait_seconds,
        },
        model=model,
        token_usage={
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
        },
    )
    _emit_run_event(
        run,
        event_type="provider.completed",
        phase=phase,
        json_stream=json_stream,
        payload={
            "provider": "litellm",
            "model": model,
            "input": str(input_path),
            "output": str(output_path),
        },
    )
    return str(output_path)


def _is_litellm_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "ratelimit" in text or "rate limit" in text or "tpm" in text


async def _litellm_completion(
    *,
    model: str,
    phase: str,
    input_payload: dict[str, object],
    temperature: float,
    timeout: float,
    max_retries: int,
    max_tokens: int | None,
) -> object:
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    litellm.suppress_debug_info = True
    litellm.disable_cost_calc = True
    kwargs: dict[str, object] = {
        "model": model,
        "messages": _litellm_messages(phase=phase, input_payload=input_payload),
        "temperature": temperature,
        "timeout": timeout,
        "max_retries": max_retries,
        "response_format": {"type": "json_object"},
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return await litellm.acompletion(**kwargs)


def _litellm_messages(
    *,
    phase: str,
    input_payload: dict[str, object],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Gaia's deterministic JSON compiler for research artifacts. "
                "Return exactly one valid JSON object. The first non-whitespace "
                "character must be `{` and the last must be `}`. Do not include "
                "markdown, prose, XML, citations outside JSON, or code fences. Use "
                "only source refs and ids present in the input artifact payloads."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "phase": phase,
                    "instruction": _litellm_phase_instruction(phase),
                    "output_shape": _litellm_output_shape(phase),
                    "validation_rules": [
                        "Return a single JSON object, not an array or string.",
                        "Do not add explanatory text before or after the JSON.",
                        "Do not add decorative or prose-only keys outside the requested shape.",
                        "Every source_refs entry must use ids present in artifact_payloads.",
                        "If evidence is weak, encode uncertainty inside JSON fields.",
                        "Prefer fewer high-quality grounded items over broad ungrounded output.",
                        (
                            "Keep strings compact; avoid LaTeX commands when Unicode "
                            "text is available."
                        ),
                    ],
                    "input": input_payload,
                },
                indent=2,
                ensure_ascii=False,
            ),
        },
    ]


def _litellm_phase_instruction(phase: str) -> str:
    if phase == "query_plan":
        return (
            "Generate 3-5 broad live-search queries for the topic. Cover distinct "
            "evidence families likely to support an autonomous review map: "
            "foundational theory, canonical models, methods/diagnostics, experiments "
            "where relevant, and recent controversies. Do not assess evidence yet."
        )
    if phase == "field_map_analysis":
        return (
            "Induce a review-oriented field map from the broad landscape before "
            "selecting narrow focuses. Build a taxonomy from primary retrieved "
            "evidence: model families, methods, observables, theory constraints, "
            "experimental systems, controversy axes, and coverage gaps. Recommend "
            "only the highest-value live-search expansions needed for review coverage."
        )
    if phase == "focus_analysis":
        return (
            "Select 1-4 assessable research focuses from the landscapes and field map. "
            "Each focus must be grounded in retrieved item ids, should fit into a "
            "field-map bucket or controversy axis, and should be narrow enough for "
            "immediate assessment."
        )
    if phase == "assess_analysis":
        return (
            "Assess only the selected focus against the selected evidence packet. "
            "Produce at most 5 grounded candidate relations, limitations, and next "
            "queries. Do not write the final review prose; later report phases will "
            "write the article from this judgment. Emit at most 2 deferred "
            "candidate obligations that directly follow from missing or conflicting "
            "evidence. Set obligation.actionable=true only for a near-term blocking "
            "task that should become an open inquiry obligation."
        )
    if phase == "report_plan":
        return (
            "Plan a scholarly evidence-review article from the field map, focus, "
            "selected evidence, and assessment judgment. Produce a concise section "
            "outline. Each section must have a stable id, title, purpose, and grounded "
            "evidence refs. Do not reassess evidence; preserve the assessment judgment."
        )
    if phase == "report_section":
        return (
            "Write exactly one article section from the section plan, selected evidence, "
            "section_evidence context, and assessment judgment. Use only refs and evidence "
            "records present in section_evidence. If section_evidence.missing_refs is not "
            "empty, explicitly describe that coverage gap instead of inventing details. Do "
            "not change the assessment conclusion. Return section markdown, not a full article."
        )
    if phase == "report_stitch":
        return (
            "Stitch section drafts into one academic evidence-review report. Add title, "
            "abstract, transitions, and conclusion. Remove repetition, keep citations as "
            "inline source refs, and do not add workflow or benchmark commentary."
        )
    return "Produce the contract-shaped JSON for this research phase."


def _litellm_output_shape(phase: str) -> dict[str, object]:
    if phase == "query_plan":
        return {
            "required_top_level_keys": ["queries"],
            "queries_item_shape": {"query": "search query text", "rationale": "why it helps"},
        }
    if phase == "field_map_analysis":
        return {
            "required_top_level_keys": [
                "domain_thesis",
                "buckets",
                "controversy_axes",
                "coverage_gaps",
                "recommended_expansions",
                "synthesis_notes",
            ],
            "buckets_item_keys": [
                "id",
                "title",
                "role",
                "required_for_review",
                "coverage_status",
                "evidence_refs",
                "recommended_queries",
            ],
            "coverage_gaps_item_keys": ["kind", "description", "recommended_queries"],
        }
    if phase == "focus_analysis":
        return {
            "required_top_level_keys": ["focuses", "coverage_gaps", "notes"],
            "focuses_item_keys": [
                "id",
                "kind",
                "status",
                "question",
                "rationale",
                "priority",
                "readiness",
                "scope",
                "coverage",
                "evidence_refs",
                "suggested_queries",
            ],
        }
    if phase == "assess_analysis":
        return {
            "required_top_level_keys": ["relations", "candidate_obligations"],
            "relations_item_keys": [
                "type",
                "claim",
                "rationale",
                "epistemic_status",
                "promotion_hint",
                "source_refs",
            ],
            "optional_judgment_keys": ["limitations", "next_queries"],
            "candidate_obligations_item_keys": [
                "kind",
                "content",
                "source_refs",
                "actionable",
            ],
        }
    if phase == "report_plan":
        return {
            "required_top_level_keys": [
                "title",
                "abstract",
                "thesis",
                "sections",
                "conclusion_prompt",
            ],
            "sections_item_keys": ["id", "title", "purpose", "evidence_refs"],
        }
    if phase == "report_section":
        return {
            "required_top_level_keys": ["section_id", "title", "markdown", "used_refs"],
            "markdown": "Markdown for exactly one report section. Start with a level-2 heading.",
        }
    if phase == "report_stitch":
        return {
            "required_top_level_keys": ["markdown"],
            "markdown": (
                "Complete final report Markdown with title, abstract, body, and conclusion."
            ),
        }
    return {"required_top_level_keys": []}


def _hydrate_analysis_provider_input(payload: dict[str, object]) -> dict[str, object]:
    hydrated = dict(payload)
    artifact_payloads: list[dict[str, object]] = []
    artifacts = payload.get("artifacts")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, str):
                continue
            path = Path(artifact)
            if path.exists():
                artifact_payloads.append(
                    {
                        "path": artifact,
                        "json": _read_json_object_path(path),
                    }
                )
    hydrated["artifact_payloads"] = artifact_payloads
    return hydrated


def _json_object_from_llm_content(content: str) -> dict[str, object]:
    text = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        repaired_text = _escape_invalid_json_backslashes(text)
        try:
            payload = json.loads(repaired_text)
        except json.JSONDecodeError:
            raise ValueError(f"LiteLLM response was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("LiteLLM response must be a JSON object.")
    return payload


def _escape_invalid_json_backslashes(text: str) -> str:
    """Preserve LaTeX-style backslashes inside otherwise valid JSON strings."""
    return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)


def _litellm_response_content(response: object) -> str:
    if isinstance(response, dict):
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    return "" if content is None else str(content)
    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        return "" if content is None else str(content)
    return ""


def _litellm_usage_dict(response: object) -> dict[str, object]:
    usage = (
        response.get("usage") if isinstance(response, dict) else getattr(response, "usage", None)
    )
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    try:
        return dict(usage)
    except Exception:
        return {}


def _litellm_request_id(response: object) -> str | None:
    if isinstance(response, dict):
        value = response.get("id") or response.get("request_id")
        return str(value) if value else None
    for attr in ("id", "request_id"):
        value = getattr(response, attr, None)
        if value:
            return str(value)
    return None


def _int_metric(value: object) -> int:
    return int(value) if isinstance(value, int | float) else 0


def _resolve_litellm_model(model: str | None) -> str:
    resolved = model or os.environ.get("GAIA_RESEARCH_LLM_MODEL")
    if resolved and resolved.strip():
        return resolved.strip()
    typer.echo(
        "Error: --analysis-provider litellm requires --model or GAIA_RESEARCH_LLM_MODEL.",
        err=True,
    )
    raise typer.Exit(2)
