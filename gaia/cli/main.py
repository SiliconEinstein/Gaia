"""Gaia CLI — knowledge package authoring toolkit."""

import typer

from gaia.cli.commands.add import add_command
from gaia.cli.commands.check import check_command
from gaia.cli.commands.compile import compile_command
from gaia.cli.commands.infer import infer_command
from gaia.cli.commands.init import init_command
from gaia.cli.commands.register import register_command
from gaia.cli.commands.render import render_command
from gaia.cli.commands.inquiry import inquiry_app

app = typer.Typer(
    name="gaia",
    help="Gaia — knowledge package authoring toolkit.",
    no_args_is_help=True,
)


@app.callback()
def _callback() -> None:
    """Gaia — knowledge package authoring toolkit."""


app.command(name="add")(add_command)
app.command(name="compile")(compile_command)
app.command(name="check")(check_command)
app.command(name="infer")(infer_command)
app.command(name="init")(init_command)
app.command(name="register")(register_command)
app.command(name="render")(render_command)

app.add_typer(inquiry_app, name="inquiry")
app.add_typer(inquiry_app, name="inquery", hidden=True)  # typo alias
