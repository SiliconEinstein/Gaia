"""Tests for Typst -> Markdown rendering."""

from pathlib import Path

from libs.lang.typst_renderer import render_typst_to_markdown

GALILEO_TYPST = Path("tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst")
GALILEO_V3 = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "gaia_language_packages"
    / "galileo_falling_bodies_v3"
)
NEWTON_V3 = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "gaia_language_packages"
    / "newton_principia_v3"
)
EINSTEIN_V3 = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "gaia_language_packages"
    / "einstein_gravity_v3"
)


def test_render_produces_nonempty_markdown():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert len(md) > 100


def test_render_v3_produces_nonempty_markdown():
    md = render_typst_to_markdown(GALILEO_V3)
    assert len(md) > 100


def test_render_v3_has_knowledge_section():
    md = render_typst_to_markdown(GALILEO_V3)
    assert "## Knowledge" in md


def test_render_v3_has_proofs_section():
    md = render_typst_to_markdown(GALILEO_V3)
    assert "## Proofs" in md


def test_render_v3_has_constraints_section():
    md = render_typst_to_markdown(GALILEO_V3)
    assert "## Constraints" in md


def test_render_v3_has_questions_section():
    md = render_typst_to_markdown(GALILEO_V3)
    assert "## Questions" in md


def test_render_v3_premises_appear():
    """Premise names should appear in the Proofs section."""
    md = render_typst_to_markdown(GALILEO_V3)
    assert "heavier_falls_faster" in md or "heavier falls faster" in md


def test_render_v3_no_chain_headings():
    """v3 rendering should not contain chain headings."""
    md = render_typst_to_markdown(GALILEO_V3)
    assert "### Chain:" not in md


def test_render_v3_references_section():
    md = render_typst_to_markdown(GALILEO_V3)
    assert "## References" in md


def test_render_v3_contradiction_in_constraints():
    md = render_typst_to_markdown(GALILEO_V3)
    assert "contradiction" in md.lower()


def test_render_v3_to_file(tmp_path):
    out = tmp_path / "package.md"
    render_typst_to_markdown(GALILEO_V3, output=out)
    assert out.exists()
    content = out.read_text()
    assert "## Proofs" in content
    assert "## Constraints" in content


def test_render_v3_corroboration_constraints_appear():
    newton_md = render_typst_to_markdown(NEWTON_V3)
    einstein_md = render_typst_to_markdown(EINSTEIN_V3)
    assert "galileo_newton_convergence" in newton_md
    assert "apollo_galileo_convergence" in newton_md
    assert "gr_dual_confirmation" in einstein_md
    assert "corroboration" in newton_md.lower()
