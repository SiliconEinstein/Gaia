"""Gaia CLI — knowledge package authoring toolkit.

The CLI organizes verbs into explicit top-level groups:

  build    init / compile / check
  run      infer / render
  inspect  starmap / starmap-replay
  review   (empty skeleton — held for downstream reviewer tooling)
  inquiry  (sub-app: focus / review / obligation / hypothesis / tactics / reject)
  pkg      add / add-import / add-module / register / scaffold
  author   claim / equal / derive / note / question / contradict / exclusive /
           decompose / observe / compute / infer / associate / parameter /
           register-prior / variable / depends-on / candidate-relation /
           materialize / compose / composition
  bayes    model / compare / distribution literals
  example  galileo / mendel (print or save the cli walkthrough for a
           shipping v0.5 example package)
  trace    (independent sub-app: verify / review / show)

See `docs/migration.md` for guidance on moving off pre-alpha-0 invocations.
"""

import typer

from gaia._meta import IR_SCHEMA, get_channel, get_commit, get_library_version
from gaia.cli.commands.add import add_command
from gaia.cli.commands.author import (
    associate_command,
    candidate_relation_command,
    claim_command,
    compose_command,
    composition_command,
    compute_command,
    contradict_command,
    decompose_command,
    depends_on_command,
    derive_command,
    equal_command,
    exclusive_command,
    list_command,
    materialize_command,
    note_command,
    observe_command,
    parameter_command,
    question_command,
    register_prior_command,
    variable_command,
)
from gaia.cli.commands.author import (
    infer_command as author_infer_command,
)
from gaia.cli.commands.bayes import (
    beta_command,
    betabinomial_command,
    binomial_command,
    cauchy_command,
    chisquared_command,
    exponential_command,
    gamma_command,
    lognormal_command,
    normal_command,
    poisson_command,
    studentt_command,
)
from gaia.cli.commands.bayes import compare_command as bayes_compare_command
from gaia.cli.commands.bayes import (
    model_command as bayes_model_command,
)
from gaia.cli.commands.check import check_command
from gaia.cli.commands.compile import compile_command
from gaia.cli.commands.example import example_app
from gaia.cli.commands.infer import infer_command
from gaia.cli.commands.init import init_command
from gaia.cli.commands.inquiry import inquiry_app
from gaia.cli.commands.pkg import add_import_command, add_module_command, scaffold_command
from gaia.cli.commands.register import register_command
from gaia.cli.commands.render import render_command
from gaia.cli.commands.starmap import starmap_command
from gaia.cli.commands.starmap_replay import starmap_replay_command
from gaia.cli.commands.trace import trace_app

_ROOT_EPILOG = (
    "What is a knowledge package?\n\n"
    "  A knowledge package is a small Python project that captures a "
    "structured argument — premises, derivations, observations — that "
    "gaia compiles into a Bayesian network. The shipped examples "
    "(`gaia example galileo`, `gaia example mendel`) walk through "
    "building one end-to-end.\n\n"
    "Typical authoring flow:\n\n"
    "  $ gaia build init my-pkg-gaia\n\n"
    '  $ gaia author claim "..." --target ./my-pkg-gaia\n\n'
    "  $ gaia build compile ./my-pkg-gaia\n\n"
    "  $ gaia run infer ./my-pkg-gaia\n\n"
    "Run `gaia <group> --help` for per-group verb references.\n\n"
    "Run `gaia example --help` to see how a full demo is authored."
)

app = typer.Typer(
    name="gaia",
    help="Gaia — knowledge package authoring toolkit.",
    epilog=_ROOT_EPILOG,
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
# The `review` top-level group lands as a help-visible empty skeleton
# so downstream reviewer-tooling work has a stable home. It is
# *different* from `gaia inquiry review` and `gaia trace review` —
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
# pkg — add / add-import / add-module / register / scaffold                    #
# --------------------------------------------------------------------------- #

pkg_app = typer.Typer(
    name="pkg",
    help="Package operations (add / add-import / add-module / register / scaffold).",
    no_args_is_help=True,
)
pkg_app.command(name="add")(add_command)
pkg_app.command(name="add-import")(add_import_command)
pkg_app.command(name="add-module")(add_module_command)
pkg_app.command(name="register")(register_command)
pkg_app.command(name="scaffold")(scaffold_command)
app.add_typer(pkg_app, name="pkg")


# --------------------------------------------------------------------------- #
# author — agent-first authoring CLI (21 verbs: 18 statement-emitting +     #
#          2 file-based validate-and-register + 1 read-only list)             #
# --------------------------------------------------------------------------- #
#
# The author group is the cli-as-client surface that lets an LLM agent
# (or a human) CRUD Gaia DSL statements through structured commands
# instead of editing `.gaia.py` source by hand. 18 statement-emitting
# verbs share the same pre-write + envelope skeleton; ``compose`` /
# ``composition`` use a file-based validate-and-register surface (see
# gaia.cli.commands.author.compose).

author_app = typer.Typer(
    name="author",
    help=(
        "Author DSL statements (claim / equal / derive / note / question / "
        "contradict / exclusive / decompose / observe / compute / infer / "
        "associate / parameter / register-prior / variable / depends-on / "
        "candidate-relation / materialize / compose / composition / list)."
    ),
    no_args_is_help=True,
)
# Knowledge tier.
author_app.command(name="claim")(claim_command)
author_app.command(name="note")(note_command)
author_app.command(name="question")(question_command)
# Structural relations.
author_app.command(name="equal")(equal_command)
author_app.command(name="contradict")(contradict_command)
author_app.command(name="exclusive")(exclusive_command)
author_app.command(name="decompose")(decompose_command)
# Support tier.
author_app.command(name="derive")(derive_command)
author_app.command(name="observe")(observe_command)
author_app.command(name="compute")(compute_command)
# Probabilistic.
author_app.command(name="infer")(author_infer_command)
author_app.command(name="associate")(associate_command)
# Sugar + prior.
author_app.command(name="parameter")(parameter_command)
author_app.command(name="register-prior")(register_prior_command)
# Typed terms.
author_app.command(name="variable")(variable_command)
# Scaffold tier of the DSL surface.
author_app.command(name="depends-on")(depends_on_command)
author_app.command(name="candidate-relation")(candidate_relation_command)
author_app.command(name="materialize")(materialize_command)
# File-based verbs: validate-and-register a @compose/@composition pattern.
author_app.command(name="compose")(compose_command)
author_app.command(name="composition")(composition_command)
# Read-only inspection: walk source AST + pyproject for a snapshot.
author_app.command(name="list")(list_command)
app.add_typer(author_app, name="author")


# --------------------------------------------------------------------------- #
# bayes — Bayesian-modelling cli surface                                      #
# --------------------------------------------------------------------------- #
#
# Top-level group `gaia bayes <verb>` mirrors `gaia.engine.bayes`
# organisation. Verbs: model / compare plus one verb per shipping
# Distribution class.

bayes_app = typer.Typer(
    name="bayes",
    help=(
        "Bayesian-modelling authoring (model / compare / Binomial / "
        "BetaBinomial / Normal / LogNormal / Beta / Exponential / Gamma / "
        "StudentT / Cauchy / ChiSquared / Poisson)."
    ),
    no_args_is_help=True,
)
bayes_app.command(name="model")(bayes_model_command)
bayes_app.command(name="compare")(bayes_compare_command)
# Distribution literal verbs — one per shipping class.
bayes_app.command(name="binomial")(binomial_command)
bayes_app.command(name="beta-binomial")(betabinomial_command)
bayes_app.command(name="poisson")(poisson_command)
bayes_app.command(name="normal")(normal_command)
bayes_app.command(name="log-normal")(lognormal_command)
bayes_app.command(name="beta")(beta_command)
bayes_app.command(name="exponential")(exponential_command)
bayes_app.command(name="gamma")(gamma_command)
bayes_app.command(name="student-t")(studentt_command)
bayes_app.command(name="cauchy")(cauchy_command)
bayes_app.command(name="chi-squared")(chisquared_command)
app.add_typer(bayes_app, name="bayes")


# --------------------------------------------------------------------------- #
# example — print or save cli walkthrough scripts                             #
# --------------------------------------------------------------------------- #
#
# Show-cli surface for the shipping v0.5 example packages. Each subverb
# reads a bundled ``walkthrough.sh`` from
# :mod:`gaia.cli.example_assets`, substitutes the ``--target NAME``
# placeholder, and either prints to stdout or writes to a file. The
# verb does NOT execute the commands; it is a documentation / scaffold
# helper that hands the user a runnable sequence.

app.add_typer(example_app, name="example")


# --------------------------------------------------------------------------- #
# trace — existing sub-app, independent of the verb groups                    #
# --------------------------------------------------------------------------- #

app.add_typer(trace_app, name="trace")
