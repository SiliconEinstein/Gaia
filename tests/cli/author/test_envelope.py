"""Envelope-shape contract tests for ``gaia author <verb>`` output.

The envelope is the agent-consumer contract — every author verb produces
the same JSON shape so the consumer parses once and dispatches on
``verb``. These tests assert the shape across the three implemented
verbs and the two stubbed verbs.
"""

from __future__ import annotations

import json
import re

import pytest
from typer.testing import CliRunner

from gaia.cli.commands.author._envelope import (
    EXIT_INPUT_SYNTAX,
    EXIT_OK,
    EXIT_SYSTEM_IO,
    AuthorResult,
    Diagnostic,
    exit_code_for_diagnostic,
    render_human,
)
from gaia.cli.main import app

from .conftest import FixturePackage

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


_ENVELOPE_TOP_KEYS = {"status", "code", "verb", "payload", "warnings", "diagnostics"}

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")


def _strip_ansi(s: str) -> str:
    """Remove ANSI color escape sequences from ``s``.

    Typer's rich-based help renderer color-segments each part of a long
    flag (e.g. ``--from-file`` becomes three ANSI-wrapped spans:
    ``-``, ``-from``, ``-file``) so the raw flag name does not survive
    as a contiguous substring of ``result.output`` in CI environments
    where color is enabled. Stripping the escapes first restores the
    plain flag spelling for substring assertions.
    """
    return _ANSI_RE.sub("", s)


def _parse(output: str) -> dict[str, object]:
    """Pluck the trailing JSON line from `result.output` (skips stderr noise)."""
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def test_envelope_shape_ok_path(gaia_package: FixturePackage) -> None:
    """Happy-path output carries every envelope field with the right types."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "A new claim.",
            "--label",
            "fresh_claim",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert set(envelope.keys()) == _ENVELOPE_TOP_KEYS
    assert envelope["status"] == "ok"
    assert envelope["code"] == 0
    assert envelope["verb"] == "claim"
    assert isinstance(envelope["payload"], dict)
    assert isinstance(envelope["warnings"], list)
    assert isinstance(envelope["diagnostics"], list)


def test_envelope_shape_error_path(gaia_package: FixturePackage) -> None:
    """Pre-write failure preserves envelope shape and exit code semantics."""
    # Label collision: ``hypothesis`` is seeded by the fixture's __init__.py.
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Different content.",
            "--label",
            "hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code != 0
    envelope = _parse(result.output)
    assert set(envelope.keys()) == _ENVELOPE_TOP_KEYS
    assert envelope["status"] == "error"
    assert envelope["verb"] == "claim"
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics, "expected at least one diagnostic on error path"
    first = diagnostics[0]
    assert isinstance(first, dict)
    assert first["source"] == "prewrite"
    assert first["level"] == "error"
    assert first["kind"] == "prewrite.collision"


def test_envelope_shape_compose_missing_from_file() -> None:
    """``gaia author compose`` requires --from-file.

    Compose is live via the file-based validate-and-register path;
    omitting ``--from-file`` is a Typer usage error. Typer surfaces it
    through its own usage path, so we just assert the exit code is
    non-zero (Typer convention: 2).
    """
    result = runner.invoke(app, ["author", "compose"])
    assert result.exit_code != 0, result.output
    # Strip ANSI before substring assertion: in CI environments where
    # color is enabled, typer's rich-based help renderer splits
    # ``--from-file`` into three independently-coloured spans (``-``,
    # ``-from``, ``-file``), so neither the flag nor any sub-token
    # survives as a contiguous substring of the raw ``result.output``.
    # Stripping the escapes restores the plain spelling and keeps the
    # flag-name contract intact.
    assert "--from-file" in _strip_ansi(result.output)


def test_human_rendering_smoke(gaia_package: FixturePackage) -> None:
    """`--human` produces non-JSON output that still contains the verb name."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Friendly claim.",
            "--label",
            "friendly",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author claim" in result.output
    # No leading "{" means the line isn't a JSON envelope.
    assert not result.output.strip().startswith("{")


def test_exit_code_table_covers_dispatch_kinds() -> None:
    """The kind→exit table covers the kinds we emit from the cli surface."""
    expected = {
        "prewrite.target_missing": EXIT_SYSTEM_IO,
        "prewrite.target_not_gaia_package": EXIT_SYSTEM_IO,
        "prewrite.target_invalid": EXIT_SYSTEM_IO,
        "prewrite.syntax": EXIT_INPUT_SYNTAX,
        "prewrite.collision": 3,
        "prewrite.reference_unresolved": 3,
        "prewrite.order_structure": 1,
        "prewrite.self_loop": 1,
        "postwrite.compile_fail": 1,
        "postwrite.check_fail": 1,
        "stub.not_implemented": EXIT_INPUT_SYNTAX,
    }
    for kind, code in expected.items():
        assert exit_code_for_diagnostic(kind) == code, kind


def test_human_renderer_unit() -> None:
    """`render_human` works on a synthesised AuthorResult without invoking Typer."""
    result = AuthorResult(
        verb="claim",
        status="ok",
        code=EXIT_OK,
        payload={"label": "x", "snippet": "x = claim('y')\n"},
    )
    rendered = render_human(result)
    assert rendered.startswith("gaia author claim: ok")
    assert "label: x" in rendered


def test_diagnostic_serialises_where() -> None:
    """Diagnostic.to_dict omits empty where and keeps populated where."""
    bare = Diagnostic(kind="prewrite.syntax", level="error", message="boom", source="prewrite")
    assert "where" not in bare.to_dict()
    withloc = Diagnostic(
        kind="prewrite.syntax",
        level="error",
        message="boom",
        source="prewrite",
        where={"line": 2},
    )
    assert withloc.to_dict()["where"] == {"line": 2}
