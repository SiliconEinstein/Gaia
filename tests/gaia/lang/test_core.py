from gaia.lang import __all__ as gaia_lang_exports
from gaia.lang import claim, question, setting


def test_setting_creates_knowledge():
    s = setting("Background assumption.")
    assert s.type == "setting"
    assert s.content == "Background assumption."


def test_claim_creates_knowledge():
    c = claim("A scientific assertion.")
    assert c.type == "claim"
    assert c.content == "A scientific assertion."


def test_question_creates_knowledge():
    q = question("An open question?")
    assert q.type == "question"


def test_claim_with_explicit_noisy_and():
    a = claim("Premise A.")
    b = claim("Premise B.")
    c = claim("Conclusion.")
    from gaia.lang import noisy_and

    noisy_and([a, b], c)
    assert c.type == "claim"
    assert c.strategy is not None
    assert c.strategy.type == "noisy_and"
    assert a in c.strategy.premises
    assert b in c.strategy.premises


def test_claim_with_background():
    bg = setting("Context.")
    c = claim("Assertion.", background=[bg])
    assert bg in c.background


def test_universal_claim_with_parameters():
    u = claim("forall x. P(x)", parameters=[{"name": "x", "type": "material"}])
    assert len(u.parameters) == 1
    assert u.parameters[0]["name"] == "x"


def test_claim_supports_provenance():
    c = claim(
        "A sourced scientific assertion.",
        provenance=[{"package_id": "paper:galileo", "version": "1.0.0"}],
    )
    assert c.provenance == [{"package_id": "paper:galileo", "version": "1.0.0"}]


def test_public_api_does_not_export_package():
    assert "Package" not in gaia_lang_exports
    assert "elimination" in gaia_lang_exports
    assert "case_analysis" in gaia_lang_exports
    assert "mathematical_induction" in gaia_lang_exports
    assert "composite" in gaia_lang_exports
    assert "fills" in gaia_lang_exports
