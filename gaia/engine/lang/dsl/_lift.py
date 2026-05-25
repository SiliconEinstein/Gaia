"""Boolean-valued → Claim lift at verb boundary.

Implements the materialisation boundary specified in
``docs/specs/2026-05-24-boolean-valued-claim-lift-design.md`` §4.2:

- :class:`gaia.engine.lang.runtime.knowledge.Claim` is returned as-is.
- :class:`gaia.engine.lang.formula.predicate.ClaimAtom` is unwrapped to its
  underlying ``Claim`` (no helper Claim created).
- Any other Formula node (``Land``, ``Lor``, ``Lnot``, ``Implies``, ``Iff``,
  ``Forall``, ``Exists``, ``Equals`` / ``Greater`` / ``UserPredicate`` / ...)
  is materialised via ``claim(content, formula=value)`` with a synthesised
  description.
- :class:`gaia.engine.lang.dsl.bool_expr.BoolExpr` is materialised via
  ``claim(content, proposition)`` with a synthesised description.
- Anything else raises an educational :class:`TypeError` pointing at the
  Term-layer wrapping idiom.
"""

from __future__ import annotations

from typing import Any

from gaia.engine.lang._boolean_valued import is_boolean_valued
from gaia.engine.lang.dsl.bool_expr import BoolExpr
from gaia.engine.lang.dsl.knowledge import claim
from gaia.engine.lang.formula.predicate import ClaimAtom, is_formula
from gaia.engine.lang.runtime.knowledge import Claim


def _synth_description(value: Any) -> str:
    """Render a Boolean-valued expression to a human-readable description.

    Formula and BoolExpr classes all implement readable :meth:`__str__`, so
    this mostly delegates to ``str(value)``. If that yields an empty string
    we fall back to :func:`repr` so the helper Claim never carries an empty
    description.
    """
    text = str(value)
    if text:
        return text
    return repr(value)


def _lift_to_claim(value: Any, *, verb: str, position: str) -> Claim:
    """Materialise a Boolean-valued expression as a :class:`Claim`.

    Behaviour (in dispatch order):

    1. ``Claim``        → returned as-is.
    2. ``ClaimAtom``    → unwrapped to ``value.claim`` (no new helper).
    3. Formula          → ``claim(_synth_description(value), formula=value)``.
    4. ``BoolExpr``     → ``claim(_synth_description(value), value)``
       (positional ``proposition`` slot).
    5. anything else    → educational :class:`TypeError`.

    ``verb`` and ``position`` are formatted into the error message; e.g.
    ``verb="exclusive"``, ``position="first argument"``.
    """
    if isinstance(value, Claim):
        return value
    if isinstance(value, ClaimAtom):
        return value.claim
    if is_formula(value):
        return claim(_synth_description(value), formula=value)
    if isinstance(value, BoolExpr):
        return claim(_synth_description(value), value)
    raise TypeError(
        f"{verb}() expected Claim or a Boolean-valued expression "
        f"(Formula / BoolExpr / ClaimAtom) as {position}; "
        f"got {type(value).__name__}. "
        f"Term-layer values (Variable, Constant, Distribution, ...) are not "
        f"directly claim-able — wrap them in a predicate first "
        f"(e.g. Equals(x, Constant(5))) or pass an explicit "
        f"claim(content=..., formula=...) helper."
    )


def _lift_optional(value: Any, *, verb: str, position: str) -> Any:
    """Lift ``value`` to a Claim if it is Boolean-valued; otherwise pass through.

    Used by verbs that already accept multiple non-Claim input shapes
    (e.g. :func:`derive` and :func:`infer` accept a ``str`` ``conclusion`` /
    ``evidence`` and create a fresh ``Claim`` from it). For those, we only
    intercept Boolean-valued inputs and leave the rest for the verb's own
    type dispatch.
    """
    if isinstance(value, str) or value is None:
        return value
    if is_boolean_valued(value):
        return _lift_to_claim(value, verb=verb, position=position)
    return value
