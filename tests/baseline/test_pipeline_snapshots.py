"""Snapshot tests for the compile / check / infer / render / starmap pipeline.

These verbs all share a common shape: they read a knowledge package on disk
and write artifacts under `<pkg>/.gaia/`. We snapshot stdout / stderr / exit
only — the byte-comparison of the artifact tree is Stage A3 / Phase 0 Layer 3.

Inputs are seeded by copying the bundled `examples/galileo-v0-5-gaia/` into
tmp_path, so the captured output is reproducible across machines as long as
the example package and the compile pipeline are unchanged.

Determinism notes
-----------------
* Timing strings like "2ms" are masked to <MS> by the conftest masker.
* Absolute paths under tmp_path are masked to <TMP>.
* The galileo example is a self-contained, dependency-free knowledge
  package, so its compile + BP run is fully deterministic for fixed input.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.baseline.conftest import cli_snapshot

pytestmark = pytest.mark.pr_gate


# --------------------------------------------------------------------------- #
# compile                                                                     #
# --------------------------------------------------------------------------- #


def test_compile_minimal_pkg_snapshot(minimal_pkg: Path, run_gaia, snapshot) -> None:
    """Gaia build compile <minimal pkg> → exit 0, IR hash printed."""
    result = run_gaia("build", "compile", str(minimal_pkg))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_compile_galileo_snapshot(galileo_pkg: Path, run_gaia, snapshot) -> None:
    """Gaia build compile examples/galileo-v0-5-gaia → exit 0, deterministic IR hash."""
    result = run_gaia("build", "compile", str(galileo_pkg))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# check                                                                       #
# --------------------------------------------------------------------------- #


def test_check_galileo_snapshot(compiled_galileo: Path, run_gaia, snapshot) -> None:
    """Gaia build check examples/galileo-v0-5-gaia after compile → text report."""
    result = run_gaia("build", "check", str(compiled_galileo))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_check_brief_galileo_snapshot(compiled_galileo: Path, run_gaia, snapshot) -> None:
    """Gaia build check --brief examples/galileo-v0-5-gaia → text + warrant brief."""
    result = run_gaia("build", "check", str(compiled_galileo), "--brief")
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_check_warrants_galileo_snapshot(compiled_galileo: Path, run_gaia, snapshot) -> None:
    """Gaia build check --warrants examples/galileo-v0-5-gaia → v6 warrant manifest dump."""
    result = run_gaia("build", "check", str(compiled_galileo), "--warrants")
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# infer                                                                       #
# --------------------------------------------------------------------------- #


def test_infer_galileo_snapshot(compiled_galileo: Path, run_gaia, snapshot) -> None:
    """Gaia run infer examples/galileo-v0-5-gaia → beliefs written, exit 0."""
    result = run_gaia("run", "infer", str(compiled_galileo))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# render                                                                      #
# --------------------------------------------------------------------------- #


def test_render_docs_galileo_snapshot(inferred_galileo: Path, run_gaia, snapshot) -> None:
    """Gaia run render --target docs after infer → docs/detailed-reasoning.md."""
    result = run_gaia("run", "render", str(inferred_galileo), "--target", "docs")
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# starmap                                                                     #
# --------------------------------------------------------------------------- #


def test_starmap_dot_galileo_snapshot(
    inferred_galileo: Path, run_gaia, snapshot, tmp_path: Path
) -> None:
    """Gaia inspect starmap --format dot → stdout summary, dot file written."""
    out = tmp_path / "starmap.dot"
    result = run_gaia(
        "inspect", "starmap", str(inferred_galileo), "--format", "dot", "--out", str(out)
    )
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_starmap_html_galileo_snapshot(
    inferred_galileo: Path, run_gaia, snapshot, tmp_path: Path
) -> None:
    """Gaia inspect starmap (default html) → stdout summary, html file written."""
    out = tmp_path / "starmap.html"
    result = run_gaia("inspect", "starmap", str(inferred_galileo), "--out", str(out))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot
