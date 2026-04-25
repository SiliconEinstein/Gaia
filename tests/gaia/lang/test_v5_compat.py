import pytest

from gaia.lang import claim, support

pytestmark = pytest.mark.legacy_dsl


def test_v5_support_preserves_prior_while_warning():
    a = claim("A.")
    b = claim("B.")
    with pytest.warns(DeprecationWarning, match="support\\(\\) is deprecated"):
        strategy = support([a], b, reason="test", prior=0.9)
    assert strategy.metadata["prior"] == 0.9
