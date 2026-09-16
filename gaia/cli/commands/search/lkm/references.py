"""``gaia search lkm references`` — POST /papers/reference.

Bibliographic forward-reference and reverse cited-by lookup for papers already
identified by numeric LKM id or DOI. This returns paper cards, not a knowledge
graph; use ``package`` for the extracted LKM paper graph.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from gaia.cli.commands.search.lkm._hints import references_hint
from gaia.cli.commands.search.lkm._shared import (
    DEFAULT_LKM_INDEX_ID,
    MAX_REFERENCE_SEEDS,
    SEARCH_BILLING_NOTE,
    emit,
    run_request,
    validate_lkm_index,
    validate_reference_seeds,
)

_REFERENCES_EPILOG = (
    "Examples:\n\n"
    "  gaia search lkm references --paper-id <paper_id>\n\n"
    "  gaia search lkm references --doi 10.1234/example --with-reference\n\n"
    "What you have:\n\n"
    "  a paper ID or DOI, cited-by list  ->  references (default)\n\n"
    "  a paper ID or DOI, forward refs   ->  --with-reference\n\n"
    "  the extracted knowledge graph     ->  package\n\n"
    "  a title or package id             ->  not this command\n\n"
    "Use this when you already know paper ids or DOIs and want bibliographic "
    "forward references and/or reverse cited-by lists. This is a paper-card "
    "lookup, not a knowledge graph; use `package` for the extracted LKM paper "
    "graph. Do not pass a title or package id.\n\n"
    "At least one of --paper-id / --doi is required (repeatable). Combined "
    f"seeds are capped at {MAX_REFERENCE_SEEDS} before dedupe. A `paper:` "
    "prefix on --paper-id is stripped.\n\n"
    "Defaults match the HTTP API and are always sent: --with-abstract, "
    "--no-with-reference, --with-cited-by. The response uses `data.papers`. "
    "An empty paper id means LKM has not covered that record.\n\n"
    f"{SEARCH_BILLING_NOTE}\n\n"
    "API: POST /papers/reference\n\n"
    "Endpoint links: gaia search lkm docs"
)


def references_command(
    index: Annotated[
        str,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = DEFAULT_LKM_INDEX_ID,
    paper_ids: Annotated[
        list[str] | None,
        typer.Option(
            "--paper-id",
            help=(
                "LKM paper id (repeatable, numeric; a `paper:` prefix is stripped). "
                f"Combined with --doi, at most {MAX_REFERENCE_SEEDS} seeds."
            ),
        ),
    ] = None,
    dois: Annotated[
        list[str] | None,
        typer.Option(
            "--doi",
            help=(
                f"Paper DOI (repeatable). Combined with --paper-id, at most "
                f"{MAX_REFERENCE_SEEDS} seeds."
            ),
        ),
    ] = None,
    with_abstract: Annotated[
        bool,
        typer.Option(
            "--with-abstract/--no-with-abstract",
            help="Include abstracts on the seed and both neighbor lists.",
        ),
    ] = True,
    with_reference: Annotated[
        bool,
        typer.Option(
            "--with-reference/--no-with-reference",
            help="Return forward references.",
        ),
    ] = False,
    with_cited_by: Annotated[
        bool,
        typer.Option(
            "--with-cited-by/--no-with-cited-by",
            help="Return reverse cited-by lists.",
        ),
    ] = True,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write JSON to PATH (atomic) instead of stdout."),
    ] = None,
    no_hint: Annotated[
        bool,
        typer.Option("--no-hint", help="Suppress Gaia follow-up suggestions on stderr."),
    ] = False,
) -> None:
    """Look up paper references and cited-by lists.

    POST /papers/reference.
    """
    index_id = validate_lkm_index(index)
    paper_ids, dois = validate_reference_seeds(paper_ids, dois)

    body: dict[str, Any] = {
        "with_abstract": with_abstract,
        "with_reference": with_reference,
        "with_cited_by": with_cited_by,
    }
    if paper_ids:
        body["paper_ids"] = paper_ids
    if dois:
        body["dois"] = dois

    payload = run_request("POST", "/papers/reference", json_body=body, index_id=index_id)
    emit(
        payload,
        out,
        hint=references_hint(payload, index_id=index_id, requested_paper_ids=paper_ids),
        show_hint=not no_hint,
    )
