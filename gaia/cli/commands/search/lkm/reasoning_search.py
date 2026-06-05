"""Hidden ``gaia search lkm reasoning-search`` compatibility alias.

The user-facing command is ``gaia search lkm reasoning <query>``. This module
keeps the older endpoint-shaped command available for PR/build compatibility.
It still calls ``POST /reasoning/search`` with the plural
``filters.paper_ids`` array per the apifox spec. The upstream POST endpoint
expects the graph-format switch in the request body.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from gaia.cli.commands.search._results import (
    SearchOutputFormat,
    normalize_lkm_reasoning_search,
)
from gaia.cli.commands.search.lkm._shared import (
    DEFAULT_LKM_INDEX_ID,
    MAX_KEYWORDS,
    MAX_LIMIT,
    MAX_OFFSET,
    MAX_PAPER_IDS,
    emit,
    run_request,
    validate_lkm_index,
)
from gaia.cli.commands.search.lkm.knowledge import RetrievalMode


def reasoning_search_command(
    query: Annotated[str, typer.Argument(help="Natural-language search query.")],
    index: Annotated[
        str,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = DEFAULT_LKM_INDEX_ID,
    retrieval_mode: Annotated[
        RetrievalMode,
        typer.Option("--retrieval-mode", help="Retrieval channel.", case_sensitive=False),
    ] = RetrievalMode.HYBRID,
    keywords: Annotated[
        list[str] | None,
        typer.Option(
            "--keywords",
            help=f"Lexical-channel keyword (repeatable, max {MAX_KEYWORDS}).",
        ),
    ] = None,
    paper_ids: Annotated[
        list[str] | None,
        typer.Option(
            "--paper-ids",
            help=(
                f"Restrict recall to these paper ids (repeatable, max {MAX_PAPER_IDS}; "
                "numeric strings only, no `paper:` prefix)."
            ),
        ),
    ] = None,
    offset: Annotated[
        int,
        typer.Option("--offset", help="Pagination offset (max 10000)."),
    ] = 0,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Page size (max 100)."),
    ] = 20,
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
    """Search reasoning chains (POST /reasoning/search)."""
    index_id = validate_lkm_index(index)
    if keywords and len(keywords) > MAX_KEYWORDS:
        typer.echo(
            f"Error: at most {MAX_KEYWORDS} --keywords allowed; got {len(keywords)}.",
            err=True,
        )
        raise typer.Exit(4)
    if offset < 0 or offset > MAX_OFFSET:
        typer.echo(
            f"Error: --offset must be between 0 and {MAX_OFFSET}; got {offset}.",
            err=True,
        )
        raise typer.Exit(4)
    if limit < 1 or limit > MAX_LIMIT:
        typer.echo(
            f"Error: --limit must be between 1 and {MAX_LIMIT}; got {limit}.",
            err=True,
        )
        raise typer.Exit(4)
    if paper_ids:
        if len(paper_ids) > MAX_PAPER_IDS:
            typer.echo(
                f"Error: at most {MAX_PAPER_IDS} --paper-ids allowed; got {len(paper_ids)}.",
                err=True,
            )
            raise typer.Exit(4)
        prefixed = [pid for pid in paper_ids if pid.startswith("paper:")]
        if prefixed:
            typer.echo(
                "Error: --paper-ids must be numeric strings without the `paper:` "
                f"prefix; got {prefixed}.",
                err=True,
            )
            raise typer.Exit(4)

    body: dict[str, Any] = {
        "query": query,
        "format": "graph",
        "retrieval_mode": retrieval_mode.value,
        "offset": offset,
        "limit": limit,
    }
    if keywords:
        body["keywords"] = list(keywords)
    if paper_ids:
        body["filters"] = {"paper_ids": list(paper_ids)}

    payload = run_request("POST", "/reasoning/search", json_body=body, index_id=index_id)
    if output_format == SearchOutputFormat.GAIA_JSON:
        payload = normalize_lkm_reasoning_search(payload, query=query, index_id=index_id)
    emit(payload, out)
