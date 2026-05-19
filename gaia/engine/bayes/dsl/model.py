"""Bayes ``model`` verb - author predictive models."""

from __future__ import annotations

from typing import Any

from gaia.engine.bayes.runtime import Model
from gaia.engine.lang.runtime import Claim, Distribution, Knowledge, Variable
from gaia.engine.lang.runtime.action import attach_reasoning, validate_no_self_warrant


def _claim_ref(claim: Claim) -> str:
    if claim.label:
        return f"[@{claim.label}]"
    return claim.content


def _observable_descriptor(observable: Variable) -> str:
    return observable.symbol


def _distribution_unit(distribution: Distribution) -> str | None:
    unit = (distribution.metadata or {}).get("unit")
    if unit is None:
        return None
    from gaia.unit import canonical_unit

    return canonical_unit(unit)


def _validate_model_units(observable: Variable, distribution: Distribution) -> None:
    from gaia.unit import ureg

    observable_unit = observable.unit
    distribution_unit = _distribution_unit(distribution)
    if observable_unit is None:
        if distribution_unit is not None:
            raise TypeError(
                "bayes.model() distribution carries unit "
                f"{distribution_unit!r} but observable {observable.symbol!r} is unitless. "
                "Declare Variable(unit=...) for unit-bearing observables."
            )
        return
    if distribution_unit is None:
        raise TypeError(
            f"bayes.model() observable {observable.symbol!r} carries unit "
            f"{observable_unit!r}, but distribution "
            f"{distribution.label or distribution.content[:40]!r} is unitless."
        )
    try:
        (1 * ureg.parse_units(distribution_unit)).to(ureg.parse_units(observable_unit))
    except Exception as err:
        raise ValueError(
            "bayes.model() distribution unit "
            f"{distribution_unit!r} is not compatible with observable unit "
            f"{observable_unit!r}: {err}"
        ) from err
    if distribution_unit != observable_unit:
        raise ValueError(
            "bayes.model() distribution unit "
            f"{distribution_unit!r} must match observable unit {observable_unit!r}."
        )


def model(
    hypothesis: Claim,
    *,
    observable: Variable,
    distribution: Distribution,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Declare a predictive model for one hypothesis and observable."""
    if not isinstance(hypothesis, Claim):
        raise TypeError("model() hypothesis must be a Claim")
    if not isinstance(observable, Variable):
        raise TypeError(f"model() observable must be a Variable; got {type(observable).__name__}")
    if not isinstance(distribution, Distribution):
        raise TypeError(
            "model() distribution must be a Distribution Knowledge object "
            "(use factories in gaia.engine.lang: Normal, Binomial, BetaBinomial, ...); "
            f"got {type(distribution).__name__}"
        )
    _validate_model_units(observable, distribution)

    merged = dict(metadata or {})
    model_meta = {
        "kind": "model",
        "hypothesis": hypothesis,
        "observable": observable,
        "distribution": distribution,
    }
    merged["model"] = {**dict(merged.get("model", {})), **model_meta}
    merged.setdefault("generated", True)
    merged.setdefault("helper_kind", "model")
    merged.setdefault("review", True)
    if rationale:
        merged["reason"] = rationale

    content = (
        f"{_claim_ref(hypothesis)} models {_observable_descriptor(observable)} "
        f"~ {distribution.kind}."
    )
    helper = Claim(content, background=background or [], metadata=merged)
    helper.label = label

    action = Model(
        label=label,
        rationale=rationale,
        background=list(background or []),
        metadata={"bayes": {"action": "model"}},
        hypothesis=hypothesis,
        observable=observable,
        distribution=distribution,
        helper=helper,
    )
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)
    return helper
