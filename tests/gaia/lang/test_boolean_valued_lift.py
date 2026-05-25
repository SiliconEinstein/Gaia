"""Tests for the Boolean-valued → Claim lift at verb boundaries (RFC #703).

Covers:

- ``is_boolean_valued`` predicate composition (Formula via ``is_formula``,
  Claim and BoolExpr via ``__gaia_boolean_valued__`` marker).
- ``_lift_to_claim`` dispatch per shape (Claim passthrough, ClaimAtom
  unwrap, Formula → ``claim(formula=...)``, BoolExpr → ``claim(content,
  proposition)``).
- Each Claim-accepting verb in scope (``equal``, ``contradict``,
  ``exclusive``, ``derive``, ``infer``, ``register_prior``) now accepts a
  Boolean-valued expression as direct argument.
- Term-layer values (``Variable``, raw Python types) raise the educational
  ``TypeError`` from the lift's else branch.
"""

import pytest

from gaia.engine.lang import (
    Beta,
    ClaimAtom,
    Constant,
    Equals,
    Forall,
    Land,
    Nat,
    Variable,
    claim,
    contradict,
    derive,
    equal,
    exclusive,
    infer,
    register_prior,
)
from gaia.engine.lang._boolean_valued import is_boolean_valued
from gaia.engine.lang.dsl._lift import _lift_to_claim, _synth_description
from gaia.engine.lang.runtime.knowledge import Claim, _current_package
from gaia.engine.lang.runtime.package import CollectedPackage

# ---------------------------------------------------------------------------
# is_boolean_valued predicate
# ---------------------------------------------------------------------------


def test_is_boolean_valued_recognizes_claim():
    a = Claim("A.")
    assert is_boolean_valued(a) is True


def test_is_boolean_valued_recognizes_claim_atom():
    a = Claim("A.")
    assert is_boolean_valued(ClaimAtom(a)) is True


def test_is_boolean_valued_recognizes_formula_connectives():
    a = Claim("A.")
    b = Claim("B.")
    assert is_boolean_valued(a & b) is True
    assert is_boolean_valued(a | b) is True
    assert is_boolean_valued(~a) is True


def test_is_boolean_valued_recognizes_predicate_formulas():
    x = Variable(symbol="x", domain=Nat)
    pred = Equals(left=x, right=Constant(value=5, primitive=Nat))
    assert is_boolean_valued(pred) is True


def test_is_boolean_valued_recognizes_quantifier_formulas():
    x = Variable(symbol="x", domain=Nat)
    body = Equals(left=x, right=Constant(value=5, primitive=Nat))
    assert is_boolean_valued(Forall(variable=x, body=body)) is True


def test_is_boolean_valued_recognizes_bool_expr():
    k = Beta("k prior", alpha=2, beta=2)
    assert is_boolean_valued(k > 0.5) is True


def test_is_boolean_valued_rejects_term_layer():
    x = Variable(symbol="x", domain=Nat)
    c = Constant(value=5, primitive=Nat)
    assert is_boolean_valued(x) is False
    assert is_boolean_valued(c) is False
    assert is_boolean_valued("a string") is False
    assert is_boolean_valued(42) is False
    assert is_boolean_valued(None) is False


# ---------------------------------------------------------------------------
# _lift_to_claim — dispatch per shape
# ---------------------------------------------------------------------------


def test_lift_passes_claim_through_unchanged():
    a = Claim("A.")
    assert _lift_to_claim(a, verb="t", position="x") is a


def test_lift_unwraps_claim_atom_without_creating_helper():
    pkg = CollectedPackage(name="bv_lift_unwrap_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        atom = ClaimAtom(a)
        lifted = _lift_to_claim(atom, verb="t", position="x")
    finally:
        _current_package.reset(token)
    # Unwrap returns the original Claim object — no new helper Claim in the package.
    assert lifted is a
    assert sum(1 for k in pkg.knowledge if isinstance(k, Claim)) == 1


def test_lift_materializes_propositional_formula_as_helper():
    pkg = CollectedPackage(name="bv_lift_propositional_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        helper = _lift_to_claim(a & b, verb="t", position="x")
    finally:
        _current_package.reset(token)
    assert isinstance(helper, Claim)
    assert helper.formula is not None
    assert isinstance(helper.formula, Land)
    # Helper is distinct from the operand claims.
    assert helper is not a
    assert helper is not b


def test_lift_materializes_bool_expr_via_proposition_path():
    pkg = CollectedPackage(name="bv_lift_boolexpr_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        k = Beta("k prior", alpha=2, beta=2)
        helper = _lift_to_claim(k > 0.5, verb="t", position="x")
    finally:
        _current_package.reset(token)
    assert isinstance(helper, Claim)
    # BoolExpr is stored via the predicate/equation metadata path, not as
    # claim.formula (which is the propositional/quantifier Formula path).
    assert helper.formula is None
    assert "predicate" in helper.metadata or "equation" in helper.metadata


def test_lift_rejects_term_layer_with_educational_message():
    x = Variable(symbol="x", domain=Nat)
    with pytest.raises(TypeError) as exc:
        _lift_to_claim(x, verb="exclusive", position="first argument")
    msg = str(exc.value)
    assert "exclusive()" in msg
    assert "first argument" in msg
    assert "Variable" in msg
    # Educational hint pointing at the Term-wrapping idiom.
    assert "Term-layer" in msg or "predicate" in msg


def test_lift_rejects_raw_python_values():
    with pytest.raises(TypeError):
        _lift_to_claim(42, verb="t", position="x")
    with pytest.raises(TypeError):
        _lift_to_claim("hello", verb="t", position="x")
    with pytest.raises(TypeError):
        _lift_to_claim(None, verb="t", position="x")


def test_synth_description_uses_str_repr():
    a = Claim("A.")
    a.label = "a"
    b = Claim("B.")
    b.label = "b"
    desc = _synth_description(a & b)
    assert isinstance(desc, str)
    assert desc  # non-empty


# ---------------------------------------------------------------------------
# Verb integration: each in-scope verb accepts a Boolean-valued argument
# ---------------------------------------------------------------------------


def test_exclusive_accepts_propositional_formula_directly():
    pkg = CollectedPackage(name="bv_exclusive_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        neg = claim("Neither A nor B.")
        # The whole point of RFC #703 — this expression was the BoardgameQA
        # failure-mode anchor.
        result = exclusive(a & b, neg, rationale="binary split", label="exc_both")
    finally:
        _current_package.reset(token)
    assert isinstance(result, Claim)


def test_contradict_accepts_propositional_formula_directly():
    pkg = CollectedPackage(name="bv_contradict_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        c = claim("C.")
        result = contradict(a & b, c, rationale="", label="con")
    finally:
        _current_package.reset(token)
    assert isinstance(result, Claim)


def test_equal_accepts_propositional_formula_directly():
    pkg = CollectedPackage(name="bv_equal_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        c = claim("C.")
        result = equal(a & b, c, rationale="", label="eq")
    finally:
        _current_package.reset(token)
    assert isinstance(result, Claim)


def test_derive_accepts_propositional_formula_in_given():
    pkg = CollectedPackage(name="bv_derive_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        conclusion = claim("Conclusion.")
        result = derive(conclusion, given=[a & b], rationale="", label="d")
    finally:
        _current_package.reset(token)
    assert isinstance(result, Claim)


def test_derive_accepts_single_propositional_formula_in_given():
    pkg = CollectedPackage(name="bv_derive_single_given_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        conclusion = claim("Conclusion.")
        result = derive(conclusion, given=a & b, rationale="", label="d_single")
    finally:
        _current_package.reset(token)
    assert isinstance(result, Claim)
    action = result.from_actions[0]
    assert len(action.given) == 1
    assert isinstance(action.given[0], Claim)
    assert isinstance(action.given[0].formula, Land)


def test_infer_accepts_propositional_formula_as_evidence_and_hypothesis():
    pkg = CollectedPackage(name="bv_infer_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        c = claim("C.")
        result = infer(
            a & b,
            hypothesis=c,
            p_e_given_h=0.9,
            p_e_given_not_h=0.5,
            label="i",
        )
    finally:
        _current_package.reset(token)
    assert isinstance(result, Claim)


def test_infer_accepts_single_propositional_formula_in_given():
    pkg = CollectedPackage(name="bv_infer_single_given_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        h = claim("Hypothesis.")
        e = claim("Evidence.")
        result = infer(
            e,
            hypothesis=h,
            given=a & b,
            p_e_given_h=0.9,
            p_e_given_not_h=0.5,
            label="i_single_given",
        )
    finally:
        _current_package.reset(token)
    assert isinstance(result, Claim)
    action = result.from_actions[0]
    assert len(action.given) == 1
    assert isinstance(action.given[0], Claim)
    assert isinstance(action.given[0].formula, Land)


def test_register_prior_accepts_propositional_formula():
    pkg = CollectedPackage(name="bv_register_prior_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        # The helper Claim minted by the lift gets a prior registered on it.
        register_prior(a & b, 0.7, justification="Joint prior for A and B.")
    finally:
        _current_package.reset(token)
    # Verify a helper Claim was created with prior records.
    helpers_with_priors = [
        k for k in pkg.knowledge if isinstance(k, Claim) and k.metadata.get("prior_records")
    ]
    assert len(helpers_with_priors) == 1


# ---------------------------------------------------------------------------
# Verb integration: educational TypeError on Term-layer arguments
# ---------------------------------------------------------------------------


def test_exclusive_rejects_term_layer_with_educational_message():
    pkg = CollectedPackage(name="bv_exclusive_term_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        x = Variable(symbol="x", domain=Nat)
        with pytest.raises(TypeError, match="exclusive"):
            exclusive(x, a, rationale="", label="t")
    finally:
        _current_package.reset(token)


def test_register_prior_still_rejects_term_layer():
    pkg = CollectedPackage(name="bv_rp_term_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        x = Variable(symbol="x", domain=Nat)
        with pytest.raises(TypeError):
            register_prior(x, 0.5, justification="should be rejected")
    finally:
        _current_package.reset(token)


# ---------------------------------------------------------------------------
# Verb integration: ClaimAtom unwraps without an extra helper Claim
# ---------------------------------------------------------------------------


def test_exclusive_with_claim_atom_unwraps_no_extra_helper():
    pkg = CollectedPackage(name="bv_atom_unwrap_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        # ClaimAtom should be unwrapped to its underlying Claim; no formula
        # helper Claim should be minted for this trivial wrapper.
        exclusive(ClaimAtom(a), b, rationale="", label="exc_atom")
    finally:
        _current_package.reset(token)
    # Count formula-bearing helper claims; ClaimAtom unwrap creates none.
    formula_helpers = [k for k in pkg.knowledge if isinstance(k, Claim) and k.formula is not None]
    assert len(formula_helpers) == 0


# ---------------------------------------------------------------------------
# Backwards compatibility: existing Claim-only callers still work
# ---------------------------------------------------------------------------


def test_exclusive_with_plain_claims_still_works():
    pkg = CollectedPackage(name="bv_compat_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        result = exclusive(a, b, rationale="", label="exc")
    finally:
        _current_package.reset(token)
    assert isinstance(result, Claim)


def test_derive_with_plain_claim_string_conclusion_still_works():
    pkg = CollectedPackage(name="bv_compat_str_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        # str conclusion remains a valid shape — it is NOT lifted (str is not
        # Boolean-valued); derive's own type dispatch handles it.
        result = derive("Conclusion from string.", given=[a], rationale="", label="d")
    finally:
        _current_package.reset(token)
    assert isinstance(result, Claim)


def test_infer_with_plain_string_evidence_still_works():
    pkg = CollectedPackage(name="bv_compat_infer_str_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        h = claim("Hypothesis.")
        result = infer(
            "Evidence as string.",
            hypothesis=h,
            p_e_given_h=0.9,
            p_e_given_not_h=0.5,
            label="i_str",
        )
    finally:
        _current_package.reset(token)
    assert isinstance(result, Claim)
