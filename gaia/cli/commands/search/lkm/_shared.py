"""Search-specific argument caps for ``gaia search lkm``.

The index resolution, exit-code contract, and output plumbing live in
:mod:`gaia.cli._lkm_runtime` because ``gaia extract`` needs them too; this
module re-exports them so the search verbs keep a single import site, and adds
the pagination / filter caps that only the retrieval endpoints have.
"""

from __future__ import annotations

from datetime import date

import typer

from gaia.cli._lkm_runtime import (
    DEFAULT_LKM_INDEX_ID,
    LKMClient,
    emit,
    run_request,
    validate_lkm_index,
    validate_lkm_server,
)

# Lexical-channel keyword caps, shared by knowledge / reasoning.
MAX_KEYWORDS = 10
MAX_KEYWORD_LENGTH = 100
# POST /search and /reasoning/search reject offset > 2000.
MAX_OFFSET = 2000
DEFAULT_SEARCH_LIMIT = 10
MAX_LIMIT = 100
MAX_PAPER_IDS = 50
MAX_DOIS = 50
MAX_VARIABLE_IDS = 100
# Combined paper_ids + dois cap for POST /papers/reference (before dedupe).
MAX_REFERENCE_SEEDS = 20


def validate_search_window(offset: int, limit: int) -> None:
    """Validate standard LKM search pagination arguments."""
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


def validate_keywords(keywords: list[str] | None) -> None:
    """Validate lexical keywords accepted by LKM search endpoints."""
    if not keywords:
        return
    if len(keywords) > MAX_KEYWORDS:
        typer.echo(
            f"Error: at most {MAX_KEYWORDS} --keywords allowed; got {len(keywords)}.",
            err=True,
        )
        raise typer.Exit(4)
    for keyword in keywords:
        if len(keyword.encode("utf-8")) > MAX_KEYWORD_LENGTH:
            typer.echo(
                f"Error: each --keywords value must be at most {MAX_KEYWORD_LENGTH} "
                f"bytes; got {len(keyword.encode('utf-8'))} for {keyword!r}.",
                err=True,
            )
            raise typer.Exit(4)


def validate_publication_dates(
    publication_date_start: str | None,
    publication_date_end: str | None,
) -> None:
    """Validate LKM publication-date bounds as YYYY-MM-DD with start <= end."""
    start = _parse_publication_date(publication_date_start, option_name="--publication-date-start")
    end = _parse_publication_date(publication_date_end, option_name="--publication-date-end")
    if start is not None and end is not None and start > end:
        typer.echo(
            "Error: --publication-date-start must be on or before --publication-date-end.",
            err=True,
        )
        raise typer.Exit(4)


def _parse_publication_date(raw: str | None, *, option_name: str) -> date | None:
    if raw is None:
        return None
    value = raw.strip()
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        parsed = None
    if parsed is None or value != parsed.isoformat():
        typer.echo(
            f"Error: {option_name} must be YYYY-MM-DD; got {raw!r}.",
            err=True,
        )
        raise typer.Exit(4)
    return parsed


def validate_paper_ids(paper_ids: list[str] | None, *, option_name: str = "--paper-ids") -> None:
    """Validate LKM paper-id filters accepted by search endpoints."""
    if not paper_ids:
        return
    if len(paper_ids) > MAX_PAPER_IDS:
        typer.echo(
            f"Error: at most {MAX_PAPER_IDS} {option_name} allowed; got {len(paper_ids)}.",
            err=True,
        )
        raise typer.Exit(4)
    prefixed = [pid for pid in paper_ids if pid.startswith("paper:")]
    if prefixed:
        typer.echo(
            f"Error: {option_name} must be numeric strings without the `paper:` "
            f"prefix; got {prefixed}.",
            err=True,
        )
        raise typer.Exit(4)
    non_numeric = [pid for pid in paper_ids if not (pid.isascii() and pid.isdigit())]
    if non_numeric:
        typer.echo(
            f"Error: {option_name} must be numeric paper ids; got {non_numeric}.",
            err=True,
        )
        raise typer.Exit(4)


def validate_dois(dois: list[str] | None, *, option_name: str = "--doi") -> None:
    """Validate DOI filters accepted by search endpoints."""
    if not dois:
        return
    if len(dois) > MAX_DOIS:
        typer.echo(
            f"Error: at most {MAX_DOIS} {option_name} values allowed; got {len(dois)}.",
            err=True,
        )
        raise typer.Exit(4)
    empty = [doi for doi in dois if not doi.strip()]
    if empty:
        typer.echo(f"Error: {option_name} values must be non-empty.", err=True)
        raise typer.Exit(4)


def validate_reference_seeds(
    paper_ids: list[str] | None,
    dois: list[str] | None,
) -> tuple[list[str], list[str]]:
    """Trim and validate ``/papers/reference`` seeds.

    ``--paper-id`` values may carry a ``paper:`` prefix (stripped). Combined
    length is capped at ``MAX_REFERENCE_SEEDS`` before dedupe. At least one
    side must be non-empty after trimming.
    """
    normalized_ids = _normalize_reference_paper_ids(paper_ids)
    normalized_dois = _normalize_reference_dois(dois)
    if not normalized_ids and not normalized_dois:
        typer.echo("Error: at least one of --paper-id / --doi is required.", err=True)
        raise typer.Exit(4)
    total = len(normalized_ids) + len(normalized_dois)
    if total > MAX_REFERENCE_SEEDS:
        typer.echo(
            f"Error: --paper-id and --doi together must be <= {MAX_REFERENCE_SEEDS} "
            f"before dedupe; got {total}.",
            err=True,
        )
        raise typer.Exit(4)
    return normalized_ids, normalized_dois


def _normalize_reference_paper_ids(paper_ids: list[str] | None) -> list[str]:
    if not paper_ids:
        return []
    normalized: list[str] = []
    for raw in paper_ids:
        value = raw.strip()
        if not value:
            typer.echo("Error: --paper-id values must be non-empty.", err=True)
            raise typer.Exit(4)
        if value.startswith("paper:"):
            value = value.split(":", 1)[1]
        if not value:
            typer.echo(
                "Error: --paper-id values must be numeric strings after stripping "
                "a `paper:` prefix.",
                err=True,
            )
            raise typer.Exit(4)
        if not (value.isascii() and value.isdigit()):
            typer.echo(
                f"Error: --paper-id must be a numeric paper id; got {raw!r}.",
                err=True,
            )
            raise typer.Exit(4)
        normalized.append(value)
    return normalized


def _normalize_reference_dois(dois: list[str] | None) -> list[str]:
    if not dois:
        return []
    normalized: list[str] = []
    for raw in dois:
        value = raw.strip()
        if not value:
            typer.echo("Error: --doi values must be non-empty.", err=True)
            raise typer.Exit(4)
        normalized.append(value)
    return normalized


__all__ = [
    "DEFAULT_LKM_INDEX_ID",
    "DEFAULT_SEARCH_LIMIT",
    "MAX_DOIS",
    "MAX_KEYWORDS",
    "MAX_KEYWORD_LENGTH",
    "MAX_LIMIT",
    "MAX_OFFSET",
    "MAX_PAPER_IDS",
    "MAX_REFERENCE_SEEDS",
    "MAX_VARIABLE_IDS",
    "LKMClient",
    "emit",
    "run_request",
    "validate_dois",
    "validate_keywords",
    "validate_lkm_index",
    "validate_lkm_server",
    "validate_paper_ids",
    "validate_publication_dates",
    "validate_reference_seeds",
    "validate_search_window",
]
