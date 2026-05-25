"""Marker for Boolean-valued types that can stand in for Claim at verb boundaries.

A Boolean-valued type is one whose values denote a Boolean-valued (T/F)
assertion that maps to a Bernoulli random variable in BP. The set of
Boolean-valued types is the union of:

- All :mod:`gaia.engine.lang.formula` Formula nodes (``Land``, ``Lor``,
  ``Lnot``, ``Implies``, ``Iff``, ``Forall``, ``Exists``, ``Equals``,
  ``NotEquals``, ``Greater``, ``GreaterEqual``, ``Less``, ``LessEqual``,
  ``UserPredicate``, ``ClaimAtom``) — detected via the existing
  :func:`gaia.engine.lang.formula.predicate.is_formula` predicate, since every
  Formula class already carries ``__gaia_formula__: ClassVar[bool] = True``.

- :class:`gaia.engine.lang.runtime.knowledge.Claim` — the probabilistic
  knowledge node itself; declares its Boolean-valued status with the
  ``__gaia_boolean_valued__: ClassVar[bool] = True`` class marker.

- :class:`gaia.engine.lang.dsl.bool_expr.BoolExpr` — the ``Distribution``
  comparison result; declares its Boolean-valued status with the same
  ``__gaia_boolean_valued__`` class marker.

Term-layer types (``Variable``, ``Constant``, ``FunctionApp``,
``Distribution``, ``DerivedDistribution``, ``Note``, ``Setting`` …) carry
neither marker. They are *not* Boolean-valued and are rejected at verb
boundaries with an educational error from
:func:`gaia.engine.lang.dsl._lift._lift_to_claim`.

See the design RFC at
``docs/specs/2026-05-24-boolean-valued-claim-lift-design.md`` for the
type-theoretic motivation (the Curry-Howard proposition/term split aligning
with Gaia's two-layer structure).
"""

from __future__ import annotations

from typing import Any

from gaia.engine.lang.formula.predicate import is_formula


def is_boolean_valued(obj: Any) -> bool:
    """Return ``True`` iff ``obj`` is a Boolean-valued expression.

    Composes the existing :func:`is_formula` predicate (which covers every
    Formula class) with a ``__gaia_boolean_valued__`` class-attribute marker
    set on :class:`Claim` and :class:`BoolExpr`. New non-Formula
    Boolean-valued types opt in by setting
    ``__gaia_boolean_valued__: ClassVar[bool] = True`` on the class; they do
    not need to be listed here.
    """
    if is_formula(obj):
        return True
    return getattr(obj, "__gaia_boolean_valued__", False) is True
