"""Tests for abduction() as a ternary CompositeStrategy (IBE)."""

import pytest

from gaia.lang import Knowledge, Strategy, claim, compare, support
from gaia.lang.dsl.strategies import abduction


def _make_abduction_triple():
    """Helper: create support_h, support_alt, comparison strategies."""
    theory_h = claim("Theory H explains the observation.")
    theory_alt = claim("Alternative theory.")
    obs = claim("Observation.")
    pred_h = claim("Prediction from H.")
    pred_alt = claim("Prediction from Alt.")

    sup_h = support(premises=[theory_h], conclusion=obs, reason="H explains obs.", prior=0.9)
    sup_alt = support(premises=[theory_alt], conclusion=obs, reason="Alt explains obs.", prior=0.5)
    comp = compare(pred_h, pred_alt, obs, reason="H matches obs better.", prior=0.9)
    return sup_h, sup_alt, comp, theory_h, theory_alt, obs, pred_h, pred_alt


def test_abduction_ternary_composite():
    """abduction takes 3 sub-strategies, returns CompositeStrategy."""
    sup_h, sup_alt, comp, *_ = _make_abduction_triple()
    s = abduction(sup_h, sup_alt, comp)

    assert isinstance(s, Strategy)
    assert s.type == "abduction"
    assert len(s.sub_strategies) == 3
    assert s.sub_strategies[0] is sup_h
    assert s.sub_strategies[1] is sup_alt
    assert s.sub_strategies[2] is comp


def test_abduction_conclusion_is_comparison_conclusion():
    """conclusion is the comparison strategy's conclusion (comparison_claim)."""
    sup_h, sup_alt, comp, *_ = _make_abduction_triple()
    s = abduction(sup_h, sup_alt, comp)

    assert s.conclusion is not None
    assert s.conclusion is comp.conclusion


def test_abduction_composition_warrant():
    """composition_warrant exists and has correct metadata."""
    sup_h, sup_alt, comp, *_ = _make_abduction_triple()
    s = abduction(sup_h, sup_alt, comp, reason="Both explain same obs.")

    assert s.composition_warrant is not None
    assert isinstance(s.composition_warrant, Knowledge)
    assert s.composition_warrant.type == "claim"
    assert s.composition_warrant.metadata["helper_kind"] == "composition_validity"
    assert s.composition_warrant.metadata["warrant"] == "Both explain same obs."


def test_abduction_composition_warrant_no_reason():
    """composition_warrant without reason has no 'warrant' key."""
    sup_h, sup_alt, comp, *_ = _make_abduction_triple()
    s = abduction(sup_h, sup_alt, comp)

    assert s.composition_warrant is not None
    assert "warrant" not in s.composition_warrant.metadata


def test_abduction_requires_strategy_inputs():
    """Raises TypeError for non-Strategy inputs."""
    k = claim("Not a strategy.")
    sup = support(premises=[claim("Theory.")], conclusion=claim("Obs."))
    pred_h = claim("Pred H.")
    pred_alt = claim("Pred Alt.")
    obs = claim("Obs.")
    comp = compare(pred_h, pred_alt, obs)

    with pytest.raises(TypeError, match="first arg must be a Strategy"):
        abduction(k, sup, comp)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="second arg must be a Strategy"):
        abduction(sup, k, comp)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="third arg must be a Strategy"):
        abduction(sup, sup, k)  # type: ignore[arg-type]


def test_abduction_requires_support_support_compare():
    """Abduction only accepts support, support, compare sub-strategies."""
    sup_h, sup_alt, comp, theory_h, *_ = _make_abduction_triple()
    not_support = Strategy(type="deduction", premises=[theory_h], conclusion=sup_h.conclusion)
    not_compare = Strategy(type="support", premises=list(comp.premises), conclusion=comp.conclusion)

    with pytest.raises(TypeError, match="first arg must be a support strategy"):
        abduction(not_support, sup_alt, comp)

    with pytest.raises(TypeError, match="second arg must be a support strategy"):
        abduction(sup_h, not_support, comp)

    with pytest.raises(TypeError, match="third arg must be a compare strategy"):
        abduction(sup_h, sup_alt, not_compare)


def test_abduction_requires_supports_to_conclude_compared_observation():
    """Both explanation supports must target compare()'s observation."""
    sup_h, sup_alt, comp, theory_h, theory_alt, _obs, *_ = _make_abduction_triple()
    other_obs = claim("Different observation.")

    bad_h = support(premises=[theory_h], conclusion=other_obs)
    with pytest.raises(ValueError, match="support_h must conclude the compared observation"):
        abduction(bad_h, sup_alt, comp)

    bad_alt = support(premises=[theory_alt], conclusion=other_obs)
    with pytest.raises(ValueError, match="support_alt must conclude the compared observation"):
        abduction(sup_h, bad_alt, comp)


def test_abduction_requires_well_formed_compare():
    """The comparison sub-strategy must expose pred_h, pred_alt, observation and conclusion."""
    sup_h, sup_alt, comp, *_ = _make_abduction_triple()
    malformed_premises = Strategy(
        type="compare", premises=comp.premises[:2], conclusion=comp.conclusion
    )
    missing_conclusion = Strategy(type="compare", premises=list(comp.premises), conclusion=None)

    with pytest.raises(ValueError, match=r"must have \[pred_h, pred_alt, observation\]"):
        abduction(sup_h, sup_alt, malformed_premises)

    with pytest.raises(ValueError, match="compare strategy must have a conclusion"):
        abduction(sup_h, sup_alt, missing_conclusion)


def test_abduction_premises_are_deduplicated():
    """Premises from all sub-strategies are merged without duplicates."""
    theory = claim("Theory.")
    obs = claim("Observation.")
    pred_h = claim("Pred H.")
    pred_alt = claim("Pred Alt.")

    sup_h = support(premises=[theory], conclusion=obs)
    # Use the same theory as premise for alt (shared premise)
    sup_alt = support(premises=[theory], conclusion=obs)
    comp = compare(pred_h, pred_alt, obs)

    s = abduction(sup_h, sup_alt, comp)

    # theory should appear only once in premises
    theory_count = sum(1 for p in s.premises if p is theory)
    assert theory_count == 1


def test_abduction_strategy_attached_to_conclusion():
    """The abduction strategy is attached to the conclusion's .strategy."""
    sup_h, sup_alt, comp, *_ = _make_abduction_triple()
    s = abduction(sup_h, sup_alt, comp)

    assert s.conclusion.strategy is s


def test_abduction_with_background():
    """Background is passed through."""
    sup_h, sup_alt, comp, *_ = _make_abduction_triple()
    bg = claim("Background context.")
    s = abduction(sup_h, sup_alt, comp, background=[bg])

    assert s.background == [bg]
