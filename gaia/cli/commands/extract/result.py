"""``gaia extract result`` — GET /parse/task/{task_id}/result.

A succeeded task returns either the default flat graph or, with
``--format graph``, ``graph.nodes`` / ``graph.edges`` (same field kinds as
``gaia search lkm package``, not that command's envelope). A partial task
is a non-retryable business terminal; failed is a technical failure that
may be resubmitted.
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
from gaia.cli.commands.extract._shared import (
    TASK_PATH,
    validate_result_format,
    validate_task_id,
)
from gaia.cli.commands.extract.docs import APIFOX_RESULT_URL

_RESULT_EPILOG = (
    "Examples:\n\n"
    "  gaia extract result <task_id>\n\n"
    "  gaia extract result <task_id> --format graph\n\n"
    "What you have:\n\n"
    "  a succeeded task, flat graph   ->  --format local (default)\n\n"
    "  a succeeded task, nodes/edges  ->  --format graph\n\n"
    "  still queued or running        ->  status, not result\n\n"
    "  a non-null global_id           ->  gaia search lkm nodes / pkg add\n\n"
    "Default `--format local` is `variables` / `factors` / `motivations` / "
    "`stats` under `data`. `--format graph` returns `addressed_problems`, "
    "`open_questions`, and `graph.nodes` / `graph.edges` under `data` — the "
    "same field kinds as `gaia search lkm package`, not that command's "
    "envelope. Format only applies to succeeded results; an unknown value "
    "exits 4 before any request.\n\n"
    "Node `local_id` values and graph node `id`s are file-local. Only a "
    "non-null `global_id` is an LKM id you can pass to `gaia search lkm "
    "nodes` or `gaia pkg add`.\n\n"
    "Extract costs 1.00 CNY per successful paper, or 0.10 CNY on a cache hit. "
    "If billing fails, retry the same task_id and do not resubmit the PDF.\n\n"
    "Queued or running: 290017, exit 1 — the task is not lost. `partial` is "
    "a non-retryable business failure; do not resubmit the same PDF. Empty "
    "`files` on partial is expected.\n\n"
    f"API docs: {APIFOX_RESULT_URL}\n\n"
    "Endpoint links: gaia extract docs"
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
    result_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Succeeded result shape: local (flat graph) or graph (nodes/edges, not the package envelope).",
        ),
    ] = "local",
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write JSON to PATH (atomic) instead of stdout."),
    ] = None,
) -> None:
    """Fetch what an LKM extraction task produced.

    GET /parse/task/{task_id}/result.
    """
    index_id = validate_lkm_index(index)
    task = validate_task_id(task_id)
    shape = validate_result_format(result_format)
    params = {"format": shape} if shape != "local" else None
    payload = run_request(
        "GET",
        f"{TASK_PATH}/{task}/result",
        params=params,
        index_id=index_id,
    )
    emit(payload, out)
