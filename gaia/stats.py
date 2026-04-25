"""Distribution-spec constructors for Gaia authors.

This module owns metadata-only distribution declarations. It intentionally does
not import scipy.
"""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable
from typing import Any, Literal

from gaia.ir.schemas import CallableRef, DistributionParam, DistributionSpec
from gaia.unit import is_quantity, to_literal


def _coerce_param(value: Any) -> DistributionParam:
    if is_quantity(value):
        return to_literal(value)
    if isinstance(value, bool):
        raise TypeError("Distribution parameters must be numeric scalars, not bool")
    if isinstance(value, int | float):
        return value
    raise TypeError(f"Unsupported distribution parameter type: {type(value).__name__}")


def _spec(kind: str, **params: Any) -> DistributionSpec:
    return DistributionSpec(
        kind=kind,
        params={name: _coerce_param(value) for name, value in params.items()},
    )


def Normal(*, sigma: Any, mu: Any = 0.0) -> DistributionSpec:
    return _spec("normal", mu=mu, sigma=sigma)


def LogNormal(*, sigma: Any, mu: Any = 0.0) -> DistributionSpec:
    return _spec("lognormal", mu=mu, sigma=sigma)


def StudentT(*, df: float, sigma: Any, mu: Any = 0.0) -> DistributionSpec:
    return _spec("student_t", df=df, mu=mu, sigma=sigma)


def Cauchy(*, gamma: Any, mu: Any = 0.0) -> DistributionSpec:
    return _spec("cauchy", mu=mu, gamma=gamma)


def Binomial(*, n: int, p: float) -> DistributionSpec:
    return _spec("binomial", n=n, p=p)


def Poisson(*, rate: Any) -> DistributionSpec:
    return _spec("poisson", rate=rate)


def Exponential(*, rate: Any) -> DistributionSpec:
    return _spec("exponential", rate=rate)


def Beta(*, alpha: float, beta: float) -> DistributionSpec:
    return _spec("beta", alpha=alpha, beta=beta)


def _callable_source_hash(fn: Callable[..., Any]) -> str:
    """Return a best-effort provenance hash, not a stable identity key."""
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        source = repr(fn)
    return f"sha256:{hashlib.sha256(source.encode()).hexdigest()}"


def from_callable(
    fn: Callable[..., Any],
    *,
    name: str,
    version: str | None = None,
    params: dict[str, Any] | None = None,
    purity: Literal["pure", "impure", "unknown"] = "unknown",
) -> DistributionSpec:
    callable_ref = CallableRef(
        name=name,
        version=version,
        signature=str(inspect.signature(fn)),
        source_hash=_callable_source_hash(fn),
        purity=purity,
    )
    return DistributionSpec(
        kind="custom",
        params={key: _coerce_param(value) for key, value in (params or {}).items()},
        callable_ref=callable_ref,
    )
