import pytest

from gaia.engine.lang import Claim
from gaia.engine.lang.compat import and_, or_

pytestmark = pytest.mark.legacy_dsl


def test_claim_boolean_truth_value_is_not_allowed():
    a = Claim("A.")
    with pytest.raises(TypeError, match="structured formula claims"):
        bool(a)


def test_explicit_and_or_functions_accept_multiple_claims():
    """``and_``/``or_`` remain available as deprecated v5-compat functions.

    They still return helper Claim nodes (the legacy shape) and still emit
    ``DeprecationWarning`` so explicit callers learn to migrate to
    ``claim(formula=land(...))``. The modern dunder operators ``~ & |`` no
    longer route through these helpers; see ``test_formula_claim_sugar.py``
    for their Formula-returning behavior.
    """
    a = Claim("A.")
    b = Claim("B.")
    c = Claim("C.")

    with pytest.warns(DeprecationWarning, match="and_\\(\\) is deprecated"):
        both = and_(a, b, c)
    with pytest.warns(DeprecationWarning, match="or_\\(\\) is deprecated"):
        either = or_(a, b, c)

    assert both.metadata["helper_kind"] == "conjunction_result"
    assert either.metadata["helper_kind"] == "disjunction_result"


def test_propositional_functions_reject_non_claim_inputs():
    a = Claim("A.")
    with (
        pytest.warns(DeprecationWarning, match="and_\\(\\) is deprecated"),
        pytest.raises(TypeError, match="Claim"),
    ):
        and_(a, object())
    with (
        pytest.warns(DeprecationWarning, match="or_\\(\\) is deprecated"),
        pytest.raises(TypeError, match="Claim"),
    ):
        or_(a, object())
