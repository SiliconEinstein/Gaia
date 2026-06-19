"""``gaia search lkm reasoning`` — search or fetch LKM reasoning chains.

With a query argument this searches reasoning chains by natural language
(``POST /reasoning/search``). With ``--claim-id`` it fetches the reasoning
chains backing one claim (``GET /claims/{id}/reasoning``). Only ``type=claim``
ids are valid for ``--claim-id``; a ``question`` id yields server code 290004.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

import typer

from gaia.cli.commands.search.lkm._hints import reasoning_hint
from gaia.cli.commands.search.lkm._indexes import normalize_lkm_index_id
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
from gaia.cli.commands.search.lkm.docs import (
    APIFOX_CLAIM_REASONING_URL,
    APIFOX_REASONING_SEARCH_URL,
)
from gaia.cli.commands.search.lkm.knowledge import RetrievalMode, SearchSortBy

SortBy = SearchSortBy


_MAX_CHAINS_CAP = 100

_REASONING_EPILOG = (
    "Use query mode as a search surface for reasoning chains and workflows. "
    "It is parallel to `knowledge <query>`, which searches paper knowledge "
    "items such as conclusions, weak points, highlights, problems, and open "
    "questions.\n\n"
    "Use --claim-id only when you already have a claim id and want that claim's "
    "supporting reasoning graph.\n\n"
    "Query mode accepts search filters (--paper-id, --doi, --sort-by). "
    "--claim-id mode fetches one claim's backing chains and only accepts "
    "--max-chains plus --sort-by comprehensive|recent.\n\n"
    f"Query API docs: {APIFOX_REASONING_SEARCH_URL}\n\n"
    f"Claim API docs: {APIFOX_CLAIM_REASONING_URL}\n"
    "Endpoint links: gaia search lkm docs"
)


def reasoning_command(
    query: Annotated[
        str | None,
        typer.Argument(help="Topic to search for reasoning chains or workflows."),
    ] = None,
    index: Annotated[
        str | None,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = None,
    claim_id: Annotated[
        str | None,
        typer.Option(
            "--claim-id",
            help=(
                "Inspect reasoning for one claim id. Accepts bare gcn_... ids or "
                "lkm:<index>:gcn_... refs from search results."
            ),
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
    paper_ids: Annotated[
        list[str] | None,
        typer.Option(
            "--paper-ids",
            "--paper-id",
            help=(
                f"Restrict query mode to these source paper ids (repeatable, max {MAX_PAPER_IDS}; "
                "numeric strings only, no `paper:` prefix)."
            ),
        ),
    ] = None,
    dois: Annotated[
        list[str] | None,
        typer.Option(
            "--doi",
            help=f"Restrict query mode to these source DOI values (repeatable, max {MAX_DOIS}).",
        ),
    ] = None,
    max_chains: Annotated[
        int,
        typer.Option(
            "--max-chains",
            help="Maximum backing chains for --claim-id mode (max 100).",
        ),
    ] = 10,
    sort_by: Annotated[
        SortBy,
        typer.Option(
            "--sort-by",
            help=(
                "Ranking profile. Query mode accepts relevance, recent, journal, "
                "or comprehensive; --claim-id mode accepts comprehensive or recent."
            ),
            case_sensitive=False,
        ),
    ] = SortBy.COMPREHENSIVE,
    offset: Annotated[
        int,
        typer.Option("--offset", help="Query-search pagination offset (max 10000)."),
    ] = 0,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Query-search page size (max 100)."),
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
    """Search reasoning chains, or fetch them for one claim with --claim-id."""
    # A claim id may arrive bare (``gcn_…``) or in the prefixed form printed
    # in search results (``lkm:<index>:gcn_…``). The prefixed form carries its
    # own index; parse it off and reconcile with an explicit --index.
    if claim_id is None and query is not None and _looks_like_claim_id(query):
        claim_id = query
        query = None
    if claim_id is not None:
        claim_id, index = _resolve_prefixed_claim_id(claim_id, index)

    index_id = validate_lkm_index(index if index is not None else DEFAULT_LKM_INDEX_ID)

    if query is not None and claim_id is not None:
        typer.echo("Error: pass either QUERY or --claim-id, not both.", err=True)
        raise typer.Exit(4)
    if query is None and claim_id is None:
        typer.echo("Error: pass QUERY or --claim-id.", err=True)
        raise typer.Exit(4)
    if claim_id is not None:
        if sort_by not in {SortBy.COMPREHENSIVE, SortBy.RECENT}:
            typer.echo(
                "Error: --claim-id mode only accepts --sort-by comprehensive or recent.",
                err=True,
            )
            raise typer.Exit(4)
        if (
            keywords
            or paper_ids
            or dois
            or offset != 0
            or limit != 20
            or retrieval_mode != RetrievalMode.HYBRID
        ):
            typer.echo(
                "Error: --claim-id mode does not accept query-search options "
                "(--retrieval-mode, --keywords, --paper-ids, --doi, --offset, --limit).",
                err=True,
            )
            raise typer.Exit(4)
        payload = _fetch_claim_reasoning(
            claim_id=claim_id,
            max_chains=max_chains,
            sort_by=sort_by,
            index_id=index_id,
        )
        emit(
            payload,
            out,
            hint=reasoning_hint(payload, index_id=index_id, claim_id=claim_id),
            show_hint=not no_hint,
        )
        return

    assert query is not None
    if max_chains != 10:
        typer.echo(
            "Error: query-search mode does not accept claim-inspection options (--max-chains).",
            err=True,
        )
        raise typer.Exit(4)
    payload = _search_reasoning(
        query=query,
        retrieval_mode=retrieval_mode,
        keywords=keywords,
        paper_ids=paper_ids,
        dois=dois,
        sort_by=sort_by,
        offset=offset,
        limit=limit,
        index_id=index_id,
    )
    emit(payload, out, hint=reasoning_hint(payload, index_id=index_id), show_hint=not no_hint)


def _looks_like_claim_id(value: str) -> bool:
    stripped = value.strip()
    if " " in stripped or stripped != value:
        return False
    if stripped.startswith("gcn_"):
        return True
    # Also recognise the prefixed form that search results print, so a bare
    # positional ``lkm:<index>:gcn_…`` routes to --claim-id mode like the bare id.
    bare, prefix_index = _split_prefixed_claim_id(stripped)
    return prefix_index is not None and bare.startswith("gcn_")


def _resolve_prefixed_claim_id(claim_id: str, index: str | None) -> tuple[str, str | None]:
    """Resolve a possibly-prefixed claim id against an explicit --index.

    Returns ``(bare_id, index)``. When ``claim_id`` carries an ``lkm:<index>:``
    prefix, the embedded index is parsed off; if --index was also given and
    disagrees, the call exits 4. A bare claim id is returned unchanged.
    """
    bare_id, prefix_index = _split_prefixed_claim_id(claim_id)
    if prefix_index is None:
        return claim_id, index
    if index is not None and normalize_lkm_index_id(index) != normalize_lkm_index_id(prefix_index):
        typer.echo(
            f"Error: --index {index!r} disagrees with the index in --claim-id ({prefix_index!r}).",
            err=True,
        )
        raise typer.Exit(4)
    return bare_id, index if index is not None else prefix_index


def _split_prefixed_claim_id(value: str) -> tuple[str, str | None]:
    """Split a prefixed claim id into ``(bare_id, index)``.

    Search results print claim ids as ``lkm:<index>:<bare-id>`` (and the inspect
    action carries ``lkm:<index>:claim:<bare-id>``). This parses either prefixed
    shape into the bare id plus the embedded index. A value without the ``lkm:``
    prefix is returned unchanged with ``index=None`` so the bare-id path is
    untouched.
    """
    stripped = value.strip()
    if not stripped.startswith("lkm:"):
        return stripped, None
    parts = stripped.split(":")
    # ``lkm:<index>:<bare>`` → 3 parts; ``lkm:<index>:claim:<bare>`` → 4 parts
    # with the ``claim`` kind segment. Anything else is left to fail downstream
    # as a literal id rather than silently mis-parsed.
    if len(parts) == 3 and all(parts):
        return parts[2], parts[1]
    if len(parts) == 4 and parts[2] == "claim" and all(parts):
        return parts[3], parts[1]
    return stripped, None


def _fetch_claim_reasoning(
    *,
    claim_id: str,
    max_chains: int,
    sort_by: SortBy,
    index_id: str,
) -> dict[str, Any]:
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
    return run_request(
        "GET",
        f"/claims/{encoded}/reasoning",
        params={"format": "graph", "max_chains": max_chains, "sort_by": sort_by.value},
        index_id=index_id,
    )


def _search_reasoning(
    *,
    query: str,
    retrieval_mode: RetrievalMode,
    keywords: list[str] | None,
    paper_ids: list[str] | None,
    dois: list[str] | None,
    sort_by: SortBy,
    offset: int,
    limit: int,
    index_id: str,
) -> dict[str, Any]:
    if not query.strip():
        typer.echo("Error: query must be non-empty.", err=True)
        raise typer.Exit(4)
    if keywords and len(keywords) > MAX_KEYWORDS:
        typer.echo(
            f"Error: at most {MAX_KEYWORDS} --keywords allowed; got {len(keywords)}.",
            err=True,
        )
        raise typer.Exit(4)
    validate_search_window(offset, limit)
    validate_paper_ids(paper_ids)
    validate_dois(dois)

    body: dict[str, Any] = {
        "query": query,
        "format": "graph",
        "retrieval_mode": retrieval_mode.value,
        "sort_by": sort_by.value,
        "offset": offset,
        "limit": limit,
    }
    if keywords:
        body["keywords"] = list(keywords)
    filters: dict[str, Any] = {}
    if paper_ids:
        filters["paper_ids"] = list(paper_ids)
    if dois:
        filters["dois"] = list(dois)
    if filters:
        body["filters"] = filters

    return run_request("POST", "/reasoning/search", json_body=body, index_id=index_id)
