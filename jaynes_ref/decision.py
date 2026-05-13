"""Bayesian decision theory (Jaynes PTLoS Ch. 13).

Given a posterior over states P(s | I) and a loss function L(a, s),
the Bayes-optimal action minimises expected loss:

    a*(I) = argmin_a sum_s L(a, s) * P(s | I).

This module operates on **discrete states** drawn from a posterior dict
or a full joint table. It is decoupled from how that posterior is
computed (exact, MaxEnt, or A_p predictive).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import numpy as np

__all__ = [
    "DecisionResult",
    "bayes_action",
    "expected_loss",
    "zero_one_loss",
    "quadratic_loss",
    "asymmetric_loss",
]


@dataclass(frozen=True)
class DecisionResult:
    action: object
    expected_loss: float
    loss_by_action: dict[object, float]


def expected_loss(
    action: object,
    posterior: Mapping[object, float],
    loss: Callable[[object, object], float],
) -> float:
    """E_{s ~ posterior}[L(action, s)]."""
    total = 0.0
    s_total = 0.0
    for state, p in posterior.items():
        if p < 0.0:
            raise ValueError(f"posterior[{state!r}]={p} is negative")
        total += p * float(loss(action, state))
        s_total += p
    if not np.isclose(s_total, 1.0, atol=1e-9):
        raise ValueError(f"posterior does not sum to 1 (sum={s_total})")
    return total


def bayes_action(
    actions: Sequence[object],
    posterior: Mapping[object, float],
    loss: Callable[[object, object], float],
) -> DecisionResult:
    """Return action minimising expected posterior loss.

    Ties are broken by the first action in 'actions' order (stable).
    """
    if len(actions) == 0:
        raise ValueError("actions must be non-empty")
    losses: dict[object, float] = {}
    best_a = actions[0]
    best_l = float("inf")
    for a in actions:
        l = expected_loss(a, posterior, loss)
        losses[a] = l
        if l < best_l:
            best_l = l
            best_a = a
    return DecisionResult(action=best_a, expected_loss=best_l, loss_by_action=losses)


# ---------------------------------------------------------------------
# Loss factories
# ---------------------------------------------------------------------

def zero_one_loss() -> Callable[[object, object], float]:
    """L(a, s) = 0 if a == s else 1.

    Under this loss, bayes_action returns the MAP estimate (most
    probable state). Pure Jaynes: equivalent posterior mode.
    """

    def loss(a: object, s: object) -> float:
        return 0.0 if a == s else 1.0

    return loss


def quadratic_loss() -> Callable[[float, float], float]:
    """L(a, s) = (a - s)^2. Best action = posterior mean."""

    def loss(a: float, s: float) -> float:
        d = float(a) - float(s)
        return d * d

    return loss


def asymmetric_loss(
    false_positive: float, false_negative: float
) -> Callable[[int, int], float]:
    """Binary loss matrix for actions/states in {0, 1}.

    L(action=1, state=0) = false_positive
    L(action=0, state=1) = false_negative
    Otherwise 0.

    Threshold on P(s=1): decide 1 when P(s=1) > false_positive / (fp+fn).
    """
    if false_positive < 0.0 or false_negative < 0.0:
        raise ValueError("loss values must be non-negative")

    def loss(a: int, s: int) -> float:
        a = int(a)
        s = int(s)
        if a not in (0, 1) or s not in (0, 1):
            raise ValueError("asymmetric_loss is binary")
        if a == s:
            return 0.0
        return false_positive if a == 1 else false_negative

    return loss
