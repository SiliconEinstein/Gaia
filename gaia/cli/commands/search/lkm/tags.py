"""List the paper tags available for LKM search filters."""

from pathlib import Path
from typing import Annotated

import typer

from gaia.cli.commands.search.lkm._shared import (
    DEFAULT_LKM_INDEX_ID,
    emit,
    run_request,
    validate_lkm_index,
)


def tags_command(
    index: Annotated[
        str, typer.Option("--index", "--server", help="Configured LKM index id.")
    ] = DEFAULT_LKM_INDEX_ID,
    out: Annotated[
        Path | None, typer.Option("--out", help="Write JSON to PATH (atomic) instead of stdout.")
    ] = None,
) -> None:
    """List available paper tags and their English descriptions for free."""
    payload = run_request("GET", "/papers/tags", index_id=validate_lkm_index(index))
    emit(payload, out)
