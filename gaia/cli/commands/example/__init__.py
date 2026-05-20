"""``gaia example`` — print or save cli walkthrough scripts.

Show-cli surface for the two shipping v0.5 example packages
(``galileo``, ``mendel``). Each subverb reads a bundled
``walkthrough.sh`` from :mod:`gaia.cli.example_assets`, substitutes the
``--target NAME`` placeholder, and either prints the script to stdout
or writes it to a file.

The verb **does not execute the commands** and **does not generate
DSL files** — it is a documentation/scaffold helper that hands the
user a runnable sequence they can pipe through ``bash`` themselves, or
read to understand how a hand-authored example package was authored
through the cli.

Mirrors ``examples/<flavor>-v0-5-gaia/CLI-AUTHORED.md`` for the
shipping flavors; see those docs for the per-step narrative.
"""

from __future__ import annotations

import typer

from gaia.cli.commands.example.galileo import galileo_command
from gaia.cli.commands.example.mendel import mendel_command

example_app = typer.Typer(
    name="example",
    help=(
        "Print or save the cli walkthrough script for a shipping example "
        "package (galileo / mendel)."
    ),
    no_args_is_help=True,
)
example_app.command(name="galileo")(galileo_command)
example_app.command(name="mendel")(mendel_command)


__all__ = [
    "example_app",
    "galileo_command",
    "mendel_command",
]
