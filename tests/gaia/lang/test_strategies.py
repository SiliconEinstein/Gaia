import pytest

from gaia.lang import (
    abduction,
    analogy,
    case_analysis,
    claim,
    composite,
    deduction,
    elimination,
    extrapolation,
    mathematical_induction,
    noisy_and,
    setting,
)


def test_noisy_and_explicit():
    a = claim("A.")
    b = claim("B.")
    c = claim("C.")
    s = noisy_and(premises=[a, b], conclusion=c, steps=["Step 1", "Step 2"])
    assert s.type == "noisy_and"
    assert s.conclusion is c
    assert len(s.premises) == 2
    assert len(s.steps) == 2


def test_noisy_and_structured_steps():
    a = claim("A.")
    b = claim("B.")
    c = claim("C.")
    s = noisy_and(
        premises=[a, b],
        conclusion=c,
        steps=[
            {
                "reasoning": "A and B jointly support C.",
                "premises": [a, b],
                "conclusion": c,
            }
        ],
    )
    assert s.steps[0]["reasoning"] == "A and B jointly support C."
    assert s.steps[0]["premises"] == [a, b]
    assert s.steps[0]["conclusion"] is c


def test_deduction():
    law = claim("forall x. P(x)", parameters=[{"name": "x", "type": "material"}])
    premise = claim("YBCO is in scope.")
    binding = setting("x = YBCO")
    instance = claim("P(YBCO)")
    s = deduction(
        premises=[law, premise],
        conclusion=instance,
        background=[binding],
        steps=[{"reasoning": "Instantiate the universal law.", "premises": [law, premise]}],
    )
    assert s.type == "deduction"
    assert s.formal_expr is None
    assert s.background == [binding]
    assert s.steps[0]["reasoning"] == "Instantiate the universal law."


def test_deduction_requires_at_least_two_premises():
    law = claim("forall x. P(x)")
    instance = claim("P(a)")
    with pytest.raises(ValueError, match="at least 2 premises"):
        deduction(premises=[law], conclusion=instance)


def test_abduction():
    obs = claim("Observation.")
    hyp = claim("Hypothesis.")
    alt = claim("Alternative.")
    s = abduction(observation=obs, hypothesis=hyp, alternative=alt)
    assert s.type == "abduction"
    assert s.conclusion is hyp
    assert obs in s.premises
    assert alt in s.premises
    assert s.formal_expr is None


def test_abduction_auto_creates_alternative():
    obs = claim("Observation.")
    hyp = claim("Hypothesis.")
    s = abduction(observation=obs, hypothesis=hyp)
    assert s.type == "abduction"
    assert s.premises == [obs]


def test_analogy():
    source = claim("Source law.")
    target = claim("Target prediction.")
    bridge = claim("Bridge claim.")
    s = analogy(source=source, target=target, bridge=bridge)
    assert s.type == "analogy"
    assert s.formal_expr is None
    assert bridge in s.premises


def test_extrapolation():
    source = claim("Known behavior.")
    target = claim("Predicted behavior.")
    cont = claim("Continuity assumption.")
    s = extrapolation(source=source, target=target, continuity=cont)
    assert s.type == "extrapolation"
    assert s.formal_expr is None


def test_elimination():
    exhaustive = claim("The listed candidates are exhaustive.")
    h1 = claim("Candidate 1.")
    e1 = claim("Evidence against candidate 1.")
    h2 = claim("Candidate 2.")
    e2 = claim("Evidence against candidate 2.")
    survivor = claim("Surviving candidate.")
    s = elimination(
        exhaustiveness=exhaustive,
        excluded=[(h1, e1), (h2, e2)],
        survivor=survivor,
    )
    assert s.type == "elimination"
    assert s.premises == [exhaustive, h1, e1, h2, e2]
    assert s.conclusion is survivor
    assert s.formal_expr is None


def test_case_analysis():
    exhaustive = claim("The listed cases are exhaustive.")
    c1 = claim("Case 1 holds.")
    p1 = claim("Case 1 implies the result.")
    c2 = claim("Case 2 holds.")
    p2 = claim("Case 2 implies the result.")
    conclusion = claim("The result holds.")
    s = case_analysis(
        exhaustiveness=exhaustive,
        cases=[(c1, p1), (c2, p2)],
        conclusion=conclusion,
    )
    assert s.type == "case_analysis"
    assert s.premises == [exhaustive, c1, p1, c2, p2]
    assert s.conclusion is conclusion
    assert s.formal_expr is None


def test_mathematical_induction():
    base = claim("P(0) holds.")
    step = claim("P(n) implies P(n+1).")
    conclusion = claim("P(n) holds for all n.")
    s = mathematical_induction(base=base, step=step, conclusion=conclusion)
    assert s.type == "mathematical_induction"
    assert s.premises == [base, step]
    assert s.conclusion is conclusion
    assert s.formal_expr is None


def test_composite():
    evidence = claim("Evidence.")
    intermediate = claim("Intermediate.")
    conclusion = claim("Conclusion.")
    s1 = noisy_and(premises=[evidence], conclusion=intermediate)
    s2 = noisy_and(premises=[intermediate], conclusion=conclusion)
    composite_strategy = composite(
        premises=[evidence],
        conclusion=conclusion,
        sub_strategies=[s1, s2],
        reason="Two-step argument.",
    )
    assert composite_strategy.type == "infer"
    assert composite_strategy.premises == [evidence]
    assert composite_strategy.conclusion is conclusion
    assert composite_strategy.sub_strategies == [s1, s2]


def test_composite_requires_sub_strategies():
    evidence = claim("Evidence.")
    conclusion = claim("Conclusion.")
    with pytest.raises(ValueError, match="at least one sub-strategy"):
        composite(premises=[evidence], conclusion=conclusion, sub_strategies=[])
