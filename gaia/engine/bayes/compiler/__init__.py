"""Bayes compiler lowering.

Two lowering passes ship side-by-side during the v0.6 PoC:

* The v0.5 lowering (:mod:`gaia.engine.bayes.compiler.lower`) handles
  :class:`PredictiveModel` and :class:`Likelihood` Actions written through
  ``bayes.model`` / ``bayes.likelihood`` / ``bayes.data``.
* The v0.6 lowering (:mod:`gaia.engine.bayes.compiler.lower_v06`) handles
  :class:`Prediction` and :class:`ModelComparison` Actions written through
  the unified ``predict`` / ``compare`` / ``observe(Variable, ...)`` surface.

Dispatch is by action type. The single registered lowerer routes each
action through the v0.5 path or the v0.6 path based on isinstance checks,
so a package may mix both surfaces during migration without conflict.
"""

from gaia.engine.bayes.compiler.lower import BayesLoweringResult, lower_bayes_claims
from gaia.engine.bayes.compiler.lower_v06 import (
    BayesV06LoweringResult,
    lower_v06_bayes_claims,
)
from gaia.engine.bayes.runtime import (
    BayesInference,
    Likelihood,
    ModelComparison,
    Prediction,
    PredictiveModel,
)
from gaia.engine.lang.compiler.extensions import (
    ActionLoweringContext,
    ActionLoweringResult,
    register_action_lowerer,
    registered_action_lowerers,
)

_LOWERER_NAME = "bayes"


def _is_bayes_action(action: object) -> bool:
    return isinstance(action, BayesInference)


def _is_v06_action(action: object) -> bool:
    return isinstance(action, (Prediction, ModelComparison))


def _is_v05_action(action: object) -> bool:
    return isinstance(action, (PredictiveModel, Likelihood))


def _lower_bayes_actions(context: ActionLoweringContext) -> ActionLoweringResult:
    """Route each BayesInference action through the v0.5 or v0.6 lowering pass.

    Splits ``context.actions`` by class, runs the v0.5 lowerer over the
    v0.5 actions and the v0.6 lowerer over the v0.6 actions, then merges
    the results. Non-Bayes actions in the context (defensive — should
    already be filtered by ``handles``) are ignored.
    """
    v05_actions = [a for a in context.actions if _is_v05_action(a)]
    v06_actions = [a for a in context.actions if _is_v06_action(a)]

    knowledges = []
    operators = []
    strategies = []
    metadata_updates: dict[str, dict[str, object]] = {}
    action_label_map: dict[str, str] = {}
    target_action_labels_by_id: dict[str, str] = {}

    if v05_actions:
        lowered_v05 = lower_bayes_claims(
            context.knowledge_nodes,
            actions=v05_actions,
            namespace=context.namespace,
            package_name=context.package_name,
            knowledge_map=context.knowledge_map,
            action_labels_by_object=context.action_labels_by_object,
            existing_operators=context.existing_operators,
        )
        knowledges.extend(lowered_v05.knowledges)
        operators.extend(lowered_v05.operators)
        strategies.extend(lowered_v05.strategies)
        metadata_updates.update(lowered_v05.metadata_updates)
        action_label_map.update(lowered_v05.action_label_map)
        target_action_labels_by_id.update(lowered_v05.target_action_labels_by_id)

    if v06_actions:
        carry_operators = list(context.existing_operators or []) + list(operators)
        lowered_v06 = lower_v06_bayes_claims(
            context.knowledge_nodes,
            actions=v06_actions,
            namespace=context.namespace,
            package_name=context.package_name,
            knowledge_map=context.knowledge_map,
            action_labels_by_object=context.action_labels_by_object,
            existing_operators=carry_operators,
        )
        knowledges.extend(lowered_v06.knowledges)
        operators.extend(lowered_v06.operators)
        strategies.extend(lowered_v06.strategies)
        # v0.6 metadata updates use distinct namespaces ("prediction" /
        # "comparison") so dict.update() over the same knowledge id is
        # safe — but use a per-id merge to preserve any v0.5 keys.
        for knowledge_id, payload in lowered_v06.metadata_updates.items():
            existing = metadata_updates.get(knowledge_id, {})
            merged = dict(existing)
            merged.update(payload)
            metadata_updates[knowledge_id] = merged
        action_label_map.update(lowered_v06.action_label_map)
        target_action_labels_by_id.update(lowered_v06.target_action_labels_by_id)

    return ActionLoweringResult(
        knowledges=knowledges,
        operators=operators,
        strategies=strategies,
        metadata_updates=metadata_updates,
        action_label_map=action_label_map,
        target_action_labels_by_id=target_action_labels_by_id,
    )


def register_bayes_lowerer() -> None:
    """Register Bayes action lowering with the Gaia Lang compiler.

    Identity-aware idempotency: returns early only when the existing
    ``"bayes"`` registration uses the official ``_is_bayes_action`` /
    ``_lower_bayes_actions`` pair. If a different lowerer is already
    registered under the ``"bayes"`` name, raise :class:`ValueError`
    instead of silently shadowing it — that case is the exact scenario the
    duplicate-name guard on :func:`register_action_lowerer` exists to
    surface, and a name-only idempotency check would mask it.

    Safe to call from both ``gaia.engine.bayes.__init__`` (import-time
    self-registration) and ``discover_and_register_extensions`` (called by
    the compiler at compile time).
    """
    for existing in registered_action_lowerers():
        if existing.name != _LOWERER_NAME:
            continue
        if existing.handles is _is_bayes_action and existing.lower is _lower_bayes_actions:
            return
        raise ValueError(
            f"action lowerer {_LOWERER_NAME!r} already registered with a "
            f"different handler/lowerer pair; refusing to silently shadow. "
            f"Pass override=True to register_action_lowerer if the "
            f"replacement was intentional."
        )
    register_action_lowerer(
        _LOWERER_NAME,
        handles=_is_bayes_action,
        lower=_lower_bayes_actions,
    )


__all__ = [
    "BayesLoweringResult",
    "BayesV06LoweringResult",
    "lower_bayes_claims",
    "lower_v06_bayes_claims",
]
