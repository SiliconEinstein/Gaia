"""``gaia bayes <distribution>`` — Distribution-literal verbs.

One verb per shipping :mod:`gaia.engine.lang` Distribution factory.
Each verb binds a Distribution literal to a module-scope identifier so
subsequent ``bayes model`` / ``observe`` invocations can reference it
by name.

The 11 shipping distributions:

* **Discrete**: Binomial(n, p) / BetaBinomial(n, alpha, beta) /
  Poisson(rate)
* **Continuous**: Normal(mu, sigma) / Beta(alpha, beta) /
  LogNormal(mu, sigma) / Exponential(rate) / Gamma(alpha, rate) /
  StudentT(df, mu=0, sigma=1) / Cauchy(mu, gamma) / ChiSquared(df)

Each verb shares the same JSON envelope + pre-write + post-write
pipeline as the rest of the cli. Parameter values pass through
:func:`parse_literal_or_identifier` — a literal (``--n 395`` /
``--p 0.5``) or a bare identifier (``--n N_TRIALS``) is accepted;
arbitrary Python expressions are refused at the flag boundary with
``prewrite.expr_unsafe`` so the splice-into-generated-source RCE
vector is closed.
"""

from __future__ import annotations

from typing import Any

import typer

from gaia.cli.commands.author._common import (
    PrewriteUnsafeError,
    build_sibling_imports,
    emit_syntax_error,
    normalize_file_option,
    parse_literal_or_identifier,
    parse_metadata,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op


def _render_dist_call(*, label: str, dist_name: str, kwargs_pairs: list[str]) -> str:
    """Render ``label = <dist_name>(content, <kwargs>)``."""
    args = [repr(label), *kwargs_pairs]
    return f"{label} = {dist_name}({', '.join(args)})"


def _validate_params(
    *,
    verb: str,
    params: list[tuple[str, str]],
    target: str,
    human: bool,
) -> tuple[list[str], list[str]] | None:
    """Run every parameter through the literal-or-identifier validator.

    Returns ``(kwargs_pairs, references)`` on success, or ``None`` when
    a parameter is rejected (the helper has already emitted the
    envelope and exited via :class:`typer.Exit`).
    """
    references: list[str] = []
    kwargs_pairs: list[str] = []
    for name, raw in params:
        try:
            _, rendered = parse_literal_or_identifier(raw, references_sink=references)
        except PrewriteUnsafeError as exc:
            emit_syntax_error(
                verb,
                f"--{name} rejected: {exc}",
                target=target,
                human=human,
                kind="prewrite.expr_unsafe",
            )
            return None
        kwargs_pairs.append(f"{name}={rendered}")
    return kwargs_pairs, references


def _run_dist_op(
    *,
    label: str,
    dist_name: str,
    params: list[tuple[str, str]],
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
    validation = _validate_params(
        verb=f"bayes.{dist_name}",
        params=params,
        target=target,
        human=human,
    )
    if validation is None:
        return
    kwargs_pairs, references = validation
    generated_code = _render_dist_call(label=label, dist_name=dist_name, kwargs_pairs=kwargs_pairs)
    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb=f"bayes.{dist_name}",
        kind="reasoning",
        label=label,
        references=references,
        generated_code=generated_code,
        required_imports=(dist_name,),
        target_file=target_file,
        sibling_imports=build_sibling_imports(references, target_file=target_file),
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
    n: str = typer.Option(..., "--n", help="Trial count: numeric literal or bare identifier."),
    p: str = typer.Option(
        ..., "--p", help="Success probability: numeric literal or bare identifier."
    ),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``Binomial(content, n=..., p=...)`` literal binding.

    Renders ``<label> = Binomial('<label>', n=..., p=...)`` into the target
    module. ``--n`` and ``--p`` accept a numeric literal (``--n 395``,
    ``--p 0.75``) or a bare module-scope identifier (``--n TOTAL_COUNT``,
    ``--p MENDELIAN_DOMINANT_PROBABILITY``); each identifier must already
    be importable in the target file.

    Example:

    .. code-block:: bash

        gaia bayes binomial --label mendel_binomial --n 395 --p 0.75
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Binomial", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Binomial",
        params=[("n", n), ("p", p)],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def betabinomial_command(
    label: str = typer.Option(..., "--label", help="Identifier the BetaBinomial binding takes."),
    n: str = typer.Option(..., "--n", help="Trial count: numeric literal or bare identifier."),
    alpha: str = typer.Option(..., "--alpha", help="Beta prior alpha (>0): literal or identifier."),
    beta: str = typer.Option(..., "--beta", help="Beta prior beta (>0): literal or identifier."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``BetaBinomial(content, n=..., alpha=..., beta=...)`` literal.

    Renders the BetaBinomial(n, alpha, beta) predictive distribution as
    a standalone binding; common as the diffuse / uniform-mean reference
    model in a likelihood comparison (``alpha=1, beta=1`` collapses to
    the uniform 1/(n+1) over counts). Each parameter accepts a numeric
    literal or a bare module-scope identifier.

    Example:

    .. code-block:: bash

        gaia bayes beta-binomial --label diffuse_binomial \\
            --n 395 --alpha 1.0 --beta 1.0
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.BetaBinomial", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="BetaBinomial",
        params=[("n", n), ("alpha", alpha), ("beta", beta)],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def poisson_command(
    label: str = typer.Option(..., "--label", help="Identifier the Poisson binding takes."),
    rate: str = typer.Option(..., "--rate", help="Poisson rate (>0): literal or identifier."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``Poisson(content, rate=...)`` literal binding.

    Renders the single-parameter Poisson(rate) distribution as a
    standalone binding. ``--rate`` accepts a numeric literal or a bare
    module-scope identifier (e.g. an expected-count constant).

    Example:

    .. code-block:: bash

        gaia bayes poisson --label arrival_rate_model --rate 4.2
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Poisson", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Poisson",
        params=[("rate", rate)],
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
    label: str = typer.Option(..., "--label", help="Identifier the Normal binding takes."),
    mu: str = typer.Option(..., "--mu", help="Location parameter: literal or identifier."),
    sigma: str = typer.Option(..., "--sigma", help="Scale parameter (>0): literal or identifier."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``Normal(content, mu=..., sigma=...)`` literal binding.

    Renders the Normal(mu, sigma) distribution as a standalone binding.
    Each parameter accepts a numeric literal or a bare module-scope
    identifier.

    Example:

    .. code-block:: bash

        gaia bayes normal --label measurement_noise --mu 0.0 --sigma 1.5
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Normal", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Normal",
        params=[("mu", mu), ("sigma", sigma)],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def lognormal_command(
    label: str = typer.Option(..., "--label", help="Identifier the LogNormal binding takes."),
    mu: str = typer.Option(..., "--mu", help="Location parameter of the underlying Normal."),
    sigma: str = typer.Option(..., "--sigma", help="Scale of the underlying Normal (>0)."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``LogNormal(content, mu=..., sigma=...)`` literal binding.

    Renders LogNormal(mu, sigma) — the distribution of ``exp(X)`` for
    ``X ~ Normal(mu, sigma)``. Common for positively-supported
    multiplicative noise. Each parameter accepts a numeric literal or a
    bare module-scope identifier.

    Example:

    .. code-block:: bash

        gaia bayes log-normal --label price_noise --mu 0.0 --sigma 0.3
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.LogNormal", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="LogNormal",
        params=[("mu", mu), ("sigma", sigma)],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def beta_command(
    label: str = typer.Option(..., "--label", help="Identifier the Beta binding takes."),
    alpha: str = typer.Option(..., "--alpha", help="Shape alpha (>0): literal or identifier."),
    beta: str = typer.Option(..., "--beta", help="Shape beta (>0): literal or identifier."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``Beta(content, alpha=..., beta=...)`` literal binding.

    Renders Beta(alpha, beta) on (0, 1) — the canonical conjugate prior
    for Bernoulli / Binomial success rates. ``alpha=1, beta=1`` is
    uniform. Each parameter accepts a numeric literal or a bare
    module-scope identifier.

    Example:

    .. code-block:: bash

        gaia bayes beta --label success_rate_prior --alpha 2.0 --beta 5.0
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Beta", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Beta",
        params=[("alpha", alpha), ("beta", beta)],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def exponential_command(
    label: str = typer.Option(..., "--label", help="Identifier the Exponential binding takes."),
    rate: str = typer.Option(..., "--rate", help="Rate (>0): literal or identifier."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``Exponential(content, rate=...)`` literal binding.

    Renders the single-parameter Exponential(rate) distribution on
    positive reals — mean ``1/rate``. ``--rate`` accepts a numeric
    literal or a bare module-scope identifier.

    Example:

    .. code-block:: bash

        gaia bayes exponential --label decay_time --rate 0.5
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Exponential", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Exponential",
        params=[("rate", rate)],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def gamma_command(
    label: str = typer.Option(..., "--label", help="Identifier the Gamma binding takes."),
    alpha: str = typer.Option(..., "--alpha", help="Shape parameter (>0)."),
    rate: str = typer.Option(..., "--rate", help="Rate parameter (>0)."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``Gamma(content, alpha=..., rate=...)`` literal binding.

    Renders Gamma(alpha, rate) on positive reals — mean ``alpha/rate``.
    Common as a conjugate prior for Poisson rates. Each parameter accepts
    a numeric literal or a bare module-scope identifier.

    Example:

    .. code-block:: bash

        gaia bayes gamma --label rate_prior --alpha 2.0 --rate 0.5
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Gamma", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Gamma",
        params=[("alpha", alpha), ("rate", rate)],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def studentt_command(
    label: str = typer.Option(..., "--label", help="Identifier the StudentT binding takes."),
    df: str = typer.Option(..., "--df", help="Degrees of freedom (>0)."),
    mu: str = typer.Option("0.0", "--mu", help="Location parameter (default 0.0)."),
    sigma: str = typer.Option("1.0", "--sigma", help="Scale parameter (default 1.0, >0)."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``StudentT(content, df=..., mu=..., sigma=...)`` literal binding.

    Renders Student's t-distribution. ``--mu`` and ``--sigma`` are
    optional location/scale (defaults 0.0 / 1.0); ``--df`` (degrees of
    freedom) is required. Heavier-tailed than Normal; useful for
    robust-likelihood comparisons.

    Example:

    .. code-block:: bash

        gaia bayes student-t --label robust_noise --df 4.0 --mu 0.0 --sigma 1.0
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.StudentT", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="StudentT",
        params=[("df", df), ("mu", mu), ("sigma", sigma)],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def cauchy_command(
    label: str = typer.Option(..., "--label", help="Identifier the Cauchy binding takes."),
    mu: str = typer.Option(..., "--mu", help="Location parameter."),
    gamma: str = typer.Option(..., "--gamma", help="Scale parameter (>0)."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``Cauchy(content, mu=..., gamma=...)`` literal binding.

    Renders Cauchy(mu, gamma) — undefined mean / variance; useful as a
    heavy-tailed robust alternative to Normal. Each parameter accepts a
    numeric literal or a bare module-scope identifier.

    Example:

    .. code-block:: bash

        gaia bayes cauchy --label heavy_tail_noise --mu 0.0 --gamma 1.0
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.Cauchy", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="Cauchy",
        params=[("mu", mu), ("gamma", gamma)],
        target=target,
        file=file,
        human=human,
        check=check,
        interactive=interactive,
        metadata_dict=metadata_dict,
    )


def chisquared_command(
    label: str = typer.Option(..., "--label", help="Identifier the ChiSquared binding takes."),
    df: str = typer.Option(..., "--df", help="Degrees of freedom (>0)."),
    target: str = typer.Option(".", "--target", help="Target package path."),
    file: str | None = typer.Option(None, "--file", help="Relative file under src/<pkg>/."),
    metadata: str | None = typer.Option(None, "--metadata", help="JSON metadata."),
    check: bool = typer.Option(True, "--check/--no-check"),
    human: bool = typer.Option(False, "--human"),
    interactive: bool = typer.Option(False, "--interactive"),
) -> None:
    r"""Declare a ``ChiSquared(content, df=...)`` literal binding.

    Renders ChiSquared(df) on positive reals — sum of squared standard
    Normals with ``df`` degrees of freedom. ``--df`` accepts a numeric
    literal or a bare module-scope identifier.

    Example:

    .. code-block:: bash

        gaia bayes chi-squared --label variance_test_stat --df 5
    """
    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.ChiSquared", metadata_error, target=str(target), human=human)
        return
    _run_dist_op(
        label=label,
        dist_name="ChiSquared",
        params=[("df", df)],
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
