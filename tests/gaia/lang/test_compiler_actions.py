import pytest

import gaia.engine.bayes as bayes
from gaia.engine.lang import (
    Claim,
    Variable,
    associate,
    candidate_relation,
    compose,
    compute,
    contradict,
    depends_on,
    derive,
    equal,
    exclusive,
    infer,
    materialize,
    observe,
    parameter,
)
from gaia.engine.lang import (
    Probability as ProbabilityDomain,
)
from gaia.engine.lang.compiler import compile_package_artifact
from gaia.engine.lang.runtime.package import CollectedPackage


class IntClaim(Claim):
    """Value is {value}."""

    value: int


class SumResult(Claim):
    """Sum is {value}."""

    value: int


class Probability(Claim):
    """Probability is {value}."""

    value: float


def _knowledge_by_label(compiled):
    return {k.label: k for k in compiled.graph.knowledges if k.label}


def test_compile_derive_action_to_deduction_formal_strategy():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        c = derive("C.", given=(a, b), rationale="A and B imply C.", label="derive_c")
        c.label = "c"

    compiled = compile_package_artifact(pkg)
    assert compiled.action_label_map["github:v6_actions::action::derive_c"].startswith("lcs_")
    strategy = compiled.graph.strategies[0]
    assert strategy.type == "deduction"
    assert strategy.metadata["action_label"] == "github:v6_actions::action::derive_c"
    assert strategy.metadata["pattern"] == "derivation"
    assert strategy.steps[0].reasoning == "A and B imply C."

    implication_helpers = [
        k
        for k in compiled.graph.knowledges
        if (k.metadata or {}).get("helper_kind") == "implication_result"
    ]
    conjunction_helpers = [
        k
        for k in compiled.graph.knowledges
        if (k.metadata or {}).get("helper_kind") == "conjunction_result"
    ]
    assert implication_helpers[0].metadata["review"] is True
    assert conjunction_helpers[0].metadata["review"] is False


def test_compile_root_observe_action_to_reviewable_supported_by():
    with CollectedPackage("v6_actions") as pkg:
        data = observe("UV spectrum data.", rationale="Measured.", label="observe_uv")
        data.label = "uv"

    compiled = compile_package_artifact(pkg)
    assert compiled.graph.strategies == []
    assert compiled.action_label_map["github:v6_actions::action::observe_uv"] == (
        "github:v6_actions::uv"
    )

    uv = _knowledge_by_label(compiled)["uv"]
    assert uv.metadata["prior"] == 0.999
    support = uv.metadata["supported_by"][0]
    assert support["action_label"] == "github:v6_actions::action::observe_uv"
    assert support["pattern"] == "observation"
    assert support["rationale"] == "Measured."
    assert support["warrants"]


def test_compile_compute_action_to_deduction_with_compute_metadata():
    with CollectedPackage("v6_actions") as pkg:
        a = IntClaim(value=3)
        a.label = "a"
        b = IntClaim(value=4)
        b.label = "b"
        result = compute(
            SumResult,
            fn=lambda a, b: a.value + b.value,
            given=(a, b),
            rationale="Addition.",
            label="sum",
        )
        result.label = "sum_result"

    compiled = compile_package_artifact(pkg)
    strategy = compiled.graph.strategies[0]
    assert strategy.type == "deduction"
    assert strategy.metadata["pattern"] == "computation"
    assert strategy.metadata["action_label"] == "github:v6_actions::action::sum"
    assert "compute" in strategy.metadata
    assert strategy.metadata["compute"]["function_ref"]


def test_compile_equal_contradict_and_exclusive_actions_to_operators():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        bg = Claim("Same background information.")
        bg.label = "bg"
        eq = equal(a, b, background=[bg], rationale="Same.", label="same")
        eq.label = "same_helper"
        conflict = contradict(a, b, rationale="Conflict.", label="conflict")
        conflict.label = "conflict_helper"
        one = exclusive(a, b, rationale="Closed binary partition.", label="exclusive")
        one.label = "exclusive_helper"

    compiled = compile_package_artifact(pkg)
    by_operator = {op.operator: op for op in compiled.graph.operators}
    assert by_operator["equivalence"].metadata["action_label"] == "github:v6_actions::action::same"
    assert by_operator["equivalence"].metadata["background"] == ["github:v6_actions::bg"]
    assert by_operator["equivalence"].conclusion == "github:v6_actions::same_helper"
    assert by_operator["contradiction"].metadata["action_label"] == (
        "github:v6_actions::action::conflict"
    )
    assert by_operator["contradiction"].conclusion == "github:v6_actions::conflict_helper"
    assert by_operator["complement"].metadata["action_label"] == (
        "github:v6_actions::action::exclusive"
    )
    assert by_operator["complement"].conclusion == "github:v6_actions::exclusive_helper"


def test_compile_infer_action_to_strategy_cpt():
    with CollectedPackage("v6_actions") as pkg:
        h = Claim("H.")
        h.label = "h"
        e = Claim("E.")
        e.label = "e"
        bg = Claim("Measurement reliable.")
        bg.label = "reliable"
        result = infer(
            e,
            hypothesis=h,
            background=[bg],
            p_e_given_h=0.8,
            p_e_given_not_h=0.2,
            rationale="Bayes.",
            label="bayes_update",
        )
        assert result is e
        helper = pkg.actions[0].helper
        assert helper is not None
        helper.label = "likelihood_helper"

    compiled = compile_package_artifact(pkg)
    strategy = compiled.graph.strategies[0]
    assert strategy.type == "infer"
    assert strategy.premises == ["github:v6_actions::h"]
    assert strategy.conclusion == "github:v6_actions::e"
    assert strategy.background == ["github:v6_actions::reliable"]
    assert strategy.metadata["action_label"] == "github:v6_actions::action::bayes_update"
    assert strategy.steps[0].reasoning == "Bayes."
    assert strategy.conditional_probabilities == [0.2, 0.8]
    assert not hasattr(compiled, "strategy_param_records")

    stat_support = _knowledge_by_label(compiled)["likelihood_helper"]
    assert stat_support.metadata["helper_kind"] == "likelihood"
    assert stat_support.metadata["review"] is True
    assert stat_support.metadata["relation"] == {
        "type": "infer",
        "hypothesis": "github:v6_actions::h",
        "evidence": "github:v6_actions::e",
        "p_e_given_h": 0.8,
        "p_e_given_not_h": 0.2,
    }


def test_compile_infer_action_with_given_switch_cpt():
    with CollectedPackage("v6_actions") as pkg:
        h = Claim("H.")
        h.label = "h"
        e = Claim("E.")
        e.label = "e"
        gate = Claim("Gate.")
        gate.label = "g"
        result = infer(
            e,
            hypothesis=h,
            given=gate,
            p_e_given_h=0.8,
            rationale="Bayes.",
            label="bayes_update",
        )
        assert result is e
        helper = pkg.actions[0].helper
        assert helper is not None
        helper.label = "likelihood_helper"

    compiled = compile_package_artifact(pkg)
    strategy = compiled.graph.strategies[0]
    assert strategy.type == "infer"
    assert strategy.premises == ["github:v6_actions::h", "github:v6_actions::g"]
    assert strategy.conclusion == "github:v6_actions::e"
    assert strategy.conditional_probabilities == [0.5, 0.5, 0.5, 0.8]
    assert strategy.metadata["given"] == ["github:v6_actions::g"]

    stat_support = _knowledge_by_label(compiled)["likelihood_helper"]
    assert stat_support.metadata["relation"]["given"] == ["github:v6_actions::g"]
    assert stat_support.metadata["relation"]["p_e_given_not_h"] == 0.5


def test_compile_infer_lifts_probability_claims_to_cpt_values():
    with CollectedPackage("v6_actions") as pkg:
        h = Claim("H.")
        h.label = "h"
        e = Claim("E.")
        e.label = "e"
        p_h = Probability(value=0.8)
        p_h.label = "p_e_given_h"
        p_not_h = Probability(value=0.2)
        p_not_h.label = "p_e_given_not_h"
        result = infer(
            e,
            hypothesis=h,
            p_e_given_h=p_h,
            p_e_given_not_h=p_not_h,
            rationale="Lift computed probabilities.",
            label="bayes_update",
        )
        assert result is e
        helper = pkg.actions[0].helper
        assert helper is not None
        helper.label = "likelihood_helper"

    compiled = compile_package_artifact(pkg)
    strategy = compiled.graph.strategies[0]
    assert strategy.type == "infer"
    assert strategy.conditional_probabilities == [0.2, 0.8]
    by_label = _knowledge_by_label(compiled)
    assert "p_e_given_h" in by_label
    assert "p_e_given_not_h" in by_label
    helper_metadata = by_label["likelihood_helper"].metadata
    assert helper_metadata["relation"]["p_e_given_h"] == "github:v6_actions::p_e_given_h"
    assert helper_metadata["relation"]["p_e_given_not_h"] == ("github:v6_actions::p_e_given_not_h")


def test_compile_associate_action_to_association_strategy():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.", prior=0.25)
        a.label = "a"
        b = Claim("B.", prior=1 / 15)
        b.label = "b"
        helper = associate(
            a,
            b,
            p_a_given_b=0.75,
            p_b_given_a=0.20,
            pattern=None,
            rationale="Observed cohort association.",
            label="assoc_ab",
        )
        helper.label = "association_helper"
        assert helper.metadata["relation"] == {
            "type": "associate",
            "a": a,
            "b": b,
            "p_a_given_b": 0.75,
            "p_b_given_a": 0.20,
            "pattern": None,
        }

    compiled = compile_package_artifact(pkg)
    strategy = compiled.graph.strategies[0]
    assert strategy.type == "associate"
    assert strategy.premises == ["github:v6_actions::a", "github:v6_actions::b"]
    assert strategy.conclusion == "github:v6_actions::association_helper"
    assert strategy.p_a_given_b == 0.75
    assert strategy.p_b_given_a == 0.20
    assert strategy.metadata["action_label"] == "github:v6_actions::action::assoc_ab"
    assert strategy.metadata["pattern"] == "association"

    assoc = _knowledge_by_label(compiled)["association_helper"]
    assert assoc.metadata["helper_kind"] == "association"
    assert assoc.metadata["review"] is True
    assert assoc.metadata["relation"] == {
        "type": "associate",
        "a": "github:v6_actions::a",
        "b": "github:v6_actions::b",
        "p_a_given_b": 0.75,
        "p_b_given_a": 0.20,
        "pattern": None,
    }


def test_associate_pattern_validation():
    a = Claim("A.")
    b = Claim("B.")

    helper = associate(a, b, p_a_given_b=0.75, p_b_given_a=0.8, pattern="equal")
    assert helper.from_actions[0].pattern == "equal"
    assert helper.metadata["relation"]["pattern"] == "equal"

    associate(a, b, p_a_given_b=0.2, p_b_given_a=0.3, pattern="contradict")
    associate(a, b, p_a_given_b=0.2, p_b_given_a=0.3, pattern="exclusive")

    with pytest.raises(ValueError, match="pattern='equal'"):
        associate(a, b, p_a_given_b=0.2, p_b_given_a=0.8, pattern="equal")

    with pytest.raises(ValueError, match="pattern='exclusive'"):
        associate(a, b, p_a_given_b=0.7, p_b_given_a=0.2, pattern="exclusive")


def test_associate_rejects_inline_prior_keywords():
    a = Claim("A.", prior=0.25)
    b = Claim("B.", prior=1 / 15)

    with pytest.raises(TypeError, match="prior_a"):
        associate(
            a,
            b,
            p_a_given_b=0.75,
            p_b_given_a=0.20,
            prior_a=0.25,
        )

    with pytest.raises(TypeError, match="prior_b"):
        associate(
            a,
            b,
            p_a_given_b=0.75,
            p_b_given_a=0.20,
            prior_b=1 / 15,
        )


def test_compile_depends_on_action_to_formalization_manifest_only():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        c = Claim("C.")
        c.label = "c"
        depends_on(
            c,
            given=(a, b),
            rationale="C currently relies on A and B.",
            label="c_depends_on_a_b",
        )
        pkg._exported_labels = {"c"}

    compiled = compile_package_artifact(pkg)

    assert compiled.graph.strategies == []
    assert compiled.graph.operators == []
    assert "github:v6_actions::c" in {k.id for k in compiled.graph.knowledges}

    manifest = compiled.formalization_manifest
    assert manifest["version"] == 1
    assert manifest["dependencies"] == [
        {
            "id": "github:v6_actions::scaffold::c_depends_on_a_b",
            "kind": "depends_on",
            "label": "c_depends_on_a_b",
            "conclusion": "github:v6_actions::c",
            "given": ["github:v6_actions::a", "github:v6_actions::b"],
            "rationale": "C currently relies on A and B.",
            "status": "unformalized",
            "metadata": {},
        }
    ]


def test_compile_candidate_relation_to_formalization_manifest_only():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        c = Claim("C.")
        c.label = "c"
        setting = Claim("The comparison uses the same observable definition.")
        setting.label = "same_observable"
        action = candidate_relation(
            claims=[a, b, c],
            pattern="equal",
            background=[setting],
            rationale="A and B may be the same scientific claim.",
            label="maybe_same_claim",
            metadata={"source": "retrieval"},
        )

    compiled = compile_package_artifact(pkg)

    assert action.claims == (a, b, c)
    assert action.pattern == "equal"
    assert compiled.graph.strategies == []
    assert compiled.graph.operators == []
    assert {k.id for k in compiled.graph.knowledges} == {
        "github:v6_actions::a",
        "github:v6_actions::b",
        "github:v6_actions::c",
        "github:v6_actions::same_observable",
    }

    manifest = compiled.formalization_manifest
    assert manifest["dependencies"] == [
        {
            "id": "github:v6_actions::scaffold::maybe_same_claim",
            "kind": "candidate_relation",
            "label": "maybe_same_claim",
            "pattern": "equal",
            "claims": [
                "github:v6_actions::a",
                "github:v6_actions::b",
                "github:v6_actions::c",
            ],
            "rationale": "A and B may be the same scientific claim.",
            "status": "hypothesis",
            "metadata": {"source": "retrieval"},
            "background": ["github:v6_actions::same_observable"],
        }
    ]


def test_candidate_relation_accepts_open_and_exclusive_multiclaim_patterns():
    a = Claim("A.")
    b = Claim("B.")
    c = Claim("C.")

    assert candidate_relation(claims=[a, b]).pattern is None
    assert candidate_relation(claims=[a, b, c], pattern="exclusive").claims == (a, b, c)

    with pytest.raises(ValueError, match="exactly two"):
        candidate_relation(claims=[a, b, c], pattern="contradict")


def test_tension_is_not_public_dsl():
    import gaia.engine.lang as lang
    import gaia.engine.lang.dsl as dsl

    assert "tension" not in dir(lang)
    assert "tension" not in lang.__all__
    assert "tension" not in dsl.__all__


def test_materialize_records_formalization_link_by_label():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        scaffold = candidate_relation(claims=[a, b], pattern="equal", label="maybe_same")
        equal(a, b, label="same_claim")
        materialize(
            scaffold,
            by="same_claim",
            rationale="The equality relation formalizes the candidate relation.",
            label="maybe_same_done",
        )

    compiled = compile_package_artifact(pkg)

    assert compiled.formalization_manifest["dependencies"] == [
        {
            "id": "github:v6_actions::scaffold::maybe_same",
            "kind": "candidate_relation",
            "label": "maybe_same",
            "pattern": "equal",
            "claims": ["github:v6_actions::a", "github:v6_actions::b"],
            "rationale": "",
            "status": "hypothesis",
            "metadata": {},
        }
    ]
    assert compiled.formalization_manifest["materializations"] == [
        {
            "id": "github:v6_actions::materialization::maybe_same_done",
            "kind": "materialization",
            "label": "maybe_same_done",
            "scaffold": "github:v6_actions::scaffold::maybe_same",
            "by": ["github:v6_actions::action::same_claim"],
            "rationale": "The equality relation formalizes the candidate relation.",
            "metadata": {},
        }
    ]


def test_materialize_records_multiple_formalizers():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        c = Claim("C.")
        c.label = "c"
        scaffold = candidate_relation(claims=[a, b, c], pattern="equal", label="maybe_same")
        same_ab = equal(a, b, label="same_ab")
        same_bc = equal(b, c, label="same_bc")
        materialize(scaffold, by=[same_ab, same_bc], label="maybe_same_done")

    compiled = compile_package_artifact(pkg)

    assert compiled.formalization_manifest["materializations"] == [
        {
            "id": "github:v6_actions::materialization::maybe_same_done",
            "kind": "materialization",
            "label": "maybe_same_done",
            "scaffold": "github:v6_actions::scaffold::maybe_same",
            "by": [
                "github:v6_actions::action::same_ab",
                "github:v6_actions::action::same_bc",
            ],
            "rationale": "",
            "metadata": {},
        }
    ]


def test_materialize_rejects_scaffold_to_scaffold_links():
    with CollectedPackage("v6_actions"):
        a = Claim("A.")
        b = Claim("B.")
        scaffold = candidate_relation(claims=[a, b])
        other_scaffold = depends_on(a, given=[b])

        with pytest.raises(TypeError, match="Scaffold"):
            materialize(scaffold, by=other_scaffold)


def test_materialize_rejects_scaffold_labels():
    with CollectedPackage("v6_actions"):
        a = Claim("A.")
        b = Claim("B.")
        scaffold = candidate_relation(claims=[a, b], label="open_relation")
        depends_on(a, given=[b], label="other_scaffold")

        with pytest.raises(TypeError, match="Scaffold"):
            materialize(scaffold, by="other_scaffold")


def test_materialize_rejects_cross_package_graph_records():
    with CollectedPackage("v6_actions") as source_pkg:
        a = Claim("A.")
        b = Claim("B.")
        scaffold = candidate_relation(claims=[a, b], pattern="equal")

    with CollectedPackage("other_pkg"):
        helper = equal(a, b, label="same_ab")

    assert scaffold in source_pkg.actions
    with pytest.raises(ValueError, match="scaffold package"):
        materialize(scaffold, by=helper)


def test_materialize_rejects_unrelated_reasoning_record():
    with CollectedPackage("v6_actions"):
        a = Claim("A.")
        b = Claim("B.")
        c = Claim("C.")
        d = Claim("D.")
        scaffold = candidate_relation(claims=[a, b])
        unrelated = equal(c, d, label="same_cd")

        with pytest.raises(ValueError, match="core claims"):
            materialize(scaffold, by=unrelated)


def test_materialize_rejects_ambiguous_producer_claim():
    with CollectedPackage("v6_actions"):
        a = Claim("A.")
        b = Claim("B.")
        c = Claim("C.")
        scaffold = candidate_relation(claims=[a, b], pattern="equal")
        helper = equal(a, b, label="same_ab")
        helper.from_actions.append(equal(a, c, label="same_ac").from_actions[0])

        with pytest.raises(ValueError, match="ambiguous"):
            materialize(scaffold, by=helper)


def test_materialize_rejects_known_relation_pattern_conflicts():
    with CollectedPackage("v6_actions"):
        a = Claim("A.")
        b = Claim("B.")
        scaffold = candidate_relation(claims=[a, b], pattern="equal")
        helper = contradict(a, b, label="not_both")

        with pytest.raises(ValueError, match="pattern"):
            materialize(scaffold, by=helper)


def test_support_action_can_share_label_with_own_conclusion():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        c = derive("C.", given=a, rationale="A implies C.", label="derive_c")
        c.label = "derive_c"

    compiled = compile_package_artifact(pkg)

    assert _knowledge_by_label(compiled)["derive_c"].id == "github:v6_actions::derive_c"


def test_unrelated_knowledge_action_label_collision_still_raises():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        unrelated = Claim("Unrelated claim.")
        unrelated.label = "derive_c"
        c = derive("C.", given=a, rationale="A implies C.", label="derive_c")
        c.label = "c"

    with pytest.raises(ValueError, match="label collision"):
        compile_package_artifact(pkg)


def test_duplicate_strategy_action_label_raises():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        c1 = derive("C1.", given=a, rationale="A implies C1.", label="same_step")
        c1.label = "c1"
        c2 = derive("C2.", given=a, rationale="A implies C2.", label="same_step")
        c2.label = "c2"

    with pytest.raises(ValueError, match="duplicate action label 'same_step'"):
        compile_package_artifact(pkg)


def test_duplicate_operator_action_label_raises():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        c = Claim("C.")
        c.label = "c"
        first = contradict(a, b, rationale="A conflicts with B.", label="same_relation")
        first.label = "first_conflict"
        second = contradict(a, c, rationale="A conflicts with C.", label="same_relation")
        second.label = "second_conflict"

    with pytest.raises(ValueError, match="duplicate action label 'same_relation'"):
        compile_package_artifact(pkg)


def test_duplicate_compose_action_label_raises():
    @compose(name="test:workflow:first", version="1.0", label="same_workflow")
    def first_workflow(seed: Claim) -> Claim:
        return derive("C1.", given=seed, rationale="First workflow.", label="first_child")

    @compose(name="test:workflow:second", version="1.0", label="same_workflow")
    def second_workflow(seed: Claim) -> Claim:
        return derive("C2.", given=seed, rationale="Second workflow.", label="second_child")

    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        c1 = first_workflow(a)
        c1.label = "c1"
        c2 = second_workflow(a)
        c2.label = "c2"

    with pytest.raises(ValueError, match="duplicate action label 'same_workflow'"):
        compile_package_artifact(pkg)


def test_duplicate_bayes_and_core_action_label_raises():
    from gaia.engine.lang import Beta

    with CollectedPackage("v6_actions") as pkg:
        theta = Variable(symbol="theta", domain=ProbabilityDomain)
        hypothesis = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h")
        bayes.model(
            hypothesis,
            observable=theta,
            distribution=Beta("theta prior", alpha=1, beta=1),
            label="same_action",
        )
        conclusion = derive("C.", given=hypothesis, rationale="H implies C.", label="same_action")
        conclusion.label = "c"

    with pytest.raises(ValueError, match="duplicate action label 'same_action'"):
        compile_package_artifact(pkg)
