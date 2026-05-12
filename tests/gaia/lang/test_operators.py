"""Tests for Gaia Lang v5 operator functions."""

import pytest

from gaia.lang import claim, complement, contradiction, disjunction, equivalence, noisy_and

pytestmark = pytest.mark.legacy_dsl


def test_contradiction_creates_helper_claim():
    a = claim("A is true.")
    b = claim("B is true.")
    with pytest.warns(DeprecationWarning, match="contradiction\\(\\) is deprecated"):
        helper = contradiction(a, b, reason="A and B cannot both be true", prior=0.95)
    assert helper.type == "claim"
    assert "not_both_true" in helper.content


def test_contradiction_helper_usable_as_premise():
    a = claim("A.")
    b = claim("B.")
    with pytest.warns(DeprecationWarning, match="contradiction\\(\\) is deprecated"):
        contra = contradiction(a, b, reason="conflict", prior=0.9)
    c = claim("C.")
    with pytest.warns(DeprecationWarning, match="noisy_and\\(\\) is deprecated"):
        noisy_and([contra], c)
    assert contra in c.strategy.premises


def test_equivalence_creates_helper_claim():
    a = claim("Predicted obs.")
    b = claim("Actual obs.")
    with pytest.warns(DeprecationWarning, match="equivalence\\(\\) is deprecated"):
        helper = equivalence(a, b, reason="Match", prior=0.9)
    assert "same_truth" in helper.content


def test_complement_creates_helper_claim():
    a = claim("Classical.")
    b = claim("Quantum.")
    with pytest.warns(DeprecationWarning, match="complement\\(\\) is deprecated"):
        helper = complement(a, b, reason="Opposite", prior=0.9)
    assert "opposite_truth" in helper.content


def test_disjunction_creates_helper_claim():
    a = claim("Mechanism A.")
    b = claim("Mechanism B.")
    c = claim("Mechanism C.")
    with pytest.warns(DeprecationWarning, match="disjunction\\(\\) is deprecated"):
        helper = disjunction(a, b, c, reason="At least one", prior=0.9)
    assert "any_true" in helper.content


# ---------------------------------------------------------------------------
# reason + prior pairing
# ---------------------------------------------------------------------------


def test_contradiction_prior_stored_in_metadata():
    a = claim("A.")
    b = claim("B.")
    with pytest.warns(DeprecationWarning, match="contradiction\\(\\) is deprecated"):
        helper = contradiction(a, b, reason="incompatible", prior=0.95)
    assert helper.metadata["prior"] == 0.95


def test_equivalence_prior_stored_in_metadata():
    a = claim("Predicted.")
    b = claim("Observed.")
    with pytest.warns(DeprecationWarning, match="equivalence\\(\\) is deprecated"):
        helper = equivalence(a, b, reason="match", prior=0.9)
    assert helper.metadata["prior"] == 0.9


def test_complement_prior_stored_in_metadata():
    a = claim("Classical.")
    b = claim("Quantum.")
    with pytest.warns(DeprecationWarning, match="complement\\(\\) is deprecated"):
        helper = complement(a, b, reason="opposite", prior=0.85)
    assert helper.metadata["prior"] == 0.85


def test_disjunction_prior_stored_in_metadata():
    a = claim("A.")
    b = claim("B.")
    with pytest.warns(DeprecationWarning, match="disjunction\\(\\) is deprecated"):
        helper = disjunction(a, b, reason="at least one", prior=0.9)
    assert helper.metadata["prior"] == 0.9


def test_operator_reason_without_prior_raises():
    """Reason and prior must be paired — reason without prior is an error."""
    import pytest

    a = claim("A.")
    b = claim("B.")
    with pytest.warns(DeprecationWarning, match="contradiction\\(\\) is deprecated"):
        with pytest.raises(ValueError, match=r"reason.*prior.*paired"):
            contradiction(a, b, reason="incompatible")  # no prior!


def test_operator_prior_without_reason_raises():
    """Prior without reason is also an error."""
    import pytest

    a = claim("A.")
    b = claim("B.")
    with pytest.warns(DeprecationWarning, match="contradiction\\(\\) is deprecated"):
        with pytest.raises(ValueError, match=r"reason.*prior.*paired"):
            contradiction(a, b, prior=0.9)  # no reason!


def test_operator_prior_outside_cromwell_bounds_raises():
    import pytest

    a = claim("A.")
    b = claim("B.")
    with pytest.warns(DeprecationWarning, match="contradiction\\(\\) is deprecated"):
        with pytest.raises(ValueError, match="Cromwell bounds"):
            contradiction(a, b, reason="invalid probability", prior=1.5)


def test_operator_no_reason_no_prior_ok():
    """Neither reason nor prior is fine — uses defaults."""
    a = claim("A.")
    b = claim("B.")
    with pytest.warns(DeprecationWarning, match="contradiction\\(\\) is deprecated"):
        helper = contradiction(a, b)
    assert "prior" not in helper.metadata
