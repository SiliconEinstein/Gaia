"""``gaia search lkm package`` — POST /papers/graph.

Fetch the latest graph-shaped extracted knowledge package for a paper
identified by exactly one of four mutually exclusive identifier flags. The
Gaia-facing command calls this a package candidate; the upstream LKM endpoint
calls it a paper graph.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from gaia.cli.commands.search.lkm._hints import package_hint
from gaia.cli.commands.search.lkm._shared import (
    DEFAULT_LKM_INDEX_ID,
    emit,
    run_request,
    validate_lkm_index,
)
from gaia.cli.commands.search.lkm.docs import APIFOX_PAPERS_GRAPH_URL

_TITLE_RESOLVE_CAP = 20
_PACKAGE_EPILOG = (
    "Fetch the default raw paper graph. Deprecated projection/hydration "
    "switches are intentionally not exposed.\n\n"
    f"API docs: {APIFOX_PAPERS_GRAPH_URL}\n"
    "Endpoint links: gaia search lkm docs"
)


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
    no_hint: Annotated[
        bool,
        typer.Option("--no-hint", help="Do not print Gaia next-step hints to stderr."),
    ] = False,
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
    if title is not None:
        body["title_resolve"] = {"limit": title_resolve_limit}

    payload = run_request("POST", "/papers/graph", json_body=body, index_id=index_id)
    requested_paper_id = paper_id or _paper_id_from_package_id(package_id)
    emit(
        payload,
        out,
        hint=package_hint(payload, index_id=index_id, requested_paper_id=requested_paper_id),
        show_hint=not no_hint,
    )


def _paper_id_from_package_id(package_id: str | None) -> str | None:
    if package_id is None or not package_id.startswith("paper:"):
        return None
    return package_id.split(":", 1)[1]
