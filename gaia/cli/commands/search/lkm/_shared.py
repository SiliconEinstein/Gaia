"""Search-specific argument caps for ``gaia search lkm``.

The index resolution, exit-code contract, and output plumbing live in
:mod:`gaia.cli._lkm_runtime` because ``gaia extract`` needs them too; this
module re-exports them so the search verbs keep a single import site, and adds
the pagination / filter caps that only the retrieval endpoints have.
"""

from __future__ import annotations

import typer

from gaia.cli._lkm_runtime import (
    DEFAULT_LKM_INDEX_ID,
    LKMClient,
    emit,
    run_request,
    validate_lkm_index,
    validate_lkm_server,
)

# Lexical-channel keyword cap, shared by knowledge / reasoning.
MAX_KEYWORDS = 10
# Per-call id caps.
MAX_OFFSET = 10000
MAX_LIMIT = 100
MAX_PAPER_IDS = 50
MAX_DOIS = 50
MAX_VARIABLE_IDS = 100


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
    non_numeric = [pid for pid in paper_ids if not pid.isdigit()]
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


__all__ = [
    "DEFAULT_LKM_INDEX_ID",
    "MAX_DOIS",
    "MAX_KEYWORDS",
    "MAX_LIMIT",
    "MAX_OFFSET",
    "MAX_PAPER_IDS",
    "MAX_VARIABLE_IDS",
    "LKMClient",
    "emit",
    "run_request",
    "validate_dois",
    "validate_lkm_index",
    "validate_lkm_server",
    "validate_paper_ids",
    "validate_search_window",
]
