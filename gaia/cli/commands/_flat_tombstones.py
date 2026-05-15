"""Flat-verb tombstones for the alpha-0 CLI cutover.

Alpha 0 reorganizes the 9 historical top-level verbs into 6 groups + `trace`
independent. Per 协作单 二·共识: "v0.5.x 不保留 `gaia <flat-verb>` alias,
新 group 形式落地即切换; 旧 flat-verb 死法直接报错并指向新形式". This is a
direct cutover with no warn/deprecate window.

This module installs 9 stub commands at the top-level `app` whose only job is
to:
  * exit with code 2 (usage error)
  * print a message to stderr naming both the old flat verb and the new
    grouped form
  * execute zero side effects

The deprecation path here is "error → remove"; the stubs themselves are
expected to disappear in a subsequent release once external callers have
migrated.

The mapping is the canonical source for `docs/migration.md`'s Layer 1 table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from collections.abc import Callable

_FLAT_VERB_REDIRECTS: dict[str, str] = {
    "init": "gaia build init",
    "compile": "gaia build compile",
    "check": "gaia build check",
    "infer": "gaia run infer",
    "render": "gaia run render",
    "starmap": "gaia inspect starmap",
    "starmap-replay": "gaia inspect starmap-replay",
    "add": "gaia pkg add",
    "register": "gaia pkg register",
}


def _flat_verb_death(old: str) -> None:
    """Raise a usage error for an old flat verb, naming the new grouped form.

    Exits with code 2 (Typer/Click convention for usage errors). The message
    goes to stderr so shell pipelines and CI logs surface it cleanly without
    polluting captured stdout.
    """
    new = _FLAT_VERB_REDIRECTS[old]
    typer.echo(
        f"error: `gaia {old}` was removed in alpha 0. Use `{new}` instead.",
        err=True,
    )
    raise typer.Exit(code=2)


def register_flat_tombstones(app: typer.Typer) -> None:
    """Install 9 flat-verb tombstone commands on the given Typer app.

    Each tombstone accepts arbitrary positional / keyword args (Typer's
    `context_settings={"allow_extra_args": True, "ignore_unknown_options": True}`)
    so users get a redirect even when they pass the old verb with its full
    historical option set. We never look at the args — the redirect fires
    unconditionally.
    """
    # We register each tombstone explicitly rather than in a loop because
    # Typer command names are part of the decorator surface and a closure
    # over the loop variable would be brittle under help-text generation.

    def _make_stub(verb: str) -> Callable[[], None]:
        def _stub() -> None:
            _flat_verb_death(verb)

        _stub.__doc__ = f"Removed in alpha 0 — use `{_FLAT_VERB_REDIRECTS[verb]}` instead."
        return _stub

    extra_args_settings = {
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    }

    for verb in _FLAT_VERB_REDIRECTS:
        app.command(
            name=verb,
            hidden=True,
            context_settings=extra_args_settings,
        )(_make_stub(verb))
