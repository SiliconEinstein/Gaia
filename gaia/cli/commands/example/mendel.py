"""``gaia example mendel`` — print or save the mendel cli walkthrough."""

from __future__ import annotations

from pathlib import Path

import typer

from gaia.cli.commands.example._runner import emit, read_walkthrough, substitute_target

_FLAVOR = "mendel"
_PLACEHOLDER = "./mendel-cli-mirror-gaia"


def mendel_command(
    target: str = typer.Option(
        _PLACEHOLDER,
        "--target",
        help=(
            "Package directory the printed commands will scaffold into. "
            "Substitutes the './mendel-cli-mirror-gaia' placeholder. The "
            "embedded `--name mendel-v0-5-gaia` flag is intentionally "
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
    """Print or save the CLI-authored Mendel walkthrough.

    Mirrors ``examples/mendel-v0-5-gaia/CLI-AUTHORED.md`` as a single
    runnable bash script. The script drives ``gaia pkg scaffold``,
    ``gaia author <verb>`` (including ``variable`` and
    ``observe --value``), ``gaia bayes model`` /
    ``gaia bayes compare`` (with inline Distribution literals), and
    ``gaia pkg add-module`` / ``gaia author register-prior`` (multi-file
    priors) to produce a separately-scaffolded ``-gaia`` package that
    compiles to the same ``LocalCanonicalGraph`` (3 notes + 23 user
    claims + 17 auto-warrants + 1 bayes-implication helper = 44 nodes,
    9 derives, 7 operators, 6 priors in a sibling ``priors.py``) as the
    hand-authored ground truth.

    Mendel exercises every cli surface galileo does not — ``bayes``,
    ``Variable`` + Variable-targeted ``observe``, ``--background`` on
    every relation verb, multi-file routing — so this walkthrough is
    the empirical demonstration that the cli covers the full v0.5
    engine.

    Examples:
      $ gaia example mendel

      $ gaia example mendel --target ./my-demo

      $ gaia example mendel --out walkthrough.sh

      $ gaia example mendel --out walkthrough.sh --force
    """
    script = read_walkthrough(_FLAVOR)
    script = substitute_target(script, _PLACEHOLDER, target)
    emit(script, Path(out) if out is not None else None, force)


__all__ = ["mendel_command"]
