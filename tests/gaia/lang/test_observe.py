from gaia.lang import observe
from gaia.lang.runtime.action import Observe
from gaia.lang.runtime.knowledge import Claim


def test_observe_with_given():
    calibrated = Claim("Calibration OK.", prior=0.95)
    data = observe("UV spectrum data.", given=calibrated, rationale="Measured.")
    assert isinstance(data, Claim)
    assert len(data.supports) == 1
    assert isinstance(data.supports[0], Observe)
    assert data.supports[0].given == (calibrated,)


def test_observe_root_fact_adds_grounding_and_reviewable_action():
    data = observe("UV spectrum data.", rationale="Measured at 5 points.")
    assert data.grounding is not None
    assert data.grounding.kind == "source_fact"
    assert len(data.supports) == 1
    assert isinstance(data.supports[0], Observe)
    assert data.supports[0].given == ()
