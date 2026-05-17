"""gaia.engine.bayes — hypothesis-data inference helpers.

The v0.6 unified surface lives at the top of this namespace:

* :func:`predict` — declare a predictive distribution for one hypothesis.
* :func:`compare` — compare equal-positioned predictive models against data.
* :class:`PrecomputedLikelihoods` — audit-bearing return type for
  external-solver wrappers (PyMC / Stan / ...).

These verbs consume :class:`gaia.engine.lang.runtime.distribution.Distribution`
Knowledge objects (created via ``Normal``, ``Binomial``, ``BetaBinomial``,
etc. from ``gaia.engine.lang``). They sit alongside the legacy
``bayes.model`` / ``bayes.likelihood`` / ``bayes.data`` verbs from v0.5
and produce distinct Action types (:class:`Prediction` /
:class:`ModelComparison`) that the v0.6 lowering recognises.

The typed-value distribution aliases (``bayes.Normal``, ``bayes.Binomial``,
...) remain importable for v0.5 callers but are not part of the v0.6
authoring surface; new code should import distributions from
``gaia.engine.lang``.
"""

from __future__ import annotations

from gaia.engine.bayes.compiler import register_bayes_lowerer as _register_bayes_lowerer
from gaia.engine.bayes.distributions import (
    Beta,
    BetaBinomial,
    Binomial,
    Cauchy,
    ChiSquared,
    DistParam,
    Distribution,
    Exponential,
    Gamma,
    LogNormal,
    Normal,
    Poisson,
    StudentT,
    UnresolvedParameterError,
)
from gaia.engine.bayes.dsl.compare import compare
from gaia.engine.bayes.dsl.data import data
from gaia.engine.bayes.dsl.likelihood import likelihood
from gaia.engine.bayes.dsl.model import model
from gaia.engine.bayes.dsl.predict import predict
from gaia.engine.bayes.runtime import (
    BayesInference,
    Likelihood,
    ModelComparison,
    PrecomputedLikelihoods,
    Prediction,
    PredictiveModel,
)
from gaia.engine.lang.runtime.action import Action
from gaia.engine.lang.runtime.roles import RoleAdder, register_role_handler


def _register_bayes_roles() -> None:
    def predictive_model_roles(action: Action, add: RoleAdder) -> None:
        if not isinstance(action, PredictiveModel):
            return
        add(action.hypothesis, "hypothesis")
        add(action.helper, "model_helper")

    def likelihood_roles(action: Action, add: RoleAdder) -> None:
        if not isinstance(action, Likelihood):
            return
        add(action.model, "compared_model")
        for alternative in action.against:
            add(alternative, "compared_alternative")
        for data_claim in action.data:
            add(data_claim, "likelihood_data")
        add(action.helper, "model_preference_helper")

    def prediction_roles(action: Action, add: RoleAdder) -> None:
        if not isinstance(action, Prediction):
            return
        add(action.hypothesis, "hypothesis")
        add(action.helper, "model_helper")

    def model_comparison_roles(action: Action, add: RoleAdder) -> None:
        if not isinstance(action, ModelComparison):
            return
        for model_helper in action.models:
            add(model_helper, "compared_model")
        for data_claim in action.data:
            add(data_claim, "likelihood_data")
        add(action.helper, "model_preference_helper")

    register_role_handler(PredictiveModel, predictive_model_roles)
    register_role_handler(Likelihood, likelihood_roles)
    register_role_handler(Prediction, prediction_roles)
    register_role_handler(ModelComparison, model_comparison_roles)


_register_bayes_roles()

_register_bayes_lowerer()

__all__ = [
    "BayesInference",
    "Beta",
    "BetaBinomial",
    "Binomial",
    "Cauchy",
    "ChiSquared",
    "DistParam",
    "Distribution",
    "Exponential",
    "Gamma",
    "Likelihood",
    "LogNormal",
    "ModelComparison",
    "Normal",
    "Poisson",
    "PrecomputedLikelihoods",
    "Prediction",
    "PredictiveModel",
    "StudentT",
    "UnresolvedParameterError",
    "compare",
    "data",
    "likelihood",
    "model",
    "predict",
]
