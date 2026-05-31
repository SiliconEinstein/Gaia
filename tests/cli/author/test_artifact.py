"""CLI E2E tests for ``gaia author artifact`` and ``gaia author figure``."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

from .conftest import FixturePackage

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _parse(output: str) -> dict[str, object]:
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def test_author_artifact_happy_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "artifact",
            "--dsl-binding-name",
            "liu2015_supplement",
            "--kind",
            "attachment",
            "--source",
            "Liu2015",
            "--locator",
            "Supplementary Data 1",
            "--path",
            "artifacts/attachments/liu2015.xlsx",
            "--description",
            "Digitized source data.",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["verb"] == "artifact"
    written = gaia_package.source_init.read_text()
    assert "liu2015_supplement = artifact(" in written
    assert "kind='attachment'" in written
    assert "source='Liu2015'" in written
    assert "path='artifacts/attachments/liu2015.xlsx'" in written


def test_author_figure_happy_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "figure",
            "--dsl-binding-name",
            "liu2015_fig3",
            "--source",
            "Liu2015",
            "--locator",
            "Fig. 3",
            "--path",
            "artifacts/figures/liu2015_fig3.png",
            "--caption",
            "Fibonacci scaling.",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "liu2015_fig3 = figure(" in written
    assert "source='Liu2015'" in written
    assert "locator='Fig. 3'" in written
    assert "caption='Fibonacci scaling.'" in written


def test_author_artifact_rejects_unsafe_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "artifact",
            "--dsl-binding-name",
            "bad_artifact",
            "--kind",
            "attachment",
            "--path",
            "../escape.txt",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.syntax"


def test_author_artifact_collision_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "artifact",
            "--dsl-binding-name",
            "hypothesis",
            "--kind",
            "attachment",
            "--path",
            "artifacts/file.txt",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3
