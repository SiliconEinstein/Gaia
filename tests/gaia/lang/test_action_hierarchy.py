from gaia.lang.runtime.action import (
    Action,
    Compute,
    Contradict,
    Derive,
    DependsOn,
    Equal,
    Infer,
    Observe,
    Relate,
    Scaffold,
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


def test_equal_is_relate():
    assert issubclass(Equal, Relate)
    assert issubclass(Relate, Action)


def test_contradict_is_relate():
    assert issubclass(Contradict, Relate)


def test_infer_is_action():
    assert issubclass(Infer, Action)
    assert not issubclass(Infer, Support)
    assert not issubclass(Infer, Relate)


def test_depends_on_is_scaffold_not_support():
    assert issubclass(DependsOn, Scaffold)
    assert issubclass(Scaffold, Action)
    assert not issubclass(DependsOn, Support)
    assert not issubclass(DependsOn, Relate)
