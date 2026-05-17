"""Bayes runtime action shapes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Union

from gaia.engine.lang.runtime.action import Reasoning
from gaia.engine.lang.runtime.distribution import Distribution as DistributionKnowledge
from gaia.engine.lang.runtime.knowledge import Claim
from gaia.engine.lang.runtime.variable import Variable

if TYPE_CHECKING:
    from gaia.engine.bayes.distributions.protocol import Distribution


@dataclass
class BayesInference(Reasoning):
    """Bayes-family reasoning record."""


@dataclass
class PredictiveModel(BayesInference):
    """Predictive model for one hypothesis and one observable.

    Used by the v0.5 ``bayes.model()`` / ``bayes.likelihood()`` surface.
    Retained for backwards compatibility during v0.6 PoC; the new
    unified surface uses :class:`Prediction` (below).
    """

    hypothesis: Claim | None = None
    observable: Variable | None = None
    distribution: Distribution | None = None
    helper: Claim | None = None


@dataclass
class Likelihood(BayesInference):
    """Likelihood comparison between predictive-model helper claims.

    Used by the v0.5 ``bayes.likelihood()`` surface. Retained for
    backwards compatibility during v0.6 PoC; the new unified surface
    uses :class:`ModelComparison` (below).
    """

    helper: Claim | None = None
    model: Claim | None = None
    against: tuple[Claim, ...] = ()
    data: tuple[Claim, ...] = ()
    exclusivity: str = "pairwise_contradiction"
    precomputed: dict[Claim, float] | None = None
    log_likelihoods: dict[Claim, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# v0.6 unified-bayes actions (Prediction + ModelComparison)
# ---------------------------------------------------------------------------
# Distinct from PredictiveModel / Likelihood. The new surface dispatches on
# these via the v0.6 lowering registered in compiler/lower_v06.py.
#
# Field-level differences vs v0.5:
#   * Prediction.target accepts Variable | DistributionKnowledge (was
#     PredictiveModel.observable: Variable only). This matches the new
#     observe() schema where the same target type can sit either side.
#   * Prediction.distribution is typed as the Distribution Knowledge wrapper
#     rather than the typed-value pydantic backend, mirroring the migration
#     to a single user-facing Distribution type.
#   * ModelComparison.models is a single ordered list (no model= / against=
#     split). The v0.5 advocacy asymmetry is recorded only via Claim priors,
#     not via the comparison API.
#   * ModelComparison.precomputed accepts either a dict (legacy escape
#     hatch) or a PrecomputedLikelihoods Claim (audit-bearing form). The
#     dict form is widened with ``Any`` to keep the dataclass annotation
#     light; the DSL verb performs structural validation at construction
#     time.


@dataclass
class Prediction(BayesInference):
    """v0.6 predictive model: ties a hypothesis to a distribution over a target.

    The ``target`` is the random variable whose value is predicted under
    ``hypothesis``; it can be a :class:`Variable` (the discrete-count Bayes
    style) or a :class:`Distribution` Knowledge (predict on top of an
    already-declared random variable).
    """

    hypothesis: Claim | None = None
    target: Union[Variable, DistributionKnowledge, None] = None
    distribution: DistributionKnowledge | None = None
    helper: Claim | None = None


@dataclass
class ModelComparison(BayesInference):
    """v0.6 model comparison: equal-positioned list of competing predictions.

    ``models`` carries the helper Claims returned by :func:`predict` (one
    per hypothesis). ``data`` are the observation Claims to evaluate. The
    lowering binds each model's distribution to its hypothesis' parameter
    values, computes a log-likelihood, and emits one ``infer`` strategy
    per hypothesis.
    """

    helper: Claim | None = None
    models: tuple[Claim, ...] = ()
    data: tuple[Claim, ...] = ()
    exclusivity: str = "pairwise_contradiction"
    precomputed: Any | None = None
    log_likelihoods: dict[Claim, float] = field(default_factory=dict)
