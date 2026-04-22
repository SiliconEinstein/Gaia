"""Gaia Lang v6 Infer verb."""

from __future__ import annotations

import warnings

from gaia.lang.runtime.action import Infer as InferAction
from gaia.lang.runtime.knowledge import Claim, Knowledge


def _claim_ref(claim: Claim) -> str:
    if claim.label:
        return f"[@{claim.label}]"
    return claim.content


def infer(
    *args,
    hypothesis: Claim | None = None,
    evidence: Claim | None = None,
    background: list[Knowledge] | None = None,
    p_e_given_h: float | None = None,
    p_e_given_not_h: float | None = None,
    rationale: str = "",
    label: str | None = None,
    **legacy_kwargs,
) -> Claim:
    """Bayesian inference. Returns a statistical-support helper Claim.

    The v6 shape is keyword-only. The old v5 ``infer([premises], conclusion, ...)``
    form is preserved as a deprecated compatibility path.
    """
    if args:
        if isinstance(args[0], (list, tuple)):
            from gaia.lang.dsl.strategies import infer as legacy_infer

            warnings.warn(
                "infer([premises], conclusion, ...) is deprecated; use keyword-only "
                "infer(hypothesis=..., evidence=..., p_e_given_h=..., "
                "p_e_given_not_h=...) instead",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy_infer(*args, **legacy_kwargs)
        raise TypeError("v6 infer() arguments are keyword-only")

    if hypothesis is None:
        raise TypeError("infer() missing required keyword argument: 'hypothesis'")
    if evidence is None:
        raise TypeError("infer() missing required keyword argument: 'evidence'")
    if p_e_given_h is None:
        raise TypeError("infer() missing required keyword argument: 'p_e_given_h'")
    if p_e_given_not_h is None:
        raise TypeError("infer() missing required keyword argument: 'p_e_given_not_h'")

    helper = Claim(
        f"{_claim_ref(evidence)} statistically supports {_claim_ref(hypothesis)}.",
        metadata={"generated": True, "helper_kind": "statistical_support", "review": True},
    )
    action = InferAction(
        label=label,
        rationale=rationale,
        background=list(background or []),
        hypothesis=hypothesis,
        evidence=evidence,
        p_e_given_h=p_e_given_h,
        p_e_given_not_h=p_e_given_not_h,
        helper=helper,
    )
    action.warrants.append(helper)
    return helper
