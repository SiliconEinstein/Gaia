"""gaia.engine.bayes — hypothesis-data inference helpers."""

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
from gaia.engine.bayes.dsl.data import data
from gaia.engine.bayes.dsl.likelihood import likelihood
from gaia.engine.bayes.dsl.model import model
from gaia.engine.bayes.runtime import BayesInference, Likelihood, PredictiveModel
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

    register_role_handler(PredictiveModel, predictive_model_roles)
    register_role_handler(Likelihood, likelihood_roles)


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
    "Normal",
    "Poisson",
    "PredictiveModel",
    "StudentT",
    "UnresolvedParameterError",
    "data",
    "likelihood",
    "model",
]
