"""Shared helpers for ``gaia example <flavor>`` subverbs.

Each subverb reads a bundled ``walkthrough.sh`` from
:mod:`gaia.cli.example_assets`, substitutes the ``--target NAME``
placeholder, and either prints the script to stdout or writes it to a
file. The helpers live here so the top-level :mod:`gaia.cli.commands.example`
can import the subverbs without circling back through itself.
"""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path

import typer


def read_walkthrough(flavor: str) -> str:
    """Return the bundled ``walkthrough.sh`` text for ``flavor``.

    The ``flavor`` argument is the subdirectory name under
    :mod:`gaia.cli.example_assets` (``galileo`` / ``mendel``).
    """
    asset = resources.files("gaia.cli.example_assets") / flavor / "walkthrough.sh"
    return asset.read_text(encoding="utf-8")


def substitute_target(script: str, placeholder: str, target: str) -> str:
    """Substitute the package-directory placeholder in ``script``.

    Replaces both the ``--target ./<placeholder>`` form **and** the
    bare ``<placeholder>`` occurrences (used inside the inline
    ``python -c`` cleanup blocks). The longer ``./<placeholder>`` form
    is substituted first so the shorter bare form does not double-match.

    The ``--name`` flag inside the script is intentionally left alone:
    only the on-disk directory changes when the caller passes
    ``--target NAME``. Each subverb's docstring documents this.
    """
    bare = placeholder.lstrip("./")
    target_bare = target.lstrip("./")
    # Order matters: replace './<bare>' first, then the leftover bare form.
    return script.replace(f"./{bare}", target).replace(bare, target_bare)


def emit(script: str, out: Path | None, force: bool) -> None:
    """Print to stdout or write to a file.

    When ``out`` is :data:`None`, the script is written to stdout
    (newline-terminated). When ``out`` is set, the script is written
    to that path; an existing file is refused unless ``force`` is
    :data:`True`.
    """
    if out is None:
        sys.stdout.write(script)
        if not script.endswith("\n"):
            sys.stdout.write("\n")
        return
    if out.exists() and not force:
        typer.echo(
            f"refusing to overwrite existing file {out} (pass --force to overwrite)",
            err=True,
        )
        raise typer.Exit(code=1)
    out.write_text(script, encoding="utf-8")


__all__ = ["emit", "read_walkthrough", "substitute_target"]
