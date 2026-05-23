"""observe() continuous-quantity polymorphism tests.

When the target of ``observe()`` is a :class:`Distribution`, the call records
a measurement event as a Claim with metadata linking back to the underlying
distribution. Existing discrete claim observation (``observe(my_claim)``)
continues to work unchanged.
"""

from __future__ import annotations

import pytest

from gaia.engine.ir.parameterization import CROMWELL_EPS
from gaia.engine.lang import Domain, Nat, Normal, Probability, Variable, claim, observe
from gaia.unit import q


def test_observe_distribution_returns_pinned_observation_claim():
    T_c = Normal("T_c", mu=200, sigma=50)
    obs = observe(T_c, value=203, error=5)
    # Returned Claim is pinned to ~1 (the measurement event happened)
    assert obs.prior == 1.0 - CROMWELL_EPS
    assert obs.content.startswith("Observed T_c")
    assert "203" in obs.content
    assert "+/- 5" in obs.content


def test_observation_metadata_links_back_to_distribution():
    """Distribution-target observation writes the unified schema.

    Same shape as ``observe(Variable, value=, error=)`` so the Bayes
    ``compare()`` lowering can read both paths through the same reader.
    """
    T_c = Normal("T_c", mu=200, sigma=50)
    obs = observe(T_c, value=203, error=5)
    payload = obs.metadata["observation"]
    assert payload["target"] is T_c
    assert payload["value"] == 203.0
    # Scalar ``error=5`` is sugared into an anonymous Normal(0, 5) Distribution.
    assert payload["noise"].kind == "normal"
    assert payload["noise"].params["sigma"] == 5.0
    assert payload["kind"] == "observation"


def test_observe_distribution_without_error_is_noise_free():
    T_c = Normal("T_c", mu=200, sigma=50)
    obs = observe(T_c, value=203)
    payload = obs.metadata["observation"]
    assert payload["noise"] is None


def test_observe_distribution_accepts_distribution_as_noise_model():
    T_c = Normal("T_c", mu=200, sigma=50)
    noise = Normal("measurement noise", mu=0, sigma=5)
    obs = observe(T_c, value=203, error=noise)
    payload = obs.metadata["observation"]
    assert payload["noise"] is noise


def test_observe_distribution_rejects_noise_distribution_with_incompatible_unit():
    T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
    noise = Normal("length noise", mu=q(0, "m"), sigma=q(1, "m"))
    with pytest.raises(ValueError, match="noise distribution unit"):
        observe(T_c, value=q(203, "K"), error=noise)


def test_observe_distribution_rejects_unitless_noise_for_unit_typed_target():
    T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
    noise = Normal("unitless noise", mu=0, sigma=5)
    with pytest.raises(TypeError, match="noise distribution must carry unit"):
        observe(T_c, value=q(203, "K"), error=noise)


def test_observe_distribution_records_source_refs_with_deprecation_warning():
    T_c = Normal("T_c", mu=200, sigma=50)
    with pytest.warns(DeprecationWarning, match="source_refs"):
        obs = observe(T_c, value=203, error=5, source_refs=["Drozdov 2015"])
    assert obs.metadata.get("source_refs") == ["Drozdov 2015"]


def test_observe_distribution_rejects_missing_value():
    T_c = Normal("T_c", mu=200, sigma=50)
    with pytest.raises(TypeError, match="requires `value="):
        observe(T_c)


def test_observe_distribution_rejects_non_numeric_value():
    T_c = Normal("T_c", mu=200, sigma=50)
    with pytest.raises(TypeError, match="must be a numeric scalar"):
        observe(T_c, value="not a number")  # type: ignore[arg-type]


def test_observe_distribution_rejects_non_positive_error():
    T_c = Normal("T_c", mu=200, sigma=50)
    with pytest.raises(ValueError, match="sigma > 0"):
        observe(T_c, value=203, error=-1)
    with pytest.raises(ValueError, match="sigma > 0"):
        observe(T_c, value=203, error=0)


def test_observe_distribution_rejects_given_clause():
    T_c = Normal("T_c", mu=200, sigma=50)
    other = claim("conditioning premise")
    with pytest.raises(TypeError, match="not supported"):
        observe(T_c, value=203, given=[other])


def test_observe_variable_rejects_value_outside_primitive_domain():
    k = Variable(symbol="k", domain=Nat)
    with pytest.raises(ValueError, match="domain Nat"):
        observe(k, value=1.5)

    p = Variable(symbol="p", domain=Probability)
    with pytest.raises(ValueError, match="domain Probability"):
        observe(p, value=1.5)


def test_observe_variable_rejects_value_outside_custom_domain():
    states = Domain("allowed count states", members=[1, 2], label="AllowedCounts")
    x = Variable(symbol="x", domain=states)
    with pytest.raises(ValueError, match="domain members"):
        observe(x, value=3)


def test_observe_discrete_claim_unchanged():
    """Existing observe(claim) path is unchanged — pins prior to ~1."""
    c = claim("Test claim")
    result = observe(c)
    assert result is c
    assert c.prior == 1.0 - CROMWELL_EPS


def test_observe_discrete_claim_with_value_rejected():
    """value=/error= are continuous-only kwargs — error on discrete claim."""
    c = claim("Test claim")
    with pytest.raises(TypeError, match="only applies to Distribution"):
        observe(c, value=203)
