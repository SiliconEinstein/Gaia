"""``gaia extract submit`` — POST /parse/task.

Upload a local PDF and queue it for LKM knowledge extraction. Acceptance is
not completion: the verb returns a task id, and ``--wait`` is the only mode
that blocks until the task reaches a terminal state.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, Any

import typer

from gaia.cli._lkm_runtime import (
    DEFAULT_LKM_INDEX_ID,
    emit,
    run_multipart_request,
    run_request,
    validate_lkm_index,
)
from gaia.cli.commands.extract._hints import status_hint, submit_hint
from gaia.cli.commands.extract._shared import (
    TASK_PATH,
    TERMINAL_STATUSES,
    task_field,
    validate_pdf,
)
from gaia.cli.commands.extract.docs import APIFOX_BASE_URL

_MIN_POLL_INTERVAL = 1.0
_MAX_POLL_INTERVAL = 300.0
_MAX_TIMEOUT = 86400.0

_SUBMIT_EPILOG = (
    "Use this when you hold a PDF that may not be in the LKM corpus yet. "
    "Resubmitting the same PDF reuses the existing extraction rather than "
    "starting over, so an already-processed PDF comes back terminal "
    "immediately with `cache_hit`. `cache_source` says where that reuse came "
    "from: `lkm` when the paper was already extracted in the corpus, `local` "
    "when an earlier submission of this same PDF produced it. Resubmitting "
    "will not hurry a running task along; it only mints extra task ids that "
    "share the same progress and result.\n\n"
    "Without --wait the task id is all you get; poll it with "
    "`gaia extract status`.\n\n"
    f"API docs: {APIFOX_BASE_URL}"
)


def submit_command(
    pdf: Annotated[
        Path,
        typer.Argument(help="Local PDF to extract (max 64 MiB)."),
    ],
    index: Annotated[
        str,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = DEFAULT_LKM_INDEX_ID,
    wait: Annotated[
        bool,
        typer.Option("--wait", help="Poll until the task reaches a terminal state."),
    ] = False,
    poll_interval: Annotated[
        float,
        typer.Option(
            "--poll-interval",
            help="Seconds between polls when --wait is set; the 5s default matches the service.",
        ),
    ] = 5.0,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Seconds to wait before giving up when --wait is set."),
    ] = 1800.0,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write JSON to PATH (atomic) instead of stdout."),
    ] = None,
    no_hint: Annotated[
        bool,
        typer.Option("--no-hint", help="Suppress Gaia follow-up suggestions on stderr."),
    ] = False,
) -> None:
    """Submit a local PDF for LKM knowledge extraction (POST /parse/task)."""
    index_id = validate_lkm_index(index)
    validate_pdf(pdf)
    if wait:
        _validate_polling(poll_interval, timeout)

    with pdf.open("rb") as handle:
        payload = run_multipart_request(
            "POST",
            TASK_PATH,
            files={"file": (pdf.name, handle, "application/pdf")},
            index_id=index_id,
        )

    task_id = task_field(payload, "task_id")
    if task_id is None:
        typer.echo("Error: LKM accepted the upload but returned no task_id.", err=True)
        raise typer.Exit(2)

    if not wait:
        emit(
            payload,
            out,
            hint=submit_hint(payload, index_id=index_id),
            show_hint=not no_hint,
        )
        return

    final = _poll_until_terminal(
        task_id,
        index_id=index_id,
        poll_interval=poll_interval,
        timeout=timeout,
    )
    emit(
        final,
        out,
        hint=status_hint(final, index_id=index_id, task_id=task_id),
        show_hint=not no_hint,
    )
    if task_field(final, "status") == "failed":
        reason = task_field(final, "failed_reason") or "no reason reported"
        typer.echo(f"Error: extraction task {task_id} failed: {reason}", err=True)
        raise typer.Exit(1)


def _validate_polling(poll_interval: float, timeout: float) -> None:
    if not _MIN_POLL_INTERVAL <= poll_interval <= _MAX_POLL_INTERVAL:
        typer.echo(
            f"Error: --poll-interval must be between {_MIN_POLL_INTERVAL:g} and "
            f"{_MAX_POLL_INTERVAL:g} seconds; got {poll_interval:g}.",
            err=True,
        )
        raise typer.Exit(4)
    if not 0 < timeout <= _MAX_TIMEOUT:
        typer.echo(
            f"Error: --timeout must be between 0 and {_MAX_TIMEOUT:g} seconds; got {timeout:g}.",
            err=True,
        )
        raise typer.Exit(4)


def _poll_until_terminal(
    task_id: str,
    *,
    index_id: str,
    poll_interval: float,
    timeout: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        payload = run_request("GET", f"{TASK_PATH}/{task_id}", index_id=index_id)
        status = task_field(payload, "status")
        if status in TERMINAL_STATUSES:
            return payload
        if time.monotonic() + poll_interval >= deadline:
            # Giving up on the wait does not cancel the remote task, and the
            # task id stays valid — say so rather than implying data loss.
            typer.echo(
                f"Error: stopped waiting for extraction task {task_id} after "
                f"{timeout:g}s; the task is still {status or 'in progress'} and "
                f"can be polled with `gaia extract status {task_id}`.",
                err=True,
            )
            raise typer.Exit(2)
        time.sleep(poll_interval)
