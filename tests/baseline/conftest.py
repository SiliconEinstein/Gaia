"""Fixtures for Phase 0 Layer 1 CLI e2e snapshot baseline.

These fixtures intentionally never mutate `gaia/` source; they only set up
deterministic inputs and run the installed `gaia` console-script via real
`subprocess.run` so the captured stdout / stderr / exit code reflects the
true end-to-end CLI surface (not Typer's in-process CliRunner).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from syrupy.extensions.json import JSONSnapshotExtension

# --------------------------------------------------------------------------- #
# Constants                                                                   #
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"
GALILEO_SRC = EXAMPLES_DIR / "galileo-v0-5-gaia"
MENDEL_SRC = EXAMPLES_DIR / "mendel-v0-5-gaia"

# A frozen Unix epoch reference for any code that honours SOURCE_DATE_EPOCH.
# Equivalent to 2026-04-28T00:00:00Z, matching the trace test helper basis in
# `tests/trace/test_cli.py`.
FROZEN_EPOCH = 1745798400  # 2026-04-28T00:00:00Z


# --------------------------------------------------------------------------- #
# Determinism env                                                             #
# --------------------------------------------------------------------------- #


def _deterministic_env() -> dict[str, str]:
    """Construct an env dict for subprocess.run that pins randomness sources."""
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SOURCE_DATE_EPOCH"] = str(FROZEN_EPOCH)
    # Force a stable locale / encoding for any localised CLI output.
    env["LC_ALL"] = "C.UTF-8"
    env["LANG"] = "C.UTF-8"
    # Defang any user-side colour preference; Typer/Rich will print plain text.
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    env["COLUMNS"] = "80"
    return env


# --------------------------------------------------------------------------- #
# Subprocess runner                                                           #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CliResult:
    """Outcome of one `gaia` CLI invocation."""

    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str


def _resolve_gaia() -> str:
    """Find the installed `gaia` console-script.

    Prefers the venv-shipped entrypoint (`<sys.prefix>/bin/gaia`) so that the
    subprocess runs against the same source tree the test suite is checking.
    """
    candidate = Path(sys.prefix) / "bin" / "gaia"
    if candidate.exists():
        return str(candidate)
    resolved = shutil.which("gaia")
    if resolved:
        return resolved
    raise RuntimeError(
        "Could not locate the `gaia` console-script; run `uv sync --extra dev` first."
    )


@pytest.fixture(scope="session")
def gaia_bin() -> str:
    """Path to the installed `gaia` console-script."""
    return _resolve_gaia()


@pytest.fixture
def snapshot(snapshot):  # type: ignore[no-untyped-def]
    """Override syrupy's default extension to JSON for this baseline suite.

    The default Amber serializer renders multi-line strings with dict-level
    indent on *every* line, including blank ones. The repo's pre-commit
    ``trailing-whitespace`` hook then rewrites those padded blank lines,
    breaking byte-identity. JSON snapshot output has no blank-line indent
    padding and is therefore byte-stable under the hook.
    """
    return snapshot.use_extension(JSONSnapshotExtension)


@pytest.fixture
def run_gaia(gaia_bin: str) -> Iterator[Callable[..., CliResult]]:
    """Return a callable that invokes `gaia <args...>` via subprocess.run."""

    def _run(*args: str, cwd: str | Path | None = None) -> CliResult:
        proc = subprocess.run(
            [gaia_bin, *args],
            cwd=str(cwd) if cwd is not None else None,
            env=_deterministic_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        return CliResult(
            argv=tuple(args),
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    yield _run


# --------------------------------------------------------------------------- #
# Output masking                                                              #
# --------------------------------------------------------------------------- #

# Patterns whose substitution makes outputs reproducible across machines,
# package source paths, and clocks without losing semantic content.

_TMP_PATH_RE = re.compile(r"(/tmp/[^\s)'\"]+|/private/var/[^\s)'\"]+)")
_PYTEST_PATH_RE = re.compile(r"(/[^\s)'\"]*?pytest-of-[^\s)'\"]+/[^\s)'\"]+)")
_TIMING_RE = re.compile(r"\b\d+(\.\d+)?\s?ms\b")
_TIMING_S_RE = re.compile(r"\b\d+\.\d+\s?s\b(?=[^\w])")
_ISO_TS_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")
_UUID_HEX_RE = re.compile(r"\b[0-9a-f]{8}\b(?=[\s\n_,):\]'\"]|$)")
_REPO_ROOT_RE = re.compile(re.escape(str(REPO_ROOT)))


def mask_output(text: str) -> str:
    """Replace nondeterministic substrings (tmp paths, timing, uuids, ISO ts).

    Trailing whitespace on each line is also stripped so the resulting
    snapshots are compatible with the repo's pre-commit
    ``trailing-whitespace`` hook (Typer / Rich help output is padded with
    trailing spaces to box width and would otherwise be silently
    rewritten by the hook, breaking byte-identity).
    """
    text = _PYTEST_PATH_RE.sub("<TMP>", text)
    text = _TMP_PATH_RE.sub("<TMP>", text)
    text = _REPO_ROOT_RE.sub("<REPO>", text)
    text = _ISO_TS_RE.sub("<ISO_TS>", text)
    text = _TIMING_RE.sub("<MS>", text)
    text = _TIMING_S_RE.sub("<S>", text)
    text = _UUID_HEX_RE.sub("<UUID8>", text)
    return "\n".join(line.rstrip() for line in text.splitlines(keepends=False)) + (
        "\n" if text.endswith("\n") else ""
    )


def cli_snapshot(result: CliResult) -> dict[str, object]:
    """Render a CliResult into a stable snapshot dict.

    Masking is applied to every text surface — including argv — because tmp
    paths can appear there too when a test passes its own tmp_path through.
    """
    return {
        "argv": [mask_output(a) for a in result.argv],
        "exit_code": result.exit_code,
        "stdout": mask_output(result.stdout),
        "stderr": mask_output(result.stderr),
    }


# --------------------------------------------------------------------------- #
# Package fixtures                                                            #
# --------------------------------------------------------------------------- #


@pytest.fixture
def minimal_pkg(tmp_path: Path) -> Path:
    """Construct a tiny knowledge package on disk and return its path.

    Mirrors the inline package built in tests/cli/test_compile.py so the
    captured `compile` output stays stable under refactor.
    """
    pkg_dir = tmp_path / "test_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "test-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / "test_pkg"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'my_claim = claim("A test claim.")\n'
        '__all__ = ["my_claim"]\n',
        encoding="utf-8",
    )
    return pkg_dir


@pytest.fixture
def galileo_pkg(tmp_path: Path) -> Path:
    """Copy the bundled galileo example into tmp_path and return its path."""
    target = tmp_path / "galileo"
    shutil.copytree(GALILEO_SRC, target)
    # Drop any pre-existing build artifacts the workspace may have left behind.
    gaia_dir = target / ".gaia"
    if gaia_dir.exists():
        shutil.rmtree(gaia_dir)
    return target


@pytest.fixture
def compiled_galileo(galileo_pkg: Path, run_gaia) -> Path:
    """Compile the galileo example so downstream verbs (infer/render/starmap) work."""
    result = run_gaia("compile", str(galileo_pkg))
    if result.exit_code != 0:
        raise RuntimeError(
            f"baseline compile fixture failed: exit={result.exit_code}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return galileo_pkg


@pytest.fixture
def inferred_galileo(compiled_galileo: Path, run_gaia) -> Path:
    """Compile + infer galileo so render snapshots have beliefs available."""
    result = run_gaia("infer", str(compiled_galileo))
    if result.exit_code != 0:
        raise RuntimeError(
            f"baseline infer fixture failed: exit={result.exit_code}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return compiled_galileo


# --------------------------------------------------------------------------- #
# Trace fixtures                                                              #
# --------------------------------------------------------------------------- #


@pytest.fixture
def clean_trace_path(tmp_path: Path) -> Path:
    """Build a tiny, hash-clean Trace file deterministically.

    Mirrors the helper pattern in tests/trace/test_cli.py: timestamps derive
    from a fixed UTC datetime, so the resulting events_root / manifest_hash
    are byte-stable across runs.
    """
    from gaia.trace.hashing import (
        GENESIS_PREV_HASH,
        compute_events_root,
        compute_manifest_hash,
        hash_event,
    )
    from gaia.trace.schema import Trace, TraceEvent, TraceManifest

    def ts(seq: int) -> datetime:
        return datetime(2026, 4, 28, tzinfo=UTC) + timedelta(seconds=seq)

    events: list[TraceEvent] = []
    prev = GENESIS_PREV_HASH
    for i in range(3):
        ev = TraceEvent(
            event_id=f"e{i}",
            seq=i,
            prev_hash=prev,
            ts=ts(i),
            kind="decision",
            actor="arm",
            reason="grounded by inputs",
            inputs={"step": "inputs"},
        )
        events.append(ev)
        prev = hash_event(ev)

    manifest = TraceManifest(
        arm_id="arm-x",
        session_id="s",
        trace_id="t",
        created_at=ts(0),
        events_root=compute_events_root(events),
    )
    manifest = manifest.model_copy(update={"manifest_hash": compute_manifest_hash(manifest)})
    trace = Trace(manifest=manifest, events=events)

    out = tmp_path / "trace.json"
    out.write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    return out


@pytest.fixture
def tampered_trace_path(tmp_path: Path) -> Path:
    """Build a Trace whose events_root no longer matches the manifest."""
    from gaia.trace.hashing import (
        GENESIS_PREV_HASH,
        compute_events_root,
        hash_event,
    )
    from gaia.trace.schema import Trace, TraceEvent, TraceManifest

    def ts(seq: int) -> datetime:
        return datetime(2026, 4, 28, tzinfo=UTC) + timedelta(seconds=seq)

    events: list[TraceEvent] = []
    prev = GENESIS_PREV_HASH
    for i in range(3):
        ev = TraceEvent(
            event_id=f"e{i}",
            seq=i,
            prev_hash=prev,
            ts=ts(i),
            kind="decision",
            actor="arm",
            reason="grounded by inputs",
            inputs={"step": "inputs"},
        )
        events.append(ev)
        prev = hash_event(ev)

    # Tamper: replace the middle event's reason to break the chain hash.
    events[1] = events[1].model_copy(update={"reason": "tampered reason"})

    manifest = TraceManifest(
        arm_id="arm-x",
        session_id="s",
        trace_id="t",
        created_at=ts(0),
        events_root=compute_events_root(events),
    )
    # We deliberately do NOT recompute manifest_hash here — drives a mismatch.
    manifest = manifest.model_copy(update={"manifest_hash": "sha256:" + "0" * 64})
    trace = Trace(manifest=manifest, events=events)

    out = tmp_path / "tampered.json"
    out.write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    return out
