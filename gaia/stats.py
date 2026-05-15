"""Distribution literal factory functions for Gaia authors.

This module owns metadata-only distribution declarations. It intentionally does
not import scipy. The capitalized built-in distribution names are functions,
not classes, following scientific-computing authoring conventions.
"""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable
from typing import Any, Literal

from gaia.engine.ir.schemas import (
    CallableRef,
    DistributionKind,
    DistributionLiteral,
    DistributionParam,
)


def _param_to_ir(value: Any) -> DistributionParam:
    if isinstance(value, bool):
        raise TypeError("Distribution parameters must be numeric scalars, not bool")
    if isinstance(value, int | float):
        return value
    from gaia.unit import is_quantity, to_literal

    if is_quantity(value):
        return to_literal(value)
    raise TypeError(f"Unsupported distribution parameter type: {type(value).__name__}")


def _spec(kind: DistributionKind, **params: Any) -> DistributionLiteral:
    return DistributionLiteral(
        kind=kind,
        params={name: _param_to_ir(value) for name, value in params.items()},
    )


def Normal(*, sigma: Any, mu: Any = 0.0) -> DistributionLiteral:
    """Create a metadata literal for a normal distribution.

    Args:
        sigma: Distribution scale parameter, either numeric or a Gaia quantity.
        mu: Distribution location parameter, either numeric or a Gaia quantity.

    Returns:
        A distribution literal with kind ``normal``.
    """
    return _spec("normal", mu=mu, sigma=sigma)


def LogNormal(*, sigma: Any, mu: Any = 0.0) -> DistributionLiteral:
    """Create a metadata literal for a log-normal distribution.

    Args:
        sigma: Distribution scale parameter, either numeric or a Gaia quantity.
        mu: Distribution log-location parameter, either numeric or a Gaia quantity.

    Returns:
        A distribution literal with kind ``lognormal``.
    """
    return _spec("lognormal", mu=mu, sigma=sigma)


def StudentT(*, df: float, sigma: Any, mu: Any = 0.0) -> DistributionLiteral:
    """Create a metadata literal for a Student's t distribution.

    Args:
        df: Degrees of freedom.
        sigma: Distribution scale parameter, either numeric or a Gaia quantity.
        mu: Distribution location parameter, either numeric or a Gaia quantity.

    Returns:
        A distribution literal with kind ``student_t``.
    """
    return _spec("student_t", df=df, mu=mu, sigma=sigma)


def Cauchy(*, gamma: Any, mu: Any = 0.0) -> DistributionLiteral:
    """Create a metadata literal for a Cauchy distribution.

    Args:
        gamma: Distribution scale parameter, either numeric or a Gaia quantity.
        mu: Distribution location parameter, either numeric or a Gaia quantity.

    Returns:
        A distribution literal with kind ``cauchy``.
    """
    return _spec("cauchy", mu=mu, gamma=gamma)


def Binomial(*, n: int, p: float) -> DistributionLiteral:
    """Create a metadata literal for a binomial distribution.

    Args:
        n: Number of Bernoulli trials.
        p: Success probability for each trial.

    Returns:
        A distribution literal with kind ``binomial``.
    """
    return _spec("binomial", n=n, p=p)


def Poisson(*, rate: Any) -> DistributionLiteral:
    """Create a metadata literal for a Poisson distribution.

    Args:
        rate: Expected event rate, either numeric or a Gaia quantity.

    Returns:
        A distribution literal with kind ``poisson``.
    """
    return _spec("poisson", rate=rate)


def Exponential(*, rate: Any) -> DistributionLiteral:
    """Create a metadata literal for an exponential distribution.

    Args:
        rate: Event rate parameter, either numeric or a Gaia quantity.

    Returns:
        A distribution literal with kind ``exponential``.
    """
    return _spec("exponential", rate=rate)


def Beta(*, alpha: float, beta: float) -> DistributionLiteral:
    """Create a metadata literal for a beta distribution.

    Args:
        alpha: First positive shape parameter.
        beta: Second positive shape parameter.

    Returns:
        A distribution literal with kind ``beta``.
    """
    return _spec("beta", alpha=alpha, beta=beta)


def _callable_source_hash(fn: Callable[..., Any]) -> str:
    """Return a best-effort provenance hash, not a stable identity key."""
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        source = repr(fn)
    return f"sha256:{hashlib.sha256(source.encode()).hexdigest()}"


def custom_distribution(
    fn: Callable[..., Any],
    *,
    name: str,
    version: str | None = None,
    params: dict[str, Any] | None = None,
    purity: Literal["pure", "impure", "unknown"] = "unknown",
) -> DistributionLiteral:
    """Create a metadata literal for an author-provided distribution function.

    Args:
        fn: Callable that implements or identifies the distribution.
        name: Stable distribution name for the callable reference.
        version: Optional version string for the callable reference.
        params: Optional literal parameters to store with the distribution.
        purity: Purity declaration for downstream execution policy.

    Returns:
        A custom distribution literal carrying a callable reference.
    """
    callable_ref = CallableRef(
        name=name,
        version=version,
        signature=str(inspect.signature(fn)),
        source_hash=_callable_source_hash(fn),
        purity=purity,
    )
    return DistributionLiteral(
        kind="custom",
        params={key: _param_to_ir(value) for key, value in (params or {}).items()},
        callable_ref=callable_ref,
    )
