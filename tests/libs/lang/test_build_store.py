"""Tests for build_store single package.md generation."""

from pathlib import Path

from libs.lang.build_store import save_build
from libs.lang.elaborator import elaborate_package
from libs.lang.loader import load_package
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"


def test_save_build_creates_single_package_md(tmp_path):
    """Build should produce a single package.md, not per-module files."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)

    save_build(elaborated, tmp_path)

    package_md = tmp_path / "package.md"
    assert package_md.exists()
    content = package_md.read_text()

    # Should contain package name in title
    assert "galileo_falling_bodies" in content

    # Should contain all modules in order
    assert "[module:motivation]" in content
    assert "[module:setting]" in content
    assert "[module:aristotle]" in content
    assert "[module:reasoning]" in content
    assert "[module:follow_up]" in content

    # motivation should appear before reasoning
    assert content.index("[module:motivation]") < content.index("[module:reasoning]")


def test_save_build_has_chain_anchors(tmp_path):
    """Chain anchors should use [chain:name] format."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)
    save_build(elaborated, tmp_path)

    content = (tmp_path / "package.md").read_text()
    assert "[chain:synthesis_chain]" in content
    assert "[chain:drag_prediction_chain]" in content


def test_save_build_has_step_anchors(tmp_path):
    """Step anchors should use [step:chain_name.N] format."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)
    save_build(elaborated, tmp_path)

    content = (tmp_path / "package.md").read_text()
    assert "[step:synthesis_chain.2]" in content
    assert "[step:drag_prediction_chain.2]" in content


def test_save_build_has_direct_references(tmp_path):
    """Steps with direct dependencies should have 'Direct references:' sections."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)
    save_build(elaborated, tmp_path)

    content = (tmp_path / "package.md").read_text()
    assert "**Direct references:**" in content


def test_save_build_has_context_section(tmp_path):
    """Chains with indirect deps should have 'Context (indirect reference):' sections."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)
    save_build(elaborated, tmp_path)

    content = (tmp_path / "package.md").read_text()
    assert "**Context (indirect reference):**" in content
