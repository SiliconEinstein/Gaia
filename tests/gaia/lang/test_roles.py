from gaia.lang import Claim, equal, infer, observe
from gaia.lang.runtime.package import CollectedPackage
from gaia.lang.runtime.roles import roles_for_claim, roles_for_package


def _role_names(occurrences):
    return [occ.role for occ in occurrences]


def test_roles_for_claim_preserves_action_occurrences():
    with CollectedPackage("roles_demo") as pkg:
        h = Claim("Hypothesis.")
        h.label = "h"
        e = observe("Observation.", rationale="Measured.", label="observe_e")
        e.label = "e"
        infer(e, hypothesis=h, p_e_given_h=0.9, rationale="Bayes.", label="infer_e")

    assert _role_names(roles_for_claim(e, pkg)) == ["observation", "evidence"]
    assert _role_names(roles_for_claim(h, pkg)) == ["hypothesis"]

    e_roles = roles_for_claim(e, pkg)
    assert e_roles[0].action_label == "observe_e"
    assert e_roles[1].action_label == "infer_e"
    assert e_roles[1].action_type == "Infer"


def test_roles_for_package_indexes_multiple_structural_roles():
    with CollectedPackage("roles_demo") as pkg:
        a = Claim("A.")
        b = Claim("B.")
        helper = equal(a, b, rationale="Same.", label="same")

    index = roles_for_package(pkg)
    assert _role_names(index[a]) == ["equivalent_claim"]
    assert _role_names(index[b]) == ["equivalent_claim"]
    assert _role_names(index[helper]) == ["equivalence_helper", "warrant"]
