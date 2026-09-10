"""Shared plumbing for ``gaia extract`` — paths, task states, validation.

The extraction endpoints hang off the same LKM index base URL as
``gaia search lkm``, so index resolution, the exit-code contract, and JSON
output all come from :mod:`gaia.cli._lkm_runtime`. What lives here is specific
to the asynchronous parse pipeline: the task lifecycle and the local checks
that keep an obviously unusable PDF or ``--content`` body from travelling to
the server.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import typer

_CONTENT_EXTS = {".md", ".txt", ".markdown"}

TASK_PATH = "/parse/task"

# Upload ceiling enforced by the service; rejecting locally avoids sending
# tens of megabytes just to be refused.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024

# `partial` is a non-retryable business terminal (review / too short /
# collection). Resubmitting the same PDF stays partial and does not rerun.
PENDING_STATUSES = frozenset({"queued", "running"})
TERMINAL_STATUSES = frozenset({"succeeded", "partial", "failed"})
KNOWN_STATUSES = PENDING_STATUSES | TERMINAL_STATUSES

RESULT_FORMATS = ("local", "graph")

_SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9._~-]+$")


def validate_result_format(result_format: str) -> str:
    """Reject a result shape the service would refuse after a round trip."""
    candidate = result_format.strip().lower()
    if candidate not in RESULT_FORMATS:
        typer.echo(
            f"Error: invalid --format {result_format!r}; expected local or graph.",
            err=True,
        )
        raise typer.Exit(4)
    return candidate


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


def resolve_submit_content(raw: str | None) -> str:
    """Resolve ``--content`` the same way ``bohr lkm parse submit`` does.

    A path or ``@file`` is read locally and posted as the API ``content``
    text field, not as a second file part. Anything that does not look like a
    path is sent as literal markdown.
    """
    if raw is None:
        return ""
    text = raw.strip()
    if not text:
        return ""
    if text.startswith("@"):
        path = text[1:].strip()
        if not path:
            typer.echo("Error: --content @file is missing a path.", err=True)
            raise typer.Exit(4)
        return _read_content_file(Path(path))
    if _looks_like_content_path(text):
        return _read_content_file(Path(text))
    candidate = Path(text)
    try:
        if candidate.is_file():
            return _read_content_file(candidate)
    except OSError:
        pass
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_UPLOAD_BYTES:
        typer.echo(
            f"Error: content is {len(encoded)} bytes; the upload limit is 64 MiB.",
            err=True,
        )
        raise typer.Exit(4)
    return text


def _looks_like_content_path(raw: str) -> bool:
    if "/" in raw or "\\" in raw:
        return True
    return Path(raw).suffix.lower() in _CONTENT_EXTS


def _read_content_file(path: Path) -> str:
    if not path.exists():
        typer.echo(f"Error: cannot open content file: {path}", err=True)
        raise typer.Exit(4)
    if not path.is_file():
        typer.echo(f"Error: {path} is not a regular file.", err=True)
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
        raw = path.read_bytes()
    except OSError as exc:
        typer.echo(f"Error: cannot read content file: {exc}", err=True)
        raise typer.Exit(4) from exc
    if len(raw) > MAX_UPLOAD_BYTES:
        typer.echo(
            f"Error: {path} is {len(raw)} bytes; the upload limit is 64 MiB.",
            err=True,
        )
        raise typer.Exit(4)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        typer.echo(f"Error: {path} is not valid UTF-8.", err=True)
        raise typer.Exit(4) from exc
    if not text.strip():
        typer.echo(f"Error: {path} is empty.", err=True)
        raise typer.Exit(4)
    return text


def normalize_submit_md5(raw: str | None) -> str:
    """Accept a 32-char hex PDF digest, or empty when the flag was omitted."""
    if raw is None:
        return ""
    digest = raw.strip().lower()
    if not digest:
        return ""
    try:
        decoded = bytes.fromhex(digest)
    except ValueError:
        decoded = b""
    if len(decoded) != 16:
        typer.echo("Error: md5 must be a 32-char hex digest.", err=True)
        raise typer.Exit(4)
    return digest


def normalize_submit_page(page: int | None) -> str | None:
    """Return the ``page`` form field only when the caller set ``--page``."""
    if page is None:
        return None
    if page < 0:
        typer.echo("Error: --page must be >= 0.", err=True)
        raise typer.Exit(4)
    return str(page)


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
    "normalize_submit_md5",
    "normalize_submit_page",
    "resolve_submit_content",
    "validate_pdf",
    "validate_returned_task_id",
    "validate_task_id",
]
