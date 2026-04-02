from gaia.lang import (
    Package,
    abduction,
    analogy,
    claim,
    deduction,
    extrapolation,
    noisy_and,
    setting,
)


def test_noisy_and_explicit():
    with Package("test_pkg"):
        a = claim("A.")
        b = claim("B.")
        c = claim("C.")
        s = noisy_and(premises=[a, b], conclusion=c, steps=["Step 1", "Step 2"])
    assert s.type == "noisy_and"
    assert s.conclusion is c
    assert len(s.premises) == 2
    assert len(s.steps) == 2


def test_deduction():
    with Package("test_pkg"):
        law = claim("∀x. P(x)", parameters=[{"name": "x", "type": "material"}])
        premise = claim("YBCO is in scope.")
        binding = setting("x = YBCO")
        instance = claim("P(YBCO)")
        s = deduction(premises=[law, premise], conclusion=instance, background=[binding])
    assert s.type == "deduction"
    assert s.formal_expr is not None
    assert len(s.formal_expr) == 2  # conjunction + implication


def test_abduction():
    with Package("test_pkg"):
        obs = claim("Observation.")
        hyp = claim("Hypothesis.")
        alt = claim("Alternative.")
        s = abduction(observation=obs, hypothesis=hyp, alternative=alt)
    assert s.type == "abduction"
    assert s.conclusion is hyp
    assert obs in s.premises
    assert alt in s.premises
    assert s.formal_expr is not None


def test_abduction_auto_creates_alternative():
    with Package("test_pkg"):
        obs = claim("Observation.")
        hyp = claim("Hypothesis.")
        s = abduction(observation=obs, hypothesis=hyp)
    assert s.type == "abduction"
    assert len(s.premises) == 2
    assert any("alternative" in p.content.lower() for p in s.premises)


def test_analogy():
    with Package("test_pkg"):
        source = claim("Source law.")
        target = claim("Target prediction.")
        bridge = claim("Bridge claim.")
        s = analogy(source=source, target=target, bridge=bridge)
    assert s.type == "analogy"
    assert s.formal_expr is not None
    assert bridge in s.premises


def test_extrapolation():
    with Package("test_pkg"):
        source = claim("Known behavior.")
        target = claim("Predicted behavior.")
        cont = claim("Continuity assumption.")
        s = extrapolation(source=source, target=target, continuity=cont)
    assert s.type == "extrapolation"
