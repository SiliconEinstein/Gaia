"""Gaia Lang v6 Evidence verb."""

from __future__ import annotations

import math
from typing import Any

from gaia.ir.schemas import DistributionLiteral
from gaia.lang.runtime.action import Evidence as EvidenceAction
from gaia.lang.runtime.knowledge import Claim, Knowledge


def _claim_ref(claim: Claim) -> str:
    return claim.content


def _as_given_tuple(given: Claim | tuple[Claim, ...] | list[Claim] | None) -> tuple[Claim, ...]:
    if given is None:
        return ()
    if isinstance(given, Knowledge):
        return (given,)
    return tuple(given)


def _model_metadata(model: DistributionLiteral) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)


def _observed_value(data: Claim, observed: Any | None) -> Any:
    if observed is not None:
        return observed
    if hasattr(data, "value"):
        return getattr(data, "value")
    raise TypeError("evidence() requires observed=... when data has no value field")


def _probability(value: float, field_name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise ValueError(f"{field_name} must be a probability in [0, 1], got {value!r}")
    return parsed


def _binomial_probability(model: DistributionLiteral, observed: Any) -> float:
    if model.kind != "binomial":
        raise TypeError("evidence() currently supports Binomial models only")

    n = model.params.get("n")
    p = model.params.get("p")
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("Binomial model parameter n must be an int")
    if isinstance(p, bool) or not isinstance(p, int | float):
        raise TypeError("Binomial model parameter p must be numeric")
    p = _probability(float(p), "model.p")
    if isinstance(observed, bool):
        raise TypeError("Binomial observed count must be an int")
    if isinstance(observed, float) and observed.is_integer():
        observed = int(observed)
    if not isinstance(observed, int):
        raise TypeError("Binomial observed count must be an int")
    if observed < 0 or observed > n:
        raise ValueError(f"Binomial observed count must be in [0, {n}], got {observed!r}")
    return math.comb(n, observed) * (p**observed) * ((1.0 - p) ** (n - observed))


def _model_probability(model: DistributionLiteral, observed: Any) -> float:
    if not isinstance(model, DistributionLiteral):
        raise TypeError("evidence() currently supports Binomial DistributionLiteral models only")
    return _binomial_probability(model, observed)


def evidence(
    data_or_legacy=None,
    *,
    hypothesis: Claim | None = None,
    data: Claim | str | None = None,
    model: DistributionLiteral | None = None,
    observed: Any | None = None,
    p_data_given_not_h: float = 0.5,
    given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
) -> Claim:
    """Model-based evidence. Returns the data Claim."""
    if data_or_legacy is not None:
        if data is not None:
            raise TypeError("evidence() got data both positionally and by keyword")
        data = data_or_legacy
    if hypothesis is None:
        raise TypeError("evidence() missing required keyword argument: 'hypothesis'")
    if data is None:
        raise TypeError("evidence() missing required keyword argument: 'data'")
    if model is None:
        raise TypeError("evidence() missing required keyword argument: 'model'")
    if isinstance(data, str):
        data = Claim(data)
    if not isinstance(data, Claim):
        raise TypeError("evidence() data must be a Claim or string")
    if not isinstance(hypothesis, Claim):
        raise TypeError("evidence() hypothesis must be a Claim")
    given_tuple = _as_given_tuple(given)
    if any(not isinstance(item, Claim) for item in given_tuple):
        raise TypeError("evidence() given entries must be Claims")

    observed_value = _observed_value(data, observed)
    p_data_given_h = _model_probability(model, observed_value)
    p_data_given_not_h = _probability(p_data_given_not_h, "p_data_given_not_h")
    model_metadata = _model_metadata(model)
    relation = {
        "type": "evidence",
        "hypothesis": hypothesis,
        "data": data,
        "model": model_metadata,
        "observed": observed_value,
        "p_data_given_h": p_data_given_h,
        "p_data_given_not_h": p_data_given_not_h,
    }
    if given_tuple:
        relation["given"] = given_tuple
    helper = Claim(
        f"{_claim_ref(data)} is model-based evidence for {_claim_ref(hypothesis)}.",
        metadata={
            "generated": True,
            "helper_kind": "evidence",
            "review": True,
            "relation": relation,
        },
    )
    action = EvidenceAction(
        label=label,
        rationale=rationale,
        background=list(background or []),
        hypothesis=hypothesis,
        data=data,
        given=given_tuple,
        model=model_metadata,
        observed=observed_value,
        p_data_given_h=p_data_given_h,
        p_data_given_not_h=p_data_given_not_h,
        helper=helper,
    )
    action.warrants.append(helper)
    data.supports.append(action)
    return data
