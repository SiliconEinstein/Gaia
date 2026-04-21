from gaia.lang.runtime.param import Param, UNBOUND


def test_param_unbound_sentinel():
    p = Param(name="value", type=float)
    assert p.value is UNBOUND
    assert p.value is not None


def test_param_bound():
    p = Param(name="value", type=float, value=5000.0)
    assert p.value == 5000.0
