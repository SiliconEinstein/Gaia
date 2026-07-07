"""``gaia search lkm feedback`` — POST /feedback."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from gaia.cli.commands.search.lkm._shared import (
    DEFAULT_LKM_INDEX_ID,
    emit,
    run_request,
    validate_lkm_index,
)
from gaia.cli.commands.search.lkm.docs import APIFOX_FEEDBACK_URL
from gaia.cli.commands.search.lkm.policy import build_feedback_body


class FeedbackType(StrEnum):
    """Feedback categories accepted by LKM."""

    BUG = "bug"
    FEATURE = "feature"
    QUESTION = "question"


_FEEDBACK_EPILOG = (
    "Submit LKM service/data feedback. This endpoint writes a feedback record "
    "and returns no knowledge content. Link at most one target: --gcn-id for a "
    "node or --paper-metadata-id for a paper metadata record.\n\n"
    f"API docs: {APIFOX_FEEDBACK_URL}\n"
    "Endpoint links: gaia search lkm docs"
)


def feedback_command(
    content: Annotated[
        str,
        typer.Argument(help="Feedback body, non-empty after trimming."),
    ],
    feedback_type: Annotated[
        FeedbackType,
        typer.Option(
            "--type",
            help="Feedback type.",
            case_sensitive=False,
        ),
    ],
    index: Annotated[
        str,
        typer.Option("--index", "--server", help="Configured LKM index id."),
    ] = DEFAULT_LKM_INDEX_ID,
    gcn_id: Annotated[
        str | None,
        typer.Option("--gcn-id", help="Optional linked GCN node id."),
    ] = None,
    paper_metadata_id: Annotated[
        str | None,
        typer.Option("--paper-metadata-id", help="Optional linked paper metadata id."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write JSON to PATH (atomic) instead of stdout."),
    ] = None,
) -> None:
    """Submit LKM service/data feedback (POST /feedback)."""
    index_id = validate_lkm_index(index)
    stripped = content.strip()
    if not stripped:
        typer.echo("Error: feedback content must be non-empty.", err=True)
        raise typer.Exit(4)
    if gcn_id and paper_metadata_id:
        typer.echo(
            "Error: --gcn-id and --paper-metadata-id are mutually exclusive.",
            err=True,
        )
        raise typer.Exit(4)

    payload = run_request(
        "POST",
        "/feedback",
        json_body=build_feedback_body(
            feedback_type=feedback_type.value,
            content=stripped,
            gcn_id=gcn_id,
            paper_metadata_id=paper_metadata_id,
        ),
        index_id=index_id,
    )
    emit(payload, out, show_hint=False)


__all__ = ["_FEEDBACK_EPILOG", "feedback_command"]
