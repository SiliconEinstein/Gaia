"""Tests for FunctionSymbol and PredicateSymbol declarations."""

import pytest

from gaia.engine.lang.formula.primitives import Nat, Real
from gaia.engine.lang.formula.symbols import FunctionSymbol, PredicateSymbol
from gaia.engine.lang.runtime.domain import Domain


def test_function_symbol_basic():
    f = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    assert f.name == "E"
    assert f.arg_domains == (Nat,)
    assert f.result_domain is Real


def test_function_symbol_multi_arity():
    f = FunctionSymbol(name="V", arg_domains=(Nat, Nat), result_domain=Real)
    assert f.arg_domains == (Nat, Nat)


def test_function_symbol_name_required():
    with pytest.raises(ValueError, match="name"):
        FunctionSymbol(name="", arg_domains=(Nat,), result_domain=Real)


def test_function_symbol_arg_domains_must_be_typed():
    with pytest.raises(TypeError, match="arg_domain"):
        FunctionSymbol(name="E", arg_domains=("Nat",), result_domain=Real)  # type: ignore[arg-type]


def test_function_symbol_with_custom_domain():
    Particle = Domain(content="x", members=["p1"])
    f = FunctionSymbol(name="E", arg_domains=(Particle,), result_domain=Real)
    assert f.arg_domains == (Particle,)


def test_predicate_symbol_basic():
    p = PredicateSymbol(name="Stable", arg_domains=(Nat,))
    assert p.name == "Stable"
    assert p.arg_domains == (Nat,)


def test_predicate_symbol_zero_arity_disallowed():
    with pytest.raises(ValueError, match="arity"):
        PredicateSymbol(name="P", arg_domains=())


def test_function_symbol_zero_arity_disallowed():
    with pytest.raises(ValueError, match="arity"):
        FunctionSymbol(name="f", arg_domains=(), result_domain=Real)


def test_function_symbol_result_domain_validation():
    with pytest.raises(TypeError, match="result_domain"):
        FunctionSymbol(name="f", arg_domains=(Nat,), result_domain="Real")  # type: ignore[arg-type]
