"""Gaia CLI hints for raw LKM extraction responses."""

from __future__ import annotations

from typing import Any

from gaia.cli.commands.extract._shared import task_field


def submit_hint(payload: dict[str, Any], *, index_id: str) -> str | None:
    """Return a stderr-only hint after an extraction task is accepted."""
    task_id = task_field(payload, "task_id")
    if task_id is None:
        return None
    status = task_field(payload, "status")
    if status in {"succeeded", "partial"}:
        return _hint_block(
            "Suggested: the extraction is already done for this PDF or --content body",
            f"gaia extract result {task_id} --index {index_id}",
            _cache_detail(payload),
        )
    if status == "failed":
        return _hint_block(
            "Suggested: read why the extraction failed",
            f"gaia extract status {task_id} --index {index_id}",
        )
    return _hint_block(
        "Suggested: poll the task until it reaches a terminal state",
        f"gaia extract status {task_id} --index {index_id}",
        "Extraction commonly takes several minutes to a quarter of an hour.",
    )


def status_hint(payload: dict[str, Any], *, index_id: str, task_id: str) -> str | None:
    """Return a stderr-only hint for an extraction status response."""
    status = task_field(payload, "status")
    if status in {"succeeded", "partial"}:
        detail = None
        if status == "partial":
            detail = "partial is a non-retryable business failure; do not resubmit the same PDF or --content body."
        return _hint_block(
            "Suggested: fetch what the task produced",
            f"gaia extract result {task_id} --index {index_id}",
            detail,
        )
    if status in {"queued", "running"}:
        return _hint_block(
            "Suggested: keep polling this task",
            f"gaia extract status {task_id} --index {index_id}",
            "Extraction commonly takes several minutes to a quarter of an hour.",
        )
    return None


def _cache_detail(payload: dict[str, Any]) -> str:
    """Say where a reused extraction came from, when the response reports it."""
    source = task_field(payload, "cache_source")
    if source == "lkm":
        return "This paper was already extracted in the LKM corpus."
    if source == "local":
        return "An earlier submission of this same PDF or --content body produced it."
    return "Resubmitting this same PDF or --content body reuses the existing extraction instead of redoing it."


def _hint_block(title: str, command: str, detail: str | None = None) -> str:
    lines = [title]
    if detail is not None:
        lines.append(f"  {detail}")
    lines.append(f"  $ {command}")
    return "\n".join(lines)


__all__ = ["status_hint", "submit_hint"]
