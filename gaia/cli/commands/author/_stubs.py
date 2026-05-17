"""Placeholder verbs for ``gaia author compose`` and ``gaia author composition``.

Per R1·❓-A=A1 (locked in 协作单 §三), the composition primitives stay
out of the R1 cut: their content is fundamentally an arbitrary-Python
function body, not a CLI-flag-shaped op. Forcing a CLI surface for them
would either reinvent a sub-DSL inside argv (bad) or have the CLI
write Python source into a file (worse — that's a code editor, not an
author tool). Both options were considered + rejected.

Shipping a stub at R1 keeps the ``gaia author`` namespace
complete-looking so an agent (or a `--help` reader) immediately knows
the verb exists and how to use it instead. The stub emits the standard
envelope with a single ``stub.not_implemented`` diagnostic and exits
with semantic code ``EXIT_INPUT_SYNTAX`` (``2``) — the agent's natural
fallback is to write the composition via the Python decorator directly,
which the diagnostic message points at.
"""

from __future__ import annotations

import typer

from gaia.cli.commands.author._envelope import (
    AuthorResult,
    Diagnostic,
    emit,
    exit_code_for_diagnostic,
)

_COMPOSE_STUB_MESSAGE = (
    "`gaia author compose` is not yet implemented (deferred to R2+). "
    "Use the `@compose` decorator directly in your package's "
    "`.gaia.py` source — see `gaia.engine.lang.runtime.composition` "
    "for the API. Tracking: 协作单 BOmHwyFRCixqy0k7gR3cCNMInId §六."
)
_COMPOSITION_STUB_MESSAGE = (
    "`gaia author composition` is not yet implemented (deferred to R2+). "
    "Use the `@composition` decorator directly in your package's "
    "`.gaia.py` source — see `gaia.engine.lang.runtime.composition` "
    "for the API. Tracking: 协作单 BOmHwyFRCixqy0k7gR3cCNMInId §六."
)


def _emit_stub(verb: str, message: str, *, human: bool) -> None:
    """Emit the canonical not-implemented envelope for the two composition stubs."""
    diag = Diagnostic(
        kind="stub.not_implemented",
        level="error",
        message=message,
        source="stub",
    )
    result = AuthorResult(
        verb=verb,
        status="error",
        code=exit_code_for_diagnostic(diag.kind),
        payload={},
        diagnostics=[diag],
    )
    emit(result, human=human)


def compose_command(
    human: bool = typer.Option(
        False,
        "--human",
        help="Render the envelope in human-readable form instead of JSON.",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    """``gaia author compose`` — stub (deferred to R2+)."""
    del json_
    _emit_stub("compose", _COMPOSE_STUB_MESSAGE, human=human)


def composition_command(
    human: bool = typer.Option(
        False,
        "--human",
        help="Render the envelope in human-readable form instead of JSON.",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    """``gaia author composition`` — stub (deferred to R2+)."""
    del json_
    _emit_stub("composition", _COMPOSITION_STUB_MESSAGE, human=human)


__all__ = ["compose_command", "composition_command"]
