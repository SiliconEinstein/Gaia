"""``gaia search lkm package`` — POST /papers/graph.

Fetch the full extracted knowledge graph (variables / factors /
motivations / ...) for a paper identified by exactly one of four mutually
exclusive identifier flags. The Gaia-facing command calls this a package
candidate; the upstream LKM endpoint calls it a paper graph.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

from gaia.cli.commands.search._results import SearchOutputFormat, normalize_lkm_paper_graph
from gaia.cli.commands.search.lkm._shared import (
    DEFAULT_LKM_INDEX_ID,
    emit,
    run_request,
    validate_lkm_index,
)


class PaperGraphInclude(StrEnum):
    """Sub-graphs that may be requested in the response."""

    PAPER = "paper"
    VARIABLES = "variables"
    FACTORS = "factors"
    MOTIVATIONS = "motivations"
    PRIORS = "priors"
    FACTOR_PARAMS = "factor_params"


_TITLE_RESOLVE_CAP = 20


def package_command(
    index: Annotated[
        str,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = DEFAULT_LKM_INDEX_ID,
    package_id: Annotated[
        str | None,
        typer.Option("--package-id", help="Identify by package id (form `paper:<digits>`)."),
    ] = None,
    paper_id: Annotated[
        str | None,
        typer.Option("--paper-id", help="Identify by paper id."),
    ] = None,
    doi: Annotated[
        str | None,
        typer.Option("--doi", help="Identify by DOI."),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option("--title", help="Identify by title (may resolve multiple papers)."),
    ] = None,
    include: Annotated[
        list[PaperGraphInclude] | None,
        typer.Option(
            "--include",
            help=(
                "Legacy sub-graph to include (repeatable). "
                "Omit to use LKM's default graph-shaped response."
            ),
            case_sensitive=False,
        ),
    ] = None,
    factor_refs_only: Annotated[
        bool,
        typer.Option(
            "--factor-refs-only",
            help="Return factor premise/conclusion ids only (~60% smaller response).",
        ),
    ] = False,
    title_resolve_limit: Annotated[
        int,
        typer.Option(
            "--title-resolve-limit",
            help="Candidate papers per title (max 20; only valid with --title).",
        ),
    ] = 5,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write JSON to PATH (atomic) instead of stdout."),
    ] = None,
    output_format: Annotated[
        SearchOutputFormat,
        typer.Option(
            "--format",
            help="Output format: raw upstream JSON or normalized Gaia search JSON.",
            case_sensitive=False,
        ),
    ] = SearchOutputFormat.GAIA_JSON,
) -> None:
    """Fetch an LKM paper package candidate (POST /papers/graph)."""
    index_id = validate_lkm_index(index)
    identifiers = {
        "package_id": package_id,
        "paper_id": paper_id,
        "doi": doi,
        "title": title,
    }
    supplied = {k: v for k, v in identifiers.items() if v is not None}
    if len(supplied) != 1:
        flags = "--package-id / --paper-id / --doi / --title"
        if not supplied:
            typer.echo(f"Error: exactly one identifier required ({flags}); none given.", err=True)
        else:
            given = ", ".join(f"--{k.replace('_', '-')}" for k in supplied)
            typer.echo(
                f"Error: exactly one identifier allowed ({flags}); got {given}.",
                err=True,
            )
        raise typer.Exit(4)

    title_limit_explicit = title_resolve_limit != 5
    if title is None and title_limit_explicit:
        typer.echo("Error: --title-resolve-limit is only valid with --title.", err=True)
        raise typer.Exit(4)
    if title is not None and (title_resolve_limit < 1 or title_resolve_limit > _TITLE_RESOLVE_CAP):
        typer.echo(
            f"Error: --title-resolve-limit must be between 1 and {_TITLE_RESOLVE_CAP}; "
            f"got {title_resolve_limit}.",
            err=True,
        )
        raise typer.Exit(4)

    body: dict[str, Any] = dict(supplied)
    if include:
        body["include"] = [item.value for item in include]
    if factor_refs_only:
        body["hydrate_factor_refs"] = False
    if title is not None:
        body["title_resolve"] = {"limit": title_resolve_limit}

    payload = run_request("POST", "/papers/graph", json_body=body, index_id=index_id)
    if output_format == SearchOutputFormat.GAIA_JSON:
        query_text = next(iter(supplied.values()))
        payload = normalize_lkm_paper_graph(
            payload,
            query=str(query_text),
            index_id=index_id,
        )
    emit(payload, out)


paper_graph_command = package_command
