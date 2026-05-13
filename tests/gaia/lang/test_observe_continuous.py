"""observe() continuous-quantity polymorphism tests.

When the target of ``observe()`` is a :class:`Distribution`, the call records
a measurement event as a Claim with metadata linking back to the underlying
distribution. Existing discrete claim observation (``observe(my_claim)``)
continues to work unchanged.
"""

from __future__ import annotations

import pytest

from gaia.ir.parameterization import CROMWELL_EPS
from gaia.lang import Normal, claim, observe


def test_observe_distribution_returns_pinned_observation_claim():
    T_c = Normal("T_c", mu=200, sigma=50)
    obs = observe(T_c, value=203, error=5)
    # Returned Claim is pinned to ~1 (the measurement event happened)
    assert obs.prior == 1.0 - CROMWELL_EPS
    assert obs.content.startswith("Observed T_c")
    assert "203" in obs.content
    assert "+/- 5" in obs.content


def test_observation_metadata_links_back_to_distribution():
    T_c = Normal("T_c", mu=200, sigma=50)
    obs = observe(T_c, value=203, error=5)
    payload = obs.metadata["observation"]
    assert payload["target_distribution"] is T_c
    assert payload["value"] == 203.0
    assert payload["error"] == 5.0
    assert payload["kind"] == "continuous_observation"


def test_observe_distribution_without_error_is_noise_free():
    T_c = Normal("T_c", mu=200, sigma=50)
    obs = observe(T_c, value=203)
    payload = obs.metadata["observation"]
    assert payload["error"] is None


def test_observe_distribution_accepts_distribution_as_noise_model():
    T_c = Normal("T_c", mu=200, sigma=50)
    noise = Normal("measurement noise", mu=0, sigma=5)
    obs = observe(T_c, value=203, error=noise)
    payload = obs.metadata["observation"]
    assert payload["error"] is noise


def test_observe_distribution_records_source_refs():
    T_c = Normal("T_c", mu=200, sigma=50)
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
