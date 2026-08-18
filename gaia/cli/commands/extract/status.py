"""``gaia extract status`` — GET /parse/task/{task_id}.

One status read, no polling. ``queued`` and ``running`` mean call again;
``succeeded``, ``partial``, and ``failed`` are terminal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from gaia.cli._lkm_runtime import (
    DEFAULT_LKM_INDEX_ID,
    emit,
    run_request,
    validate_lkm_index,
)
from gaia.cli.commands.extract._hints import status_hint
from gaia.cli.commands.extract._shared import TASK_PATH, validate_task_id
from gaia.cli.commands.extract.docs import APIFOX_BASE_URL

_STATUS_EPILOG = (
    "`status` reads the task once and exits; it does not block. Use "
    "`gaia extract submit --wait` when you want the CLI to poll for you.\n\n"
    "`stage` is progress narration (metadata, ocr, step0-step4, graph, done); "
    "branch on `status`, not on `stage`.\n\n"
    "`step_durations` lists the pipeline steps that have finished so far, in "
    "order, with their `duration_ms` — measured progress for a task that has "
    "been running a while.\n\n"
    f"API docs: {APIFOX_BASE_URL}"
)


def status_command(
    task_id: Annotated[
        str,
        typer.Argument(help="Extraction task id returned by `gaia extract submit`."),
    ],
    index: Annotated[
        str,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = DEFAULT_LKM_INDEX_ID,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write JSON to PATH (atomic) instead of stdout."),
    ] = None,
    no_hint: Annotated[
        bool,
        typer.Option("--no-hint", help="Suppress Gaia follow-up suggestions on stderr."),
    ] = False,
) -> None:
    """Check one LKM extraction task (GET /parse/task/{task_id})."""
    index_id = validate_lkm_index(index)
    task = validate_task_id(task_id)
    payload = run_request("GET", f"{TASK_PATH}/{task}", index_id=index_id)
    emit(
        payload,
        out,
        hint=status_hint(payload, index_id=index_id, task_id=task),
        show_hint=not no_hint,
    )
