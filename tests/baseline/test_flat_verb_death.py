"""Snapshot tests for the 9 alpha-0 flat-verb tombstones.

Per 协作单 `VgdMw7N5NikAHIkFu6UckWuznHI` 二·共识, the historical
top-level flat verbs are removed in alpha 0 and replaced with hidden stubs
that exit with code 2 and print a redirect message to stderr naming the new
grouped form. These tests pin that behavior:

  * exit code is 2
  * stderr names both the old verb and the new grouped form
  * no side effects (snapshot includes stdout — should be empty)

The mapping under test is the source-of-truth in
`gaia.cli.commands._flat_tombstones._FLAT_VERB_REDIRECTS`.
"""

from __future__ import annotations

import pytest

from gaia.cli.commands._flat_tombstones import _FLAT_VERB_REDIRECTS
from tests.baseline.conftest import cli_snapshot

pytestmark = pytest.mark.pr_gate


@pytest.mark.parametrize(
    ("flat_verb", "new_form"),
    sorted(_FLAT_VERB_REDIRECTS.items()),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_flat_verb_dies_with_redirect(flat_verb: str, new_form: str, run_gaia, snapshot) -> None:
    """Each removed flat verb exits 2 with a stderr redirect message."""
    result = run_gaia(flat_verb)
    assert result.exit_code == 2, (
        f"`gaia {flat_verb}` should exit 2; got {result.exit_code}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert flat_verb in result.stderr, (
        f"stderr should name the old verb `{flat_verb}`; got:\n{result.stderr}"
    )
    assert new_form in result.stderr, (
        f"stderr should point to the new form `{new_form}`; got:\n{result.stderr}"
    )
    assert cli_snapshot(result) == snapshot


def test_flat_verb_dies_with_args_too(run_gaia, snapshot) -> None:
    """Tombstone fires regardless of extra positional / option args.

    Users migrating from old scripts will retain the full historical option
    set (e.g. `gaia compile ./pkg --brief`). The stub must surface the
    redirect rather than choking on unknown args.
    """
    result = run_gaia("compile", "./some-pkg", "--made-up-flag", "value")
    assert result.exit_code == 2
    assert "gaia compile" in result.stderr
    assert "gaia build compile" in result.stderr
    assert cli_snapshot(result) == snapshot
