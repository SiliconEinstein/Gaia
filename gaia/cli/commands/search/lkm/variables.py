"""``gaia search lkm nodes`` — POST /variables/batch.

Batch-fetch LKM graph node detail by id. The upstream endpoint calls these
nodes ``variables``; the Gaia-facing CLI uses ``nodes`` to avoid confusion
with Gaia typed variables. Ids may be passed positionally and/or via a
newline-delimited ``--ids-file``; the two sources are merged, de-duplicated
(order-preserving), and capped at 100.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from gaia.cli.commands.search.lkm._shared import (
    DEFAULT_LKM_INDEX_ID,
    MAX_VARIABLE_IDS,
    emit,
    run_request,
    validate_lkm_index,
)


def nodes_command(
    ids: Annotated[
        list[str] | None,
        typer.Argument(help="LKM graph node ids to fetch (positional, variadic)."),
    ] = None,
    index: Annotated[
        str,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = DEFAULT_LKM_INDEX_ID,
    ids_file: Annotated[
        Path | None,
        typer.Option(
            "--ids-file",
            help="Newline-delimited file of additional ids (merged + deduped).",
        ),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write JSON to PATH (atomic) instead of stdout."),
    ] = None,
) -> None:
    """Batch-fetch LKM graph node detail (POST /variables/batch)."""
    index_id = validate_lkm_index(index)
    merged: list[str] = list(ids or [])

    if ids_file is not None:
        if not ids_file.exists():
            typer.echo(f"Error: --ids-file not found: {ids_file}", err=True)
            raise typer.Exit(4)
        try:
            file_text = ids_file.read_text(encoding="utf-8")
        except OSError as exc:
            typer.echo(f"Error: could not read --ids-file {ids_file}: {exc}", err=True)
            raise typer.Exit(4) from exc
        merged.extend(line.strip() for line in file_text.splitlines())

    # Drop empty strings, dedupe preserving first-seen order.
    seen: set[str] = set()
    deduped: list[str] = []
    for raw in merged:
        vid = raw.strip()
        if not vid or vid in seen:
            continue
        seen.add(vid)
        deduped.append(vid)

    if not deduped:
        typer.echo(
            "Error: no variable ids supplied (after dropping blanks/duplicates).",
            err=True,
        )
        raise typer.Exit(4)
    if len(deduped) > MAX_VARIABLE_IDS:
        typer.echo(
            f"Error: at most {MAX_VARIABLE_IDS} ids allowed; got {len(deduped)}.",
            err=True,
        )
        raise typer.Exit(4)

    payload = run_request(
        "POST",
        "/variables/batch",
        json_body={"ids": deduped},
        index_id=index_id,
    )
    emit(payload, out)
