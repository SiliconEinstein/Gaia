"""Snapshot tests for every `gaia ... --help` text.

Help output is the cheapest, highest-signal byte-baseline we can capture
before Stage B/C refactors: it pins the verb tree, option flags, defaults,
and Typer rendering. Any drift here flags either an intentional CLI change
or an accidental regression.

The verb tree is hand-curated from a recursive walk of `gaia --help`. If
new verbs land between captures, add them here and re-record snapshots.
"""

from __future__ import annotations

import pytest

from tests.baseline.conftest import cli_snapshot

pytestmark = pytest.mark.pr_gate

# Every reachable help path. Order matters only for readability.
#
# Alpha 0 reorganizes 9 flat verbs into 6 groups + trace independent
# (协作单 二·共识). The HELP_PATHS list mirrors the new invocation
# surface: `gaia <group> <leaf>`. Old flat verbs are tombstoned and
# covered separately in `test_flat_verb_death.py`.
HELP_PATHS: list[tuple[str, ...]] = [
    # root
    ("--help",),
    # build group
    ("build", "--help"),
    ("build", "init", "--help"),
    ("build", "compile", "--help"),
    ("build", "check", "--help"),
    # run group
    ("run", "--help"),
    ("run", "infer", "--help"),
    ("run", "render", "--help"),
    # inspect group
    ("inspect", "--help"),
    ("inspect", "starmap", "--help"),
    ("inspect", "starmap-replay", "--help"),
    # review group (alpha 0: empty skeleton)
    ("review", "--help"),
    # inquiry subgroup
    ("inquiry", "--help"),
    ("inquiry", "focus", "--help"),
    ("inquiry", "reject", "--help"),
    ("inquiry", "review", "--help"),
    ("inquiry", "obligation", "--help"),
    ("inquiry", "obligation", "add", "--help"),
    ("inquiry", "obligation", "list", "--help"),
    ("inquiry", "obligation", "close", "--help"),
    ("inquiry", "hypothesis", "--help"),
    ("inquiry", "hypothesis", "add", "--help"),
    ("inquiry", "hypothesis", "list", "--help"),
    ("inquiry", "hypothesis", "remove", "--help"),
    ("inquiry", "tactics", "--help"),
    ("inquiry", "tactics", "log", "--help"),
    # pkg group
    ("pkg", "--help"),
    ("pkg", "add", "--help"),
    ("pkg", "register", "--help"),
    # trace subgroup
    ("trace", "--help"),
    ("trace", "verify", "--help"),
    ("trace", "review", "--help"),
    ("trace", "show", "--help"),
]


@pytest.mark.parametrize(
    "argv",
    HELP_PATHS,
    ids=lambda argv: "gaia_" + "_".join(a.lstrip("-") or "root" for a in argv),
)
def test_help_text_snapshot(argv: tuple[str, ...], run_gaia, snapshot) -> None:
    """Capture `gaia <argv>` help text byte-for-byte."""
    result = run_gaia(*argv)
    assert result.exit_code == 0, (
        f"`gaia {' '.join(argv)}` should exit 0 for --help; got {result.exit_code}\n"
        f"stderr:\n{result.stderr}"
    )
    assert cli_snapshot(result) == snapshot
