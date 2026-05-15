from gaia.engine.ir.parameterization import CROMWELL_EPS
from gaia.engine.lang import observe
from gaia.engine.lang.runtime.action import Observe
from gaia.engine.lang.runtime.knowledge import Claim


def test_observe_with_given():
    calibrated = Claim("Calibration OK.", prior=0.95)
    data = observe("UV spectrum data.", given=calibrated, rationale="Measured.")
    assert isinstance(data, Claim)
    assert len(data.from_actions) == 1
    assert isinstance(data.from_actions[0], Observe)
    assert data.from_actions[0].given == (calibrated,)


def test_observe_root_fact_pins_prior_and_adds_reviewable_action():
    data = observe("UV spectrum data.", rationale="Measured at 5 points.")
    assert data.prior == 1.0 - CROMWELL_EPS
    assert len(data.from_actions) == 1
    assert isinstance(data.from_actions[0], Observe)
    assert data.from_actions[0].given == ()


def test_observe_root_fact_rejects_conflicting_prior():
    data = Claim("UV spectrum data.", prior=0.9)
    try:
        observe(data, rationale="Measured.")
    except ValueError as exc:
        assert "pins the conclusion" in str(exc)
    else:
        raise AssertionError("observe() accepted a conflicting pre-set prior")


def test_observe_creates_reviewable_implication_warrant():
    calibrated = Claim("Calibration OK.", prior=0.95)
    data = observe("UV spectrum data.", given=calibrated, rationale="Measured.")
    action = data.from_actions[0]
    assert len(action.warrants) == 1
    warrant = action.warrants[0]
    assert warrant.metadata["generated"] is True
    assert warrant.metadata["helper_kind"] == "implication_warrant"
    assert warrant.metadata["review"] is True
    assert warrant.metadata["relation"] == {
        "type": "observe",
        "given": (calibrated,),
        "conclusion": data,
    }
