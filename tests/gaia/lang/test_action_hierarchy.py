from gaia.engine.lang.bayes.runtime import BayesInference, Likelihood, PredictiveModel
from gaia.engine.lang.runtime.action import (
    Action,
    CandidateRelation,
    Compute,
    Contradict,
    DependsOn,
    Derive,
    Directed,
    Equal,
    Exclusive,
    GaiaGraph,
    Infer,
    Observe,
    Reasoning,
    Relation,
    Scaffold,
    Structural,
    Support,
)


def test_action_base_has_label():
    action = Derive(label="my_step", rationale="test")
    assert action.label == "my_step"


def test_compat_action_alias_points_to_reasoning_root():
    assert Action is Reasoning
    assert issubclass(Reasoning, GaiaGraph)
    assert issubclass(Directed, Reasoning)
    assert issubclass(Relation, Reasoning)
    assert issubclass(Scaffold, GaiaGraph)
    assert not issubclass(Scaffold, Reasoning)


def test_derive_is_directed_support():
    assert issubclass(Derive, Support)
    assert issubclass(Support, Directed)
    assert issubclass(Derive, Reasoning)


def test_observe_is_directed_support():
    assert issubclass(Observe, Support)
    assert issubclass(Observe, Directed)


def test_compute_is_directed_support():
    assert issubclass(Compute, Support)
    assert issubclass(Compute, Directed)


def test_equal_contradict_exclusive_are_relations():
    assert issubclass(Structural, Relation)
    assert issubclass(Equal, Structural)
    assert issubclass(Contradict, Structural)
    assert issubclass(Exclusive, Structural)


def test_structural_does_not_own_relation_fields():
    assert "a" not in getattr(Structural, "__dataclass_fields__", {})
    assert "b" not in getattr(Structural, "__dataclass_fields__", {})
    assert "helper" not in getattr(Structural, "__dataclass_fields__", {})


def test_infer_is_directed_not_legacy_probabilistic_family():
    assert issubclass(Infer, Directed)
    assert not issubclass(Infer, Support)
    assert not issubclass(Infer, Relation)


def test_associate_is_relation_not_directed():
    from gaia.engine.lang.runtime.action import Associate

    assert issubclass(Associate, Relation)
    assert not issubclass(Associate, Directed)


def test_decompose_and_compose_are_reasoning_not_relations():
    from gaia.engine.lang.runtime.action import Compose, Decompose

    assert issubclass(Decompose, Reasoning)
    assert issubclass(Compose, Reasoning)
    assert not issubclass(Decompose, Relation)
    assert not issubclass(Compose, Relation)


def test_depends_on_is_scaffold_not_reasoning():
    assert issubclass(DependsOn, Scaffold)
    assert not issubclass(DependsOn, Reasoning)
    assert not issubclass(DependsOn, Support)
    assert not issubclass(DependsOn, Structural)


def test_candidate_relation_is_scaffold_not_reasoning():
    assert issubclass(CandidateRelation, Scaffold)
    assert not issubclass(CandidateRelation, Reasoning)
    assert not issubclass(CandidateRelation, Support)
    assert not issubclass(CandidateRelation, Relation)


def test_bayes_action_shapes_follow_reasoning_taxonomy():
    assert issubclass(BayesInference, Reasoning)
    assert not issubclass(BayesInference, Directed)
    assert issubclass(PredictiveModel, BayesInference)
    assert not issubclass(PredictiveModel, Directed)
    assert issubclass(Likelihood, BayesInference)
    assert not issubclass(Likelihood, Directed)
