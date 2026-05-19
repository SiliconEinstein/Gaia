"""Tests for Variable Knowledge subclass."""

import pytest
from pint.errors import UndefinedUnitError

from gaia.engine.lang import Real, Variable
from gaia.engine.lang.compiler.compile import _metadata_to_ir
from gaia.engine.lang.formula.primitives import Nat, Probability
from gaia.engine.lang.runtime.domain import Domain
from gaia.engine.lang.runtime.knowledge import Knowledge


def test_variable_is_knowledge_subclass():
    assert issubclass(Variable, Knowledge)


def test_variable_with_primitive_domain_and_value():
    n = Variable(symbol="n", domain=Nat, value=395)
    assert n.symbol == "n"
    assert n.domain is Nat
    assert n.value == 395


def test_variable_unbound():
    p = Variable(symbol="p", domain=Probability)
    assert p.value is None


def test_variable_with_custom_domain():
    Particle = Domain(content="Subatomic particles", members=["p1", "p2"])
    x = Variable(symbol="x", domain=Particle)
    assert x.domain is Particle


def test_variable_value_must_be_in_primitive_domain():
    with pytest.raises(ValueError, match=r"value .* not accepted"):
        Variable(symbol="n", domain=Nat, value=-1)


def test_variable_value_must_be_in_probability_range():
    with pytest.raises(ValueError, match=r"value .* not accepted"):
        Variable(symbol="p", domain=Probability, value=1.5)


def test_variable_with_custom_domain_value_must_be_member():
    Particle = Domain(content="x", members=["p1", "p2"])
    with pytest.raises(ValueError, match=r"value .* not in domain members"):
        Variable(symbol="x", domain=Particle, value="p3")


def test_variable_with_custom_domain_member_value_ok():
    Particle = Domain(content="x", members=["p1", "p2"])
    x = Variable(symbol="x", domain=Particle, value="p1")
    assert x.value == "p1"


def test_variable_unit_canonicalizes_through_gaia_unit() -> None:
    temperature = Variable(symbol="T", domain=Real, unit="K")
    assert temperature.unit == "kelvin"
    assert "kelvin" in temperature.content


def test_variable_rejects_invalid_unit() -> None:
    with pytest.raises(UndefinedUnitError, match="not_a_unit"):
        Variable(symbol="T", domain=Real, unit="not_a_unit")


def test_variable_metadata_serializes_canonical_unit() -> None:
    temperature = Variable(symbol="T", domain=Real, unit="K")

    assert _metadata_to_ir(temperature, {}) == {
        "kind": "variable",
        "symbol": "T",
        "domain": "Real",
        "unit": "kelvin",
    }


def test_variable_metadata_serializes_custom_domain_structure() -> None:
    particle = Domain(content="Particle domain", members=["electron", "muon"])
    particle.label = "Particle"
    variable = Variable(symbol="x", domain=particle)

    assert _metadata_to_ir(variable, {}) == {
        "kind": "variable",
        "symbol": "x",
        "domain": "Particle",
        "domain_content": "Particle domain",
        "domain_members": ["electron", "muon"],
        "unit": None,
    }


def test_variable_symbol_required():
    with pytest.raises(TypeError, match="symbol"):
        Variable(domain=Nat)  # type: ignore[call-arg]


def test_variable_no_prior():
    n = Variable(symbol="n", domain=Nat, value=0)
    assert not hasattr(n, "prior")


def test_variable_default_content_uses_symbol():
    n = Variable(symbol="n", domain=Nat, value=0)
    assert "n" in n.content


def test_variable_carries_term_marker():
    """Spec §3 typed-AST discipline — Variable must satisfy the Term protocol."""
    n = Variable(symbol="n", domain=Nat, value=0)
    assert getattr(n, "__gaia_term__", False) is True


def test_variable_does_not_register_into_package_knowledge_map():
    """Spec §2.4: Variable must NOT enter pkg._register_knowledge."""
    from gaia.engine.lang.runtime.knowledge import _current_package
    from gaia.engine.lang.runtime.package import CollectedPackage

    pkg = CollectedPackage(name="test_pkg", namespace="test")
    token = _current_package.set(pkg)
    try:
        v = Variable(symbol="x", domain=Nat, value=1)
        assert v._package is pkg
        registered = list(getattr(pkg, "knowledge", []) or [])
        assert v not in registered
    finally:
        _current_package.reset(token)
