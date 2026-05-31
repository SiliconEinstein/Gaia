"""Tests for Claim<->Formula authoring sugar.

Covers two ergonomic improvements that remove `ClaimAtom(...)` boilerplate
without merging the Formula and Claim layers:

* Sugar A: ``Land/Lor/Lnot/Implies/Iff`` auto-coerce ``Claim`` operands into
  ``ClaimAtom(claim)``. Operands that are already Formula nodes (including
  ``ClaimAtom``, ``Equals``, ``UserPredicate``, nested connectives) pass
  through unchanged. Non-Claim non-Formula operands still raise ``TypeError``.

* Sugar B: ``Claim.__invert__/__and__/__or__`` produce modern Formula nodes
  (``Lnot/Land/Lor`` wrapping ``ClaimAtom``) instead of the deprecated
  propositional helper claims, and emit no ``DeprecationWarning``. The
  deprecated function-call API (``and_/or_/not_`` in ``gaia.engine.lang.compat``)
  continues to work for explicit legacy callers and is covered separately in
  ``test_propositional.py``.
"""

import warnings

import pytest

from gaia.engine.lang import (
    ClaimAtom,
    Constant,
    Equals,
    Iff,
    Implies,
    Land,
    Lnot,
    Lor,
    Nat,
    Variable,
    claim,
    equals,
    iff,
    implies,
    land,
    lnot,
    lor,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.knowledge import Claim, _current_package
from gaia.engine.lang.runtime.package import CollectedPackage

# ---------------------------------------------------------------------------
# Sugar A: connective auto-coercion of Claim -> ClaimAtom
# ---------------------------------------------------------------------------


def test_land_auto_wraps_claim_operands_into_claim_atoms():
    pkg = CollectedPackage(name="sugar_a_land_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        formula = land(a, b)
    finally:
        _current_package.reset(token)

    assert isinstance(formula, Land)
    assert len(formula.operands) == 2
    for op, original in zip(formula.operands, (a, b), strict=True):
        assert isinstance(op, ClaimAtom)
        assert op.claim is original


def test_lor_auto_wraps_claim_operands_into_claim_atoms():
    pkg = CollectedPackage(name="sugar_a_lor_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        formula = lor(a, b)
    finally:
        _current_package.reset(token)

    assert isinstance(formula, Lor)
    assert all(isinstance(op, ClaimAtom) for op in formula.operands)
    assert [op.claim for op in formula.operands] == [a, b]


def test_lnot_auto_wraps_claim_operand_into_claim_atom():
    pkg = CollectedPackage(name="sugar_a_lnot_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        formula = lnot(a)
    finally:
        _current_package.reset(token)

    assert isinstance(formula, Lnot)
    assert isinstance(formula.operand, ClaimAtom)
    assert formula.operand.claim is a


def test_implies_auto_wraps_claim_operands_into_claim_atoms():
    pkg = CollectedPackage(name="sugar_a_implies_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        formula = implies(a, b)
    finally:
        _current_package.reset(token)

    assert isinstance(formula, Implies)
    assert isinstance(formula.antecedent, ClaimAtom)
    assert isinstance(formula.consequent, ClaimAtom)
    assert formula.antecedent.claim is a
    assert formula.consequent.claim is b


def test_iff_auto_wraps_claim_operands_into_claim_atoms():
    pkg = CollectedPackage(name="sugar_a_iff_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        formula = iff(a, b)
    finally:
        _current_package.reset(token)

    assert isinstance(formula, Iff)
    assert isinstance(formula.left, ClaimAtom)
    assert isinstance(formula.right, ClaimAtom)
    assert formula.left.claim is a
    assert formula.right.claim is b


def test_land_passes_through_already_formula_operands_untouched():
    pkg = CollectedPackage(name="sugar_a_passthrough_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        n = Variable(symbol="n", domain=Nat)
        existing_atom = ClaimAtom(a)
        existing_equals = equals(n, Constant(395, Nat))
        formula = land(existing_atom, existing_equals)
    finally:
        _current_package.reset(token)

    assert formula.operands[0] is existing_atom
    assert formula.operands[1] is existing_equals


def test_land_mixes_claim_and_term_formula_operands():
    pkg = CollectedPackage(name="sugar_a_mixed_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        n = Variable(symbol="n", domain=Nat)
        formula = land(a, equals(n, Constant(395, Nat)))
    finally:
        _current_package.reset(token)

    assert isinstance(formula.operands[0], ClaimAtom)
    assert formula.operands[0].claim is a
    assert isinstance(formula.operands[1], Equals)


def test_land_rejects_non_claim_non_formula_operand():
    pkg = CollectedPackage(name="sugar_a_reject_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        with pytest.raises(TypeError, match="not a Formula"):
            land(a, "not a formula")
        with pytest.raises(TypeError, match="not a Formula"):
            land(a, 42)
    finally:
        _current_package.reset(token)


def test_lnot_rejects_non_claim_non_formula_operand():
    with pytest.raises(TypeError, match="not a Formula"):
        lnot("not a formula")
    with pytest.raises(TypeError, match="not a Formula"):
        lnot(42)


def test_land_arity_validation_still_applies_after_coercion():
    pkg = CollectedPackage(name="sugar_a_arity_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        with pytest.raises(ValueError, match="at least two operands"):
            land(a)
    finally:
        _current_package.reset(token)


def test_claim_with_coerced_land_formula_compiles_to_conjunction_operator():
    pkg = CollectedPackage(name="sugar_a_compile_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        both = claim("A and B.", formula=land(a, b))
        both.label = "both"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    op = next(
        op
        for op in artifact.graph.operators
        if (op.metadata or {}).get("formula_lowering") == "connective"
    )
    assert op.operator == "conjunction"
    assert op.variables == ["t:sugar_a_compile_pkg::a", "t:sugar_a_compile_pkg::b"]
    assert op.conclusion == "t:sugar_a_compile_pkg::both"
    # Formula-emitted operators are top-level in graph.operators (not embedded
    # inside a FormalExpr), so they must carry an lco_ operator_id per the
    # validator contract (validator.py:199-203). Regression for issue #702.
    assert op.operator_id is not None
    assert op.operator_id.startswith("lco_")
    assert op.scope == "local"


def test_formula_claim_package_passes_local_graph_validation():
    """Regression for issue #702.

    `gaia build compile` calls `validate_local_graph` on the artifact.graph;
    `compile_package_artifact` alone does not. Before the fix, formula
    lowering emitted top-level operators without `operator_id`, so the
    validator rejected any package that used `claim(formula=...)`. This
    test exercises the exact validate-after-compile path the CLI uses.
    """
    from gaia.engine.ir.validator import validate_local_graph

    pkg = CollectedPackage(name="validator_regression_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        # The exact shape that triggered the bug — implicit Sugar B path
        # (`a & b` returns Land via Claim.__and__) plus explicit Sugar A
        # path (claim(formula=land(...))) — both must validate.
        both_implicit = claim("A and B (implicit).", formula=a & b)
        both_implicit.label = "both_implicit"
        both_explicit = claim("A and B (explicit).", formula=land(a, b))
        both_explicit.label = "both_explicit"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    result = validate_local_graph(artifact.graph)
    assert not result.errors, f"Expected validation to pass, got errors: {result.errors}"


# ---------------------------------------------------------------------------
# Sugar B: Claim dunder operators return modern Formula nodes (no warning)
# ---------------------------------------------------------------------------


def test_claim_invert_returns_lnot_formula_without_deprecation_warning():
    pkg = CollectedPackage(name="sugar_b_invert_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            formula = ~a
    finally:
        _current_package.reset(token)

    assert isinstance(formula, Lnot)
    assert isinstance(formula.operand, ClaimAtom)
    assert formula.operand.claim is a


def test_claim_and_returns_land_formula_without_deprecation_warning():
    pkg = CollectedPackage(name="sugar_b_and_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            formula = a & b
    finally:
        _current_package.reset(token)

    assert isinstance(formula, Land)
    assert [op.claim for op in formula.operands] == [a, b]


def test_claim_or_returns_lor_formula_without_deprecation_warning():
    pkg = CollectedPackage(name="sugar_b_or_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            formula = a | b
    finally:
        _current_package.reset(token)

    assert isinstance(formula, Lor)
    assert [op.claim for op in formula.operands] == [a, b]


def test_claim_and_with_formula_operand_passes_through():
    pkg = CollectedPackage(name="sugar_b_and_mixed_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        b = claim("B.")
        existing = ClaimAtom(b)
        formula = a & existing
    finally:
        _current_package.reset(token)

    assert isinstance(formula, Land)
    assert isinstance(formula.operands[0], ClaimAtom)
    assert formula.operands[0].claim is a
    assert formula.operands[1] is existing


def test_claim_and_with_non_claim_non_formula_returns_not_implemented():
    pkg = CollectedPackage(name="sugar_b_and_reject_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        with pytest.raises(TypeError):
            a & "not a claim"
        with pytest.raises(TypeError):
            a | 42
    finally:
        _current_package.reset(token)


def test_claim_dunder_chain_compiles_end_to_end():
    """Compile ``claim(formula=~a | b)`` into the expected disjunction operator.

    The compiled IR should record both a negation helper for ``a`` and a
    top-level disjunction whose conclusion is the user-named compound Claim.
    """
    pkg = CollectedPackage(name="sugar_b_chain_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        either = claim("not A or B.", formula=~a | b)
        either.label = "either"
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)
    connective_ops = [
        op
        for op in artifact.graph.operators
        if (op.metadata or {}).get("formula_lowering") == "connective"
    ]
    operator_names = sorted(op.operator for op in connective_ops)
    assert operator_names == ["disjunction", "negation"]

    disjunction_op = next(op for op in connective_ops if op.operator == "disjunction")
    assert disjunction_op.conclusion == "t:sugar_b_chain_pkg::either"


def test_claim_and_compiles_to_same_shape_as_explicit_land_form():
    """Show structural parity between the dunder form and the explicit form.

    ``a & b`` and ``land(ClaimAtom(a), ClaimAtom(b))`` must lower to the same
    operator (conjunction), the same operand identifiers, and the same
    conclusion identifier.
    """

    def _build(pkg_name: str, *, use_dunder: bool):
        pkg = CollectedPackage(name=pkg_name, namespace="t")
        token = _current_package.set(pkg)
        try:
            a = claim("A.")
            a.label = "a"
            b = claim("B.")
            b.label = "b"
            both = claim(
                "A and B.",
                formula=(a & b) if use_dunder else land(ClaimAtom(a), ClaimAtom(b)),
            )
            both.label = "both"
        finally:
            _current_package.reset(token)
        artifact = compile_package_artifact(pkg)
        return next(
            op
            for op in artifact.graph.operators
            if (op.metadata or {}).get("formula_lowering") == "connective"
        )

    dunder_op = _build("sugar_b_parity_dunder_pkg", use_dunder=True)
    explicit_op = _build("sugar_b_parity_explicit_pkg", use_dunder=False)

    assert dunder_op.operator == explicit_op.operator == "conjunction"
    assert [v.split("::", 1)[1] for v in dunder_op.variables] == [
        v.split("::", 1)[1] for v in explicit_op.variables
    ]
    assert dunder_op.conclusion.split("::", 1)[1] == explicit_op.conclusion.split("::", 1)[1]


# ---------------------------------------------------------------------------
# Claim is still not truthy in a Python sense (regression guard)
# ---------------------------------------------------------------------------


def test_claim_bool_still_raises_after_dunder_modernization():
    """Confirm Sugar B leaves ``__bool__`` rejecting accidental truth tests.

    Even though ``~ & |`` are now well-defined formula constructors, ``bool(a)``
    must continue to raise so that accidental ``if a:`` patterns surface as
    errors rather than truthy passes.
    """
    a = Claim("A.")
    with pytest.raises(TypeError, match="structured formula claims"):
        bool(a)
