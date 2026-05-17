"""Shared helpers for ``gaia author`` verbs.

R2 lifts the duplicate ``_parse_metadata`` / ``_split_csv`` / metadata-error
envelope helpers out of every per-verb file into one place. The shape stays
identical to what R1's ``claim`` / ``equal`` / ``derive`` did inline — this
module is a refactor, not a behavior change.
"""

from __future__ import annotations

import json
from typing import Any

from gaia.cli.commands.author._envelope import (
    AuthorResult,
    Diagnostic,
    emit,
    exit_code_for_diagnostic,
)


def parse_metadata(metadata_json: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """Decode the ``--metadata`` JSON option into a dict (or return an error string)."""
    if metadata_json is None:
        return None, None
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        return None, f"--metadata is not valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return None, "--metadata must encode a JSON object (got non-object value)"
    return parsed, None


def split_csv(value: str | None) -> list[str]:
    """Split a comma-separated CLI option into a clean list of tokens."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def emit_syntax_error(
    verb: str,
    message: str,
    *,
    target: str,
    human: bool,
) -> None:
    """Emit a pre-write syntax-error envelope and exit.

    Used by per-verb option parsers when an option is shaped wrong (bad JSON,
    empty mutually-required input, etc.) — surfaces the failure with the
    standard ``prewrite.syntax`` kind + ``EXIT_INPUT_SYNTAX`` (``2``) code
    before the runner pipeline gets called.
    """
    diag = Diagnostic(
        kind="prewrite.syntax",
        level="error",
        message=message,
        source="prewrite",
    )
    result = AuthorResult(
        verb=verb,
        status="error",
        code=exit_code_for_diagnostic(diag.kind),
        payload={"target": target},
        diagnostics=[diag],
    )
    emit(result, human=human)


__all__ = ["emit_syntax_error", "parse_metadata", "split_csv"]
