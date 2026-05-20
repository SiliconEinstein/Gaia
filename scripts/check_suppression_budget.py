"""No-net-growth gate for type-check / lint suppressions in `gaia/`.

Counts lines under tracked `gaia/**/*.py` that carry a `# noqa[: …]` or
`# type: ignore[: …]` comment and compares the total against the budget
declared in `scripts/suppression_budget.txt`.

Pass criterion: ``current <= budget``. Going down is always fine; going
up requires bumping the budget file in the same commit, with a justifying
paragraph in the commit body.

The script is intentionally stdlib-only so it can run as a `local` hook
under pre-commit without dragging extra dev deps into the gate path.

Exit codes
----------
0
    Current count is at or below the budget. Prints both numbers.
1
    Current count exceeds the budget. Prints the budget, the current
    count, and every offending suppression line so the diff is obvious.
2
    Configuration error (budget file unreadable / not an integer, git
    invocation failed, etc.).

Usage
-----
::

    uv run python scripts/check_suppression_budget.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUDGET_FILE = REPO_ROOT / "scripts" / "suppression_budget.txt"
SCOPE_PATTERN = "gaia/**/*.py"

# Match either the ruff suppression marker (with or without a `: CODE`
# suffix) or the mypy `type: ignore` marker (with or without `[CODE]`).
# Bare forms are already kept out of the tree by ruff PGH003 / PGH004,
# so this regex just needs to locate the markers themselves.
SUPPRESSION_RE = re.compile(r"#\s*(?:type:\s*ignore|noqa)\b")


def _read_budget(path: Path) -> int:
    """Return the integer budget from `path`, skipping `#` comment lines."""
    if not path.is_file():
        raise SystemExit(f"budget file not found: {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            return int(line)
        except ValueError as exc:
            raise SystemExit(f"budget file {path} has non-integer content: {line!r}") from exc
    raise SystemExit(f"budget file {path} contains no integer line")


def _tracked_files(pattern: str) -> list[str]:
    """Return tracked files matching `pattern` via `git ls-files`."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", pattern],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"`git ls-files {pattern}` failed: {exc.stderr.strip()}") from exc
    return [line for line in proc.stdout.splitlines() if line]


def _collect_suppressions(files: list[str]) -> list[tuple[str, int, str]]:
    """Return `(path, lineno, line)` triples for every suppression hit."""
    hits: list[tuple[str, int, str]] = []
    for rel in files:
        full = REPO_ROOT / rel
        try:
            text = full.read_text(encoding="utf-8")
        except OSError:
            # File listed by git but missing on disk (e.g. mid-rename); skip.
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if SUPPRESSION_RE.search(line):
                hits.append((rel, lineno, line.rstrip()))
    return hits


def main() -> int:
    """Compare current suppression count against the budget and report."""
    budget = _read_budget(BUDGET_FILE)
    files = _tracked_files(SCOPE_PATTERN)
    hits = _collect_suppressions(files)
    current = len(hits)

    if current <= budget:
        print(
            f"suppression budget OK: {current} <= {budget} "
            f"(scope: {SCOPE_PATTERN}, files scanned: {len(files)})"
        )
        if current < budget:
            print(
                "note: current count is below the budget; consider lowering "
                f"{BUDGET_FILE.relative_to(REPO_ROOT)} to {current} to lock the win."
            )
        return 0

    print(
        f"suppression budget exceeded: {current} > {budget} "
        f"(scope: {SCOPE_PATTERN}, files scanned: {len(files)})",
        file=sys.stderr,
    )
    print("All current suppression sites:", file=sys.stderr)
    for path, lineno, line in hits:
        print(f"  {path}:{lineno}: {line}", file=sys.stderr)
    print(
        "\nIf the new suppression is necessary, raise the integer in "
        f"{BUDGET_FILE.relative_to(REPO_ROOT)} and justify it in the commit body.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
