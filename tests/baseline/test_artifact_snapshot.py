"""Phase 0 Layer 3 — artifact byte-tree snapshot baseline.

A1 captured stdout / stderr / exit code for write-side verbs but explicitly
deferred byte-comparison of the produced artifact directory to A3. After
the alpha-0 engine refactor lands, these snapshots must remain byte-
identical — proving the refactor preserved artifact-write behavior.

Scope (see ``home_agent/projects/gaia/alpha-0/plan.md`` Stage A3):

* **Flavor 1 — artifact-tree snapshots for side-effecting verbs** A1 runs:
  ``compile`` / ``infer`` / ``init`` / ``render`` (docs|obsidian|github) /
  ``starmap`` (file output). For each, snapshot the resulting artifact
  directory as ``{root, files: [{path, kind, content}, ...]}`` after
  applying the conftest masker.

* **Flavor 2 — inquiry write-path happy paths** A1 deferred:
  ``inquiry obligation add / close``, ``inquiry hypothesis add / remove``,
  ``inquiry reject``, ``inquiry review``. Each snapshots both the CLI
  surface (stdout/stderr/exit) *and* the state-after dir tree.

Out of scope (skipped, documented inline):

* ``gaia add`` — network call to a remote registry.
* ``gaia register`` (with or without ``--create-pr``) — requires a git
  remote / tag inside the fixture pkg. Network-adjacent + brittle.

Determinism strategy for inquiry qids:

``mint_qid()`` in ``gaia/inquiry/state.py`` returns
``f"{prefix}_{uuid.uuid4().hex[:8]}"``. A1's masker already collapses
8-hex tails to ``<UUID8>`` via ``_UUID_HEX_RE`` — we reuse that here
rather than patching uuid4. The masker is also extended (in conftest)
with ``_ISO_TS_HYPHEN_RE`` to cover review filenames like
``2026-05-15T04-20-28Z_<sha>_auto.json``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.baseline.conftest import (
    cli_snapshot,
    list_artifact_paths,
    serialize_artifact_tree,
)

# --------------------------------------------------------------------------- #
# Flavor 1 — artifact-tree snapshots for compile / infer / starmap / render   #
# --------------------------------------------------------------------------- #


def test_compile_minimal_artifact_tree_snapshot(minimal_pkg: Path, run_gaia, snapshot) -> None:
    """`.gaia/` byte tree after `gaia build compile <minimal pkg>`."""
    result = run_gaia("build", "compile", str(minimal_pkg))
    assert result.exit_code == 0, result.stderr
    artifacts = serialize_artifact_tree(minimal_pkg / ".gaia")
    assert artifacts == snapshot


def test_compile_galileo_artifact_tree_snapshot(galileo_pkg: Path, run_gaia, snapshot) -> None:
    """`.gaia/` byte tree after `gaia build compile examples/galileo-v0-5-gaia`."""
    result = run_gaia("build", "compile", str(galileo_pkg))
    assert result.exit_code == 0, result.stderr
    artifacts = serialize_artifact_tree(galileo_pkg / ".gaia")
    assert artifacts == snapshot


def test_infer_galileo_artifact_tree_snapshot(compiled_galileo: Path, run_gaia, snapshot) -> None:
    """`.gaia/` byte tree after `gaia run infer`. Adds beliefs.json to compile tree."""
    result = run_gaia("run", "infer", str(compiled_galileo))
    assert result.exit_code == 0, result.stderr
    artifacts = serialize_artifact_tree(compiled_galileo / ".gaia")
    assert artifacts == snapshot


def test_starmap_dot_artifact_snapshot(
    inferred_galileo: Path, run_gaia, snapshot, tmp_path: Path
) -> None:
    """Byte content of `<out>.dot` produced by `gaia inspect starmap --format dot`."""
    out = tmp_path / "starmap.dot"
    result = run_gaia(
        "inspect",
        "starmap",
        str(inferred_galileo),
        "--format",
        "dot",
        "--out",
        str(out),
    )
    assert result.exit_code == 0, result.stderr
    # starmap writes a single file; snapshot it as a single-file tree so the
    # shape matches the other tests and a future multi-file starmap output
    # would still slot in.
    artifacts = serialize_artifact_tree(out.parent, include=(out.name,))
    assert artifacts == snapshot


def test_starmap_html_artifact_path_snapshot(
    inferred_galileo: Path, run_gaia, snapshot, tmp_path: Path
) -> None:
    """Path + size of `<out>.html` produced by `gaia inspect starmap`.

    HTML embeds a vendored bundle whose minified JS contains short hex
    tokens A1's masker would mangle. Path-and-size proves the file is
    produced; full content parity is already covered by the dot variant.
    """
    out = tmp_path / "starmap.html"
    result = run_gaia("inspect", "starmap", str(inferred_galileo), "--out", str(out))
    assert result.exit_code == 0, result.stderr
    artifacts = list_artifact_paths(out.parent)
    # The html embeds a deterministic large bundle; we only care that the
    # file exists and is non-empty. Replace the (large, jitter-prone) size
    # with a 'present' marker so packaging changes to the bundler don't
    # break us — A1's stdout snapshot already pins node/edge counts.
    for entry in artifacts["files"]:  # type: ignore[index]
        if isinstance(entry, dict):
            entry["size"] = "<NONZERO>" if entry["size"] else 0  # type: ignore[index]
    assert artifacts == snapshot


# --------------------------------------------------------------------------- #
# init                                                                        #
# --------------------------------------------------------------------------- #


def test_init_scaffold_tree_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Scaffolded source files after `gaia build init <name>-gaia`.

    `gaia build init` also runs `uv venv` and `git init`; both produce
    machine-dependent state (.venv/.git). The fixture filter strips both,
    leaving only the scaffolded source layout (pyproject.toml, README,
    .gitignore, src/<name>/__init__.py, src/<name>/py.typed, .python-version).
    """
    result = run_gaia("build", "init", "demo-gaia", cwd=tmp_path)
    assert result.exit_code == 0, result.stderr
    pkg_root = tmp_path / "demo-gaia"
    # serialize_artifact_tree's default `exclude=(".venv",".git","__pycache__")`
    # already drops the noisy directories.
    artifacts = serialize_artifact_tree(pkg_root)
    assert artifacts == snapshot


# --------------------------------------------------------------------------- #
# render targets (docs / obsidian / github)                                   #
# --------------------------------------------------------------------------- #


def test_render_docs_artifact_tree_snapshot(inferred_galileo: Path, run_gaia, snapshot) -> None:
    """`docs/detailed-reasoning.md` byte content after `run render --target docs`."""
    result = run_gaia("run", "render", str(inferred_galileo), "--target", "docs")
    assert result.exit_code == 0, result.stderr
    artifacts = serialize_artifact_tree(inferred_galileo / "docs")
    assert artifacts == snapshot


def test_render_obsidian_artifact_tree_snapshot(inferred_galileo: Path, run_gaia, snapshot) -> None:
    """`gaia-wiki/` page tree after `run render --target obsidian`."""
    result = run_gaia("run", "render", str(inferred_galileo), "--target", "obsidian")
    assert result.exit_code == 0, result.stderr
    artifacts = serialize_artifact_tree(inferred_galileo / "gaia-wiki")
    assert artifacts == snapshot


def test_render_github_artifact_paths_snapshot(inferred_galileo: Path, run_gaia, snapshot) -> None:
    """`.github-output/` path-listing after `run render --target github`.

    The target emits a vendored TSX/CSS presentation bundle (~48 files).
    Byte-content of the bundle is out of refactor scope: it's the engine
    refactor we're guarding, not the renderer's vendored deps. Path-set
    parity is what proves the renderer still emits the same shape.
    """
    result = run_gaia("run", "render", str(inferred_galileo), "--target", "github")
    assert result.exit_code == 0, result.stderr
    artifacts = list_artifact_paths(inferred_galileo / ".github-output")
    # Replace sizes with a 'present' marker so vendored-bundle byte jitter
    # (npm cache differences, minifier version drift) doesn't break us.
    for entry in artifacts["files"]:  # type: ignore[index]
        if isinstance(entry, dict):
            entry["size"] = "<NONZERO>" if entry["size"] else 0  # type: ignore[index]
    assert artifacts == snapshot


# --------------------------------------------------------------------------- #
# Flavor 2 — inquiry write-path happy paths                                   #
# --------------------------------------------------------------------------- #
#
# Helper fixtures here are kept local to this module; they aren't reused
# by A1 and pulling them up to conftest would entangle Layer 1 / Layer 3.


@pytest.fixture
def inquiry_workspace(tmp_path: Path) -> Path:
    """Empty fixture dir suitable for `gaia inquiry <write>` --path <here>.

    The inquiry write commands tolerate the absence of a compiled IR for
    the simple state mutations covered here (add / remove / reject / close);
    only `inquiry review` requires a compiled pkg, and that test uses
    `compiled_galileo` instead.
    """
    return tmp_path


def test_inquiry_obligation_add_state_snapshot(inquiry_workspace: Path, run_gaia, snapshot) -> None:
    """State.json + tactics.jsonl after one `inquiry obligation add`."""
    result = run_gaia(
        "inquiry",
        "obligation",
        "add",
        "some-target",
        "--content",
        "Need to verify this claim",
        "--kind",
        "other",
        "--path",
        str(inquiry_workspace),
    )
    assert result.exit_code == 0, result.stderr
    assert {
        "cli": cli_snapshot(result),
        "artifacts": serialize_artifact_tree(inquiry_workspace / ".gaia"),
    } == snapshot


def test_inquiry_obligation_close_state_snapshot(
    inquiry_workspace: Path, run_gaia, snapshot
) -> None:
    """State.json after add → close round-trip (close ack stdout + state)."""
    add_res = run_gaia(
        "inquiry",
        "obligation",
        "add",
        "some-target",
        "--content",
        "First obligation",
        "--kind",
        "other",
        "--path",
        str(inquiry_workspace),
    )
    assert add_res.exit_code == 0, add_res.stderr
    # mint_qid is uuid4-derived; the add stdout contains "obligation added <qid>".
    # Parse it deterministically (still masked in snapshot via <UUID8>).
    qid = add_res.stdout.strip().split()[-1]
    close_res = run_gaia(
        "inquiry",
        "obligation",
        "close",
        qid,
        "--path",
        str(inquiry_workspace),
    )
    assert close_res.exit_code == 0, close_res.stderr
    assert {
        "cli": cli_snapshot(close_res),
        "artifacts": serialize_artifact_tree(inquiry_workspace / ".gaia"),
    } == snapshot


def test_inquiry_hypothesis_add_state_snapshot(inquiry_workspace: Path, run_gaia, snapshot) -> None:
    """State.json + tactics.jsonl after one `inquiry hypothesis add`."""
    result = run_gaia(
        "inquiry",
        "hypothesis",
        "add",
        "Maybe X causes Y",
        "--path",
        str(inquiry_workspace),
    )
    assert result.exit_code == 0, result.stderr
    assert {
        "cli": cli_snapshot(result),
        "artifacts": serialize_artifact_tree(inquiry_workspace / ".gaia"),
    } == snapshot


def test_inquiry_hypothesis_remove_state_snapshot(
    inquiry_workspace: Path, run_gaia, snapshot
) -> None:
    """State.json after hypothesis add → remove round-trip."""
    add_res = run_gaia(
        "inquiry",
        "hypothesis",
        "add",
        "A working hypothesis",
        "--path",
        str(inquiry_workspace),
    )
    assert add_res.exit_code == 0, add_res.stderr
    qid = add_res.stdout.strip().split()[-1]
    rm_res = run_gaia(
        "inquiry",
        "hypothesis",
        "remove",
        qid,
        "--path",
        str(inquiry_workspace),
    )
    assert rm_res.exit_code == 0, rm_res.stderr
    assert {
        "cli": cli_snapshot(rm_res),
        "artifacts": serialize_artifact_tree(inquiry_workspace / ".gaia"),
    } == snapshot


def test_inquiry_reject_state_snapshot(inquiry_workspace: Path, run_gaia, snapshot) -> None:
    """State.json + tactics.jsonl after one `inquiry reject <strategy>`."""
    result = run_gaia(
        "inquiry",
        "reject",
        "some-strategy",
        "--content",
        "Does not apply to this domain",
        "--path",
        str(inquiry_workspace),
    )
    assert result.exit_code == 0, result.stderr
    assert {
        "cli": cli_snapshot(result),
        "artifacts": serialize_artifact_tree(inquiry_workspace / ".gaia"),
    } == snapshot


def test_inquiry_review_state_snapshot(compiled_galileo: Path, run_gaia, snapshot) -> None:
    """State.json + reviews/* + tactics.jsonl after one `inquiry review`.

    Uses `--no-infer` to keep the review deterministic against the
    compiled IR alone (no JT solve jitter), and runs against the
    bundled galileo example so the review file content has structure
    worth byte-checking.
    """
    result = run_gaia(
        "inquiry",
        "review",
        str(compiled_galileo),
        "--no-infer",
        "--mode",
        "auto",
    )
    assert result.exit_code == 0, result.stderr
    # Snapshot only the inquiry/ subdir — the rest of .gaia/ is already
    # covered by the compile/infer flavor-1 tests and would duplicate.
    assert {
        "cli": cli_snapshot(result),
        "artifacts": serialize_artifact_tree(compiled_galileo / ".gaia" / "inquiry"),
    } == snapshot
