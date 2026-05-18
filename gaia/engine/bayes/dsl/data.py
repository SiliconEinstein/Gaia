"""Bayes observed-data helper."""

from __future__ import annotations

import math
from typing import Any

from gaia.engine.bayes.distributions.continuous import Normal
from gaia.engine.bayes.distributions.protocol import Distribution
from gaia.engine.lang.dsl.formula import equals
from gaia.engine.lang.dsl.support import observe
from gaia.engine.lang.formula.primitives import PrimitiveType
from gaia.engine.lang.formula.term import Constant
from gaia.engine.lang.runtime import Claim, Knowledge, Variable


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | float):
        return format(value, "g")
    return repr(value)


def _noise_payload(error: Any) -> dict[str, Any] | None:
    if error is None:
        return None
    if isinstance(error, bool):
        raise TypeError("bayes.data() error must be a positive numeric sigma or a Normal noise")
    if isinstance(error, int | float):
        sigma = float(error)
        if not math.isfinite(sigma) or sigma <= 0.0:
            raise ValueError(f"bayes.data() error=sigma requires sigma > 0, got {error!r}")
        return Normal(mu=0.0, sigma=sigma).model_dump()
    if isinstance(error, Distribution):
        payload = error.model_dump()
        if payload.get("kind") != "normal":
            raise ValueError("bayes.data() error currently supports only Normal additive noise")
        return payload
    raise TypeError("bayes.data() error must be a positive numeric sigma or a Normal noise")


def _merged_metadata(
    metadata: dict[str, Any] | None, noise_payload: dict[str, Any] | None
) -> dict[str, Any]:
    merged = dict(metadata or {})
    if noise_payload is None:
        return merged

    bayes_meta = merged.get("bayes")
    if bayes_meta is None:
        bayes_meta = {}
    elif not isinstance(bayes_meta, dict):
        raise TypeError("bayes.data() metadata['bayes'] must be a dict when present")
    else:
        bayes_meta = dict(bayes_meta)

    if "noise" in bayes_meta:
        raise ValueError("bayes.data() got both error= and metadata['bayes']['noise']")
    bayes_meta["noise"] = noise_payload
    merged["bayes"] = bayes_meta
    return merged


def _default_content(observable: Variable, value: Any, error: Any) -> str:
    content = f"Observed {observable.symbol} = {_format_value(value)}"
    if error is None:
        return content + "."
    if isinstance(error, int | float) and not isinstance(error, bool):
        return content + f" +/- {_format_value(error)}."
    if isinstance(error, Distribution):
        return content + f" with {error.kind} additive noise."
    return content + "."


def data(
    observable: Variable,
    *,
    value: Any,
    error: Any = None,
    content: str | None = None,
    background: list[Knowledge] | None = None,
    source_refs: list[str] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Declare an observed value claim consumable by ``bayes.likelihood()``."""
    if not isinstance(observable, Variable):
        raise TypeError("bayes.data() observable must be a Variable")
    if not isinstance(observable.domain, PrimitiveType):
        raise TypeError("bayes.data() observable must have a PrimitiveType domain")

    payload = _noise_payload(error)
    observed = Claim(
        content or _default_content(observable, value, error),
        background=background or [],
        formula=equals(observable, Constant(value, observable.domain)),
        metadata=_merged_metadata(metadata, payload),
    )
    observed.label = label
    observe(
        observed,
        background=background,
        source_refs=source_refs,
        rationale=rationale or observed.content,
        label=f"observe_{label}" if label else None,
    )
    return observed
