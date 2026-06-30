"""``gaia search lkm knowledge`` — POST /search.

Cross-node retrieval over claim / question nodes. The
returned ``score`` / ``rerank_score`` values are retrieval ranking signals,
not probabilities — see the verb help epilog.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

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
from gaia.cli.commands.search.lkm.policy import (
    DEFAULT_SEARCH_SORT_BY,
    build_knowledge_search_body,
)


class ScopeChoice(StrEnum):
    """Node types the search can be scoped to."""

    CLAIM = "claim"
    QUESTION = "question"
    ABSTRACT = "abstract"
    CONCLUSION = "conclusion"
    PREMISE = "premise"


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


DEFAULT_SEARCH_SORT_CHOICE = SearchSortBy(DEFAULT_SEARCH_SORT_BY)


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
    "Use --scopes abstract for paper-level abstract hits. Treat abstracts as "
    "paper context, not Gaia claims; same-paper `related` hits are folded "
    "context, not cross-paper recommendations.\n\n"
    f"API docs: {APIFOX_SEARCH_URL}\n"
    "Endpoint links: gaia search lkm docs\n\n"
    "Note: `score` / `rerank_score` are retrieval ranking signals, not probabilities — "
    "do not pass to Gaia priors."
)

_REASONING_ONLY_SCOPES = ([ScopeChoice.CLAIM], [ScopeChoice.CONCLUSION])


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
            help=(
                "Search scopes: claim/question/abstract types or "
                "conclusion/premise roles (repeatable)."
            ),
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
    ] = DEFAULT_SEARCH_SORT_CHOICE,
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
            "--dois",
            "--doi",
            help=f"Restrict to these source DOI values (repeatable, max {MAX_DOIS}).",
        ),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option(
            "--title",
            help="Restrict by fuzzy paper title, ANDed with paper ids / DOIs.",
        ),
    ] = None,
    publication_date_start: Annotated[
        str | None,
        typer.Option(
            "--publication-date-start",
            help="Restrict publication date lower bound (YYYY-MM-DD).",
        ),
    ] = None,
    publication_date_end: Annotated[
        str | None,
        typer.Option(
            "--publication-date-end",
            help="Restrict publication date upper bound (YYYY-MM-DD).",
        ),
    ] = None,
    limit_publication_date: Annotated[
        bool,
        typer.Option(
            "--limit-publication-date/--no-limit-publication-date",
            help=(
                "Apply LKM publication-date filtering. The server default is true; "
                "--no-limit-publication-date also recalls papers without dates."
            ),
        ),
    ] = True,
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
    if reasoning_only and scopes and scopes not in _REASONING_ONLY_SCOPES:
        typer.echo(
            "Error: --reasoning-only requires --scopes to be omitted or exactly "
            "`claim` or `conclusion`; question/abstract/premise results do not have "
            "reasoning chains.",
            err=True,
        )
        raise typer.Exit(4)

    body = build_knowledge_search_body(
        query=query,
        retrieval_mode=retrieval_mode.value,
        sort_by=sort_by.value,
        offset=offset,
        limit=limit,
        scopes=[s.value for s in scopes] if scopes else None,
        keywords=keywords,
        reasoning_only=reasoning_only,
        include_paper_enrich=include_paper_enrich,
        visibility=visibility,
        role=role,
        paper_ids=paper_ids,
        dois=dois,
        title=title,
        publication_date_start=publication_date_start,
        publication_date_end=publication_date_end,
        limit_publication_date=limit_publication_date,
    )

    payload = run_request("POST", "/search", json_body=body, index_id=index_id)
    emit(payload, out, hint=knowledge_hint(payload, index_id=index_id), show_hint=not no_hint)
