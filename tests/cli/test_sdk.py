"""CLI E2E tests for ``gaia sdk`` — the first/primary authoring entry point.

Asserts:

* the ``--out`` directory is created;
* ``CHEATSHEET.md`` lands at the top tier of ``--out``;
* key API symbols (verbs / relations / scaffolds / typed terms / formula
  ops / distributions / bayes) appear in the generated per-module docs;
* the stdout contract: the cheatsheet path is printed BEFORE the full SDK
  docs pointer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def test_sdk_creates_out_dir_and_cheatsheet_at_top_tier(tmp_path: Path) -> None:
    """``gaia sdk --out`` creates the dir with ``CHEATSHEET.md`` at the top tier."""
    out = tmp_path / "gaia-sdk"
    result = runner.invoke(app, ["sdk", "--out", str(out)])
    assert result.exit_code == 0, result.output

    assert out.is_dir()
    cheatsheet = out / "CHEATSHEET.md"
    assert cheatsheet.exists(), "CHEATSHEET.md must be at the top tier of --out"
    # Top tier: directly under --out, not nested.
    assert cheatsheet.parent == out
    assert (out / "index.md").exists()


def test_sdk_default_out_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no ``--out``, the default ``./gaia-sdk/`` is created under cwd."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["sdk"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "gaia-sdk" / "CHEATSHEET.md").exists()


def test_sdk_generated_docs_contain_key_symbols(tmp_path: Path) -> None:
    """The generated module docs surface the documented public API."""
    out = tmp_path / "gaia-sdk"
    result = runner.invoke(app, ["sdk", "--out", str(out)])
    assert result.exit_code == 0, result.output

    lang_md = (out / "gaia_engine_lang.md").read_text()
    bayes_md = (out / "gaia_engine_bayes.md").read_text()

    # A representative spread across every surface family from the spec.
    for symbol in (
        "claim",
        "note",
        "question",
        "derive",
        "observe",
        "compute",
        "infer",
        "equal",
        "contradict",
        "exclusive",
        "associate",
        "decompose",
        "depends_on",
        "candidate_relation",
        "materialize",
        "compose",
        "composition",
        "register_prior",
        "Variable",
        "land",
        "implies",
        "forall",
        "exists",
        "Normal",
        "Beta",
        "Binomial",
        "Poisson",
    ):
        assert f"## `{symbol}`" in lang_md, f"missing {symbol} in lang reference"

    assert "## `model`" in bayes_md
    assert "## `compare`" in bayes_md


def test_sdk_no_private_symbols_leak(tmp_path: Path) -> None:
    """``_``-prefixed privates are filtered (mirrors mkdocstrings ``!^_``)."""
    out = tmp_path / "gaia-sdk"
    result = runner.invoke(app, ["sdk", "--out", str(out)])
    assert result.exit_code == 0, result.output
    lang_md = (out / "gaia_engine_lang.md").read_text()
    # No symbol heading starting with an underscore.
    assert "## `_" not in lang_md


def test_sdk_stdout_prints_cheatsheet_before_docs_pointer(tmp_path: Path) -> None:
    """Stdout contract: cheatsheet location echoed BEFORE the SDK docs pointer."""
    out = tmp_path / "gaia-sdk"
    result = runner.invoke(app, ["sdk", "--out", str(out)])
    assert result.exit_code == 0, result.output

    stdout = result.output
    cheatsheet_idx = stdout.find("CHEATSHEET.md")
    docs_idx = stdout.find("Full SDK reference")
    assert cheatsheet_idx != -1, f"cheatsheet line missing: {stdout!r}"
    assert docs_idx != -1, f"docs pointer line missing: {stdout!r}"
    assert cheatsheet_idx < docs_idx, "cheatsheet path must be printed before the docs pointer"
