from gaia.lang import (
    Claim,
    associate,
    compute,
    contradict,
    depends_on,
    derive,
    equal,
    exclusive,
    infer,
    observe,
)
from gaia.lang.compiler import compile_package_artifact
from gaia.lang.runtime.package import CollectedPackage


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


def test_compile_root_observe_action_to_reviewable_grounding():
    with CollectedPackage("v6_actions") as pkg:
        data = observe("UV spectrum data.", rationale="Measured.", label="observe_uv")
        data.label = "uv"

    compiled = compile_package_artifact(pkg)
    assert compiled.graph.strategies == []
    assert compiled.action_label_map["github:v6_actions::action::observe_uv"] == (
        "github:v6_actions::uv"
    )

    uv = _knowledge_by_label(compiled)["uv"]
    assert uv.metadata["grounding"]["kind"] == "source_fact"
    assert uv.metadata["grounding"]["action_label"] == "github:v6_actions::action::observe_uv"


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
            prior_hypothesis=0.4,
            prior_evidence=0.3,
            rationale="Bayes.",
            label="bayes_update",
        )
        assert result is pkg.actions[0].helper
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
    assert strategy.prior_hypothesis == 0.4
    assert strategy.prior_evidence == 0.3
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
        "prior_hypothesis": 0.4,
        "prior_evidence": 0.3,
    }


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
        helper = infer(
            e,
            hypothesis=h,
            p_e_given_h=p_h,
            p_e_given_not_h=p_not_h,
            rationale="Lift computed probabilities.",
            label="bayes_update",
        )
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
            prior_a=0.25,
            prior_b=1 / 15,
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
            "prior_a": 0.25,
            "prior_b": 1 / 15,
        }

    compiled = compile_package_artifact(pkg)
    strategy = compiled.graph.strategies[0]
    assert strategy.type == "associate"
    assert strategy.premises == ["github:v6_actions::a", "github:v6_actions::b"]
    assert strategy.conclusion == "github:v6_actions::association_helper"
    assert strategy.p_a_given_b == 0.75
    assert strategy.p_b_given_a == 0.20
    assert strategy.prior_a == 0.25
    assert strategy.prior_b == 1 / 15
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
        "prior_a": 0.25,
        "prior_b": 1 / 15,
    }


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
