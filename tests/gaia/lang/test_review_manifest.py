from gaia.lang import Claim, contradict, derive, equal, exclusive, infer, observe
from gaia.lang.compiler import compile_package_artifact
from gaia.lang.review.manifest import generate_review_manifest
from gaia.lang.review.templates import generate_audit_question
from gaia.lang.runtime.package import CollectedPackage


def test_audit_question_for_derive():
    question = generate_audit_question("derive", conclusion_label="quantum_hyp")
    assert "[@quantum_hyp]" in question
    assert "premises" in question.lower()


def test_audit_question_for_observe():
    question = generate_audit_question("observe", conclusion_label="uv_data")
    assert "[@uv_data]" in question
    assert "observation" in question.lower() or "reliable" in question.lower()


def test_audit_question_for_infer():
    question = generate_audit_question(
        "infer", hypothesis_label="quantum_hyp", evidence_label="spectrum"
    )
    assert "[@quantum_hyp]" in question
    assert "[@spectrum]" in question
    assert "predict" in question.lower()
    assert "association" not in question.lower()


def test_audit_question_for_equal():
    question = generate_audit_question("equal", a_label="pred", b_label="obs")
    assert "[@pred]" in question
    assert "[@obs]" in question


def test_audit_question_for_exclusive():
    question = generate_audit_question("exclusive", a_label="case_a", b_label="case_b")
    assert "[@case_a]" in question
    assert "[@case_b]" in question
    assert "exactly one" in question.lower()


def test_generate_review_manifest_for_v6_actions():
    with CollectedPackage("review_pkg") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        c = derive("C.", given=(a, b), rationale="A and B imply C.", label="derive_c")
        c.label = "c"
        data = observe("Observation.", rationale="Measured.", label="observe_data")
        data.label = "data"
        eq = equal(c, data, rationale="Same.", label="same")
        eq.label = "same_helper"
        conflict = contradict(a, data, rationale="Conflict.", label="conflict")
        conflict.label = "conflict_helper"
        one = exclusive(a, b, rationale="Closed binary partition.", label="exclusive")
        one.label = "exclusive_helper"
        infer(
            data,
            hypothesis=c,
            p_e_given_h=0.8,
            p_e_given_not_h=0.2,
            rationale="Bayes.",
            label="bayes_update",
        )

    compiled = compile_package_artifact(pkg)
    manifest = generate_review_manifest(compiled)
    assert len(manifest.reviews) == 6
    assert {review.status for review in manifest.reviews} == {"unreviewed"}

    by_action = {review.action_label: review for review in manifest.reviews}
    assert by_action["github:review_pkg::action::derive_c"].target_kind == "strategy"
    assert "[@c]" in by_action["github:review_pkg::action::derive_c"].audit_question
    assert by_action["github:review_pkg::action::observe_data"].target_kind == "knowledge"
    assert by_action["github:review_pkg::action::observe_data"].target_id == (
        "github:review_pkg::data"
    )
    assert by_action["github:review_pkg::action::same"].target_kind == "operator"
    assert by_action["github:review_pkg::action::exclusive"].target_kind == "operator"
    assert "[@a]" in by_action["github:review_pkg::action::conflict"].audit_question
    assert "exactly one" in by_action["github:review_pkg::action::exclusive"].audit_question.lower()
    assert "[@data]" in by_action["github:review_pkg::action::bayes_update"].audit_question


def test_compiled_package_carries_review_manifest_outside_graph_json():
    with CollectedPackage("review_pkg") as pkg:
        a = Claim("A.")
        a.label = "a"
        c = derive("C.", given=a, rationale="A implies C.", label="derive_c")
        c.label = "c"

    compiled = compile_package_artifact(pkg)
    assert compiled.review is not None
    assert len(compiled.review.reviews) == 1
    assert "review" not in compiled.to_json()
