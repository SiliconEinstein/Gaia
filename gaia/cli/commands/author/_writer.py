"""File-append helper for ``gaia author`` verbs.

The writer is intentionally simple: append the generated snippet to the
target package's source ``__init__.py`` with a separating blank line.
Authoring more sophisticated edit ops (insert-before, rewrite-section,
multi-file) is on the R2 docket.

Returns the appended snippet plus a small location record so the verb's
JSON payload can carry the write target back to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class WriteResult:
    """Where + what got written."""

    path: Path
    appended: str


def append_statement(source_init_path: Path, generated_code: str) -> WriteResult:
    """Append ``generated_code`` to ``source_init_path`` with a blank-line separator.

    The file is read and rewritten in one shot so partial writes don't
    leave the source half-broken. The blank-line separator is only added
    when the existing tail does not already end with one blank line.
    """
    existing = source_init_path.read_text() if source_init_path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    if existing and not existing.endswith("\n\n"):
        existing += "\n"
    snippet = generated_code.rstrip() + "\n"
    source_init_path.write_text(existing + snippet)
    return WriteResult(path=source_init_path, appended=snippet)


__all__ = ["WriteResult", "append_statement"]
