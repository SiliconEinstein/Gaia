"""Milestone C migration/deprecation tests for legacy helper APIs."""

import pytest

from gaia.engine.lang import (
    ClaimAtom,
    claim,
    land,
)
from gaia.engine.lang.compat import (
    and_,
    complement,
    contradiction,
    disjunction,
    equivalence,
    not_,
    or_,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.package import CollectedPackage

pytestmark = pytest.mark.legacy_dsl


@pytest.mark.parametrize(
    ("call_name", "factory", "helper_kind"),
    [
        ("not_", lambda a, _b: not_(a), "negation_result"),
        ("and_", lambda a, b: and_(a, b), "conjunction_result"),
        ("or_", lambda a, b: or_(a, b), "disjunction_result"),
    ],
)
def test_legacy_propositional_helpers_warn_but_preserve_behavior(
    call_name,
    factory,
    helper_kind,
):
    a = claim("A.")
    b = claim("B.")

    with pytest.warns(DeprecationWarning, match=f"{call_name}\\(\\) is deprecated"):
        helper = factory(a, b)

    assert helper.metadata["helper_kind"] == helper_kind


@pytest.mark.parametrize(
    ("call_name", "factory", "helper_kind"),
    [
        ("contradiction", contradiction, "contradiction_result"),
        ("equivalence", equivalence, "equivalence_result"),
        ("complement", complement, "complement_result"),
        ("disjunction", disjunction, "disjunction_result"),
    ],
)
def test_legacy_relation_helpers_warn_but_preserve_behavior(
    call_name,
    factory,
    helper_kind,
):
    a = claim("A.")
    b = claim("B.")

    with pytest.warns(DeprecationWarning, match=f"{call_name}\\(\\) is deprecated"):
        helper = factory(a, b, reason="legacy compatibility", prior=0.9)

    assert helper.metadata["helper_kind"] == helper_kind
    assert helper.metadata["prior"] == 0.9


def test_formula_claim_replacement_for_legacy_conjunction_compiles_to_same_operator_shape():
    with CollectedPackage("formula_migration_pkg", namespace="t") as pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        both = claim("A and B.", formula=land(ClaimAtom(a), ClaimAtom(b)))
        both.label = "both"

    artifact = compile_package_artifact(pkg)
    op = next(
        op
        for op in artifact.graph.operators
        if (op.metadata or {}).get("formula_lowering") == "connective"
    )

    assert op.operator == "conjunction"
    assert op.variables == ["t:formula_migration_pkg::a", "t:formula_migration_pkg::b"]
    assert op.conclusion == "t:formula_migration_pkg::both"
