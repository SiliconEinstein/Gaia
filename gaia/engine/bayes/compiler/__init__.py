"""Bayes compiler lowering."""

from gaia.engine.bayes.compiler.lower import BayesLoweringResult, lower_bayes_claims
from gaia.engine.bayes.runtime import BayesInference
from gaia.engine.lang.compiler.extensions import (
    ActionLoweringContext,
    ActionLoweringResult,
    register_action_lowerer,
    registered_action_lowerers,
)

_LOWERER_NAME = "bayes"


def _is_bayes_action(action: object) -> bool:
    return isinstance(action, BayesInference)


def _lower_bayes_actions(context: ActionLoweringContext) -> ActionLoweringResult:
    lowered = lower_bayes_claims(
        context.knowledge_nodes,
        actions=context.actions,
        namespace=context.namespace,
        package_name=context.package_name,
        knowledge_map=context.knowledge_map,
        action_labels_by_object=context.action_labels_by_object,
        existing_operators=context.existing_operators,
    )
    return ActionLoweringResult(
        knowledges=lowered.knowledges,
        operators=lowered.operators,
        strategies=lowered.strategies,
        metadata_updates=lowered.metadata_updates,
        action_label_map=lowered.action_label_map,
        target_action_labels_by_id=lowered.target_action_labels_by_id,
    )


def register_bayes_lowerer() -> None:
    """Register Bayes action lowering with the Gaia Lang compiler.

    Idempotent: returns early if the Bayes lowerer is already registered.
    Safe to call from both ``gaia.engine.bayes.__init__`` (import-time
    self-registration) and ``discover_and_register_extensions`` (called by
    the compiler at compile time).
    """
    for lowerer in registered_action_lowerers():
        if lowerer.name == _LOWERER_NAME:
            return
    register_action_lowerer(
        _LOWERER_NAME,
        handles=_is_bayes_action,
        lower=_lower_bayes_actions,
    )


__all__ = ["BayesLoweringResult", "lower_bayes_claims"]
