"""``gaia search lkm reasoning`` — search or fetch LKM reasoning chains.

With a query argument this searches reasoning chains by natural language
(``POST /reasoning/search``). With ``--claim-id`` it fetches the reasoning
chains backing one claim (``GET /claims/{id}/reasoning``). Only ``type=claim``
ids are valid for ``--claim-id``; a ``question`` id yields server code 290004.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

import typer

from gaia.cli.commands.search._results import (
    SearchOutputFormat,
    normalize_lkm_reasoning_search,
)
from gaia.cli.commands.search.lkm._shared import (
    MAX_KEYWORDS,
    MAX_LIMIT,
    MAX_OFFSET,
    MAX_PAPER_IDS,
    emit,
    run_request,
)
from gaia.cli.commands.search.lkm.knowledge import RetrievalMode


class SortBy(StrEnum):
    """Ordering of returned reasoning chains."""

    COMPREHENSIVE = "comprehensive"
    RECENT = "recent"


_MAX_CHAINS_CAP = 100


def reasoning_command(
    query: Annotated[
        str | None,
        typer.Argument(help="Natural-language query for reasoning-chain search."),
    ] = None,
    claim_id: Annotated[
        str | None,
        typer.Option(
            "--claim-id",
            help="Fetch reasoning chains for one claim id instead of searching by query.",
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
    paper_ids: Annotated[
        list[str] | None,
        typer.Option(
            "--paper-ids",
            help=(
                f"Restrict query search to these paper ids (repeatable, max {MAX_PAPER_IDS}; "
                "numeric strings only, no `paper:` prefix)."
            ),
        ),
    ] = None,
    max_chains: Annotated[
        int,
        typer.Option(
            "--max-chains",
            help="Max chains to return for --claim-id mode (max 100).",
        ),
    ] = 10,
    sort_by: Annotated[
        SortBy,
        typer.Option(
            "--sort-by",
            help="comprehensive (by premise count) or recent (by time).",
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
    output_format: Annotated[
        SearchOutputFormat,
        typer.Option(
            "--format",
            help="Output format: raw upstream JSON or normalized Gaia search JSON.",
            case_sensitive=False,
        ),
    ] = SearchOutputFormat.GAIA_JSON,
) -> None:
    """Search reasoning chains, or fetch them for one claim with --claim-id."""
    if claim_id is None and query is not None and _looks_like_claim_id(query):
        claim_id = query
        query = None

    if query is not None and claim_id is not None:
        typer.echo("Error: pass either QUERY or --claim-id, not both.", err=True)
        raise typer.Exit(4)
    if query is None and claim_id is None:
        typer.echo("Error: pass QUERY or --claim-id.", err=True)
        raise typer.Exit(4)
    if claim_id is not None:
        if (
            keywords
            or paper_ids
            or offset != 0
            or limit != 20
            or retrieval_mode != RetrievalMode.HYBRID
        ):
            typer.echo(
                "Error: --claim-id mode does not accept query-search options "
                "(--retrieval-mode, --keywords, --paper-ids, --offset, --limit).",
                err=True,
            )
            raise typer.Exit(4)
        payload = _fetch_claim_reasoning(
            claim_id=claim_id,
            max_chains=max_chains,
            sort_by=sort_by,
        )
        payload = _normalize(payload)
        if output_format == SearchOutputFormat.GAIA_JSON:
            payload = normalize_lkm_reasoning_search(payload, query=claim_id)
        emit(payload, out)
        return

    assert query is not None
    if max_chains != 10 or sort_by != SortBy.COMPREHENSIVE:
        typer.echo(
            "Error: query-search mode does not accept claim-inspection options "
            "(--max-chains, --sort-by).",
            err=True,
        )
        raise typer.Exit(4)
    payload = _search_reasoning(
        query=query,
        retrieval_mode=retrieval_mode,
        keywords=keywords,
        paper_ids=paper_ids,
        offset=offset,
        limit=limit,
    )
    if output_format == SearchOutputFormat.GAIA_JSON:
        payload = normalize_lkm_reasoning_search(payload, query=query)
    emit(payload, out)


def _looks_like_claim_id(value: str) -> bool:
    stripped = value.strip()
    return stripped.startswith("gcn_") and stripped == value and " " not in stripped


def _fetch_claim_reasoning(
    *,
    claim_id: str,
    max_chains: int,
    sort_by: SortBy,
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
        params={"max_chains": max_chains, "sort_by": sort_by.value},
    )


def _search_reasoning(
    *,
    query: str,
    retrieval_mode: RetrievalMode,
    keywords: list[str] | None,
    paper_ids: list[str] | None,
    offset: int,
    limit: int,
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
        "retrieval_mode": retrieval_mode.value,
        "offset": offset,
        "limit": limit,
    }
    if keywords:
        body["keywords"] = list(keywords)
    if paper_ids:
        body["filters"] = {"paper_ids": list(paper_ids)}

    return run_request("POST", "/reasoning/search", json_body=body)


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
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
