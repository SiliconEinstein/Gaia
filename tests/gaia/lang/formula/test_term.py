"""Tests for Formula AST Term hierarchy with typed validation."""

import pytest

from gaia.engine.lang.formula.primitives import Bool, Nat, Probability, Real
from gaia.engine.lang.formula.symbols import FunctionSymbol
from gaia.engine.lang.formula.term import (  # noqa: F401
    ArithOp,
    Constant,
    FunctionApp,
    Term,
    is_term,
)
from gaia.engine.lang.runtime.domain import Domain
from gaia.engine.lang.runtime.variable import Variable


def test_constant_construction():
    c = Constant(value=395, primitive=Nat)
    assert c.value == 395
    assert c.primitive is Nat


def test_constant_value_must_match_primitive():
    """Spec §3 typed-AST: Constant validates its value against primitive."""
    with pytest.raises(ValueError, match="not accepted"):
        Constant(value=2, primitive=Probability)
    with pytest.raises(ValueError, match="not accepted"):
        Constant(value=-1, primitive=Nat)
    with pytest.raises(ValueError, match="not accepted"):
        Constant(value=1, primitive=Bool)


def test_constant_equality():
    c1 = Constant(value=395, primitive=Nat)
    c2 = Constant(value=395, primitive=Nat)
    c3 = Constant(value=396, primitive=Nat)
    assert c1 == c2
    assert c1 != c3


def test_constant_is_term():
    c = Constant(value=1, primitive=Nat)
    assert is_term(c)


def test_variable_is_term():
    n = Variable(symbol="n", domain=Nat, value=395)
    assert is_term(n)


def test_function_app_typed_construction():
    n = Variable(symbol="x", domain=Nat)
    E = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    fa = FunctionApp(symbol=E, args=(n,))
    assert fa.symbol is E
    assert fa.args == (n,)


def test_function_app_arity_mismatch_rejected():
    E = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    with pytest.raises(ValueError, match="arity"):
        FunctionApp(symbol=E, args=())
    with pytest.raises(ValueError, match="arity"):
        FunctionApp(symbol=E, args=(Constant(1, Nat), Constant(2, Nat)))


def test_function_app_arg_domain_mismatch_rejected():
    """E expects Nat; passing a Real-domain Variable should raise."""
    E = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    real_var = Variable(symbol="r", domain=Real)
    with pytest.raises(TypeError, match="domain"):
        FunctionApp(symbol=E, args=(real_var,))


def test_function_app_arg_domain_match_with_custom_domain():
    Particle = Domain(content="x", members=["p1"])
    E = FunctionSymbol(name="E", arg_domains=(Particle,), result_domain=Real)
    x = Variable(symbol="x", domain=Particle)
    fa = FunctionApp(symbol=E, args=(x,))
    assert fa.symbol.name == "E"


def test_function_app_args_must_be_terms():
    E = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    with pytest.raises(TypeError, match="argument"):
        FunctionApp(symbol=E, args=(395,))  # type: ignore[arg-type]


def test_function_app_is_term():
    E = FunctionSymbol(name="E", arg_domains=(Nat,), result_domain=Real)
    fa = FunctionApp(symbol=E, args=(Constant(1, Nat),))
    assert is_term(fa)


def test_arith_op_basic():
    n = Variable(symbol="n", domain=Nat, value=395)
    k = Variable(symbol="k", domain=Nat, value=295)
    expr = ArithOp(op="+", left=n, right=k)
    assert expr.op == "+"
    assert expr.left is n
    assert expr.right is k


def test_arith_op_is_term():
    n = Variable(symbol="n", domain=Nat)
    expr = ArithOp(op="+", left=n, right=Constant(1, Nat))
    assert is_term(expr)


def test_arith_op_rejects_unknown_op():
    n = Variable(symbol="n", domain=Nat)
    with pytest.raises(ValueError, match="op"):
        ArithOp(op="??", left=n, right=Constant(1, Nat))


def test_arith_op_operands_must_be_terms():
    with pytest.raises(TypeError, match="left"):
        ArithOp(op="+", left="x", right=Constant(1, Nat))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="right"):
        ArithOp(op="+", left=Constant(1, Nat), right="y")  # type: ignore[arg-type]


def test_term_protocol_does_not_match_arbitrary_objects():
    assert not is_term(395)
    assert not is_term("string")
    assert not is_term([Constant(1, Nat)])


def test_nested_term_tree():
    """E(x + 1) — build a deep tree, walk it, confirm structure."""
    x = Variable(symbol="x", domain=Real)
    E = FunctionSymbol(name="E", arg_domains=(Real,), result_domain=Real)
    inner_arith = ArithOp(op="+", left=x, right=Constant(1, Real))
    e_call = FunctionApp(symbol=E, args=(inner_arith,))
    assert is_term(e_call)
    assert is_term(e_call.args[0])
    assert e_call.args[0].left is x
