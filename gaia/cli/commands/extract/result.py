"""``gaia extract result`` — GET /parse/task/{task_id}/result.

A succeeded task returns a flat variables / factors / motivations graph. A
partial or failed task returns its stage, failure reason, and expiring links
to whatever intermediate XML exists.
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
from gaia.cli.commands.extract._shared import TASK_PATH, validate_task_id
from gaia.cli.commands.extract.docs import APIFOX_BASE_URL

_RESULT_EPILOG = (
    "The success payload is `variables` / `factors` / `motivations` / `stats` "
    "directly under `data` — not the `papers[]` wrapper `gaia search lkm "
    "package` returns, and not a nodes/edges graph. Every result also carries "
    "`step_durations`: how long each finished pipeline step took, in order.\n\n"
    "Node `local_id` values such as `paper:6::P1` are file-local. Only a "
    "non-null `global_id` is an LKM id you can pass to `gaia search lkm "
    "nodes` or `gaia pkg add`.\n\n"
    "Asking for the result of a queued or running task is a business error "
    "(code 290017, exit 1); that does not mean the task was lost. Reviews and "
    "abstract collections often stop early, so an empty `files` list on a "
    "partial task is expected.\n\n"
    f"API docs: {APIFOX_BASE_URL}"
)


def result_command(
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
) -> None:
    """Fetch what an LKM extraction task produced (GET /parse/task/{id}/result)."""
    index_id = validate_lkm_index(index)
    task = validate_task_id(task_id)
    payload = run_request("GET", f"{TASK_PATH}/{task}/result", index_id=index_id)
    emit(payload, out)
