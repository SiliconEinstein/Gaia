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


def test_question_creation():
    q = Question("Should we ship variant B?")
    assert q.type == "question"


def test_context_cannot_have_prior():
    with pytest.raises(TypeError):
        Context("raw text", prior=0.5)


def test_setting_cannot_have_prior():
    with pytest.raises(TypeError):
        Setting("background", prior=0.5)
