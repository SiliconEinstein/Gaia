"""Gaia CLI — knowledge package authoring toolkit.

Alpha 0 reorganizes the historical 9 flat verbs into 6 groups + `trace`
independent (per 协作单 `VgdMw7N5NikAHIkFu6UckWuznHI` 二·共识):

  build    init / compile / check
  run      infer / render
  inspect  starmap / starmap-replay
  review   (alpha 0: empty skeleton — held for downstream reviewer tooling)
  inquiry  (unchanged sub-app: focus / review / obligation / hypothesis / tactics / reject)
  pkg      add / register
  trace    (unchanged sub-app, NOT part of the 6 groups: verify / review / show)

Old flat verbs (`gaia compile <pkg>` etc.) are tombstoned: invoking them
prints a redirect message to stderr and exits with code 2. See
`gaia.cli.commands._flat_tombstones` for the mapping and
`docs/migration.md` for the migration guide.
"""

import typer

from gaia._meta import IR_SCHEMA, get_channel, get_commit, get_library_version
from gaia.cli.commands._flat_tombstones import register_flat_tombstones
from gaia.cli.commands.add import add_command
from gaia.cli.commands.check import check_command
from gaia.cli.commands.compile import compile_command
from gaia.cli.commands.infer import infer_command
from gaia.cli.commands.init import init_command
from gaia.cli.commands.inquiry import inquiry_app
from gaia.cli.commands.register import register_command
from gaia.cli.commands.render import render_command
from gaia.cli.commands.starmap import starmap_command
from gaia.cli.commands.starmap_replay import starmap_replay_command
from gaia.cli.commands.trace import trace_app

app = typer.Typer(
    name="gaia",
    help="Gaia — knowledge package authoring toolkit.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"gaia-lang {get_library_version()}")
        typer.echo(f"channel: {get_channel()}")
        typer.echo(f"commit: {get_commit()}")
        typer.echo(f"ir_schema: {IR_SCHEMA}")
        raise typer.Exit()


@app.callback()
def _callback(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version, channel, commit, and ir_schema; then exit.",
    ),
) -> None:
    """Gaia — knowledge package authoring toolkit."""


# --------------------------------------------------------------------------- #
# build — init / compile / check                                              #
# --------------------------------------------------------------------------- #

build_app = typer.Typer(
    name="build",
    help="Build artifacts (init / compile / check).",
    no_args_is_help=True,
)
build_app.command(name="init")(init_command)
build_app.command(name="compile")(compile_command)
build_app.command(name="check")(check_command)
app.add_typer(build_app, name="build")


# --------------------------------------------------------------------------- #
# run — infer / render                                                        #
# --------------------------------------------------------------------------- #

run_app = typer.Typer(
    name="run",
    help="Run inference and rendering (infer / render).",
    no_args_is_help=True,
)
run_app.command(name="infer")(infer_command)
run_app.command(name="render")(render_command)
app.add_typer(run_app, name="run")


# --------------------------------------------------------------------------- #
# inspect — starmap / starmap-replay                                          #
# --------------------------------------------------------------------------- #

inspect_app = typer.Typer(
    name="inspect",
    help="Inspect compiled artifacts (starmap / starmap-replay).",
    no_args_is_help=True,
)
inspect_app.command(name="starmap")(starmap_command)
inspect_app.command(name="starmap-replay")(starmap_replay_command)
app.add_typer(inspect_app, name="inspect")


# --------------------------------------------------------------------------- #
# review — reviewer tooling skeleton (alpha 0: empty)                         #
# --------------------------------------------------------------------------- #
#
# Per 协作单 二·共识, the `review` top-level group lands as a help-visible
# empty skeleton so downstream reviewer-tooling work has a stable home.
# It is *different* from `gaia inquiry review` and `gaia trace review` —
# those are pre-existing inner subcommands, untouched by alpha 0.

review_app = typer.Typer(
    name="review",
    help="Reviewer tooling (alpha 0: skeleton only — no commands yet).",
    no_args_is_help=True,
)


@review_app.callback(invoke_without_command=True)
def _review_skeleton(ctx: typer.Context) -> None:
    """Placeholder for the reviewer-tooling group.

    Alpha 0 ships this group as a help-visible skeleton; concrete commands
    will arrive in a later release. Invoking `gaia review` directly with no
    subcommand prints the help text (no_args_is_help=True).
    """
    if ctx.invoked_subcommand is None:
        # no_args_is_help handles the bare case; this branch is defensive.
        return


app.add_typer(review_app, name="review")


# --------------------------------------------------------------------------- #
# inquiry — existing sub-app (internals untouched)                            #
# --------------------------------------------------------------------------- #

app.add_typer(inquiry_app, name="inquiry")
app.add_typer(inquiry_app, name="inquery", hidden=True)  # typo alias


# --------------------------------------------------------------------------- #
# pkg — add / register                                                        #
# --------------------------------------------------------------------------- #

pkg_app = typer.Typer(
    name="pkg",
    help="Package operations (add / register).",
    no_args_is_help=True,
)
pkg_app.command(name="add")(add_command)
pkg_app.command(name="register")(register_command)
app.add_typer(pkg_app, name="pkg")


# --------------------------------------------------------------------------- #
# trace — existing sub-app, independent of the 6 groups                       #
# --------------------------------------------------------------------------- #

app.add_typer(trace_app, name="trace")


# --------------------------------------------------------------------------- #
# Flat-verb tombstones — direct cutover, no alias                             #
# --------------------------------------------------------------------------- #
#
# Each of the 9 historical flat verbs is replaced with a hidden stub that
# exits with code 2 and a stderr message pointing to the new grouped form.
# Hidden so they don't pollute `gaia --help`, but `gaia <flat>` still
# dispatches into the stub (Typer resolves command names regardless of
# `hidden` for invocation purposes).

register_flat_tombstones(app)
