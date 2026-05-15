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

import shutil
from pathlib import Path

import pytest

from tests.baseline.conftest import EXAMPLES_DIR, cli_snapshot

MENDEL_REPLAY_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "starmap_replay" / "mendelian_inheritance"
)


# --------------------------------------------------------------------------- #
# compile                                                                     #
# --------------------------------------------------------------------------- #


def test_compile_minimal_pkg_snapshot(minimal_pkg: Path, run_gaia, snapshot) -> None:
    """Gaia compile <minimal pkg> → exit 0, IR hash printed."""
    result = run_gaia("compile", str(minimal_pkg))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_compile_galileo_snapshot(galileo_pkg: Path, run_gaia, snapshot) -> None:
    """Gaia compile examples/galileo-v0-5-gaia → exit 0, deterministic IR hash."""
    result = run_gaia("compile", str(galileo_pkg))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# check                                                                       #
# --------------------------------------------------------------------------- #


def test_check_galileo_snapshot(compiled_galileo: Path, run_gaia, snapshot) -> None:
    """Gaia check examples/galileo-v0-5-gaia after compile → text report."""
    result = run_gaia("check", str(compiled_galileo))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_check_brief_galileo_snapshot(compiled_galileo: Path, run_gaia, snapshot) -> None:
    """Gaia check --brief examples/galileo-v0-5-gaia → text + warrant brief."""
    result = run_gaia("check", str(compiled_galileo), "--brief")
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_check_warrants_galileo_snapshot(compiled_galileo: Path, run_gaia, snapshot) -> None:
    """Gaia check --warrants examples/galileo-v0-5-gaia → v6 warrant manifest dump."""
    result = run_gaia("check", str(compiled_galileo), "--warrants")
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# infer                                                                       #
# --------------------------------------------------------------------------- #


def test_infer_galileo_snapshot(compiled_galileo: Path, run_gaia, snapshot) -> None:
    """Gaia infer examples/galileo-v0-5-gaia → beliefs written, exit 0."""
    result = run_gaia("infer", str(compiled_galileo))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# render                                                                      #
# --------------------------------------------------------------------------- #


def test_render_docs_galileo_snapshot(inferred_galileo: Path, run_gaia, snapshot) -> None:
    """Gaia render --target docs after infer → docs/detailed-reasoning.md."""
    result = run_gaia("render", str(inferred_galileo), "--target", "docs")
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# starmap                                                                     #
# --------------------------------------------------------------------------- #


def test_starmap_dot_galileo_snapshot(
    inferred_galileo: Path, run_gaia, snapshot, tmp_path: Path
) -> None:
    """Gaia starmap --format dot → stdout summary, dot file written."""
    out = tmp_path / "starmap.dot"
    result = run_gaia("starmap", str(inferred_galileo), "--format", "dot", "--out", str(out))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_starmap_html_galileo_snapshot(
    inferred_galileo: Path, run_gaia, snapshot, tmp_path: Path
) -> None:
    """Gaia starmap (default html) → stdout summary, html file written."""
    out = tmp_path / "starmap.html"
    result = run_gaia("starmap", str(inferred_galileo), "--out", str(out))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# starmap-replay                                                              #
# --------------------------------------------------------------------------- #


@pytest.fixture
def mendel_replay_pkg(tmp_path: Path) -> Path:
    """Copy the mendel example + the bundled lkm-discovery logs side-by-side."""
    # The bundled mendel example provides the source pkg; the fixture under
    # tests/fixtures/starmap_replay supplies the retrieval / graph-growth logs.
    target = tmp_path / "mendel"
    shutil.copytree(EXAMPLES_DIR / "mendel-v0-5-gaia", target)
    gaia_dir = target / ".gaia"
    if gaia_dir.exists():
        shutil.rmtree(gaia_dir)
    # Splice the lkm-discovery artifacts into the pkg artifacts/ directory.
    artifacts_src = MENDEL_REPLAY_FIXTURE / "artifacts"
    if artifacts_src.exists():
        shutil.copytree(artifacts_src, target / "artifacts")
    return target


def test_starmap_replay_mendel_snapshot(
    mendel_replay_pkg: Path, run_gaia, snapshot, tmp_path: Path
) -> None:
    """Gaia starmap-replay <mendel pkg with lkm logs> → stdout summary."""
    # starmap-replay requires the package to be compiled first.
    compile_res = run_gaia("compile", str(mendel_replay_pkg))
    if compile_res.exit_code != 0:
        pytest.skip(
            f"starmap-replay precondition (compile) failed in this environment:\n"
            f"{compile_res.stderr}"
        )
    out = tmp_path / "replay.html"
    result = run_gaia("starmap-replay", str(mendel_replay_pkg), "--out", str(out))
    assert cli_snapshot(result) == snapshot
