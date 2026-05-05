from gaia.lang import (
    Claim,
    ClaimAtom,
    associate,
    compute,
    decompose,
    derive,
    equal,
    infer,
    observe,
    predict,
)
from gaia.lang.runtime.action import (
    Associate,
    Compose,
    Compute,
    Contradict,
    Decompose,
    DependsOn,
    Derive,
    Equal,
    Exclusive,
    Infer,
    Predict,
    Support,
)
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


def test_roles_cover_authored_action_shapes_and_sources():
    a = Claim("A.")
    b = Claim("B.")
    c = Claim("C.")
    d = Claim("D.")
    helper = Claim("Helper.")
    bg = Claim("Background.")
    warrant = Claim("Warrant.")
    likelihood_param = Claim("Likelihood parameter.")

    actions = (
        Derive(label="derive_c", conclusion=c, given=(a,), background=[bg], warrants=[warrant]),
        Compute(label="compute_d", conclusion=d, given=(c,)),
        Predict(label="predict_d", conclusion=d, given=(a,)),
        DependsOn(label="depends_d", conclusion=d, given=(b,)),
        Infer(
            label="infer_b",
            hypothesis=a,
            evidence=b,
            given=(c,),
            helper=helper,
            p_e_given_h=likelihood_param,
            p_e_given_not_h=0.2,
        ),
        Associate(label="assoc_ab", a=a, b=b, helper=helper),
        Equal(label="eq_ab", a=a, b=b, helper=helper),
        Contradict(label="contradict_ab", a=a, b=b, helper=helper),
        Exclusive(label="exclusive_ab", a=a, b=b, helper=helper),
        Decompose(label="split_c", whole=c, parts=(a, b), formula=ClaimAtom(a)),
    )

    index = roles_for_package(actions)

    assert "premise" in _role_names(index[a])
    assert "prediction_basis" in _role_names(index[a])
    assert "hypothesis" in _role_names(index[a])
    assert "association_target" in _role_names(index[a])
    assert "equivalent_claim" in _role_names(index[a])
    assert "contradiction_target" in _role_names(index[a])
    assert "exclusive_alternative" in _role_names(index[a])
    assert "decomposition_part" in _role_names(index[a])
    assert "dependency_target" in _role_names(index[d])
    assert "computed_result" in _role_names(index[d])
    assert "prediction" in _role_names(index[d])
    assert "likelihood_helper" in _role_names(index[helper])
    assert "association_helper" in _role_names(index[helper])
    assert "equivalence_helper" in _role_names(index[helper])
    assert "contradiction_helper" in _role_names(index[helper])
    assert "exclusivity_helper" in _role_names(index[helper])
    assert _role_names(index[likelihood_param]) == ["likelihood_parameter"]
    assert _role_names(index[bg]) == ["background"]
    assert index[bg][0].source == "background"
    assert _role_names(index[warrant]) == ["warrant"]
    assert index[warrant][0].source == "warrant"


def test_roles_can_exclude_background_and_warrants():
    claim = Claim("Claim.")
    bg = Claim("Background.")
    warrant = Claim("Warrant.")
    action = Derive(
        label="derive_claim",
        conclusion=claim,
        background=[bg],
        warrants=[warrant],
    )

    assert roles_for_claim(bg, (action,), include_background=False) == ()
    assert roles_for_claim(warrant, (action,), include_warrants=False) == ()


def test_roles_traverse_composed_child_actions_with_path():
    a = Claim("A.")
    b = Claim("B.")
    child = Derive(label="child_derive", conclusion=b, given=(a,))
    composition = Compose(
        label="workflow",
        name="test:workflow",
        version="1.0",
        inputs=(a,),
        actions=(child,),
        conclusion=b,
    )

    roles = roles_for_claim(a, (composition,))

    assert [occ.role for occ in roles] == ["composition_input", "premise"]
    assert roles[1].path == ("child_derive",)


def test_roles_falls_back_for_legacy_support_action():
    premise = Claim("Premise.")
    conclusion = Claim("Conclusion.")
    action = Support(label="legacy_support", conclusion=conclusion, given=(premise,))

    assert _role_names(roles_for_claim(conclusion, (action,))) == ["conclusion"]
    assert _role_names(roles_for_claim(premise, (action,))) == ["premise"]


def test_roles_for_core_predict_action():
    with CollectedPackage("roles_predict") as pkg:
        basis = Claim("Hypothesis and setup.")
        prediction = predict("Falsifiable prediction.", given=basis, label="predict_result")

    assert _role_names(roles_for_claim(prediction, pkg)) == ["prediction"]
    assert _role_names(roles_for_claim(basis, pkg)) == ["prediction_basis"]


def test_roles_for_package_accepts_collected_package_with_more_verbs():
    with CollectedPackage("roles_more") as pkg:
        a = Claim("A.")
        b = Claim("B.")
        c = derive("C.", given=a, label="derive_c")
        observed = observe("Observed B.", given=b, label="observe_b")
        computed = compute(Claim, fn=lambda _c: Claim("Computed."), given=c, label="compute_c")
        assoc_helper = associate(
            a,
            b,
            p_a_given_b=0.7,
            p_b_given_a=0.3,
            label="assoc_ab",
        )
        decompose(c, parts=(a,), formula=ClaimAtom(a), label="split_c")

    index = roles_for_package(pkg)
    assert "conclusion" in _role_names(index[c])
    assert "observation" in _role_names(index[observed])
    assert "computed_result" in _role_names(index[computed])
    assert "association_helper" in _role_names(index[assoc_helper])
