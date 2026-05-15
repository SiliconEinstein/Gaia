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
# Filename-safe ISO ts variant (colons → hyphens) used by inquiry review
# artifacts like `2026-05-15T04-20-28Z_<sha>_auto.json`. A3 addition.
_ISO_TS_HYPHEN_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z")
_UUID_HEX_RE = re.compile(r"\b[0-9a-f]{8}\b(?=[\s\n_,):\]'\"]|$)")
# Full canonical uuid4 (8-4-4-4-12 hex with hyphens) as produced by
# `gaia init` for `[tool.gaia].uuid`. A3 addition.
_UUID4_FULL_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
# Inquiry qid form: `<prefix>_<8hex>` from `mint_qid` in gaia/inquiry/state.py.
# The leading underscore is a word char so the generic `\b<8hex>\b` regex
# above misses these — capture them here, preserving the prefix. A3 addition.
_INQUIRY_QID_RE = re.compile(r"\b(oblig|hyp|rej)_[0-9a-f]{8}\b")
# Author block in `pyproject.toml` produced by `gaia init` → `uv init`,
# which seeds the entry from the local `git config user.name` / `user.email`.
# Mask so snapshots are stable across developers and CI. A3 addition.
_PYPROJECT_AUTHOR_RE = re.compile(r"""\{\s*name\s*=\s*"[^"]*"\s*,\s*email\s*=\s*"[^"]*"\s*\}""")
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
    text = _ISO_TS_HYPHEN_RE.sub("<ISO_TS_H>", text)
    text = _TIMING_RE.sub("<MS>", text)
    text = _TIMING_S_RE.sub("<S>", text)
    text = _INQUIRY_QID_RE.sub(r"\1_<QID8>", text)
    text = _PYPROJECT_AUTHOR_RE.sub('{ name = "<AUTHOR>", email = "<AUTHOR_EMAIL>" }', text)
    # Full uuid4 must be replaced before the 8-hex regex below, otherwise
    # the latter would only catch the leading 8 hex chars and leave the
    # rest of the uuid form intact.
    text = _UUID4_FULL_RE.sub("<UUID4>", text)
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


# --------------------------------------------------------------------------- #
# Artifact-tree serialization (A3 / Phase 0 Layer 3)                          #
# --------------------------------------------------------------------------- #


def serialize_artifact_tree(
    root: Path,
    *,
    include: tuple[str, ...] | None = None,
    exclude: tuple[str, ...] = (".venv", ".git", "__pycache__"),
    binary_as_size: tuple[str, ...] = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
    ),
) -> dict[str, object]:
    """Walk an artifact directory and produce a stable, ordered snapshot dict.

    Output shape:
        {
            "root": "<masked relpath label>",
            "files": [
                {"path": "<rel>", "kind": "text"|"binary", "content": "..."|<size>},
                ...
            ],
        }

    Ordering: paths are sorted lexicographically so the snapshot is stable
    regardless of OS walk order. Text content is masked with `mask_output`
    so timestamps / tmp paths / uuid hex tails / hyphen-form ISO ts don't
    perturb the byte snapshot. Binary files (per `binary_as_size`) are
    captured as `{"kind": "binary", "size": <int>}` instead of bytes — the
    snapshot's job is to prove behavior parity, not to round-trip binary
    blobs (which never appear in current engine output anyway, but the
    safety net is cheap).

    When `include` is given, only files whose first path component matches
    one of the prefixes (or the file itself) are included; this keeps
    the snapshot scoped to the artifact dir (e.g. ".gaia") even if the
    fixture directory contains the pkg source as siblings.
    """
    if not root.exists():
        return {"root": "<missing>", "files": []}

    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        rel_str = rel.as_posix()
        # Exclude noise (vendored python venv, git internals, pyc caches).
        parts = rel.parts
        if any(part in exclude for part in parts):
            continue
        if include is not None and not any(
            rel_str == inc or rel_str.startswith(inc + "/") or parts[0] == inc for inc in include
        ):
            continue
        # Mask the path itself: filenames can carry hyphen-form ISO ts
        # (inquiry review files) or uuid hex tails.
        rel_str_masked = mask_output(rel_str).rstrip("\n")
        ext = path.suffix.lower()
        if ext in binary_as_size:
            entries.append({"path": rel_str_masked, "kind": "binary", "size": path.stat().st_size})
            continue
        # Read as text; if it's not utf-8 (rare for our artifacts) fall
        # back to size-only so the snapshot stays diffable.
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            entries.append({"path": rel_str_masked, "kind": "binary", "size": path.stat().st_size})
            continue
        entries.append({"path": rel_str_masked, "kind": "text", "content": mask_output(content)})
    return {"root": root.name, "files": entries}


def list_artifact_paths(
    root: Path,
    *,
    exclude: tuple[str, ...] = (".venv", ".git", "__pycache__"),
) -> dict[str, object]:
    """Walk an artifact directory and return only the path listing + sizes.

    Useful for large vendored bundles (e.g. `gaia render --target github`
    emits a TSX/CSS site) where byte-snapshotting every file is overkill
    and stdout already covers the user-visible report. Path-set parity is
    what we care about for refactor — file contents inside vendored
    presentation code are out of refactor scope.
    """
    if not root.exists():
        return {"root": "<missing>", "files": []}
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in exclude for part in rel.parts):
            continue
        entries.append(
            {
                "path": mask_output(rel.as_posix()).rstrip("\n"),
                "size": path.stat().st_size,
            }
        )
    return {"root": root.name, "files": entries}
