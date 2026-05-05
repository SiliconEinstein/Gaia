from gaia.lang.runtime.action import (
    Action,
    Compute,
    Contradict,
    Derive,
    DependsOn,
    Equal,
    Exclusive,
    Infer,
    Observe,
    Probabilistic,
    Scaffold,
    Structural,
    Support,
)


def test_action_base_has_label():
    action = Derive(label="my_step", rationale="test")
    assert action.label == "my_step"


def test_derive_is_support():
    assert issubclass(Derive, Support)
    assert issubclass(Support, Action)


def test_observe_is_support():
    assert issubclass(Observe, Support)


def test_compute_is_support():
    assert issubclass(Compute, Support)


def test_equal_contradict_exclusive_are_structural():
    assert issubclass(Structural, Action)
    assert issubclass(Equal, Structural)
    assert issubclass(Contradict, Structural)
    assert issubclass(Exclusive, Structural)


def test_structural_does_not_own_relation_fields():
    assert "a" not in getattr(Structural, "__dataclass_fields__", {})
    assert "b" not in getattr(Structural, "__dataclass_fields__", {})
    assert "helper" not in getattr(Structural, "__dataclass_fields__", {})


def test_infer_is_probabilistic():
    assert issubclass(Infer, Probabilistic)
    assert issubclass(Probabilistic, Action)
    assert not issubclass(Infer, Support)
    assert not issubclass(Infer, Structural)


def test_depends_on_is_scaffold_not_support():
    assert issubclass(DependsOn, Scaffold)
    assert issubclass(Scaffold, Action)
    assert not issubclass(DependsOn, Support)
    assert not issubclass(DependsOn, Structural)
