"""Run the gaia toolchain end-to-end against the locked alpha package corpus.

This script implements the package-corpus runner described in the gaia
release-channel strategy spec
(`docs/specs/2026-05-16-gaia-release-channel-strategy.md`,
§5 Package Corpus E2E and §8 Minimal Implementation Plan step 3).

Locked alpha corpus (hardcoded; do not parameterize):
    - examples/galileo-v0-5-gaia
    - examples/mendel-v0-5-gaia

Per-package toolchain steps (in order; first failure stops the package
and the whole run):

    gaia build compile <pkg>
    gaia build check <pkg>
    gaia build check --gate <pkg>
    gaia run infer <pkg>
    gaia run render <pkg> --target docs
    gaia run render <pkg> --target github
    gaia run render <pkg> --target obsidian

After all toolchain steps succeed for a package, the GitHub-render
publication-bundle assertions from spec §5 are verified against
``<pkg>/.github-output/``:

    MUST exist and be non-empty:
        README.md
        wiki/Home.md
        docs/public/data/graph.json
        docs/public/data/meta.json
        docs/public/data/beliefs.json
    MUST NOT exist (Vite/React leak prevention):
        docs/package.json
        docs/src

Exit codes
----------
0
    All corpus packages green.
N (N >= 1)
    The N-th package in the locked list failed. galileo failure exits 1,
    mendel failure exits 2.

Errors are echoed to stderr with the format::

    [FAIL] <pkg>/<step>: <reason>

Success prints to stdout::

    [OK] corpus all green: galileo mendel

Invocation
----------
This script expects an activated virtualenv with ``gaia`` on ``PATH``
(it invokes ``gaia`` as a bare command, not ``uv run gaia``). The
nightly workflow that wires this in (spec §8 step 2) is responsible for
activating the venv before calling the script.

For local verification from the repo root::

    uv run python scripts/run_package_corpus.py

``uv run`` injects the project venv so ``gaia`` resolves correctly.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Locked alpha corpus per spec §5 + dispatch lock. Order matters: it
# determines the per-package failure exit code (1-indexed).
CORPUS_PACKAGES: tuple[tuple[str, Path], ...] = (
    ("galileo", REPO_ROOT / "examples" / "galileo-v0-5-gaia"),
    ("mendel", REPO_ROOT / "examples" / "mendel-v0-5-gaia"),
)

# Toolchain step labels and argv tails. The leading ``gaia`` and the
# trailing ``<pkg-path>`` are added by ``_run_step``.
TOOLCHAIN_STEPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("build-compile", ("build", "compile")),
    ("build-check", ("build", "check")),
    ("build-check-gate", ("build", "check", "--gate")),
    ("run-infer", ("run", "infer")),
    ("render-docs", ("run", "render", "--target", "docs")),
    ("render-github", ("run", "render", "--target", "github")),
    ("render-obsidian", ("run", "render", "--target", "obsidian")),
)

# Spec §5 GitHub-render assertions. Paths are relative to
# ``<pkg>/.github-output/``.
REQUIRED_GITHUB_OUTPUTS: tuple[str, ...] = (
    "README.md",
    "wiki/Home.md",
    "docs/public/data/graph.json",
    "docs/public/data/meta.json",
    "docs/public/data/beliefs.json",
)
FORBIDDEN_GITHUB_OUTPUTS: tuple[str, ...] = (
    "docs/package.json",
    "docs/src",
)
# Paths that must additionally parse as JSON (subset of REQUIRED).
JSON_GITHUB_OUTPUTS: tuple[str, ...] = (
    "docs/public/data/graph.json",
    "docs/public/data/meta.json",
    "docs/public/data/beliefs.json",
)


@dataclass(frozen=True)
class StepFailure:
    """A single failing step inside one package's pipeline."""

    package: str
    step: str
    reason: str


def compute_exit_code(failing_index: int | None) -> int:
    """Return the process exit code for a corpus run.

    ``failing_index`` is the 0-based index in :data:`CORPUS_PACKAGES` of
    the first package that failed, or ``None`` if every package passed.
    Per spec §8.3 the exit code is ``failing_index + 1`` so galileo
    failure exits 1 and mendel failure exits 2.
    """
    if failing_index is None:
        return 0
    return failing_index + 1


def _format_output_tail(stderr: str, stdout: str, *, max_lines: int = 5) -> str:
    """Return the last ``max_lines`` non-empty output lines, single-line.

    Prefers ``stderr`` when populated; falls back to ``stdout`` because the
    gaia CLI emits some failure detail (e.g. ``gaia build check --gate``
    quality-gate report) on stdout, and a single-line diagnostic shouldn't
    appear empty when the CI logs clearly show the failure.
    """
    stream = stderr if stderr.strip() else stdout
    label = "stderr" if stderr.strip() else "stdout"
    lines = [line.rstrip() for line in stream.splitlines() if line.strip()]
    tail = lines[-max_lines:]
    return f"({label}) " + " | ".join(tail) if tail else "<no output>"


def _run_step(
    package_name: str,
    step_label: str,
    argv_tail: tuple[str, ...],
    pkg_path: Path,
) -> StepFailure | None:
    """Invoke one toolchain step; return a :class:`StepFailure` or ``None``."""
    argv = ["gaia", *argv_tail, str(pkg_path)]
    try:
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return StepFailure(
            package=package_name,
            step=step_label,
            reason="`gaia` executable not found on PATH (activate the project venv)",
        )
    if proc.returncode != 0:
        return StepFailure(
            package=package_name,
            step=step_label,
            reason=(
                f"{' '.join(argv[:-1])} exited {proc.returncode}: "
                f"{_format_output_tail(proc.stderr, proc.stdout)}"
            ),
        )
    return None


def assert_github_render_outputs(pkg_path: Path) -> str | None:
    """Verify spec §5 GitHub-render publication-bundle invariants.

    Returns ``None`` on success, or a one-line failure reason. The
    runner wraps the reason in the canonical ``[FAIL] <pkg>/<step>:`` form.
    """
    out_root = pkg_path / ".github-output"
    if not out_root.is_dir():
        return f"missing .github-output/ directory under {pkg_path}"

    for rel in REQUIRED_GITHUB_OUTPUTS:
        target = out_root / rel
        if not target.is_file():
            return f"missing required output: {rel}"
        if target.stat().st_size == 0:
            return f"required output is empty: {rel}"

    for rel in JSON_GITHUB_OUTPUTS:
        target = out_root / rel
        try:
            json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return f"required output is not valid JSON ({rel}): {exc}"

    for rel in FORBIDDEN_GITHUB_OUTPUTS:
        target = out_root / rel
        if target.exists():
            return f"forbidden output present (Vite/React leak): {rel}"

    return None


def _run_package(package_name: str, pkg_path: Path) -> StepFailure | None:
    """Run the full toolchain and assertions for one package."""
    if not pkg_path.is_dir():
        return StepFailure(
            package=package_name,
            step="setup",
            reason=f"corpus package directory not found: {pkg_path}",
        )
    for step_label, argv_tail in TOOLCHAIN_STEPS:
        failure = _run_step(package_name, step_label, argv_tail, pkg_path)
        if failure is not None:
            return failure
    assertion_reason = assert_github_render_outputs(pkg_path)
    if assertion_reason is not None:
        return StepFailure(
            package=package_name,
            step="render-assert",
            reason=assertion_reason,
        )
    return None


def main() -> int:
    """Drive the corpus run; return the process exit code."""
    for index, (name, path) in enumerate(CORPUS_PACKAGES):
        failure = _run_package(name, path)
        if failure is not None:
            print(
                f"[FAIL] {failure.package}/{failure.step}: {failure.reason}",
                file=sys.stderr,
                flush=True,
            )
            return compute_exit_code(index)
    names = " ".join(name for name, _ in CORPUS_PACKAGES)
    print(f"[OK] corpus all green: {names}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
