"""Gaia CLI — knowledge package authoring toolkit.

The CLI organizes verbs into explicit top-level groups:

  sdk      generate the SDK reference + cheat sheet (start here, then
           author the DSL directly — the primary path)
  build    init / compile / check
  run      infer / render
  inspect  starmap
  review   (empty skeleton — held for downstream reviewer tooling)
  inquiry  (sub-app: focus / review / obligation / hypothesis / tactics / reject)
  pkg      add / add-import / add-module / register / scaffold
  author   OPTIONAL authoring convenience (primary path: `gaia sdk` + write
           the DSL directly). claim / artifact / figure / equal / derive /
           note / question / contradict / exclusive / decompose / observe /
           compute / infer / associate / parameter / register-prior /
           variable / depends-on / candidate-relation / materialize /
           compose / composition
  bayes    model / compare / distribution literals
  research external gaia-research plugin when installed
  example  galileo / mendel (print or save the cli walkthrough for a
           shipping v0.5 example package)
  trace    (independent sub-app: verify / review / show)

See `docs/migration.md` for guidance on moving off pre-alpha-0 invocations.
"""

import sys
from collections.abc import Iterable
from importlib import metadata
from typing import Any, Protocol

import typer

from gaia._meta import IR_SCHEMA, get_channel, get_commit, get_library_version
from gaia.cli.commands.add import add_command
from gaia.cli.commands.author import (
    artifact_command,
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
    figure_command,
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
from gaia.cli.commands.review import app as review_app
from gaia.cli.commands.sdk import sdk_command
from gaia.cli.commands.search import search_app
from gaia.cli.commands.skill import list_command as skill_list_command
from gaia.cli.commands.skill import register_command as skill_register_command
from gaia.cli.commands.starmap import starmap_command
from gaia.cli.commands.trace import trace_app

_CLI_PLUGIN_ENTRY_POINT_GROUP = "gaia.cli_plugins"


class _EntryPointLike(Protocol):
    name: str

    def load(self) -> object: ...


def _registered_top_level_names(root_app: typer.Typer) -> set[str]:
    names: set[str] = set()
    for command_info in root_app.registered_commands:
        if command_info.name is not None:
            names.add(command_info.name)
    for group_info in root_app.registered_groups:
        if group_info.name is not None:
            names.add(group_info.name)
    return names


_RegistrationSnapshot = tuple[list[Any], list[Any]]


def _registration_snapshot(root_app: typer.Typer) -> _RegistrationSnapshot:
    return (list(root_app.registered_commands), list(root_app.registered_groups))


def _rollback_registration(
    root_app: typer.Typer,
    snapshot: _RegistrationSnapshot,
) -> None:
    commands, groups = snapshot
    root_app.registered_commands[:] = commands
    root_app.registered_groups[:] = groups


def _new_registration_names(
    root_app: typer.Typer,
    snapshot: _RegistrationSnapshot,
) -> list[str]:
    command_count = len(snapshot[0])
    group_count = len(snapshot[1])
    names: list[str] = []
    for command_info in root_app.registered_commands[command_count:]:
        if command_info.name is not None:
            names.append(command_info.name)
    for group_info in root_app.registered_groups[group_count:]:
        if group_info.name is not None:
            names.append(group_info.name)
    return names


def _remove_registered_top_level_name(root_app: typer.Typer, name: str) -> None:
    root_app.registered_commands[:] = [
        command_info for command_info in root_app.registered_commands if command_info.name != name
    ]
    root_app.registered_groups[:] = [
        group_info for group_info in root_app.registered_groups if group_info.name != name
    ]


def _has_plugin_name_conflict(
    *,
    existing_names: set[str],
    new_names: list[str],
) -> bool:
    seen: set[str] = set()
    for name in new_names:
        if name in existing_names or name in seen:
            return True
        seen.add(name)
    return False


def _iter_cli_plugin_entry_points() -> list[_EntryPointLike]:
    entry_points = metadata.entry_points()
    if hasattr(entry_points, "select"):
        return list(entry_points.select(group=_CLI_PLUGIN_ENTRY_POINT_GROUP))
    return list(entry_points.get(_CLI_PLUGIN_ENTRY_POINT_GROUP, ()))  # type: ignore[attr-defined]


def load_cli_plugins(
    root_app: typer.Typer,
    *,
    entry_points: Iterable[_EntryPointLike] | None = None,
) -> list[str]:
    """Load installed CLI plugins from the ``gaia.cli_plugins`` entry point group."""
    loaded: list[str] = []
    selected_entry_points = (
        entry_points if entry_points is not None else _iter_cli_plugin_entry_points()
    )
    for entry_point in selected_entry_points:
        snapshot = _registration_snapshot(root_app)
        existing_names = _registered_top_level_names(root_app)
        if entry_point.name == "research":
            # Transitional handoff: gaia-research owns the public group when installed.
            _remove_registered_top_level_name(root_app, "research")
            existing_names = _registered_top_level_names(root_app)
        try:
            plugin = entry_point.load()
        except Exception:
            _rollback_registration(root_app, snapshot)
            continue
        if not callable(plugin):
            _rollback_registration(root_app, snapshot)
            continue
        try:
            plugin(root_app)
        except Exception:
            _rollback_registration(root_app, snapshot)
            continue
        new_names = _new_registration_names(root_app, snapshot)
        if _has_plugin_name_conflict(
            existing_names=existing_names,
            new_names=new_names,
        ):
            _rollback_registration(root_app, snapshot)
            continue
        loaded.append(entry_point.name)
    return loaded


_MISSING_RESEARCH_HINT = (
    "The research workflow now ships separately. Install the gaia-research "
    "package to enable `gaia research`, for example: pip install gaia-research"
)


def add_missing_research_hint(root_app: typer.Typer) -> None:
    """Add a hidden ``gaia research`` hint when no installed plugin provides it."""
    if "research" in _registered_top_level_names(root_app):
        return

    @root_app.command(
        name="research",
        hidden=True,
        help=_MISSING_RESEARCH_HINT,
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def _missing_research_plugin(_ctx: typer.Context) -> None:
        typer.echo(_MISSING_RESEARCH_HINT, err=True)
        raise typer.Exit(4)


_ROOT_EPILOG = (
    "What gaia does:\n\n"
    "  Gaia turns a structured argument — claims, observations, "
    "derivations — into a compiled Bayesian network. Start with "
    "`gaia sdk` to get the SDK reference + cheat sheet, then author the "
    "DSL directly in Python (the primary path; `gaia author …` is an "
    "optional convenience). Compile with `gaia build compile`, run "
    "inference with `gaia run infer`, and render a slide-deck-ready "
    "artifact with `gaia run render`. "
    "See `gaia example galileo` for an end-to-end walkthrough.\n\n"
    "What is a knowledge package?\n\n"
    "  A knowledge package is a small Python project that captures a "
    "structured argument — premises, derivations, observations — that "
    "gaia compiles into a Bayesian network. The shipped examples "
    "(`gaia example galileo`, `gaia example mendel`) walk through "
    "building one end-to-end.\n\n"
    "Typical authoring flow:\n\n"
    "  $ gaia build init my-pkg-gaia\n\n"
    "  $ gaia sdk            # SDK reference + CHEATSHEET.md; author directly\n\n"
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
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version, channel, commit, and ir_schema; then exit.",
    ),
) -> None:
    """Gaia — knowledge package authoring toolkit."""
    # Non-blocking PyPI update check (after the eager --version short-circuit;
    # `version` is True only while that eager callback runs and exits first).
    # Skip the bare-help / no-args case — there is no subcommand to run, and the
    # help screen should stay quiet. Broad guard so this can NEVER break the CLI.
    if version or ctx.invoked_subcommand is None:
        return
    # Keep *subcommand* help screens quiet too. `gaia build --help`,
    # `gaia inquiry --help`, `gaia inquiry focus --help`, etc. still route
    # through this root callback before Typer renders the help (invoked_subcommand
    # is the group/command, not None), so the no-args guard above misses them.
    # The not-yet-parsed --help only exists in argv at this point, so check it
    # there. Conservative: a stray -h option *value* would suppress a single
    # notice — harmless for a fail-silent check.
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        return
    try:
        from gaia.cli._update_check import maybe_notify_update

        maybe_notify_update()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# sdk — the first/primary entry: generate the SDK reference + cheat sheet      #
# --------------------------------------------------------------------------- #
#
# Authoring the Gaia DSL directly via the Python SDK is the recommended
# first move. `gaia sdk` writes a self-contained Markdown reference plus a
# one-page CHEATSHEET.md into --out (default ./gaia-sdk/) so an author —
# human or agent — can read the surface and write DSL statements directly.
# The `gaia author` CLI is an optional convenience, not a peer first-entry.

app.command(name="sdk")(sdk_command)


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
# inspect — starmap                                                           #
# --------------------------------------------------------------------------- #

inspect_app = typer.Typer(
    name="inspect",
    help="Inspect compiled artifacts (starmap).",
    no_args_is_help=True,
)
inspect_app.command(name="starmap")(starmap_command)
app.add_typer(inspect_app, name="inspect")


# --------------------------------------------------------------------------- #
# review — unified reviewer tooling (status / comprehensive / manifest)       #
# --------------------------------------------------------------------------- #
#
# The `review` top-level group provides a unified interface across all three
# review layers: ReviewManifest (IR-level), Inquiry Review (semantic), and
# Trace Review (ARM verification). This is *different* from the specialized
# `gaia inquiry review` and `gaia trace review` — those are deep dives into
# specific aspects, while `gaia review` orchestrates and aggregates.

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
# author — OPTIONAL authoring CLI (21 verbs: 18 statement-emitting +          #
#          2 file-based validate-and-register + 1 read-only list)             #
# --------------------------------------------------------------------------- #
#
# Direct SDK authoring (run `gaia sdk`, write the DSL directly) is the
# primary path. The author group is an OPTIONAL convenience that CRUDs the
# same DSL statements through structured commands — useful for machine-
# checked appends, but not the recommended first move. Every write is
# confined to the package's composed ``authored/`` submodule; the CLI
# never writes the package-root ``__init__.py``. 18 statement-emitting
# verbs share the same pre-write + envelope skeleton; ``compose`` /
# ``composition`` use a file-based validate-and-register surface (see
# gaia.cli.commands.author.compose).

author_app = typer.Typer(
    name="author",
    help=(
        "Optional authoring convenience (primary path: `gaia sdk` + write the "
        "DSL directly). Writes into the package's authored/ submodule. Verbs: "
        "claim / artifact / figure / equal / derive / note / question / "
        "contradict / exclusive / decompose / observe / compute / infer / "
        "associate / parameter / register-prior / variable / depends-on / "
        "candidate-relation / materialize / compose / composition / list."
    ),
    no_args_is_help=True,
)
# Knowledge tier.
author_app.command(name="claim")(claim_command)
author_app.command(name="artifact")(artifact_command)
author_app.command(name="figure")(figure_command)
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
# skill — materialise bundled SKILL.md registry into cwd                      #
# --------------------------------------------------------------------------- #
#
# `gaia skill register` copies the in-package `gaia/_skills/` tree into a
# per-cwd `.gaia-skills/` registry and symlinks each skill into
# `.claude/skills/` and/or `.agent/skills/`. `gaia skill list` reports the
# diff. POSIX-only; see `gaia.cli.commands.skill` for the safety contract.

skill_app = typer.Typer(
    name="skill",
    help="Materialise bundled Gaia skills into cwd (register / list).",
    no_args_is_help=True,
)
skill_app.command(name="register")(skill_register_command)
skill_app.command(name="list")(skill_list_command)
app.add_typer(skill_app, name="skill")


# --------------------------------------------------------------------------- #
# search — retrieval backends (sub-app: lkm)                                  #
# --------------------------------------------------------------------------- #
#
# `gaia search lkm <verb>` wraps the Bohrium LKM public search API as five
# atomic verbs (1:1 with the HTTP endpoints) plus an `auth` credential
# lifecycle. The `search` parent leaves room for future non-LKM retrieval
# backends; see `gaia.cli.commands.search`.

app.add_typer(search_app, name="search")


# --------------------------------------------------------------------------- #
# trace — existing sub-app, independent of the verb groups                    #
# --------------------------------------------------------------------------- #

app.add_typer(trace_app, name="trace")


load_cli_plugins(app)
add_missing_research_hint(app)
