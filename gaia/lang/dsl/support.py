"""Gaia Lang v6 Support verbs: derive, observe, compute."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from gaia.lang.runtime.action import Compute, Derive, Observe
from gaia.lang.runtime.grounding import Grounding
from gaia.lang.runtime.knowledge import Claim, Knowledge


def _as_given_tuple(given: Claim | tuple[Claim, ...] | list[Claim] | None) -> tuple[Claim, ...]:
    if given is None:
        return ()
    if isinstance(given, Knowledge):
        return (given,)
    return tuple(given)


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
    action = Derive(
        label=label,
        rationale=rationale,
        background=list(background or []),
        conclusion=conclusion,
        given=given_tuple,
    )
    conclusion.supports.append(action)
    return conclusion


def observe(
    conclusion: Claim | str,
    *,
    given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Empirical observation. A no-premise observation is still reviewable."""
    if isinstance(conclusion, str):
        conclusion = Claim(conclusion)
    given_tuple = _as_given_tuple(given)
    action = Observe(
        label=label,
        rationale=rationale,
        background=list(background or []),
        conclusion=conclusion,
        given=given_tuple,
    )
    if not given_tuple and conclusion.grounding is None:
        conclusion.grounding = Grounding(kind="source_fact", rationale=rationale)
    conclusion.supports.append(action)
    return conclusion


def _wrap_result(return_type: type[Claim], result_value: Any) -> Claim:
    if isinstance(result_value, return_type):
        return result_value
    return return_type(value=result_value)


def _bound_given(sig: inspect.Signature, *args, **kwargs) -> tuple[Knowledge, ...]:
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
    return tuple(given)


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
    action = Compute(
        label=label,
        rationale=rationale,
        background=list(background or []),
        conclusion=conclusion,
        given=given_tuple,
        fn=fn,
    )
    conclusion.supports.append(action)
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
        def wrapper(*args, **kwargs) -> Claim:
            result_value = wrapped_fn(*args, **kwargs)
            conclusion = _wrap_result(return_type, result_value)
            action = Compute(
                label=label,
                rationale=inspect.getdoc(wrapped_fn) or "",
                background=list(background or []),
                conclusion=conclusion,
                given=_bound_given(sig, *args, **kwargs),
                fn=wrapped_fn,
            )
            conclusion.supports.append(action)
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
