"""gaia.lang.bayes — hypothesis-data inference helpers."""

from __future__ import annotations

from gaia.lang.bayes.distributions import (
    Beta,
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
from gaia.lang.bayes.runtime import Likelihood, PredictiveModel
from gaia.lang.bayes.verbs.likelihood import likelihood
from gaia.lang.bayes.verbs.model import model
from gaia.lang.bayes.verbs.predict import predict
from gaia.lang.runtime.action import Action
from gaia.lang.runtime.roles import RoleAdder, register_role_handler


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

    register_role_handler(PredictiveModel, predictive_model_roles)
    register_role_handler(Likelihood, likelihood_roles)


_register_bayes_roles()

__all__ = [
    "Beta",
    "Binomial",
    "Cauchy",
    "ChiSquared",
    "DistParam",
    "Distribution",
    "Exponential",
    "Gamma",
    "Likelihood",
    "LogNormal",
    "Normal",
    "Poisson",
    "PredictiveModel",
    "StudentT",
    "UnresolvedParameterError",
    "likelihood",
    "model",
    "predict",
]
