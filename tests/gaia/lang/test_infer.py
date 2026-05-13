import inspect

import pytest

from gaia.lang import infer
from gaia.lang.runtime.action import Infer
from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.package import CollectedPackage


def test_infer_returns_evidence_and_keeps_likelihood_warrant_on_action():
    with CollectedPackage("v6_test") as pkg:
        h = Claim("Quantum theory is correct.", prior=0.5)
        e = Claim("Planck spectrum observed.", prior=0.95)
        result = infer(
            e,
            hypothesis=h,
            p_e_given_h=0.9,
            p_e_given_not_h=0.05,
            rationale="Strong evidence.",
        )

    action = pkg.actions[0]
    assert result is e
    assert action.evidence is e
    assert action.hypothesis is h
    assert action in e.from_actions
    assert action.helper is not None
    assert action.helper is not e
    assert action.helper.metadata.get("generated") is True
    assert action.helper.metadata.get("helper_kind") == "likelihood"
    assert action.helper.metadata.get("review") is True
    assert action.helper.metadata.get("relation") == {
        "type": "infer",
        "hypothesis": h,
        "evidence": e,
        "p_e_given_h": 0.9,
        "p_e_given_not_h": 0.05,
    }
    assert action.warrants == [action.helper]


def test_infer_rejects_inline_prior_keywords():
    h = Claim("H.")
    e = Claim("E.")

    with pytest.raises(TypeError, match="prior_hypothesis"):
        infer(
            e,
            hypothesis=h,
            p_e_given_h=0.9,
            prior_hypothesis=0.4,
        )

    with pytest.raises(TypeError, match="prior_evidence"):
        infer(
            e,
            hypothesis=h,
            p_e_given_h=0.9,
            prior_evidence=0.3,
        )


def test_infer_returns_evidence_claim_and_defaults_not_h_to_neutral():
    with CollectedPackage("v6_test") as pkg:
        h = Claim("H.")
        e = Claim("E.")
        result = infer(
            e,
            hypothesis=h,
            p_e_given_h=0.8,
            rationale="H supports E.",
        )

    action = pkg.actions[0]
    assert result is e
    assert action in e.from_actions
    assert action.evidence is e
    assert action.hypothesis is h
    assert action.p_e_given_h == 0.8
    assert action.p_e_given_not_h == 0.5
    assert action.helper is not None
    assert action.helper is not e
    assert action.warrants == [action.helper]
    assert action.helper.metadata["relation"]["p_e_given_not_h"] == 0.5


def test_infer_accepts_given_claim_as_gate_condition():
    with CollectedPackage("v6_test") as pkg:
        h = Claim("H.")
        e = Claim("E.")
        g = Claim("G.")
        result = infer(
            e,
            hypothesis=h,
            given=g,
            p_e_given_h=0.8,
            rationale="If G, H supports E.",
        )

    action = pkg.actions[0]
    assert result is e
    assert action.given == (g,)
    assert action.helper is not None
    assert action.helper.metadata["relation"]["given"] == (g,)


def test_infer_keyword_evidence_also_returns_evidence():
    h = Claim("Quantum theory is correct.", prior=0.5)
    e = Claim("Planck spectrum observed.", prior=0.95)
    result = infer(
        hypothesis=h,
        evidence=e,
        p_e_given_h=0.9,
        p_e_given_not_h=0.05,
        rationale="Strong evidence.",
    )
    action = result.from_actions[0]
    assert action.evidence is e
    assert action.helper is not None
    assert action.helper.metadata["helper_kind"] == "likelihood"
    assert (
        action.helper.content
        == "Planck spectrum observed. statistically supports Quantum theory is correct.."
    )


def test_infer_string_evidence_creates_and_returns_evidence():
    with CollectedPackage("v6_test") as pkg:
        h = Claim("Quantum theory is correct.", prior=0.5)
        result = infer(
            "Planck spectrum observed.",
            hypothesis=h,
            p_e_given_h=0.9,
            p_e_given_not_h=0.05,
            rationale="Strong evidence.",
        )

    assert isinstance(result, Claim)
    assert result.content == "Planck spectrum observed."
    action = pkg.actions[0]
    assert action.evidence.content == "Planck spectrum observed."
    assert action.hypothesis is h
    assert action in action.evidence.from_actions
    assert action.helper is not None
    assert action.helper.metadata["helper_kind"] == "likelihood"
    assert (
        action.helper.content
        == "Planck spectrum observed. statistically supports Quantum theory is correct.."
    )
    assert action.warrants == [action.helper]


def test_infer_rejects_ambiguous_extra_positional_v6_shape():
    h = Claim("H.")
    e = Claim("E.")
    with pytest.raises(TypeError):
        infer(h, e, 0.9, 0.1)


def test_infer_registers_action_and_warrant():
    with CollectedPackage("v6_test") as pkg:
        h = Claim("H.")
        e = Claim("E.")
        bg = Setting("Experiment conditions.")
        result = infer(
            e,
            hypothesis=h,
            background=[bg],
            p_e_given_h=0.8,
            p_e_given_not_h=0.2,
            rationale="Test.",
            label="bayes_update",
        )
    assert len(pkg.actions) == 1
    action = pkg.actions[0]
    assert result is e
    assert isinstance(action, Infer)
    assert action.label == "bayes_update"
    assert action.hypothesis is h
    assert action.evidence is e
    assert action.background == [bg]
    assert action.p_e_given_h == 0.8
    assert action.p_e_given_not_h == 0.2
    assert action in e.from_actions
    assert action.helper is not None
    assert action.warrants == [action.helper]


def test_infer_public_signature_is_evidence_first_without_legacy_list_shape():
    signature = inspect.signature(infer)
    first_parameter = next(iter(signature.parameters.values()))

    assert first_parameter.name == "evidence"
    annotation = str(first_parameter.annotation)
    assert "list" not in annotation
    assert "tuple" not in annotation
    assert "Knowledge" not in annotation


@pytest.mark.legacy_dsl
def test_infer_preserves_v5_positional_shape():
    a = Claim("A.")
    b = Claim("B.")
    c = Claim("C.")
    with pytest.warns(DeprecationWarning, match="infer\\(\\[premises\\], conclusion"):
        strategy = infer([a, b], c, reason="custom CPT")
    assert strategy.type == "infer"
    assert strategy.premises == [a, b]
    assert strategy.conclusion is c
