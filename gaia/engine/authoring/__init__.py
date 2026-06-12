"""Public engine-side authoring API.

This package exposes authoring primitives for SDKs and downstream packages
without requiring callers to import Typer command modules. The CLI keeps its
envelope and exit-code translation; engine callers receive structured return
objects and exceptions-free failure reports.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from gaia.cli.commands.author._authored import ensure_authored_submodule
from gaia.cli.commands.author._common import split_csv_refs
from gaia.cli.commands.author._writer import WriteResult, append_statement
from gaia.engine.authoring._ops import ProposedAuthorOp

if TYPE_CHECKING:
    from gaia.engine.authoring._batch import (
        AuthorBatchResult,
        AuthorBatchWrite,
        AuthoringCheckSummary,
        AuthoringDiagnostic,
    )


def run_author_batch(
    target: str | Path,
    operations: list[ProposedAuthorOp],
    *,
    check: bool = True,
) -> AuthorBatchResult:
    """Write multiple author operations with one final validation pass."""
    from gaia.engine.authoring._batch import run_author_batch as _run_author_batch

    return _run_author_batch(target, operations, check=check)


def __getattr__(name: str) -> object:
    """Lazily expose batch authoring objects without importing CLI prewrite early."""
    if name in {
        "AuthorBatchResult",
        "AuthorBatchWrite",
        "AuthoringCheckSummary",
        "AuthoringDiagnostic",
    }:
        from gaia.engine.authoring import _batch

        return getattr(_batch, name)
    raise AttributeError(name)


__all__ = [
    "AuthorBatchResult",
    "AuthorBatchWrite",
    "AuthoringCheckSummary",
    "AuthoringDiagnostic",
    "ProposedAuthorOp",
    "WriteResult",
    "append_statement",
    "ensure_authored_submodule",
    "run_author_batch",
    "split_csv_refs",
]
