import pytest

from gaia.lang import evidence
from gaia.lang.runtime.action import Evidence
from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.package import CollectedPackage
from gaia.stats import Binomial, Normal


def test_evidence_returns_data_and_keeps_model_warrant_on_action():
    with CollectedPackage("evidence_test") as pkg:
        h = Claim("The coin has success probability 0.8.", prior=0.5)
        d = Claim("Eight successes were observed in ten trials.", prior=0.95)
        gate = Claim("Trials are independent.", prior=0.9)
        result = evidence(
            d,
            hypothesis=h,
            model=Binomial(n=10, p=0.8),
            null_model=Binomial(n=10, p=0.5),
            observed=8,
            given=gate,
            rationale="Under H, the observed count is Binomial(n=10, p=0.8).",
            label="count_evidence",
        )

    action = pkg.actions[0]
    assert result is d
    assert isinstance(action, Evidence)
    assert action.data is d
    assert action.hypothesis is h
    assert action.given == (gate,)
    assert action.model["kind"] == "binomial"
    assert action.model["params"] == {"n": 10, "p": 0.8}
    assert action.null_model["kind"] == "binomial"
    assert action.null_model["params"] == {"n": 10, "p": 0.5}
    assert action.p_data_given_h == pytest.approx(0.301989888)
    assert action.p_data_given_not_h == pytest.approx(0.0439453125)
    assert action in d.supports
    assert action.helper is not None
    assert action.helper is not d
    assert "Binomial(n=10, p=0.8)" in action.helper.content
    assert "Binomial(n=10, p=0.5)" in action.helper.content
    assert action.warrants == [action.helper]
    assert action.helper.metadata["helper_kind"] == "evidence"
    assert action.helper.metadata["review"] is True
    assert action.helper.metadata["relation"]["type"] == "evidence"
    assert action.helper.metadata["relation"]["hypothesis"] is h
    assert action.helper.metadata["relation"]["data"] is d
    assert action.helper.metadata["relation"]["given"] == (gate,)
    assert action.helper.metadata["relation"]["model"]["kind"] == "binomial"
    assert action.helper.metadata["relation"]["null_model"]["kind"] == "binomial"
    assert action.helper.metadata["relation"]["observed"] == 8
    assert action.helper.metadata["relation"]["p_data_given_h"] == pytest.approx(0.301989888)
    assert action.helper.metadata["relation"]["p_data_given_not_h"] == pytest.approx(0.0439453125)


def test_evidence_requires_null_model():
    with CollectedPackage("evidence_test"):
        h = Claim("H.")
        d = Claim("D.")
        with pytest.raises(TypeError, match="null_model"):
            evidence(d, hypothesis=h, model=Binomial(n=2, p=0.5), observed=1)


def test_evidence_accepts_string_data_when_observed_is_explicit():
    with CollectedPackage("evidence_test"):
        h = Claim("H.")
        result = evidence(
            "Eight successes were observed in ten trials.",
            hypothesis=h,
            model=Binomial(n=10, p=0.8),
            null_model=Binomial(n=10, p=0.5),
            observed=8,
        )

    assert isinstance(result, Claim)
    assert result.content == "Eight successes were observed in ten trials."


def test_evidence_rejects_kind_mismatch():
    h = Claim("H.")
    d = Claim("D.")
    with pytest.raises(ValueError, match="same kind"):
        evidence(
            d,
            hypothesis=h,
            model=Binomial(n=10, p=0.8),
            null_model=Normal(mu=0, sigma=1),
            observed=8,
        )


def test_evidence_rejects_binomial_n_mismatch():
    h = Claim("H.")
    d = Claim("D.")
    with pytest.raises(ValueError, match="must share n"):
        evidence(
            d,
            hypothesis=h,
            model=Binomial(n=10, p=0.8),
            null_model=Binomial(n=20, p=0.5),
            observed=8,
        )


def test_evidence_requires_binomial_model_for_initial_release():
    h = Claim("H.")
    d = Claim("D.")
    with pytest.raises(TypeError, match="currently supports Binomial"):
        evidence(
            d, hypothesis=h, model={"kind": "normal"}, null_model=Binomial(n=2, p=0.5), observed=1
        )


def test_evidence_requires_binomial_null_model_for_initial_release():
    h = Claim("H.")
    d = Claim("D.")
    with pytest.raises(TypeError, match="currently supports Binomial"):
        evidence(
            d, hypothesis=h, model=Binomial(n=2, p=0.5), null_model={"kind": "normal"}, observed=1
        )


def test_evidence_rejects_typed_non_binomial_model_for_initial_release():
    h = Claim("H.")
    d = Claim("D.")
    with pytest.raises(
        TypeError, match="currently supports Binomial models only; got kind='normal'"
    ):
        evidence(
            d,
            hypothesis=h,
            model=Normal(mu=0, sigma=1),
            null_model=Normal(mu=1, sigma=1),
            observed=0,
        )
