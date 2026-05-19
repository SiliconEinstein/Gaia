"""Structured Claim sugar for common formula shapes."""

from __future__ import annotations

from typing import Any

from gaia.engine.lang.dsl.formula import equals
from gaia.engine.lang.dsl.knowledge import claim
from gaia.engine.lang.formula.primitives import PrimitiveType
from gaia.engine.lang.formula.term import Constant
from gaia.engine.lang.runtime import Claim, Knowledge, Variable
from gaia.engine.lang.runtime.knowledge import ClaimKind


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
