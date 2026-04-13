"""Gaia Lang v5 — Operator functions (deterministic logical constraints)."""

from __future__ import annotations

import math
from typing import Any

from gaia.ir.parameterization import CROMWELL_EPS
from gaia.lang.runtime import Knowledge, Operator


def _validate_prior_range(prior: float | None) -> None:
    if prior is None:
        return
    if isinstance(prior, bool) or not isinstance(prior, (int, float)):
        raise ValueError(f"prior must be a number, got {type(prior).__name__}.")
    prior_value = float(prior)
    if not math.isfinite(prior_value):
        raise ValueError(f"prior must be finite, got {prior_value!r}.")
    if prior_value < CROMWELL_EPS or prior_value > 1 - CROMWELL_EPS:
        raise ValueError(
            f"prior {prior_value} outside Cromwell bounds [{CROMWELL_EPS}, {1 - CROMWELL_EPS}]"
        )


def _validate_reason_prior(reason: str | Any, prior: float | None) -> None:
    """Enforce reason+prior pairing: both or neither."""
    has_reason = bool(reason)
    has_prior = prior is not None
    if has_reason != has_prior:
        raise ValueError(
            "reason and prior must be paired: provide both or neither. "
            f"Got reason={'yes' if has_reason else 'no'}, prior={'yes' if has_prior else 'no'}."
        )
    _validate_prior_range(prior)


def _helper_metadata(helper_kind: str, prior: float | None) -> dict:
    meta: dict = {"helper_kind": helper_kind}
    if prior is not None:
        meta["prior"] = prior
    return meta


def contradiction(
    a: Knowledge, b: Knowledge, *, reason: str = "", prior: float | None = None
) -> Knowledge:
    """not(A and B). Creates Operator, returns helper claim."""
    _validate_reason_prior(reason, prior)
    helper = Knowledge(
        content=f"not_both_true({a.label or 'A'}, {b.label or 'B'})",
        type="claim",
        metadata=_helper_metadata("contradiction_result", prior),
    )
    Operator(operator="contradiction", variables=[a, b], conclusion=helper, reason=reason)
    return helper


def equivalence(
    a: Knowledge, b: Knowledge, *, reason: str = "", prior: float | None = None
) -> Knowledge:
    """A = B. Creates Operator, returns helper claim."""
    _validate_reason_prior(reason, prior)
    helper = Knowledge(
        content=f"same_truth({a.label or 'A'}, {b.label or 'B'})",
        type="claim",
        metadata=_helper_metadata("equivalence_result", prior),
    )
    Operator(operator="equivalence", variables=[a, b], conclusion=helper, reason=reason)
    return helper


def complement(
    a: Knowledge, b: Knowledge, *, reason: str = "", prior: float | None = None
) -> Knowledge:
    """A != B (XOR). Creates Operator, returns helper claim."""
    _validate_reason_prior(reason, prior)
    helper = Knowledge(
        content=f"opposite_truth({a.label or 'A'}, {b.label or 'B'})",
        type="claim",
        metadata=_helper_metadata("complement_result", prior),
    )
    Operator(operator="complement", variables=[a, b], conclusion=helper, reason=reason)
    return helper


def disjunction(*claims: Knowledge, reason: str = "", prior: float | None = None) -> Knowledge:
    """At least one true. Creates Operator, returns helper claim."""
    _validate_reason_prior(reason, prior)
    labels = ", ".join(c.label or f"C{i}" for i, c in enumerate(claims))
    helper = Knowledge(
        content=f"any_true({labels})",
        type="claim",
        metadata=_helper_metadata("disjunction_result", prior),
    )
    Operator(operator="disjunction", variables=list(claims), conclusion=helper, reason=reason)
    return helper
