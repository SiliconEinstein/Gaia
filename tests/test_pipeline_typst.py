"""Tests for Typst pipeline_build_typst()."""

from pathlib import Path

import pytest

from libs.pipeline import TypstBuildResult, pipeline_build_typst

GALILEO_V3 = (
    Path(__file__).parent / "fixtures" / "gaia_language_packages" / "galileo_falling_bodies_v3"
)


@pytest.mark.asyncio
async def test_pipeline_build_typst_returns_result():
    result = await pipeline_build_typst(GALILEO_V3)
    assert isinstance(result, TypstBuildResult)


@pytest.mark.asyncio
async def test_pipeline_build_typst_has_graph_data():
    result = await pipeline_build_typst(GALILEO_V3)
    assert "nodes" in result.graph_data
    assert "factors" in result.graph_data
    assert result.graph_data["package"] == "galileo_falling_bodies"


@pytest.mark.asyncio
async def test_pipeline_build_typst_has_raw_graph():
    result = await pipeline_build_typst(GALILEO_V3)
    assert result.raw_graph.package == "galileo_falling_bodies"
    assert len(result.raw_graph.knowledge_nodes) > 0
    assert len(result.raw_graph.factor_nodes) > 0


@pytest.mark.asyncio
async def test_pipeline_build_typst_has_local_graph():
    result = await pipeline_build_typst(GALILEO_V3)
    assert len(result.local_graph.knowledge_nodes) > 0
    assert result.local_graph.package == "galileo_falling_bodies"


@pytest.mark.asyncio
async def test_pipeline_build_typst_collects_source_files():
    result = await pipeline_build_typst(GALILEO_V3)
    assert "lib.typ" in result.source_files
    assert "galileo.typ" in result.source_files
