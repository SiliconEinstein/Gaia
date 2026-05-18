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
    # S8 / audit §H.4 — split the overloaded ``target_invalid`` kind
    # into four distinct kinds so downstream dispatch can distinguish
    # the four shapes (missing pyproject / missing source root /
    # missing __init__.py / TOML parse failure). All four map to the
    # same exit code as the parent for backwards compatibility.
    "prewrite.target_no_pyproject": EXIT_SYSTEM_IO,
    "prewrite.target_no_source_root": EXIT_SYSTEM_IO,
    "prewrite.target_no_init_py": EXIT_SYSTEM_IO,
    "prewrite.target_bad_toml": EXIT_SYSTEM_IO,
    "prewrite.target_missing": EXIT_SYSTEM_IO,
    "prewrite.target_not_gaia_package": EXIT_SYSTEM_IO,
    # S3 / audit §D.1+§D.2 — reserved-role rejection (priors.py /
    # review.py / reviews/<sub>.py) for Knowledge-emitting verbs.
    "prewrite.target_role_forbidden": EXIT_COLLISION_OR_REF,
    "prewrite.syntax": EXIT_INPUT_SYNTAX,
    "prewrite.expr_unsafe": EXIT_INPUT_SYNTAX,
    "prewrite.collision": EXIT_COLLISION_OR_REF,
    "prewrite.reference_unresolved": EXIT_COLLISION_OR_REF,
    "prewrite.order_structure": EXIT_PREWRITE_STRUCTURAL,
    "prewrite.self_loop": EXIT_PREWRITE_STRUCTURAL,
    # R3 warning kinds — level=warning, but kind→code is still meaningful
    # for downstream consumers building dispatch tables.
    "prewrite.label_shadow": EXIT_OK,
    "prewrite.deprecated_ref": EXIT_OK,
    "postwrite.compile_fail": EXIT_PREWRITE_STRUCTURAL,
    "postwrite.check_fail": EXIT_PREWRITE_STRUCTURAL,
    # S9 / audit §F.1 — snapshot-rollback diagnostic when postwrite
    # fails. Informational; the underlying error already carries the
    # rollback context, so the snapshot kind maps to the parent's
    # exit code for consistency.
    "writer.rolled_back": EXIT_PREWRITE_STRUCTURAL,
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

    S4 / audit §H.1 / chenkun #3 — the ``group`` field replaces the
    hardcoded ``"gaia author"`` prefix in :func:`render_human`. The
    envelope carries the command group ("author" / "pkg" / "bayes")
    so the human renderer can prefix correctly. JSON consumers are
    unaffected: ``to_dict()`` does not surface the group, since the
    verb name already carries its namespace (``pkg.scaffold`` /
    ``bayes.Binomial``).
    """

    verb: str
    status: AuthorStatus = "ok"
    code: int = EXIT_OK
    payload: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    group: str = "author"

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


def infer_group(verb: str) -> str:
    """Infer the cli command group from the verb namespace.

    S4 / audit §H.1 / chenkun #3 — verbs carry their group in the
    namespaced form (``pkg.scaffold``, ``bayes.Binomial``); strip it
    out to get the group name. Bare verbs without a dot fall through
    to ``"author"`` (the original cli group + the historic default).
    """
    if "." in verb:
        head, _, _ = verb.partition(".")
        if head == "pkg":
            return "pkg"
        if head == "bayes":
            return "bayes"
    if verb in {"scaffold", "add_module"}:
        return "pkg"
    return "author"


def render_human(result: AuthorResult) -> str:
    """Render an :class:`AuthorResult` as a short human-readable summary.

    The text form is a courtesy; the JSON form is the contract. We keep it
    deliberately short — no boxes, no tables — so it stays useful when a
    human is scanning a flood of verb invocations from an agent run.

    S4 / audit §H.1 / chenkun #3 — the prefix is now
    ``gaia <group> <verb>`` where ``group`` comes from
    :attr:`AuthorResult.group` (verb-emitter sets it; defaults to
    ``"author"`` for backwards compat with the bulk of verbs). Falls
    back to :func:`infer_group` when the group is the default and the
    verb is namespaced.
    """
    lines: list[str] = []
    glyph = "ok" if result.status == "ok" else f"error[{result.code}]"
    group = result.group
    if group == "author":
        group = infer_group(result.verb)
    # For namespaced verbs, the verb already carries the group prefix
    # (``bayes.Binomial``), so we drop the dotted head to avoid the
    # ugly ``gaia bayes bayes.Binomial`` shape.
    display_verb = result.verb
    if "." in display_verb:
        head, sep, tail = display_verb.partition(".")
        if head in {"pkg", "bayes"}:
            display_verb = tail
    lines.append(f"gaia {group} {display_verb}: {glyph}")
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
