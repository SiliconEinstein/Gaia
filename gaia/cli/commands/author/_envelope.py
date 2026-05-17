"""Uniform JSON envelope + semantic exit codes for ``gaia author <verb>``.

Per 协作单 §五, every author verb returns the same envelope shape so an
agent consumer can ``json.loads(stdout)`` once and dispatch on ``verb`` to
interpret ``payload``. The envelope is:

.. code-block:: json

    {
      "status": "ok" | "error",
      "code": 0 | 1 | 2 | 3 | 4,
      "verb": "<verb_name>",
      "payload": { ... },
      "warnings": [ "<str>", ... ],
      "diagnostics": [
        {
          "kind": "<str>",
          "level": "error" | "warning",
          "message": "<str>",
          "source": "prewrite" | "postwrite" | "stub",
          "where": { ... }
        }
      ]
    }

Semantic exit codes (R1·❓-6=A dispatch, locked in §三 of the 协作单):

* ``0`` — success.
* ``1`` — pre-write semantic failure (collision-refs, structural).
* ``2`` — input syntax error / unimplemented stub.
* ``3`` — collision-or-ref error (label conflict, missing reference).
* ``4`` — system / IO error (filesystem, target not found).

The pre-write ``_prewrite`` module maps invariant-failure kinds onto these
codes through :func:`exit_code_for_diagnostic`. Post-write check failures
use ``1`` with ``source: "postwrite"``.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Literal

import typer

# --------------------------------------------------------------------------- #
# Exit-code constants                                                         #
# --------------------------------------------------------------------------- #

EXIT_OK = 0
EXIT_PREWRITE_STRUCTURAL = 1
EXIT_INPUT_SYNTAX = 2
EXIT_COLLISION_OR_REF = 3
EXIT_SYSTEM_IO = 4

# Mapping from prewrite invariant kinds → semantic exit code. Kinds not
# explicitly listed fall through to EXIT_PREWRITE_STRUCTURAL (1).
_KIND_TO_EXIT = {
    "prewrite.target_invalid": EXIT_SYSTEM_IO,
    "prewrite.target_missing": EXIT_SYSTEM_IO,
    "prewrite.target_not_gaia_package": EXIT_SYSTEM_IO,
    "prewrite.syntax": EXIT_INPUT_SYNTAX,
    "prewrite.collision": EXIT_COLLISION_OR_REF,
    "prewrite.reference_unresolved": EXIT_COLLISION_OR_REF,
    "prewrite.order_structure": EXIT_PREWRITE_STRUCTURAL,
    "prewrite.self_loop": EXIT_PREWRITE_STRUCTURAL,
    "postwrite.compile_fail": EXIT_PREWRITE_STRUCTURAL,
    "postwrite.check_fail": EXIT_PREWRITE_STRUCTURAL,
    "stub.not_implemented": EXIT_INPUT_SYNTAX,
}


def exit_code_for_diagnostic(kind: str) -> int:
    """Return the semantic exit code that matches a diagnostic kind."""
    return _KIND_TO_EXIT.get(kind, EXIT_PREWRITE_STRUCTURAL)


# --------------------------------------------------------------------------- #
# Diagnostic + envelope dataclasses                                           #
# --------------------------------------------------------------------------- #

DiagnosticLevel = Literal["error", "warning"]
DiagnosticSource = Literal["prewrite", "postwrite", "stub"]


@dataclass
class Diagnostic:
    """Structured error / warning entry attached to an author-verb envelope."""

    kind: str
    level: DiagnosticLevel
    message: str
    source: DiagnosticSource
    where: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "level": self.level,
            "message": self.message,
            "source": self.source,
        }
        if self.where:
            out["where"] = dict(self.where)
        return out


AuthorStatus = Literal["ok", "error", "aborted"]


@dataclass
class AuthorResult:
    """Envelope returned by every ``gaia author <verb>`` invocation.

    R2 adds the ``"aborted"`` status for user-driven interactive aborts;
    R1 only used ``"ok"`` / ``"error"``. ``"aborted"`` carries ``code=0``
    by convention (the run did not fail — the user opted not to proceed).
    """

    verb: str
    status: AuthorStatus = "ok"
    code: int = EXIT_OK
    payload: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "code": self.code,
            "verb": self.verb,
            "payload": dict(self.payload),
            "warnings": list(self.warnings),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }


# --------------------------------------------------------------------------- #
# Emission                                                                    #
# --------------------------------------------------------------------------- #


def render_human(result: AuthorResult) -> str:
    """Render an :class:`AuthorResult` as a short human-readable summary.

    The text form is a courtesy; the JSON form is the contract. We keep it
    deliberately short — no boxes, no tables — so it stays useful when a
    human is scanning a flood of verb invocations from an agent run.
    """
    lines: list[str] = []
    glyph = "ok" if result.status == "ok" else f"error[{result.code}]"
    lines.append(f"gaia author {result.verb}: {glyph}")
    if result.payload:
        for key, value in result.payload.items():
            lines.append(f"  {key}: {value}")
    for warning in result.warnings:
        lines.append(f"  warning: {warning}")
    for diag in result.diagnostics:
        lines.append(f"  {diag.level} [{diag.kind}] {diag.message}")
    return "\n".join(lines)


def emit(result: AuthorResult, *, human: bool) -> None:
    """Write the envelope to stdout in either JSON or human-readable form.

    Always raises :class:`typer.Exit` carrying ``result.code`` so the
    process exit status is the contracted semantic code.
    """
    if human:
        typer.echo(render_human(result))
    else:
        typer.echo(json.dumps(result.to_dict(), ensure_ascii=False))
    if result.code != EXIT_OK:
        # Force stdout to flush before Exit raises — Typer/Click swallow the
        # output buffer otherwise when CliRunner captures.
        sys.stdout.flush()
    raise typer.Exit(result.code)


def system_error(verb: str, message: str, *, kind: str = "prewrite.target_invalid") -> AuthorResult:
    """Build a system-error envelope for an unrecoverable I/O failure.

    Used for the cases where an exception escaped before pre-write could
    even be entered (filesystem races, permission denied, etc.).
    """
    diag = Diagnostic(kind=kind, level="error", message=message, source="prewrite")
    return AuthorResult(
        verb=verb,
        status="error",
        code=exit_code_for_diagnostic(kind),
        diagnostics=[diag],
    )
