"""gaia.engine.bayes - hypothesis-data inference verbs.

The user-facing surface is two verbs plus Bayes runtime records:

* :func:`model` - declare a predictive model for one hypothesis.
* :func:`compare` - compare equal-positioned predictive models against data.
* :class:`PrecomputedLikelihoods` - audit-bearing return type for
  external-solver wrappers (PyMC / Stan / NumPyro / ...). Always pair
  with the standard :func:`gaia.engine.lang.compute` decorator to
  record the wrapper's ``fn`` / ``code_hash`` provenance.

Distributions live at :mod:`gaia.engine.lang` (the same factories that
back the quantity-with-predicate surface). The pydantic
``_BaseDistribution`` types at :mod:`gaia.engine.bayes.distributions` are
internal scipy-backend implementations - they are not part of the
authoring surface.
"""

from __future__ import annotations

from gaia.engine.bayes.compiler import register_bayes_lowerer as _register_bayes_lowerer
from gaia.engine.bayes.dsl import compare, model
from gaia.engine.bayes.runtime import (
    BayesInference,
    Model,
    ModelCompare,
    PrecomputedLikelihoods,
)
from gaia.engine.lang.runtime.action import Action
from gaia.engine.lang.runtime.roles import RoleAdder, register_role_handler


def _register_bayes_roles() -> None:
    def model_roles(action: Action, add: RoleAdder) -> None:
        if not isinstance(action, Model):
            return
        add(action.hypothesis, "hypothesis")
        add(action.helper, "model_helper")

    def model_compare_roles(action: Action, add: RoleAdder) -> None:
        if not isinstance(action, ModelCompare):
            return
        for model_helper in action.models:
            add(model_helper, "compared_model")
        for data_claim in action.data:
            add(data_claim, "likelihood_data")
        add(action.helper, "model_preference_helper")

    register_role_handler(Model, model_roles)
    register_role_handler(ModelCompare, model_compare_roles)


_register_bayes_roles()
_register_bayes_lowerer()

__all__ = [
    "BayesInference",
    "Model",
    "ModelCompare",
    "PrecomputedLikelihoods",
    "compare",
    "model",
]
