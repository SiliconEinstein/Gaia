"""``gaia search lkm knowledge`` — POST /search.

Cross-node retrieval over claim / question nodes. The
returned ``score`` is a retrieval ranking signal, not a probability — see
the verb help epilog.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

from gaia.cli.commands.search.lkm._hints import knowledge_hint
from gaia.cli.commands.search.lkm._shared import (
    DEFAULT_LKM_INDEX_ID,
    MAX_KEYWORDS,
    MAX_LIMIT,
    MAX_OFFSET,
    emit,
    run_request,
    validate_lkm_index,
)


class ScopeChoice(StrEnum):
    """Node types the search can be scoped to."""

    CLAIM = "claim"
    QUESTION = "question"


class RetrievalMode(StrEnum):
    """Retrieval channel for the query."""

    SEMANTIC = "semantic"
    LEXICAL = "lexical"
    HYBRID = "hybrid"


_KNOWLEDGE_EPILOG = (
    "Retrieval modes:\n\n"
    "  semantic  meaning-similarity recall (different wording, same idea)\n"
    "  lexical   keyword literal recall (must contain a specific term)\n"
    "  hybrid    both channels fused, auto-degrading on single-channel "
    "failure (default)\n\n"
    "Note: `score` is a retrieval ranking signal, not a probability — "
    "do not pass to Gaia priors."
)


def knowledge_command(
    query: Annotated[str, typer.Argument(help="Natural-language search query.")],
    index: Annotated[
        str,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = DEFAULT_LKM_INDEX_ID,
    scopes: Annotated[
        list[ScopeChoice] | None,
        typer.Option(
            "--scopes",
            help="Restrict recall to claim/question nodes (repeatable). Empty = both.",
            case_sensitive=False,
        ),
    ] = None,
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
    reasoning_only: Annotated[
        bool,
        typer.Option(
            "--reasoning-only",
            help="Only return claims backed by reasoning chains (narrows scopes/role).",
        ),
    ] = False,
    role: Annotated[
        str | None,
        typer.Option("--role", help="Filter by node role (e.g. conclusion / premise)."),
    ] = None,
    include_paper_enrich: Annotated[
        bool,
        typer.Option(
            "--include-paper-enrich",
            help="Ask LKM to include enriched paper metadata when the index supports it.",
        ),
    ] = False,
    visibility: Annotated[
        str,
        typer.Option("--visibility", help="Visibility filter."),
    ] = "public",
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
    no_hint: Annotated[
        bool,
        typer.Option("--no-hint", help="Do not print Gaia next-step hints to stderr."),
    ] = False,
) -> None:
    """Search LKM knowledge nodes (POST /search)."""
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
    if reasoning_only and scopes and scopes != [ScopeChoice.CLAIM]:
        typer.echo(
            "Error: --reasoning-only requires --scopes to be omitted or exactly "
            "`claim`; question nodes do not have reasoning chains.",
            err=True,
        )
        raise typer.Exit(4)

    body: dict[str, Any] = {
        "query": query,
        "retrieval_mode": retrieval_mode.value,
        "offset": offset,
        "limit": limit,
    }
    if scopes:
        body["scopes"] = [s.value for s in scopes]
    if keywords:
        body["keywords"] = list(keywords)
    if reasoning_only:
        body["reasoning_only"] = True
    if include_paper_enrich:
        body["include_paper_enrich"] = True
    filters: dict[str, Any] = {"visibility": visibility}
    if role:
        filters["role"] = role
    body["filters"] = filters

    payload = run_request("POST", "/search", json_body=body, index_id=index_id)
    emit(payload, out, hint=knowledge_hint(payload, index_id=index_id), show_hint=not no_hint)
