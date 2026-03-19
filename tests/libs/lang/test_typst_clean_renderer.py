"""Tests for Typst -> clean Typst rendering."""

from pathlib import Path

from libs.lang.typst_clean_renderer import render_typst_to_clean_typst

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "gaia_language_packages"
GALILEO_V3 = _FIXTURES / "galileo_falling_bodies_v3"
NEWTON_V3 = _FIXTURES / "newton_principia_v3"
EINSTEIN_V3 = _FIXTURES / "einstein_gravity_v3"


def test_clean_renderer_keeps_galileo_proved_claims():
    text = render_typst_to_clean_typst(GALILEO_V3)
    assert "vacuum prediction" in text
    assert "air resistance is confound" in text


def test_clean_renderer_keeps_newton_proved_claims():
    text = render_typst_to_clean_typst(NEWTON_V3)
    assert "law of gravity" in text
    assert "freefall acceleration equals g" in text


def test_clean_renderer_keeps_einstein_proved_claims():
    text = render_typst_to_clean_typst(EINSTEIN_V3)
    assert "gr light deflection" in text
    assert "gr mercury precession" in text
