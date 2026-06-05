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
from gaia.cli.commands.search.lkm._indexes import normalize_lkm_index_id
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
    index: Annotated[
        str | None,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = None,
    claim_id: Annotated[
        str | None,
        typer.Option(
            "--claim-id",
            help=(
                "Fetch reasoning chains for one claim id instead of searching by query. "
                "Accepts the bare id (gcn_…, pair with --index) or the prefixed form "
                "printed in search results (lkm:<index>:gcn_…), which infers --index."
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
            index_id=index_id,
        )
        payload = _normalize(payload)
        if output_format == SearchOutputFormat.GAIA_JSON:
            payload = normalize_lkm_reasoning_search(payload, query=claim_id, index_id=index_id)
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
        index_id=index_id,
    )
    if output_format == SearchOutputFormat.GAIA_JSON:
        payload = normalize_lkm_reasoning_search(payload, query=query, index_id=index_id)
    emit(payload, out)


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

    return run_request("POST", "/reasoning/search", json_body=body, index_id=index_id)


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
