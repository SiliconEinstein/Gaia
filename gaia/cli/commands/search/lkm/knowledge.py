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
    MAX_DOIS,
    MAX_KEYWORDS,
    MAX_PAPER_IDS,
    emit,
    run_request,
    validate_dois,
    validate_lkm_index,
    validate_paper_ids,
    validate_search_window,
)
from gaia.cli.commands.search.lkm.docs import APIFOX_SEARCH_URL


class ScopeChoice(StrEnum):
    """Node types the search can be scoped to."""

    CLAIM = "claim"
    QUESTION = "question"


class RetrievalMode(StrEnum):
    """Retrieval channel for the query."""

    SEMANTIC = "semantic"
    LEXICAL = "lexical"
    HYBRID = "hybrid"


class SearchSortBy(StrEnum):
    """LKM search ordering profile."""

    RELEVANCE = "relevance"
    RECENT = "recent"
    JOURNAL = "journal"
    COMPREHENSIVE = "comprehensive"


_KNOWLEDGE_EPILOG = (
    "Use this surface when you need LKM-grounded paper knowledge items: "
    "conclusion claims, weak-point / highlight claims, problems, and open "
    "questions from papers. `reasoning <query>` is a parallel search surface "
    "for reasoning chains and workflows, not a later phase of knowledge search.\n\n"
    "For paper conclusions you plan to audit, add --reasoning-only. If a hit "
    "has a claim id, --claim-id can fetch that claim's supporting reasoning graph.\n\n"
    "Default search uses hybrid retrieval and comprehensive ranking. Add "
    "--keywords for lexical recall; use --sort-by recent or --sort-by journal "
    "when freshness or venue should dominate the first page.\n\n"
    f"API docs: {APIFOX_SEARCH_URL}\n"
    "Endpoint links: gaia search lkm docs\n\n"
    "Note: `score` is a retrieval ranking signal, not a probability — "
    "do not pass to Gaia priors."
)


def knowledge_command(
    query: Annotated[str, typer.Argument(help="Research question or claim to ground in LKM.")],
    index: Annotated[
        str,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = DEFAULT_LKM_INDEX_ID,
    scopes: Annotated[
        list[ScopeChoice] | None,
        typer.Option(
            "--scopes",
            help="Search scopes (repeatable; default: claim and question).",
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
            help=f"Keyword for the lexical channel (repeatable, max {MAX_KEYWORDS}).",
        ),
    ] = None,
    reasoning_only: Annotated[
        bool,
        typer.Option(
            "--reasoning-only",
            help="Return only conclusion claims that have reasoning chains.",
        ),
    ] = False,
    role: Annotated[
        str | None,
        typer.Option(
            "--role", help="Filter by node role (e.g. conclusion / highlight / weakpoint)."
        ),
    ] = None,
    include_paper_enrich: Annotated[
        bool,
        typer.Option(
            "--include-paper-enrich",
            help="Request enriched paper metadata when the index supports it.",
        ),
    ] = False,
    visibility: Annotated[
        str,
        typer.Option("--visibility", help="Visibility filter."),
    ] = "public",
    sort_by: Annotated[
        SearchSortBy,
        typer.Option(
            "--sort-by",
            help="Ranking profile: relevance, recent, journal, or comprehensive.",
            case_sensitive=False,
        ),
    ] = SearchSortBy.COMPREHENSIVE,
    paper_ids: Annotated[
        list[str] | None,
        typer.Option(
            "--paper-ids",
            "--paper-id",
            help=(
                f"Restrict to these source paper ids (repeatable, max {MAX_PAPER_IDS}; "
                "numeric strings only, no `paper:` prefix)."
            ),
        ),
    ] = None,
    dois: Annotated[
        list[str] | None,
        typer.Option(
            "--doi",
            help=f"Restrict to these source DOI values (repeatable, max {MAX_DOIS}).",
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
    no_hint: Annotated[
        bool,
        typer.Option("--no-hint", help="Suppress Gaia follow-up suggestions on stderr."),
    ] = False,
) -> None:
    """Search LKM paper knowledge items (POST /search)."""
    index_id = validate_lkm_index(index)
    if keywords and len(keywords) > MAX_KEYWORDS:
        typer.echo(
            f"Error: at most {MAX_KEYWORDS} --keywords allowed; got {len(keywords)}.",
            err=True,
        )
        raise typer.Exit(4)
    validate_search_window(offset, limit)
    validate_paper_ids(paper_ids)
    validate_dois(dois)
    if reasoning_only and scopes and scopes != [ScopeChoice.CLAIM]:
        typer.echo(
            "Error: --reasoning-only requires --scopes to be omitted or exactly "
            "`claim`; question results do not have reasoning chains.",
            err=True,
        )
        raise typer.Exit(4)

    body: dict[str, Any] = {
        "query": query,
        "retrieval_mode": retrieval_mode.value,
        "offset": offset,
        "limit": limit,
        "sort_by": sort_by.value,
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
    if paper_ids:
        filters["paper_ids"] = list(paper_ids)
    if dois:
        filters["dois"] = list(dois)
    body["filters"] = filters

    payload = run_request("POST", "/search", json_body=body, index_id=index_id)
    emit(payload, out, hint=knowledge_hint(payload, index_id=index_id), show_hint=not no_hint)
