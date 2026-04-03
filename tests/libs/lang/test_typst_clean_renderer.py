"""Tests for typst_clean_renderer with v4 packages."""

from __future__ import annotations

from pathlib import Path

import pytest

from libs.lang.typst_clean_renderer import render_typst_to_clean_typst

FIXTURES = Path(__file__).parents[2] / "fixtures" / "ir"
GALILEO_V4 = FIXTURES / "galileo_falling_bodies_v4"
NEWTON_V4 = FIXTURES / "newton_principia_v4"
EINSTEIN_V4 = FIXTURES / "einstein_gravity_v4"


@pytest.fixture(scope="module")
def galileo_typst():
    return render_typst_to_clean_typst(GALILEO_V4)


@pytest.fixture(scope="module")
def newton_typst():
    return render_typst_to_clean_typst(NEWTON_V4)


@pytest.fixture(scope="module")
def einstein_typst():
    return render_typst_to_clean_typst(EINSTEIN_V4)


class TestGalileoCleanTypst:
    """Galileo v4: settings, claims with premises, contradiction constraint."""

    def test_has_package_header(self, galileo_typst):
        assert galileo_typst.startswith("= galileo falling bodies")

    def test_has_version_and_authors(self, galileo_typst):
        assert "Version: 4.0.0" in galileo_typst

    def test_settings_rendered(self, galileo_typst):
        assert "设定" in galileo_typst
        assert "<setting.thought-experiment-env>" in galileo_typst

    def test_claims_with_premises_rendered(self, galileo_typst):
        # vacuum_prediction has multiple premises
        assert "<galileo.vacuum-prediction>" in galileo_typst
        assert "@galileo.tied-balls-contradiction" in galileo_typst

    def test_question_rendered(self, galileo_typst):
        assert "问题" in galileo_typst
        assert "<motivation.main-question>" in galileo_typst

    def test_constraint_section(self, galileo_typst):
        assert "约束关系" in galileo_typst
        assert "矛盾" in galileo_typst
        assert "@galileo.composite-is-slower" in galileo_typst
        assert "@galileo.composite-is-faster" in galileo_typst

    def test_single_premise_uses_inline_format(self, galileo_typst):
        # heavier_falls_faster has a single premise → "基于 @ref，得出："
        assert "基于 @aristotle.everyday-observation，得出" in galileo_typst

    def test_multi_premise_uses_list_format(self, galileo_typst):
        # composite_is_slower has multiple premises → "基于以下前提："
        assert "基于以下前提" in galileo_typst

    def test_no_external_section(self, galileo_typst):
        # Galileo has no external refs
        assert "外部引用" not in galileo_typst


class TestNewtonCleanTypst:
    """Newton v4: has external reference to galileo."""

    def test_has_package_header(self, newton_typst):
        assert newton_typst.startswith("= newton principia")

    def test_external_reference_section(self, newton_typst):
        assert "外部引用" in newton_typst
        assert "galileo_falling_bodies@4.0.0" in newton_typst

    def test_external_ref_has_label(self, newton_typst):
        assert "<vacuum-prediction>" in newton_typst

    def test_claims_reference_external(self, newton_typst):
        # Newton's derivation references galileo's vacuum_prediction
        assert "@vacuum-prediction" in newton_typst


class TestEinsteinCleanTypst:
    """Einstein v4: has contradiction and equivalence constraints."""

    def test_has_package_header(self, einstein_typst):
        assert einstein_typst.startswith("= einstein gravity")

    def test_constraint_section(self, einstein_typst):
        assert "约束关系" in einstein_typst

    def test_settings_rendered(self, einstein_typst):
        assert "设定" in einstein_typst

    def test_output_to_file(self, tmp_path):
        output = tmp_path / "test.typ"
        result = render_typst_to_clean_typst(EINSTEIN_V4, output=output)
        assert output.exists()
        assert output.read_text() == result
