"""Bayes runtime action shapes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gaia.engine.lang.runtime.action import Action, Probabilistic
from gaia.engine.lang.runtime.knowledge import Claim
from gaia.engine.lang.runtime.variable import Variable

if TYPE_CHECKING:
    from gaia.engine.lang.bayes.distributions.protocol import Distribution


@dataclass
class PredictiveModel(Action):
    """Predictive model for one hypothesis and one observable."""

    hypothesis: Claim | None = None
    observable: Variable | None = None
    distribution: Distribution | None = None
    helper: Claim | None = None


@dataclass
class Likelihood(Probabilistic):
    """Likelihood comparison between predictive-model helper claims."""

    model: Claim | None = None
    against: tuple[Claim, ...] = ()
    data: tuple[Claim, ...] = ()
    exclusivity: str = "pairwise_contradiction"
    precomputed: dict[Claim, float] | None = None
    log_likelihoods: dict[Claim, float] = field(default_factory=dict)
