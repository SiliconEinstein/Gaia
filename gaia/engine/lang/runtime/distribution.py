"""Distribution — a continuous quantity declared with a probability distribution.

This is the Lang-side first-class wrapper around the existing computational
distribution objects in ``gaia/engine/lang/bayes/distributions/``. It carries
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
``baseline + slope * x`` inside an equation proposition).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, cast

from gaia.engine.lang.runtime.knowledge import Knowledge, _current_package

if TYPE_CHECKING:
    from gaia.engine.lang.bayes.distributions.base import _BaseDistribution
    from gaia.engine.lang.bayes.distributions.protocol import (
        Distribution as _DistImpl,
    )
    from gaia.engine.lang.dsl.bool_expr import BoolExpr, DerivedDistribution


# ---------------------------------------------------------------------------
# Unit-aware parameter coercion
# ---------------------------------------------------------------------------
# The pydantic-backed ``_BaseDistribution`` only accepts numeric scalars (or
# deferred references with a ``.symbol`` attribute) as parameter values.
# Authors writing scientific-domain code naturally reach for unit-aware values
# (e.g. ``Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))``); this helper
# strips the unit, hands the magnitude to the pydantic constructor, and
# returns the per-param unit dict so the factory can stash it on the
# Distribution's metadata for downstream audit and consistency checks.


def _coerce_quantity_params(params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Strip Pint Quantity values from a parameter dict.

    Returns a pair ``(magnitudes, units)`` where ``magnitudes`` is the same
    keys with ``.magnitude`` extracted from any Quantity-typed values
    (non-Quantity values pass through unchanged), and ``units`` is the
    subset of keys whose value carried a unit, mapped to the canonical
    Pint unit string (e.g. ``"kelvin"``, ``"meter / second"``).
    """
    from gaia.unit import is_quantity, to_literal

    magnitudes: dict[str, Any] = {}
    units: dict[str, str] = {}
    for name, value in params.items():
        if is_quantity(value):
            literal = to_literal(value)
            magnitudes[name] = literal.value
            units[name] = literal.unit
        else:
            magnitudes[name] = value
    return magnitudes, units


def _validate_shared_unit(
    units: dict[str, str], group: tuple[str, ...], distribution_name: str
) -> str | None:
    """Verify that all parameters in ``group`` share the same unit (or none).

    Returns the shared unit string when the group has a unit, ``None`` when
    no parameter in the group carries a unit. Raises ``ValueError`` when
    parameters in the group disagree (some unit-typed, some not, or different
    unit strings) — this catches mistakes like
    ``Normal("T", mu=q(200, "K"), sigma=50)`` early.
    """
    in_group = {name: units[name] for name in group if name in units}
    if not in_group:
        return None
    unit_set = set(in_group.values())
    if len(unit_set) > 1:
        raise ValueError(
            f"{distribution_name} location/scale parameters {sorted(in_group)} "
            f"must share a single unit; got {in_group}."
        )
    missing = [name for name in group if name not in units]
    if missing:
        raise ValueError(
            f"{distribution_name} location/scale parameters disagree on "
            f"unit-aware-ness: {sorted(in_group)} carry units, "
            f"{sorted(missing)} do not. Pass either all unitless scalars or "
            "all gaia.unit.Quantity values."
        )
    return next(iter(unit_set))


def _attach_units(
    metadata_kwarg: dict[str, Any] | None,
    units: dict[str, str],
    shared_unit: str | None,
) -> dict[str, Any]:
    """Merge per-param units (and optional shared unit) into metadata.

    Always returns a dict (a fresh copy) — the bare-scalar / unitless call
    path also gets a fresh empty dict rather than ``None`` so
    :class:`Distribution` retains the Knowledge invariant that ``metadata``
    is dict-typed. Downstream readers can therefore use
    ``distribution.metadata.get(...)`` directly without defensive
    ``(meta or {})`` patterns.
    """
    meta = dict(metadata_kwarg or {})
    if units:
        existing_units = dict(meta.get("units") or {})
        existing_units.update(units)
        meta["units"] = existing_units
    if shared_unit is not None:
        meta.setdefault("unit", shared_unit)
    return meta


def _inverse_unit(unit: str) -> str:
    """Return the canonical inverse unit string for a Pint unit literal."""
    from gaia.unit import ureg

    return str((1 / ureg.parse_units(unit)).units)


@dataclass(init=False, eq=False)
class Distribution(Knowledge):
    """Knowledge-wrapped continuous quantity with a probability distribution.

    Use the family-specific factories (:func:`Normal`, :func:`LogNormal`,
    :func:`Beta`, etc.) rather than constructing this directly — they wrap the
    matching ``gaia.engine.lang.bayes.distributions._BaseDistribution`` subclass into
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
        from gaia.engine.lang.bayes.distributions.base import _BaseDistribution

        if not isinstance(impl, _BaseDistribution):
            raise TypeError(
                "Distribution(impl=...) must be a _BaseDistribution instance "
                "from gaia.engine.lang.bayes.distributions; got "
                f"{type(impl).__name__}. Use the family factories (Normal, "
                "LogNormal, Beta, ...) instead of constructing Distribution "
                "directly."
            )
        super().__init__(content=content, type="distribution", format=format, **kwargs)
        self._impl = impl

    def __post_init__(self) -> None:
        """Associate with the package for provenance, but skip IR registration.

        Mirrors the Lang-only treatment in :class:`Variable` and :class:`Domain`
        — distributions exist for the author and Lang-side compiler, but the
        IR sees them only through claim/action metadata that references them.
        Appending to ``pkg.distributions`` lets compile-time diagnostics
        detect quantities declared but never referenced.
        """
        pkg = _current_package.get()
        source_module = None
        if pkg is None:
            from gaia.engine.lang.runtime.package import infer_package_and_module

            pkg, source_module = infer_package_and_module()
        if pkg is not None:
            self._source_module = source_module
            self._package = pkg
            # NO pkg._register_knowledge(self) — Lang-only.
            pkg.distributions.append(self)

    # Restore object-identity hash. ``@dataclass(eq=False)`` does NOT
    # auto-generate a structural hash, but Python sets ``__hash__ = None``
    # whenever ``__eq__`` is overridden (which we do below to return a
    # BoolExpr). Without this explicit definition the class would be
    # unhashable and break set/dict membership. Python short-circuits
    # identical-object set membership before calling ``__eq__``, so
    # ``dist in {dist}`` works correctly even though the eq op itself
    # returns a BoolExpr rather than a bool.
    def __hash__(self) -> int:
        """Return object-identity hash so containers can store Distributions."""
        return id(self)

    # ----- Computational backend delegations --------------------------------
    # The ``_impl`` field is typed Any at the dataclass level so the dataclass
    # machinery does not need to resolve the (TYPE_CHECKING-only) backend
    # types. Each accessor casts to the appropriate type for delegation:
    # the runtime-checkable :class:`Distribution` Protocol from
    # ``gaia.engine.lang.bayes.distributions.protocol`` for the standard methods, and
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
        from gaia.engine.lang.bayes.adapters.scipy_backend import _to_scipy_dist

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
        from gaia.engine.lang.dsl.bool_expr import BoolExpr

        return BoolExpr(">", self, other)

    def __ge__(self, other: Any) -> BoolExpr:
        """``k >= x`` → :class:`BoolExpr` for use as a claim proposition."""
        from gaia.engine.lang.dsl.bool_expr import BoolExpr

        return BoolExpr(">=", self, other)

    def __lt__(self, other: Any) -> BoolExpr:
        """``k < x`` → :class:`BoolExpr` for use as a claim proposition."""
        from gaia.engine.lang.dsl.bool_expr import BoolExpr

        return BoolExpr("<", self, other)

    def __le__(self, other: Any) -> BoolExpr:
        """``k <= x`` → :class:`BoolExpr` for use as a claim proposition."""
        from gaia.engine.lang.dsl.bool_expr import BoolExpr

        return BoolExpr("<=", self, other)

    def __eq__(self, other: Any) -> Any:
        """``k == x`` → :class:`BoolExpr` (used as equation proposition).

        Note: this overrides Python's structural equality to return a BoolExpr
        rather than ``bool``. Use ``a is b`` or ``a.label == b.label`` for
        identity checks. ``__hash__`` is preserved as identity hash so set/dict
        membership still works.
        """
        from gaia.engine.lang.dsl.bool_expr import BoolExpr

        return BoolExpr("==", self, other)

    def __ne__(self, other: Any) -> Any:
        """``k != x`` → :class:`BoolExpr` (rarely useful but symmetric)."""
        from gaia.engine.lang.dsl.bool_expr import BoolExpr

        return BoolExpr("!=", self, other)

    # ----- Operator overloading -- arithmetic returns DerivedDistribution ---

    def __add__(self, other: Any) -> DerivedDistribution:
        """``k + x`` → :class:`DerivedDistribution` (for equation RHS)."""
        from gaia.engine.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("+", self, other)

    def __radd__(self, other: Any) -> DerivedDistribution:
        """Reflected ``x + k`` → :class:`DerivedDistribution`."""
        from gaia.engine.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("+", other, self)

    def __sub__(self, other: Any) -> DerivedDistribution:
        """``k - x`` → :class:`DerivedDistribution`."""
        from gaia.engine.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("-", self, other)

    def __rsub__(self, other: Any) -> DerivedDistribution:
        """Reflected ``x - k`` → :class:`DerivedDistribution`."""
        from gaia.engine.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("-", other, self)

    def __mul__(self, other: Any) -> DerivedDistribution:
        """``k * x`` → :class:`DerivedDistribution`."""
        from gaia.engine.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("*", self, other)

    def __rmul__(self, other: Any) -> DerivedDistribution:
        """Reflected ``x * k`` → :class:`DerivedDistribution`."""
        from gaia.engine.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("*", other, self)

    def __truediv__(self, other: Any) -> DerivedDistribution:
        """``k / x`` → :class:`DerivedDistribution`."""
        from gaia.engine.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("/", self, other)

    def __rtruediv__(self, other: Any) -> DerivedDistribution:
        """Reflected ``x / k`` → :class:`DerivedDistribution`."""
        from gaia.engine.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("/", other, self)

    def __neg__(self) -> DerivedDistribution:
        """Unary ``-k`` → :class:`DerivedDistribution`."""
        from gaia.engine.lang.dsl.bool_expr import DerivedDistribution

        return DerivedDistribution("-", 0, self)


# ---------------------------------------------------------------------------
# Family-specific factories — top-level author API
#
# These are the canonical author-facing entry points. They accept either bare
# numeric scalars or :class:`gaia.unit.Quantity` values for parameters. When
# Quantities are supplied, the unit string is recorded on the resulting
# Distribution's ``metadata['units']`` (per-param) and, for distributions
# with a shared location/scale, ``metadata['unit']`` (the unit of the
# underlying random variable). The pydantic ``_BaseDistribution`` continues
# to receive only numeric magnitudes so its frozen-Pydantic validation pass
# is unchanged.
#
# Per-distribution unit semantics:
# ``Normal``, ``StudentT``, ``Cauchy``           — location/scale share a unit
# ``Gamma`` (alpha, rate)                        — alpha dimensionless;
#                                                   ``rate`` carries inverse
#                                                   random-variable unit
# ``Exponential`` (rate)                         — ``rate`` carries inverse
#                                                   random-variable unit
# ``Poisson`` (rate)                             — dimensionless expected
#                                                   count; no unit-typed rate
# ``LogNormal``, ``Beta``, ``ChiSquared``,       — all parameters are
#   ``Binomial``                                   conventionally dimensionless;
#                                                   raise if a Quantity is
#                                                   passed (use the content
#                                                   string to convey the unit
#                                                   of the underlying RV).
# ---------------------------------------------------------------------------


def _build_distribution(
    content: str,
    *,
    impl_cls: type[_BaseDistribution],
    raw_params: dict[str, Any],
    location_scale_group: tuple[str, ...] = (),
    unit_carriers: tuple[str, ...] = (),
    inverse_unit_carriers: tuple[str, ...] = (),
    dimensionless_params: tuple[str, ...] = (),
    distribution_name: str,
    kwargs: dict[str, Any],
) -> Distribution:
    """Common factory body — coerce Quantities, validate units, construct."""
    magnitudes, units = _coerce_quantity_params(raw_params)
    if dimensionless_params:
        offending = {p: units[p] for p in dimensionless_params if p in units}
        if offending:
            raise ValueError(
                f"{distribution_name} parameters {sorted(offending)} are "
                "dimensionless and must be passed as bare scalars; got "
                f"unit-typed values {offending}. Encode the random "
                "variable's unit in the content string instead."
            )
    shared_unit = (
        _validate_shared_unit(units, location_scale_group, distribution_name)
        if location_scale_group
        else None
    )
    impl = impl_cls(**magnitudes)
    new_kwargs = dict(kwargs)
    new_kwargs["metadata"] = _attach_units(new_kwargs.get("metadata"), units, shared_unit)
    if inverse_unit_carriers:
        carrier_units = {p: units[p] for p in inverse_unit_carriers if p in units}
        if carrier_units:
            new_kwargs["metadata"] = _attach_units(
                new_kwargs.get("metadata"), {}, _inverse_unit(next(iter(carrier_units.values())))
            )
    elif unit_carriers:
        carrier_units = {p: units[p] for p in unit_carriers if p in units}
        if carrier_units:
            new_kwargs["metadata"] = _attach_units(
                new_kwargs.get("metadata"), {}, next(iter(carrier_units.values()))
            )
    return Distribution(content, impl=impl, **new_kwargs)


def Normal(
    content: str,
    *,
    mu: Any,
    sigma: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Normal-distributed continuous quantity with a name.

    ``mu`` and ``sigma`` may both be bare scalars or both be
    :class:`gaia.unit.Quantity` values sharing a unit; mixing them raises.
    """
    from gaia.engine.lang.bayes.distributions.continuous import Normal as _BaseNormal

    return _build_distribution(
        content,
        impl_cls=_BaseNormal,
        raw_params={"mu": mu, "sigma": sigma},
        location_scale_group=("mu", "sigma"),
        distribution_name="Normal",
        kwargs=kwargs,
    )


def LogNormal(
    content: str,
    *,
    mu: Any,
    sigma: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a LogNormal-distributed continuous quantity with a name.

    The LogNormal parameters live in log-space; ``mu`` and ``sigma`` must be
    dimensionless scalars. Encode the unit of the underlying random variable
    in the content string (e.g. ``LogNormal("k / s^-1", mu=log(1e-3), sigma=2)``).
    """
    from gaia.engine.lang.bayes.distributions.continuous import LogNormal as _BaseLogNormal

    return _build_distribution(
        content,
        impl_cls=_BaseLogNormal,
        raw_params={"mu": mu, "sigma": sigma},
        dimensionless_params=("mu", "sigma"),
        distribution_name="LogNormal",
        kwargs=kwargs,
    )


def Beta(
    content: str,
    *,
    alpha: Any,
    beta: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Beta-distributed continuous quantity with a name.

    Beta shape parameters ``alpha`` and ``beta`` are dimensionless.
    """
    from gaia.engine.lang.bayes.distributions.continuous import Beta as _BaseBeta

    return _build_distribution(
        content,
        impl_cls=_BaseBeta,
        raw_params={"alpha": alpha, "beta": beta},
        dimensionless_params=("alpha", "beta"),
        distribution_name="Beta",
        kwargs=kwargs,
    )


def Exponential(
    content: str,
    *,
    rate: Any,
    **kwargs: Any,
) -> Distribution:
    """Create an Exponential-distributed continuous quantity with a name.

    ``rate`` may be a bare scalar or a :class:`gaia.unit.Quantity` (typically
    ``1 / time``). The corresponding random variable's unit is the inverse of
    ``rate``'s unit; for predicate / observe consistency we record that
    inverse unit as the distribution's canonical ``metadata["unit"]``.
    """
    from gaia.engine.lang.bayes.distributions.continuous import Exponential as _BaseExponential

    return _build_distribution(
        content,
        impl_cls=_BaseExponential,
        raw_params={"rate": rate},
        inverse_unit_carriers=("rate",),
        distribution_name="Exponential",
        kwargs=kwargs,
    )


def Gamma(
    content: str,
    *,
    alpha: Any,
    rate: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Gamma-distributed continuous quantity with a name.

    ``alpha`` is dimensionless; ``rate`` may carry the inverse unit of the
    underlying random variable (typically ``1 / x``).
    """
    from gaia.engine.lang.bayes.distributions.continuous import Gamma as _BaseGamma

    return _build_distribution(
        content,
        impl_cls=_BaseGamma,
        raw_params={"alpha": alpha, "rate": rate},
        dimensionless_params=("alpha",),
        inverse_unit_carriers=("rate",),
        distribution_name="Gamma",
        kwargs=kwargs,
    )


def StudentT(
    content: str,
    *,
    df: Any,
    mu: Any,
    sigma: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Student-t distributed continuous quantity with a name.

    ``df`` is dimensionless; ``mu`` and ``sigma`` share the location/scale
    unit of the underlying random variable.
    """
    from gaia.engine.lang.bayes.distributions.continuous import StudentT as _BaseStudentT

    return _build_distribution(
        content,
        impl_cls=_BaseStudentT,
        raw_params={"df": df, "mu": mu, "sigma": sigma},
        location_scale_group=("mu", "sigma"),
        dimensionless_params=("df",),
        distribution_name="StudentT",
        kwargs=kwargs,
    )


def Cauchy(
    content: str,
    *,
    mu: Any,
    gamma: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Cauchy-distributed continuous quantity with a name.

    ``mu`` and ``gamma`` share the location/scale unit of the underlying
    random variable.
    """
    from gaia.engine.lang.bayes.distributions.continuous import Cauchy as _BaseCauchy

    return _build_distribution(
        content,
        impl_cls=_BaseCauchy,
        raw_params={"mu": mu, "gamma": gamma},
        location_scale_group=("mu", "gamma"),
        distribution_name="Cauchy",
        kwargs=kwargs,
    )


def ChiSquared(
    content: str,
    *,
    df: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Chi-squared distributed continuous quantity with a name.

    ``df`` is dimensionless.
    """
    from gaia.engine.lang.bayes.distributions.continuous import ChiSquared as _BaseChiSquared

    return _build_distribution(
        content,
        impl_cls=_BaseChiSquared,
        raw_params={"df": df},
        dimensionless_params=("df",),
        distribution_name="ChiSquared",
        kwargs=kwargs,
    )


def Binomial(
    content: str,
    *,
    n: Any,
    p: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Binomial-distributed discrete quantity with a name.

    ``n`` and ``p`` are dimensionless.
    """
    from gaia.engine.lang.bayes.distributions.discrete import Binomial as _BaseBinomial

    return _build_distribution(
        content,
        impl_cls=_BaseBinomial,
        raw_params={"n": n, "p": p},
        dimensionless_params=("n", "p"),
        distribution_name="Binomial",
        kwargs=kwargs,
    )


def Poisson(
    content: str,
    *,
    rate: Any,
    **kwargs: Any,
) -> Distribution:
    """Create a Poisson-distributed discrete quantity with a name.

    ``rate`` is the dimensionless expected count for the interval encoded by
    the quantity name. Pass a bare scalar; unit-typed rates are rejected.
    """
    from gaia.engine.lang.bayes.distributions.discrete import Poisson as _BasePoisson

    return _build_distribution(
        content,
        impl_cls=_BasePoisson,
        raw_params={"rate": rate},
        dimensionless_params=("rate",),
        distribution_name="Poisson",
        kwargs=kwargs,
    )


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
