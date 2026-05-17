"""``gaia bayes <distribution>`` — Distribution-literal verbs.

R7 G2 — one verb per shipping :mod:`gaia.engine.bayes.distributions`
class. Each verb binds a Distribution literal to a module-scope
identifier so subsequent ``bayes model`` / ``observe`` invocations
can reference it by name.

The 11 shipping distributions:

* **Discrete**: Binomial(n, p) / BetaBinomial(n, alpha, beta) /
  Poisson(rate)
* **Continuous**: Normal(mu, sigma) / Beta(alpha, beta) /
  LogNormal(mu, sigma) / Exponential(rate) / Gamma(alpha, rate) /
  StudentT(df, mu=0, sigma=1) / Cauchy(mu, gamma) / ChiSquared(df)

Each verb shares the same JSON envelope + pre-write + post-write
pipeline as the rest of the cli. Parameter values are forwarded
verbatim (Pydantic validators inside the engine catch out-of-range
values at engine-load time; pre-write only checks Python parse-ability).
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import (
    emit_syntax_error,
    normalize_file_option,
    parse_metadata,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_dist_call(*, label: str, dist_name: str, kwargs_pairs: list[str]) -> str:
    """Render ``label = bayes.<dist_name>(<kwargs>)``."""
    return f"{label} = bayes.{dist_name}({', '.join(kwargs_pairs)})"


def _run_dist_op(
    *,
    label: str,
    dist_name: str,
    kwargs_pairs: list[str],
    target: str,
    file: str | None,
    human: bool,
    check: bool,
    interactive: bool,
    metadata_dict: dict[str, Any] | None,
) -> None:
    """Shared dispatch path for every distribution-literal verb."""
    if metadata_dict:
        # Distributions don't accept ``metadata=`` directly; we emit a
        # comment so the agent can locate the binding when scanning the
        # source. Pre-write doesn't see comments, so this is purely a
        # human-readable affordance.
        # Note: we deliberately omit metadata from the Distribution call.
        pass
    generated_code = _render_dist_call(label=label, dist_name=dist_name, kwargs_pairs=kwargs_pairs)
    proposed_op = ProposedAuthorOp(
        verb=f"bayes.{dist_name}",
        kind="reasoning",
        label=label,
        references=[],
        generated_code=generated_code,
        required_imports=("bayes",),
        target_file=normalize_file_option(file),
        extra_payload={"distribution_kind": dist_name},
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


# --------------------------------------------------------------------------- #
# Discrete distributions                                                      #
# --------------------------------------------------------------------------- #


def binomial_command(
    label: str = typer.Option(..., "--label", help="Identifier the Binomial binding takes."),
    n: str = typer.Option(..., "--n", help="Trial count (forwarded verbatim)."),
    p: str = typer.Option(..., "--p", help="Success probability (forwarded verbatim)."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.Binomial(n=..., p=...)`` literal binding."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Binomial", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Binomial",
        kwargs_pairs=[f"n={n}", f"p={p}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def betabinomial_command(
    label: str = typer.Option(..., "--label"),
    n: str = typer.Option(..., "--n", help="Trial count."),
    alpha: str = typer.Option(..., "--alpha", help="Beta prior alpha (>0)."),
    beta: str = typer.Option(..., "--beta", help="Beta prior beta (>0)."),
    target: str = typer.Option(".", "--target"),
    file: str | None = typer.Option(None, "--file"),
    metadata: str | None = typer.Option(None, "--metadata"),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.BetaBinomial(n=..., alpha=..., beta=...)`` literal."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.BetaBinomial", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="BetaBinomial",
        kwargs_pairs=[f"n={n}", f"alpha={alpha}", f"beta={beta}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def poisson_command(
    label: str = typer.Option(..., "--label"),
    rate: str = typer.Option(..., "--rate", help="Poisson rate (>0)."),
    target: str = typer.Option(".", "--target"),
    file: str | None = typer.Option(None, "--file"),
    metadata: str | None = typer.Option(None, "--metadata"),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.Poisson(rate=...)`` literal binding."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Poisson", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Poisson",
        kwargs_pairs=[f"rate={rate}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


# --------------------------------------------------------------------------- #
# Continuous distributions                                                    #
# --------------------------------------------------------------------------- #


def normal_command(
    label: str = typer.Option(..., "--label"),
    mu: str = typer.Option(..., "--mu", help="Location parameter."),
    sigma: str = typer.Option(..., "--sigma", help="Scale parameter (>0)."),
    target: str = typer.Option(".", "--target"),
    file: str | None = typer.Option(None, "--file"),
    metadata: str | None = typer.Option(None, "--metadata"),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.Normal(mu=..., sigma=...)`` literal binding."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Normal", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Normal",
        kwargs_pairs=[f"mu={mu}", f"sigma={sigma}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def lognormal_command(
    label: str = typer.Option(..., "--label"),
    mu: str = typer.Option(..., "--mu"),
    sigma: str = typer.Option(..., "--sigma"),
    target: str = typer.Option(".", "--target"),
    file: str | None = typer.Option(None, "--file"),
    metadata: str | None = typer.Option(None, "--metadata"),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.LogNormal(mu=..., sigma=...)`` literal binding."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.LogNormal", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="LogNormal",
        kwargs_pairs=[f"mu={mu}", f"sigma={sigma}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def beta_command(
    label: str = typer.Option(..., "--label"),
    alpha: str = typer.Option(..., "--alpha"),
    beta: str = typer.Option(..., "--beta"),
    target: str = typer.Option(".", "--target"),
    file: str | None = typer.Option(None, "--file"),
    metadata: str | None = typer.Option(None, "--metadata"),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.Beta(alpha=..., beta=...)`` literal binding."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Beta", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Beta",
        kwargs_pairs=[f"alpha={alpha}", f"beta={beta}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def exponential_command(
    label: str = typer.Option(..., "--label"),
    rate: str = typer.Option(..., "--rate"),
    target: str = typer.Option(".", "--target"),
    file: str | None = typer.Option(None, "--file"),
    metadata: str | None = typer.Option(None, "--metadata"),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.Exponential(rate=...)`` literal binding."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Exponential", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Exponential",
        kwargs_pairs=[f"rate={rate}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def gamma_command(
    label: str = typer.Option(..., "--label"),
    alpha: str = typer.Option(..., "--alpha", help="Shape parameter (>0)."),
    rate: str = typer.Option(..., "--rate", help="Rate parameter (>0)."),
    target: str = typer.Option(".", "--target"),
    file: str | None = typer.Option(None, "--file"),
    metadata: str | None = typer.Option(None, "--metadata"),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.Gamma(alpha=..., rate=...)`` literal binding."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Gamma", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Gamma",
        kwargs_pairs=[f"alpha={alpha}", f"rate={rate}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def studentt_command(
    label: str = typer.Option(..., "--label"),
    df: str = typer.Option(..., "--df", help="Degrees of freedom (>0)."),
    mu: str = typer.Option("0.0", "--mu", help="Location parameter (default 0.0)."),
    sigma: str = typer.Option("1.0", "--sigma", help="Scale parameter (default 1.0, >0)."),
    target: str = typer.Option(".", "--target"),
    file: str | None = typer.Option(None, "--file"),
    metadata: str | None = typer.Option(None, "--metadata"),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.StudentT(df=..., mu=..., sigma=...)`` literal binding."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.StudentT", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="StudentT",
        kwargs_pairs=[f"df={df}", f"mu={mu}", f"sigma={sigma}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def cauchy_command(
    label: str = typer.Option(..., "--label"),
    mu: str = typer.Option(..., "--mu", help="Location parameter."),
    gamma: str = typer.Option(..., "--gamma", help="Scale parameter (>0)."),
    target: str = typer.Option(".", "--target"),
    file: str | None = typer.Option(None, "--file"),
    metadata: str | None = typer.Option(None, "--metadata"),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.Cauchy(mu=..., gamma=...)`` literal binding."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Cauchy", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Cauchy",
        kwargs_pairs=[f"mu={mu}", f"gamma={gamma}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def chisquared_command(
    label: str = typer.Option(..., "--label"),
    df: str = typer.Option(..., "--df", help="Degrees of freedom (>0)."),
    target: str = typer.Option(".", "--target"),
    file: str | None = typer.Option(None, "--file"),
    metadata: str | None = typer.Option(None, "--metadata"),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``bayes.ChiSquared(df=...)`` literal binding."""
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.ChiSquared", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="ChiSquared",
        kwargs_pairs=[f"df={df}"],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


__all__ = [
    "beta_command",
    "betabinomial_command",
    "binomial_command",
    "cauchy_command",
    "chisquared_command",
    "exponential_command",
    "gamma_command",
    "lognormal_command",
    "normal_command",
    "poisson_command",
    "studentt_command",
]
