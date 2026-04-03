"""Gaia CLI — knowledge package authoring toolkit."""

import typer

from gaia.cli.commands.check import check_command
from gaia.cli.commands.compile import compile_command
from gaia.cli.commands.infer import infer_command
from gaia.cli.commands.register import register_command

app = typer.Typer(
    name="gaia",
    help="Gaia — knowledge package authoring toolkit.",
    no_args_is_help=True,
)


@app.callback()
def _callback() -> None:
    """Gaia — knowledge package authoring toolkit."""


app.command(name="compile")(compile_command)
app.command(name="check")(check_command)
app.command(name="infer")(infer_command)
app.command(name="register")(register_command)
