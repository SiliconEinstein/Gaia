import pytest

from gaia.lang.runtime.grounding import Grounding
from gaia.lang.runtime.knowledge import Claim, Context, Question, Setting


def test_context_creation():
    ctx = Context("Raw experiment notes.")
    assert ctx.content == "Raw experiment notes."
    assert ctx.type == "context"


def test_setting_creation():
    s = Setting("Blackbody cavity at thermal equilibrium.")
    assert s.type == "setting"
    assert s.content == "Blackbody cavity at thermal equilibrium."


def test_claim_creation():
    c = Claim("Energy exchange is quantized.", prior=0.5)
    assert c.type == "claim"
    assert c.prior == 0.5
    assert c.supports == []


def test_claim_no_prior():
    c = Claim("A proposition.")
    assert c.prior is None


def test_claim_with_grounding():
    g = Grounding(kind="source_fact", rationale="From paper.")
    c = Claim("UV data.", prior=0.95, grounding=g)
    assert c.grounding.kind == "source_fact"


def test_claim_is_hashable_for_priors_dict():
    c = Claim("A proposition.")
    priors = {c: (0.5, "uninformative")}
    assert priors[c] == (0.5, "uninformative")


def test_question_creation():
    q = Question("Should we ship variant B?")
    assert q.type == "question"


def test_context_cannot_have_prior():
    with pytest.raises(TypeError):
        Context("raw text", prior=0.5)


def test_setting_cannot_have_prior():
    with pytest.raises(TypeError):
        Setting("background", prior=0.5)


def test_context_dsl_function():
    from gaia.lang.dsl.knowledge import context

    ctx = context("Raw experiment notes.")
    assert ctx.type == "context"
    assert ctx.content == "Raw experiment notes."
    assert isinstance(ctx, Context)


def test_v5_claim_still_works():
    """v5 claim() function returns a v6 Claim."""
    from gaia.lang import claim

    c = claim("A proposition.")
    assert c.type == "claim"
    assert isinstance(c, Claim)


def test_v5_setting_still_works():
    from gaia.lang import setting

    s = setting("Background info.")
    assert s.type == "setting"
    assert isinstance(s, Setting)


def test_v5_question_still_works():
    from gaia.lang import question

    q = question("Question?")
    assert q.type == "question"
    assert isinstance(q, Question)


def test_grounding_public_export():
    from gaia.lang import Grounding as PublicGrounding

    assert PublicGrounding is Grounding
