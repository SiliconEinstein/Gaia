"""Bayes runtime action shapes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gaia.engine.lang.runtime.action import Reasoning
from gaia.engine.lang.runtime.knowledge import Claim
from gaia.engine.lang.runtime.variable import Variable

if TYPE_CHECKING:
    from gaia.engine.bayes.distributions.protocol import Distribution


@dataclass
class BayesInference(Reasoning):
    """Bayes-family reasoning record."""


@dataclass
class PredictiveModel(BayesInference):
    """Predictive model for one hypothesis and one observable."""

    hypothesis: Claim | None = None
    observable: Variable | None = None
    distribution: Distribution | None = None
    helper: Claim | None = None


@dataclass
class Likelihood(BayesInference):
    """Likelihood comparison between predictive-model helper claims."""

    helper: Claim | None = None
    model: Claim | None = None
    against: tuple[Claim, ...] = ()
    data: tuple[Claim, ...] = ()
    exclusivity: str = "pairwise_contradiction"
    precomputed: dict[Claim, float] | None = None
    log_likelihoods: dict[Claim, float] = field(default_factory=dict)
