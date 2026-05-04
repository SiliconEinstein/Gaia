"""Structured Claim sugar for common formula shapes."""

from __future__ import annotations

from typing import Any

from gaia.lang.dsl.formula import causes, equals, land
from gaia.lang.dsl.knowledge import claim
from gaia.lang.formula.term import Constant
from gaia.lang.runtime import Claim, Knowledge, Variable
from gaia.lang.runtime.knowledge import ClaimKind
from gaia.lang.types.primitives import PrimitiveType


def parameter(
    variable: Variable,
    value: Any,
    *,
    content: str | None = None,
    describe: str | None = None,
    title: str | None = None,
    format: str = "markdown",
    background: list[Knowledge] | None = None,
    provenance: list[dict[str, str]] | None = None,
    prior: float | None = None,
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Declare that a primitive Variable takes a concrete value."""
    formula = equals(variable, _constant_for(variable, value))
    result = claim(
        _content_text(content, describe, _parameter_content(variable, value)),
        title=title,
        format=format,
        background=background,
        provenance=provenance,
        prior=prior,
        formula=formula,
        kind=ClaimKind.PARAMETER,
        metadata=metadata or {},
    )
    result.label = label
    return result


def observation(
    *,
    content: str | None = None,
    describe: str | None = None,
    title: str | None = None,
    format: str = "markdown",
    background: list[Knowledge] | None = None,
    provenance: list[dict[str, str]] | None = None,
    prior: float | None = None,
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
    **observed: Variable,
) -> Claim:
    """Declare observed values carried by primitive Variables with value set."""
    if not observed:
        raise ValueError("observation() requires at least one observed Variable")
    formulas = []
    for name, variable in observed.items():
        if not isinstance(variable, Variable):
            raise TypeError(f"observation() value for {name!r} must be a Variable")
        if variable.value is None:
            raise ValueError(f"observation() Variable {variable.symbol!r} must have value set")
        formulas.append(equals(variable, _constant_for(variable, variable.value)))

    formula = formulas[0] if len(formulas) == 1 else land(*formulas)
    result = claim(
        _content_text(content, describe, _observation_content(observed)),
        title=title,
        format=format,
        background=background,
        provenance=provenance,
        prior=prior,
        formula=formula,
        kind=ClaimKind.OBSERVATION,
        metadata=metadata or {},
    )
    result.label = label
    return result


def causal(
    cause: Any,
    effect: Any,
    *,
    content: str | None = None,
    describe: str | None = None,
    title: str | None = None,
    format: str = "markdown",
    background: list[Knowledge] | None = None,
    provenance: list[dict[str, str]] | None = None,
    prior: float | None = None,
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Declare a top-level causal marker Claim."""
    formula = causes(cause, effect)
    result = claim(
        _content_text(content, describe, _causal_content(cause, effect)),
        title=title,
        format=format,
        background=background,
        provenance=provenance,
        prior=prior,
        formula=formula,
        kind=ClaimKind.CAUSAL,
        metadata=metadata or {},
    )
    result.label = label
    return result


def _content_text(content: str | None, describe: str | None, fallback: str) -> str:
    if content is not None and describe is not None:
        raise TypeError("Pass either content or describe, not both")
    return content if content is not None else describe if describe is not None else fallback


def _constant_for(variable: Variable, value: Any) -> Constant:
    if not isinstance(variable, Variable):
        raise TypeError(f"expected a Variable, got {type(variable).__name__}")
    if not isinstance(variable.domain, PrimitiveType):
        raise TypeError("structured value sugar currently supports PrimitiveType variables")
    if variable.value is not None and variable.value != value:
        raise ValueError(
            f"Variable {variable.symbol!r} already has value {variable.value!r}, got {value!r}"
        )
    return Constant(value, variable.domain)


def _parameter_content(variable: Variable, value: Any) -> str:
    return f"{variable.symbol} = {value!r}."


def _observation_content(observed: dict[str, Variable]) -> str:
    rendered = ", ".join(f"{variable.symbol}={variable.value!r}" for variable in observed.values())
    return f"Observed {rendered}."


def _term_name(term: Any) -> str:
    return getattr(term, "symbol", repr(term))


def _causal_content(cause: Any, effect: Any) -> str:
    return f"{_term_name(cause)} causes {_term_name(effect)}."
