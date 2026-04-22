import pytest

from gaia.lang import infer
from gaia.lang.runtime.action import Infer
from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.package import CollectedPackage


def test_infer_returns_positional_evidence_and_keeps_helper_on_action():
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

    assert result is e
    action = pkg.actions[0]
    assert action.evidence is e
    assert action.hypothesis is h
    assert action in e.supports
    assert action.helper is not None
    assert action.helper is not e
    assert action.helper.metadata.get("generated") is True
    assert action.helper.metadata.get("helper_kind") == "statistical_support"
    assert action.helper.metadata.get("review") is True
    assert action.warrants == [action.helper]


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
    assert result is e


def test_infer_string_evidence_creates_and_returns_evidence_claim():
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
    assert action.evidence is result
    assert action.hypothesis is h
    assert action in result.supports
    assert action.helper is not None
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
    assert result is e
    assert len(pkg.actions) == 1
    action = pkg.actions[0]
    assert isinstance(action, Infer)
    assert action.label == "bayes_update"
    assert action.hypothesis is h
    assert action.evidence is e
    assert action.background == [bg]
    assert action.p_e_given_h == 0.8
    assert action.p_e_given_not_h == 0.2
    assert action in e.supports
    assert action.helper is not None
    assert action.warrants == [action.helper]


def test_infer_preserves_v5_positional_shape():
    a = Claim("A.")
    b = Claim("B.")
    c = Claim("C.")
    strategy = infer([a, b], c, reason="custom CPT")
    assert strategy.type == "infer"
    assert strategy.premises == [a, b]
    assert strategy.conclusion is c
