"""``gaia example galileo`` — print or save the galileo cli walkthrough."""

from __future__ import annotations

from pathlib import Path

import typer

from gaia.cli.commands.example._runner import emit, read_walkthrough, substitute_target

_FLAVOR = "galileo"
_PLACEHOLDER = "./galileo-cli-mirror-gaia"


def galileo_command(
    target: str = typer.Option(
        _PLACEHOLDER,
        "--target",
        help=(
            "Package directory the printed commands will scaffold into. "
            "Substitutes the './galileo-cli-mirror-gaia' placeholder. The "
            "embedded `--name galileo-v0-5-gaia` flag is intentionally "
            "left alone so the package's import_name stays stable; pass "
            "a different `--target` only to change the on-disk directory."
        ),
    ),
    out: str | None = typer.Option(
        None,
        "--out",
        help=(
            "Write the walkthrough to this file instead of stdout. The "
            "file is a runnable bash script (`#!/usr/bin/env bash` + "
            "`set -euo pipefail`). Refuses to overwrite an existing file "
            "unless `--force` is also passed."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow `--out` to overwrite an existing file.",
    ),
) -> None:
    """Print or save the CLI-authored Galileo walkthrough.

    Mirrors ``examples/galileo-v0-5-gaia/CLI-AUTHORED.md`` as a single
    runnable bash script. The script drives ``gaia pkg scaffold``,
    ``gaia author <verb>``, and ``gaia pkg add-module`` /
    ``gaia author register-prior`` to produce a separately-scaffolded
    ``-gaia`` package that compiles to the same ``LocalCanonicalGraph``
    (14 user-authored knowledge contents, 5 derive strategies,
    3 structural operators, 24 total knowledge nodes) as the
    hand-authored ground truth.

    Examples:
      $ gaia example galileo

      $ gaia example galileo --target ./my-demo

      $ gaia example galileo --out walkthrough.sh

      $ gaia example galileo --out walkthrough.sh --force
    """
    script = read_walkthrough(_FLAVOR)
    script = substitute_target(script, _PLACEHOLDER, target)
    emit(script, Path(out) if out is not None else None, force)


__all__ = ["galileo_command"]
