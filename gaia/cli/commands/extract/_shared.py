"""Shared plumbing for ``gaia extract`` — paths, task states, validation.

The extraction endpoints hang off the same LKM index base URL as
``gaia search lkm``, so index resolution, the exit-code contract, and JSON
output all come from :mod:`gaia.cli._lkm_runtime`. What lives here is specific
to the asynchronous PDF pipeline: the task lifecycle and the local file checks
that keep an obviously unusable upload from travelling to the server.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import typer

TASK_PATH = "/parse/task"

# Upload ceiling enforced by the service; rejecting locally avoids sending
# tens of megabytes just to be refused.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024

# `partial` is terminal: the pipeline stopped early but kept the intermediate
# XML it did produce.
PENDING_STATUSES = frozenset({"queued", "running"})
TERMINAL_STATUSES = frozenset({"succeeded", "partial", "failed"})
KNOWN_STATUSES = PENDING_STATUSES | TERMINAL_STATUSES

_SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9._~-]+$")


def validate_task_id(task_id: str) -> str:
    """Reject a task id that would reshape the request path."""
    candidate = task_id.strip()
    if not candidate or candidate in {".", ".."} or not _SAFE_TASK_ID.match(candidate):
        typer.echo(f"Error: invalid task id {task_id!r}.", err=True)
        raise typer.Exit(4)
    return candidate


def validate_returned_task_id(task_id: str) -> str:
    """Reject a server-returned task id before it reaches a path or shell hint."""
    candidate = task_id.strip()
    if not candidate or candidate in {".", ".."} or not _SAFE_TASK_ID.match(candidate):
        typer.echo(f"Error: LKM returned an invalid task id {task_id!r}.", err=True)
        raise typer.Exit(2)
    return candidate


def validate_pdf(path: Path) -> None:
    """Reject anything the extraction service would refuse after the upload."""
    if not path.exists():
        typer.echo(f"Error: file not found: {path}", err=True)
        raise typer.Exit(4)
    if not path.is_file():
        typer.echo(f"Error: {path} is not a regular file.", err=True)
        raise typer.Exit(4)
    if path.suffix.lower() != ".pdf":
        typer.echo(f"Error: {path} must be a PDF file.", err=True)
        raise typer.Exit(4)

    size = path.stat().st_size
    if size == 0:
        typer.echo(f"Error: {path} is empty.", err=True)
        raise typer.Exit(4)
    if size > MAX_UPLOAD_BYTES:
        typer.echo(
            f"Error: {path} is {size} bytes; the upload limit is 64 MiB.",
            err=True,
        )
        raise typer.Exit(4)

    try:
        header = path.open("rb").read(5)
    except OSError as exc:
        typer.echo(f"Error: could not read {path}: {exc}", err=True)
        raise typer.Exit(4) from exc
    if header != b"%PDF-":
        typer.echo(f"Error: {path} does not contain a valid PDF header.", err=True)
        raise typer.Exit(4)


def task_field(payload: dict[str, Any], key: str) -> str | None:
    """Read one string field from the LKM envelope's ``data`` object."""
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    value = data.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "KNOWN_STATUSES",
    "MAX_UPLOAD_BYTES",
    "PENDING_STATUSES",
    "TASK_PATH",
    "TERMINAL_STATUSES",
    "task_field",
    "validate_pdf",
    "validate_returned_task_id",
    "validate_task_id",
]
