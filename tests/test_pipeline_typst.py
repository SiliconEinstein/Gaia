"""Tests for Typst pipeline_build()."""

from pathlib import Path

import pytest

from libs.pipeline import BuildResult, pipeline_build

GALILEO_V4 = (
    Path(__file__).parent / "fixtures" / "ir" / "galileo_falling_bodies_v4"
)


@pytest.mark.asyncio
async def test_pipeline_build_returns_result():
    result = await pipeline_build(GALILEO_V4)
    assert isinstance(result, BuildResult)


@pytest.mark.asyncio
async def test_pipeline_build_has_graph_data():
    result = await pipeline_build(GALILEO_V4)
    assert "nodes" in result.graph_data
    assert "factors" in result.graph_data
    assert result.graph_data["package"] == "galileo_falling_bodies"


@pytest.mark.asyncio
async def test_pipeline_build_has_raw_graph():
    result = await pipeline_build(GALILEO_V4)
    assert result.raw_graph.package == "galileo_falling_bodies"
    assert len(result.raw_graph.knowledge_nodes) > 0
    assert len(result.raw_graph.factor_nodes) > 0


@pytest.mark.asyncio
async def test_pipeline_build_has_local_graph():
    result = await pipeline_build(GALILEO_V4)
    assert len(result.local_graph.knowledge_nodes) > 0
    assert result.local_graph.package == "galileo_falling_bodies"


@pytest.mark.asyncio
async def test_pipeline_build_collects_source_files():
    result = await pipeline_build(GALILEO_V4)
    assert "lib.typ" in result.source_files
    assert "galileo.typ" in result.source_files
