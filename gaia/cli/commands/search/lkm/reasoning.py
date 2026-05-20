"""``gaia search lkm reasoning`` — GET /claims/{id}/reasoning.

Returns the reasoning chains backing a single ``claim`` id. Only
``type=claim`` ids are valid; a ``question`` id yields server code 290004.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import typer

from gaia.cli.commands.search.lkm._shared import emit, run_request


class SortBy(StrEnum):
    """Ordering of returned reasoning chains."""

    COMPREHENSIVE = "comprehensive"
    RECENT = "recent"


_MAX_CHAINS_CAP = 100


def reasoning_command(
    claim_id: Annotated[
        str,
        typer.Argument(help="Claim id (type=claim only; question ids return 290004)."),
    ],
    max_chains: Annotated[
        int,
        typer.Option("--max-chains", help="Max chains to return (max 100)."),
    ] = 10,
    sort_by: Annotated[
        SortBy,
        typer.Option(
            "--sort-by",
            help="comprehensive (by premise count) or recent (by time).",
            case_sensitive=False,
        ),
    ] = SortBy.COMPREHENSIVE,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write JSON to PATH (atomic) instead of stdout."),
    ] = None,
) -> None:
    """Fetch reasoning chains for a claim (GET /claims/{id}/reasoning)."""
    if not claim_id.strip():
        typer.echo("Error: claim id must be non-empty.", err=True)
        raise typer.Exit(4)
    if max_chains < 1 or max_chains > _MAX_CHAINS_CAP:
        typer.echo(
            f"Error: --max-chains must be between 1 and {_MAX_CHAINS_CAP}; got {max_chains}.",
            err=True,
        )
        raise typer.Exit(4)

    encoded = quote(claim_id, safe="")
    payload = run_request(
        "GET",
        f"/claims/{encoded}/reasoning",
        params={"max_chains": max_chains, "sort_by": sort_by.value},
    )
    emit(_normalize(payload), out)


def _normalize(payload: dict[str, object]) -> dict[str, object]:
    """Flatten the two shapes the API may return into one stable envelope.

    The api-contract and the reference SKILL body disagree on whether the
    reasoning fields sit under ``data`` or at the top level:

      * ``{code, msg, data: {reasoning_chains, total_chains, ...}}``
      * ``{code, msg, reasoning_chains, total_chains, papers}``

    We surface ``reasoning_chains`` / ``total_chains`` (and ``papers`` when
    present) at the top level without dropping the original envelope keys,
    so downstream consumers find them regardless of source shape.
    """
    data = payload.get("data")
    if isinstance(data, dict) and ("reasoning_chains" in data or "total_chains" in data):
        merged = dict(payload)
        for key in ("reasoning_chains", "total_chains", "papers"):
            if key in data and key not in merged:
                merged[key] = data[key]
        return merged
    return payload
