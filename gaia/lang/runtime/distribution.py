"""Distribution — a continuous quantity declared with a probability distribution.

This is the Lang-side first-class wrapper around the existing computational
distribution objects in ``gaia/lang/bayes/distributions/``. It carries
:class:`Knowledge`-style identity (label, provenance, metadata) so authors can
name a continuous quantity once and reference it elsewhere (predicates,
equations, observe sugar) — the existing pydantic ``_BaseDistribution`` class
hierarchy is preserved as the computational backend (held in ``self._impl``).

Lang-only — like :class:`Variable` and :class:`Domain`, it overrides
``__post_init__`` to skip IR-bound knowledge map registration. Distributions
do not appear as top-level IR Knowledge nodes; they are referenced from
claim/action metadata that the BP layer consumes.

Operator overloading on Distribution produces :class:`BoolExpr` (for
comparisons used as claim propositions / equations) and
:class:`DerivedDistribution` (for arithmetic combinations such as
``A * exp(-Ea / (R * T))`` inside an Arrhenius-style equation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, cast

from gaia.lang.runtime.knowledge import Knowledge, _current_package

if TYPE_CHECKING:
    from gaia.lang.bayes.distributions.base import _BaseDistribution
    from gaia.lang.bayes.distributions.protocol import (
        Distribution as _DistImpl,
    )
    from gaia.lang.dsl.bool_expr import BoolExpr, DerivedDistribution


@dataclass(init=False, eq=False)
class Distribution(Knowledge):
    """Knowledge-wrapped continuous quantity with a probability distribution.

    Use the family-specific factories (:func:`Normal`, :func:`LogNormal`,
    :func:`Beta`, etc.) rather than constructing this directly — they wrap the
    matching ``gaia.lang.bayes.distributions._BaseDistribution`` subclass into
    a Distribution carrying a content string + identity.

    The wrapped computational object is available as ``.impl`` and exposes
    ``logpdf`` / ``logpmf`` / ``cdf`` / ``support`` / ``model_dump`` via thin
    delegating properties on this class.
    """

    __gaia_term__: ClassVar[bool] = True

    _impl: Any = field(default=None, init=False, repr=False, compare=False)

    def __init__(
        self,
        content: str,
        *,
        impl: _BaseDistribution,
        format: str = "markdown",
        **kwargs: Any,
    ) -> None:
        """Create a Knowledge-wrapped distribution.

        Args:
            content: Human-readable description of what this quantity is.
            impl: A ``_BaseDistribution`` subclass instance (Normal, Beta, …)
                that provides the computational backend.
            format: Content format (markdown by default).
            **kwargs: Standard :class:`Knowledge` keyword arguments
                (``title``, ``label``, ``metadata``, ``provenance``, …).
        """
        from gaia.lang.bayes.distributions.base import _BaseDistribution

        if not isinstance(impl, _BaseDistribution):
            raise TypeError(
                "Distribution(impl=...) must be a _BaseDistribution instance "
                "from gaia.lang.bayes.distributions; got "
                f"{type(impl).__name__}. Use the family factories (Normal, "
                "LogNormal, Beta, ...) instead of constructing Distribution "
                "directly."
            )
        super().__init__(content=content, type="distribution", format=format, **kwargs)
        object.__setattr__(self, "_impl", impl)

    def __post_init__(self) -> None:
        """Associate with the package for provenance, but skip IR registration.

        Mirrors the Lang-only treatment in :class:`Variable` and :class:`Domain`
        — distributions exist for the author and Lang-side compiler, but the
        IR sees them only through claim/action metadata that references them.
        """
        pkg = _current_package.get()
        source_module = None
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_and_module

            pkg, source_module = infer_package_and_module()
        if pkg is not None:
            self._source_module = source_module
            self._package = pkg
            # NO pkg._register_knowledge(self) — Lang-only.

    # Object identity (not structural equality) so this Distribution can sit in
    # set/dict containers even though __eq__ returns a BoolExpr below.
    def __hash__(self) -> int:
        """Identity hash (overrides @dataclass-generated structural hash)."""
        return id(self)

    # ----- Computational backend delegations --------------------------------
    # The ``_impl`` field is typed Any at the dataclass level so the dataclass
    # machinery does not need to resolve the (TYPE_CHECKING-only) backend
    # types. Each accessor casts to the appropriate type for delegation:
    # the runtime-checkable :class:`Distribution` Protocol from
    # ``gaia.lang.bayes.distributions.protocol`` for the standard methods, and
    # to the concrete ``_BaseDistribution`` for ``_resolved_params`` (which
    # the protocol does not surface).

    @property
    def impl(self) -> _BaseDistribution:
        """Return the wrapped computational distribution object."""
        return cast("_BaseDistribution", self._impl)

    @property
    def kind(self) -> str:
        """Distribution family identifier (``"normal"``, ``"beta"``, ...)."""
        return cast("_DistImpl", self._impl).kind

    @property
    def params(self) -> dict[str, Any]:
        """Return the distribution parameter dictionary."""
        return dict(cast("_DistImpl", self._impl).params)

    def logpdf(self, x: float) -> float:
        """Evaluate the log probability density at ``x`` (continuous)."""
        return cast("_DistImpl", self._impl).logpdf(x)

    def logpmf(self, k: int) -> float:
        """Evaluate the log probability mass at ``k`` (discrete)."""
        return cast("_DistImpl", self._impl).logpmf(k)

    def support(self) -> tuple[float, float]:
        """Return the inclusive support bounds of the distribution."""
        return cast("_DistImpl", self._impl).support()

    def cdf(self, x: float) -> float:
        """Cumulative distribution function P(X <= x).

        Used at compile time to compute the prior of a predicate claim
        (``P(k > c) = 1 - dist.cdf(c)``). Lazy import of scipy keeps this
        out of the cold import path.
        """
        from gaia.lang.bayes.adapters.scipy_backend import _to_scipy_dist

        impl = cast("_BaseDistribution", self._impl)
        resolved = impl._resolved_params()
        return float(_to_scipy_dist(impl.kind, resolved).cdf(x))

    def model_dump(self) -> dict[str, Any]:
        """Return the JSON-serialisable distribution literal payload."""
        return cast("_DistImpl", self._impl).model_dump()

    # ----- Operator overloading -- comparisons return BoolExpr --------------
    #
    # The comparison operators below are intentionally not boolean; they
    # construct a :class:`BoolExpr` describing the proposition (``k > 1e-3``).
    # Authors pass these expressions to ``claim(content, expr)`` to get a
    # discrete Claim whose prior is computed from the underlying distribution.
    # ``BoolExpr.__bool__`` raises so accidental ``if k > 1e-3:`` use in
    # Python control flow surfaces as a clear error rather than always-truthy.

    def __gt__(self, other: Any) -> BoolExpr:
        """``k > x`` → :class:`BoolExpr` for use as a claim proposition."""
        from gaia.lang.dsl.bool_expr import BoolExpr

        return BoolExpr(">", self, other)

    def __ge__(self, other: Any) -> BoolExpr:
        """``k >= x`` → :class:`BoolExpr` for use as a claim proposition."""
        from gaia.lang.dsl.bool_expr import BoolExpr

        return BoolExpr(">=", self, other)

    def __lt__(self, other: Any) -> BoolExpr:
        """``k < x`` → :class:`BoolExpr` for use as a claim proposition."""
        from gaia.lang.dsl.bool_expr import BoolExpr

        return BoolExpr("<", self, other)

    def __le__(self, other: Any) -> BoolExpr:
        """``k <= x`` → :class:`BoolExpr` for use as a claim proposition."""
        from gaia.lang.dsl.bool_expr import BoolExpr

        return BoolExpr("<=", self, other)

    def __eq__(self, other: Any) -> Any:
        """``k == x`` → :class:`BoolExpr` (used as equation proposition).

        Note: this overrides Python's structural equality to return a BoolExpr
        rather than ``bool``. Use ``a is b`` or ``a.label == b.label`` for
        identity checks. ``__hash__`` is preserved as identity hash so set/dict
        membership still works.
        """
        from gaia.lang.dsl.bool_expr import BoolExpr

        return BoolExpr("==", self, other)

    def __ne__(self, other: Any) -> Any:
        """``k != x`` → :class:`BoolExpr` (rarely useful but symmetric)."""
        from gaia.lang.dsl.bool_expr import BoolExpr

        return BoolExpr("!=", self, other)

    # ----- Operator overloading -- arithmetic returns DerivedDistribution ---

    def __add__(self, other: Any) -> DerivedDistribution:
        """``k + x`` → :class:`DerivedDistribution` (for equation RHS)."""
        from gaia.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("+", self, other)

    def __radd__(self, other: Any) -> DerivedDistribution:
        """Reflected ``x + k`` → :class:`DerivedDistribution`."""
        from gaia.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("+", other, self)

    def __sub__(self, other: Any) -> DerivedDistribution:
        """``k - x`` → :class:`DerivedDistribution`."""
        from gaia.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("-", self, other)

    def __rsub__(self, other: Any) -> DerivedDistribution:
        """Reflected ``x - k`` → :class:`DerivedDistribution`."""
        from gaia.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("-", other, self)

    def __mul__(self, other: Any) -> DerivedDistribution:
        """``k * x`` → :class:`DerivedDistribution`."""
        from gaia.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("*", self, other)

    def __rmul__(self, other: Any) -> DerivedDistribution:
        """Reflected ``x * k`` → :class:`DerivedDistribution`."""
        from gaia.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("*", other, self)

    def __truediv__(self, other: Any) -> DerivedDistribution:
        """``k / x`` → :class:`DerivedDistribution`."""
        from gaia.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("/", self, other)

    def __rtruediv__(self, other: Any) -> DerivedDistribution:
        """Reflected ``x / k`` → :class:`DerivedDistribution`."""
        from gaia.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("/", other, self)

    def __neg__(self) -> DerivedDistribution:
        """Unary ``-k`` → :class:`DerivedDistribution`."""
        from gaia.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("-", 0, self)


# ---------------------------------------------------------------------------
# Family-specific factories — top-level author API
#
# These are the canonical author-facing entry points. They match the parameter
# shapes of ``gaia.lang.bayes.distributions.<Name>`` so authors familiar with
# the existing bayes module find no surprises in the parameter names.
# ---------------------------------------------------------------------------


def Normal(
    content: str,
    *,
    mu: Any,
    sigma: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Normal-distributed continuous quantity with a name."""
    from gaia.lang.bayes.distributions.continuous import Normal as _BaseNormal

    return Distribution(content, impl=_BaseNormal(mu=mu, sigma=sigma), **kwargs)


def LogNormal(
    content: str,
    *,
    mu: Any,
    sigma: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a LogNormal-distributed continuous quantity with a name."""
    from gaia.lang.bayes.distributions.continuous import LogNormal as _BaseLogNormal

    return Distribution(content, impl=_BaseLogNormal(mu=mu, sigma=sigma), **kwargs)


def Beta(
    content: str,
    *,
    alpha: Any,
    beta: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Beta-distributed continuous quantity with a name."""
    from gaia.lang.bayes.distributions.continuous import Beta as _BaseBeta

    return Distribution(content, impl=_BaseBeta(alpha=alpha, beta=beta), **kwargs)


def Exponential(
    content: str,
    *,
    rate: Any,
    **kwargs: Any,
) -> Distribution:
    """Create an Exponential-distributed continuous quantity with a name."""
    from gaia.lang.bayes.distributions.continuous import Exponential as _BaseExponential

    return Distribution(content, impl=_BaseExponential(rate=rate), **kwargs)


def Gamma(
    content: str,
    *,
    alpha: Any,
    rate: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Gamma-distributed continuous quantity with a name."""
    from gaia.lang.bayes.distributions.continuous import Gamma as _BaseGamma

    return Distribution(content, impl=_BaseGamma(alpha=alpha, rate=rate), **kwargs)


def StudentT(
    content: str,
    *,
    df: Any,
    mu: Any,
    sigma: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Student-t distributed continuous quantity with a name."""
    from gaia.lang.bayes.distributions.continuous import StudentT as _BaseStudentT

    return Distribution(content, impl=_BaseStudentT(df=df, mu=mu, sigma=sigma), **kwargs)


def Cauchy(
    content: str,
    *,
    mu: Any,
    gamma: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Cauchy-distributed continuous quantity with a name."""
    from gaia.lang.bayes.distributions.continuous import Cauchy as _BaseCauchy

    return Distribution(content, impl=_BaseCauchy(mu=mu, gamma=gamma), **kwargs)


def ChiSquared(
    content: str,
    *,
    df: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Chi-squared distributed continuous quantity with a name."""
    from gaia.lang.bayes.distributions.continuous import ChiSquared as _BaseChiSquared

    return Distribution(content, impl=_BaseChiSquared(df=df), **kwargs)


def Binomial(
    content: str,
    *,
    n: Any,
    p: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Binomial-distributed discrete quantity with a name."""
    from gaia.lang.bayes.distributions.discrete import Binomial as _BaseBinomial

    return Distribution(content, impl=_BaseBinomial(n=n, p=p), **kwargs)


def Poisson(
    content: str,
    *,
    rate: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Poisson-distributed discrete quantity with a name."""
    from gaia.lang.bayes.distributions.discrete import Poisson as _BasePoisson

    return Distribution(content, impl=_BasePoisson(rate=rate), **kwargs)


__all__ = [
    "Beta",
    "Binomial",
    "Cauchy",
    "ChiSquared",
    "Distribution",
    "Exponential",
    "Gamma",
    "LogNormal",
    "Normal",
    "Poisson",
    "StudentT",
]
