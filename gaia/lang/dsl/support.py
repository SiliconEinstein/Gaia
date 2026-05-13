"""Gaia Lang v6 Support verbs: derive, observe, compute."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from gaia.ir.parameterization import CROMWELL_EPS
from gaia.lang.runtime.action import Compute, Derive, Observe
from gaia.lang.runtime.distribution import Distribution
from gaia.lang.runtime.knowledge import Claim, Knowledge


def _as_given_tuple(given: Claim | tuple[Claim, ...] | list[Claim] | None) -> tuple[Claim, ...]:
    if given is None:
        return ()
    if isinstance(given, Knowledge):
        return (given,)
    return tuple(given)


def _implication_warrant(
    action_type: str,
    *,
    given: tuple[Claim, ...],
    conclusion: Claim,
    rationale: str,
) -> Claim:
    content = f"{action_type} warrants {conclusion.content}"
    metadata: dict[str, Any] = {
        "generated": True,
        "helper_kind": "implication_warrant",
        "review": True,
        "relation": {
            "type": action_type,
            "given": given,
            "conclusion": conclusion,
        },
    }
    if rationale:
        metadata["warrant"] = rationale
    return Claim(content, metadata=metadata)


def _pin_observed_claim(conclusion: Claim) -> None:
    pinned = 1.0 - CROMWELL_EPS
    if conclusion.prior is not None and conclusion.prior != pinned:
        raise ValueError(
            "zero-premise observe() pins the conclusion to 1 - CROMWELL_EPS; "
            "do not combine it with a different Claim.prior"
        )
    conclusion.prior = pinned


def derive(
    conclusion: Claim | str,
    *,
    given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Logical derivation. Returns the conclusion Claim."""
    if isinstance(conclusion, str):
        conclusion = Claim(conclusion)
    given_tuple = _as_given_tuple(given)
    warrant = _implication_warrant(
        "derive",
        given=given_tuple,
        conclusion=conclusion,
        rationale=rationale,
    )
    action = Derive(
        label=label,
        rationale=rationale,
        background=list(background or []),
        warrants=[warrant],
        conclusion=conclusion,
        given=given_tuple,
    )
    conclusion.from_actions.append(action)
    return conclusion


_OBSERVE_VALUE_SENTINEL: Any = object()


def observe(
    conclusion: Claim | Distribution | str,
    *,
    value: Any = _OBSERVE_VALUE_SENTINEL,
    error: Any = None,
    given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
    background: list[Knowledge] | None = None,
    source_refs: list[str] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Empirical observation.

    Two authoring shapes:

    1. **Discrete claim observation** — ``observe(my_claim)``. A no-premise
       observation pins ``my_claim.prior`` to ``1 - CROMWELL_EPS``. Use
       ``given=`` to record a conditional observation that does not pin the
       conclusion.
    2. **Continuous quantity observation** — ``observe(distribution,
       value=v, error=σ)``. Records a measurement event for a
       :class:`Distribution`-typed quantity. Returns a freshly minted
       :class:`Claim` representing the observation event (pinned to
       ``1 - CROMWELL_EPS`` since the measurement was made), with metadata
       linking back to the underlying distribution. The compiler reads this
       linkage for audit and future posterior-CDF lowering. The current
       predicate-prior lowering still uses the Distribution's prior CDF and
       emits a warning when an observation targets the same Distribution.

       ``value`` is the measured numeric value; ``error`` is either ``None``
       for a noise-free observation, a scalar interpreted as the Gaussian
       additive standard deviation, or a :class:`Distribution` for a
       custom noise model.
    """  # noqa: RUF002 (sigma symbol used in scientific docstring)
    if isinstance(conclusion, Distribution):
        if value is _OBSERVE_VALUE_SENTINEL:
            raise TypeError(
                "observe(distribution, ...) requires `value=` (the measured "
                "numeric value). For a discrete claim observation use "
                "observe(claim) without value/error."
            )
        if given:
            raise TypeError(
                "observe(distribution, value=..., given=...) is not supported "
                "— continuous observations are unconditional measurement "
                "events. To express a conditional measurement, observe a "
                "Claim wrapping the conditioning premise."
            )
        return _observe_continuous(
            conclusion,
            value=value,
            error=error,
            background=background,
            source_refs=source_refs,
            rationale=rationale,
            label=label,
        )

    if value is not _OBSERVE_VALUE_SENTINEL or error is not None:
        raise TypeError(
            "observe(..., value=..., error=...) only applies to Distribution "
            "targets. For discrete claim observations omit value/error."
        )

    if isinstance(conclusion, str):
        conclusion = Claim(conclusion)
    given_tuple = _as_given_tuple(given)
    warrant = _implication_warrant(
        "observe",
        given=given_tuple,
        conclusion=conclusion,
        rationale=rationale,
    )
    action = Observe(
        label=label,
        rationale=rationale,
        background=list(background or []),
        warrants=[warrant],
        metadata={"source_refs": list(source_refs)} if source_refs else {},
        conclusion=conclusion,
        given=given_tuple,
    )
    if not given_tuple:
        _pin_observed_claim(conclusion)
    conclusion.from_actions.append(action)
    return conclusion


def _coerce_observation_scalar(
    raw: Any,
    *,
    target: Distribution,
    role: str,
) -> tuple[float, str | None]:
    """Coerce ``observe(...)`` ``value=`` or ``error=`` to (magnitude, unit).

    Mirrors the predicate-threshold rules — a unit-typed Distribution requires
    a Quantity-typed observation (and the unit must be dimensionally
    compatible); a unitless Distribution requires bare scalars.
    """
    from gaia.unit import is_quantity, ureg

    distribution_unit: str | None = (target.metadata or {}).get("unit")
    if is_quantity(raw):
        if distribution_unit is None:
            raise TypeError(
                f"observe(distribution, {role}=...) is a unit-typed Quantity "
                f"but the target distribution "
                f"{target.label or target.content[:40]!r} is unitless. Pass a "
                f"bare scalar {role} or attach a unit to the distribution by "
                f"passing Quantity-typed parameters."
            )
        try:
            converted = raw.to(ureg.parse_units(distribution_unit))
        except Exception as err:
            raise ValueError(
                f"observe(distribution, {role}=...) unit {raw.units!s} is not "
                f"compatible with the target distribution unit "
                f"{distribution_unit!r}: {err}"
            ) from err
        return float(converted.magnitude), distribution_unit
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise TypeError(
            f"observe(distribution, {role}=...) must be a numeric scalar or "
            f"a gaia.unit.Quantity, got {type(raw).__name__}: {raw!r}."
        )
    if distribution_unit is not None:
        raise TypeError(
            f"observe(distribution, {role}=...) must be a Quantity in "
            f"{distribution_unit!r} because the target distribution "
            f"{target.label or target.content[:40]!r} carries that unit; got "
            f"bare scalar {raw!r}."
        )
    return float(raw), None


def _validate_noise_distribution_unit(noise: Distribution, *, target: Distribution) -> None:
    """Ensure a Distribution-valued noise model uses the target quantity's unit."""
    from gaia.unit import ureg

    target_unit: str | None = (target.metadata or {}).get("unit")
    noise_unit: str | None = (noise.metadata or {}).get("unit")
    if target_unit is None:
        if noise_unit is not None:
            raise TypeError(
                "observe(distribution, error=<Distribution>) got a unit-typed "
                f"noise distribution {noise_unit!r} for unitless target "
                f"{target.label or target.content[:40]!r}."
            )
        return
    if noise_unit is None:
        raise TypeError(
            "observe(distribution, error=<Distribution>) noise distribution "
            f"must carry unit {target_unit!r} because the target distribution "
            f"{target.label or target.content[:40]!r} carries that unit."
        )
    try:
        (1 * ureg.parse_units(noise_unit)).to(ureg.parse_units(target_unit))
    except Exception as err:
        raise ValueError(
            f"observe(distribution, error=<Distribution>) noise distribution unit "
            f"{noise_unit!r} is not compatible with target unit {target_unit!r}: {err}"
        ) from err
    if noise_unit != target_unit:
        raise ValueError(
            f"observe(distribution, error=<Distribution>) noise distribution unit "
            f"{noise_unit!r} must match target unit {target_unit!r}; pass a noise "
            "Distribution already expressed in the target's canonical unit."
        )


def _observe_continuous(
    target: Distribution,
    *,
    value: Any,
    error: Any,
    background: list[Knowledge] | None,
    source_refs: list[str] | None,
    rationale: str,
    label: str | None,
) -> Claim:
    """Build the observation Claim for a continuous quantity measurement."""
    coerced_value, value_unit = _coerce_observation_scalar(value, target=target, role="value")

    coerced_error: Any
    if error is None:
        coerced_error = None
    elif isinstance(error, Distribution):
        _validate_noise_distribution_unit(error, target=target)
        coerced_error = error
    else:
        coerced_error_scalar, _ = _coerce_observation_scalar(error, target=target, role="error")
        if coerced_error_scalar <= 0.0:
            raise ValueError(
                f"observe(distribution, error=sigma) requires sigma > 0, got {error!r}."
            )
        coerced_error = coerced_error_scalar

    label_part = target.label or target.content[:40]
    unit_suffix = f" {value_unit}" if value_unit else ""
    # Format numerics with :g so ``203.0`` renders as ``203`` and ``0.0015``
    # stays ``0.0015`` (no trailing zeros, no scientific notation for sane
    # magnitudes; Python's :g default flips to scientific only at very small
    # or very large magnitudes).
    value_part = format(coerced_value, "g")
    if isinstance(error, Distribution):
        error_part = f" with noise {error.kind}"
    elif error is None:
        error_part = ""
    else:
        error_part = f" +/- {format(coerced_error, 'g')}{unit_suffix}"
    content = f"Observed {label_part} = {value_part}{unit_suffix}{error_part}"

    obs_metadata: dict[str, Any] = {
        "observation": {
            "target_distribution": target,
            "value": coerced_value,
            "error": coerced_error,
            "unit": value_unit,
            "kind": "continuous_observation",
        },
    }
    if source_refs:
        obs_metadata["source_refs"] = list(source_refs)
    obs_claim = Claim(content, metadata=obs_metadata)
    warrant = _implication_warrant(
        "observe",
        given=(),
        conclusion=obs_claim,
        rationale=rationale,
    )
    action = Observe(
        label=label,
        rationale=rationale,
        background=list(background or []),
        warrants=[warrant],
        metadata={"source_refs": list(source_refs)} if source_refs else {},
        conclusion=obs_claim,
        given=(),
    )
    _pin_observed_claim(obs_claim)
    obs_claim.from_actions.append(action)
    return obs_claim


def _wrap_result(return_type: type[Claim], result_value: Any) -> Claim:
    if isinstance(result_value, return_type):
        return result_value
    return return_type(value=result_value)


def _bound_given(sig: inspect.Signature, *args: Any, **kwargs: Any) -> tuple[Claim, ...]:
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    given: list[Knowledge] = []
    for name, value in bound.arguments.items():
        parameter = sig.parameters[name]
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            values = value
        elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
            values = value.values()
        else:
            values = (value,)
        given.extend(item for item in values if isinstance(item, Knowledge))
    return cast(tuple[Claim, ...], tuple(given))


def _compute_call(
    conclusion_type: type[Claim],
    *,
    fn: Callable[..., Any] | None,
    given: Claim | tuple[Claim, ...] | list[Claim] | None,
    background: list[Knowledge] | None,
    rationale: str,
    label: str | None,
) -> Claim:
    given_tuple = _as_given_tuple(given)
    result_value = fn(*given_tuple) if fn is not None else None
    conclusion = _wrap_result(conclusion_type, result_value)
    warrant = _implication_warrant(
        "compute",
        given=given_tuple,
        conclusion=conclusion,
        rationale=rationale,
    )
    action = Compute(
        label=label,
        rationale=rationale,
        background=list(background or []),
        warrants=[warrant],
        conclusion=conclusion,
        given=given_tuple,
        fn=fn,
    )
    conclusion.from_actions.append(action)
    return conclusion


def compute(
    conclusion_type: type[Claim] | Callable[..., Any],
    *,
    fn: Callable[..., Any] | None = None,
    given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim | Callable[..., Claim]:
    """Deterministic computation.

    Used either as ``compute(ResultClaim, fn=..., given=...)`` or as ``@compute``.
    """
    if callable(conclusion_type) and not inspect.isclass(conclusion_type) and fn is None:
        wrapped_fn = conclusion_type
        sig = inspect.signature(wrapped_fn)
        return_type = sig.return_annotation
        if return_type is inspect.Signature.empty:
            raise TypeError("@compute requires a Claim return annotation")

        @wraps(wrapped_fn)
        def wrapper(*args: Any, **kwargs: Any) -> Claim:
            result_value = wrapped_fn(*args, **kwargs)
            conclusion = _wrap_result(return_type, result_value)
            given_tuple = _bound_given(sig, *args, **kwargs)
            action_rationale = inspect.getdoc(wrapped_fn) or ""
            warrant = _implication_warrant(
                "compute",
                given=given_tuple,
                conclusion=conclusion,
                rationale=action_rationale,
            )
            action = Compute(
                label=label,
                rationale=action_rationale,
                background=list(background or []),
                warrants=[warrant],
                conclusion=conclusion,
                given=given_tuple,
                fn=wrapped_fn,
            )
            conclusion.from_actions.append(action)
            return conclusion

        return wrapper

    if not inspect.isclass(conclusion_type) or not issubclass(conclusion_type, Claim):
        raise TypeError("compute() first argument must be a Claim subclass or decorated function")
    return _compute_call(
        conclusion_type,
        fn=fn,
        given=given,
        background=background,
        rationale=rationale,
        label=label,
    )
