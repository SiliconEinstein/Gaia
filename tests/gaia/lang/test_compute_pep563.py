"""Regression: ``@compute`` must work with PEP-563 (``from __future__ import annotations``).

Modern Python projects ship ``from __future__ import annotations`` at the
top of every module so type annotations are deferred-evaluated (PEP 563)
and become plain strings. Before this regression test, ``@compute``
called ``inspect.signature(fn).return_annotation`` which would return
the literal string ``"SumResult"`` instead of the ``SumResult`` class,
and the subsequent ``isinstance(result, return_type)`` in
``_wrap_result`` raised ``TypeError: isinstance() arg 2 must be a type``.

The fix in ``gaia/engine/lang/dsl/support.py`` switches to
``inspect.signature(fn, eval_str=True)`` so string annotations are
resolved through the wrapper function's globals. This test pins that
fix end-to-end: declare a Claim subclass, decorate a wrapper that
returns it, call the wrapper, confirm we get the Claim back rather
than an exception.
"""

from __future__ import annotations

from gaia.engine.lang import compute
from gaia.engine.lang.runtime.action import Compute
from gaia.engine.lang.runtime.knowledge import Claim
from gaia.engine.lang.runtime.package import CollectedPackage


class IntClaim(Claim):
    """Value is {value}."""

    value: int


class SumResult(Claim):
    """Sum is {value}."""

    value: int


def test_compute_decorator_resolves_pep563_string_return_annotation():
    """``@compute`` with deferred annotations does not raise TypeError.

    Mirrors ``test_compute_v6.test_compute_decorator`` but in a module
    that opts into PEP-563. Without the ``eval_str=True`` fix, this
    test errors at the ``add(a, b)`` call.
    """
    with CollectedPackage("pep563_compute") as pkg:  # noqa: F841

        @compute
        def add(a: IntClaim, b: IntClaim) -> SumResult:
            """Add two integers."""
            return a.value + b.value

        a = IntClaim(value=3)
        b = IntClaim(value=4)
        result = add(a, b)

    assert isinstance(result, SumResult)
    assert result.value == 7
    assert len(result.from_actions) == 1
    assert isinstance(result.from_actions[0], Compute)
    assert result.from_actions[0].given == (a, b)


def test_compute_decorator_resolves_pep563_for_forward_referenced_claim():
    """A Claim type that is only resolvable through the wrapper's globals.

    Belt-and-suspenders: forward-ref-style string annotations (the actual
    PEP-563 mode) must be resolved using ``wrapped_fn.__globals__``,
    which is exactly what ``inspect.signature(fn, eval_str=True)`` does
    by default.
    """
    with CollectedPackage("pep563_compute_forward_ref") as pkg:  # noqa: F841

        @compute
        def double(x: IntClaim) -> SumResult:
            """Return 2x."""
            return x.value * 2

        x = IntClaim(value=21)
        result = double(x)

    assert isinstance(result, SumResult)
    assert result.value == 42
