"""Tests for Typst → Markdown rendering."""

from pathlib import Path

from libs.lang.typst_renderer import render_typst_to_markdown

GALILEO_TYPST = Path("tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst")


def test_render_produces_nonempty_markdown():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert len(md) > 100


def test_render_contains_module_heading():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert "reasoning" in md


def test_render_contains_chain_heading():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert "tied_balls_argument" in md


def test_render_contains_claim_content():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert "复合体" in md or "tied_pair_slower" in md


def test_render_contains_premise_annotation():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert "Premise" in md or "premise" in md


def test_render_to_file(tmp_path):
    out = tmp_path / "package.md"
    render_typst_to_markdown(GALILEO_TYPST, output=out)
    assert out.exists()
    content = out.read_text()
    assert "reasoning" in content
