"""Tests for ``gaia example <flavor>`` show-cli verbs.

The verbs do not execute the printed commands — they hand the user a
runnable bash script. Tests focus on:

* default-mode stdout shape (shebang + sequence body)
* ``--target NAME`` substitution rewrites both the ``--target ./...``
  flag occurrences and the bare placeholder used inside the inline
  ``python -c`` cleanup blocks
* ``--out FILE`` writes a syntactically-valid bash script (validated
  via ``bash -n``); refuses to overwrite an existing file unless
  ``--force`` is also passed
* ``gaia example --help`` lists both subverbs
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


# --------------------------------------------------------------------------- #
# Group-level help                                                            #
# --------------------------------------------------------------------------- #


def test_example_group_help_lists_both_subverbs() -> None:
    result = runner.invoke(app, ["example", "--help"])
    assert result.exit_code == 0, result.output
    assert "galileo" in result.output
    assert "mendel" in result.output


# --------------------------------------------------------------------------- #
# Parametrised per-flavor checks                                              #
# --------------------------------------------------------------------------- #


_FLAVOR_PLACEHOLDER = {
    "galileo": "./galileo-cli-mirror-gaia",
    "mendel": "./mendel-cli-mirror-gaia",
}


@pytest.mark.parametrize("flavor", ["galileo", "mendel"])
def test_default_prints_runnable_script(flavor: str) -> None:
    """Default mode prints to stdout starting with a shebang."""
    result = runner.invoke(app, ["example", flavor])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("#!/usr/bin/env bash\n"), result.output[:200]
    # Set -e bash safety prelude is part of the bundled script.
    assert "set -euo pipefail" in result.output
    # Script must drive ``gaia pkg scaffold`` as its first invocation.
    assert "gaia pkg scaffold" in result.output


@pytest.mark.parametrize("flavor", ["galileo", "mendel"])
def test_default_target_placeholder_is_present(flavor: str) -> None:
    """No-arg invocation leaves the default placeholder verbatim."""
    result = runner.invoke(app, ["example", flavor])
    assert result.exit_code == 0, result.output
    assert _FLAVOR_PLACEHOLDER[flavor] in result.output


@pytest.mark.parametrize("flavor", ["galileo", "mendel"])
def test_target_substitution(flavor: str) -> None:
    """``--target NAME`` substitutes both ``--target ./...`` and the bare form."""
    placeholder = _FLAVOR_PLACEHOLDER[flavor]
    bare = placeholder.lstrip("./")

    result = runner.invoke(app, ["example", flavor, "--target", "./my-demo"])
    assert result.exit_code == 0, result.output
    # Placeholder in both forms must be gone from the substantive body.
    # (Stripping the script's own header comment, which mentions the new
    # target string by design.)
    body = result.output
    assert placeholder not in body, "default placeholder leaked into --target output"
    assert "--target ./my-demo" in body
    # Bare placeholder occurs inside the inline ``python -c`` cleanup
    # block; it must also be rewritten.
    assert bare not in body, "bare placeholder leaked into --target output"
    assert "my-demo" in body


@pytest.mark.parametrize("flavor", ["galileo", "mendel"])
def test_out_writes_file_passing_bash_n(flavor: str, tmp_path: Path) -> None:
    """``--out FILE`` writes a file; ``bash -n`` accepts it."""
    out = tmp_path / "walkthrough.sh"
    result = runner.invoke(app, ["example", flavor, "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    text = out.read_text()
    assert text.startswith("#!/usr/bin/env bash\n")

    # Validate bash syntax of the produced script.
    check = subprocess.run(
        ["bash", "-n", str(out)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr


@pytest.mark.parametrize("flavor", ["galileo", "mendel"])
def test_out_refuses_to_overwrite_without_force(flavor: str, tmp_path: Path) -> None:
    """``--out FILE`` refuses to overwrite an existing file."""
    out = tmp_path / "walkthrough.sh"
    out.write_text("pre-existing-content\n")

    result = runner.invoke(app, ["example", flavor, "--out", str(out)])
    assert result.exit_code != 0
    assert "refusing to overwrite" in (
        result.output + (result.stderr if hasattr(result, "stderr") else "")
    )
    # Existing content is preserved.
    assert out.read_text() == "pre-existing-content\n"


@pytest.mark.parametrize("flavor", ["galileo", "mendel"])
def test_out_force_overwrites(flavor: str, tmp_path: Path) -> None:
    """``--out FILE --force`` overwrites an existing file."""
    out = tmp_path / "walkthrough.sh"
    out.write_text("pre-existing-content\n")

    result = runner.invoke(app, ["example", flavor, "--out", str(out), "--force"])
    assert result.exit_code == 0, result.output
    text = out.read_text()
    assert text.startswith("#!/usr/bin/env bash\n")
    assert text != "pre-existing-content\n"


# --------------------------------------------------------------------------- #
# Substantive sequence assertions                                             #
# --------------------------------------------------------------------------- #


def test_galileo_walkthrough_drives_full_authoring_surface() -> None:
    """Galileo script touches the expected cli verbs."""
    result = runner.invoke(app, ["example", "galileo"])
    assert result.exit_code == 0
    body = result.output
    for fragment in (
        "gaia pkg scaffold",
        "gaia author note",
        "gaia author claim",
        "gaia author derive",
        "gaia author equal",
        "gaia author contradict",
        "gaia pkg add-module",
        "gaia author register-prior",
        "gaia build compile",
        "gaia build check",
    ):
        assert fragment in body, f"missing fragment: {fragment}"


def test_mendel_walkthrough_drives_bayes_and_variable_surface() -> None:
    """Mendel script touches bayes + Variable + multi-file surfaces."""
    result = runner.invoke(app, ["example", "mendel"])
    assert result.exit_code == 0
    body = result.output
    for fragment in (
        "gaia pkg scaffold",
        "gaia author variable",
        "gaia author note",
        "gaia author claim",
        "gaia author exclusive",
        "gaia author observe",
        "gaia author derive",
        "gaia bayes model",
        "gaia bayes compare",
        "gaia pkg add-module",
        "gaia author register-prior",
        "gaia build compile",
        "gaia build check",
        "Binomial(",
        "BetaBinomial(",
    ):
        assert fragment in body, f"missing fragment: {fragment}"
