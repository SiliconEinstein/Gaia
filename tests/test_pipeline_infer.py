"""Tests for pipeline_infer (Chunk 4 — Typst v4 ReviewOutput)."""

from pathlib import Path

import pytest

from libs.pipeline import InferResult, pipeline_build, pipeline_infer, pipeline_review

GALILEO_V4 = (
    Path(__file__).parent / "fixtures" / "ir" / "galileo_falling_bodies_v4"
)


@pytest.mark.asyncio
async def test_pipeline_infer_returns_result():
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    assert isinstance(infer, InferResult)


@pytest.mark.asyncio
async def test_pipeline_infer_has_beliefs():
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    assert len(infer.beliefs) > 0
    for name, belief in infer.beliefs.items():
        assert 0.0 <= belief <= 1.0


@pytest.mark.asyncio
async def test_pipeline_infer_has_bp_run_id():
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    assert infer.bp_run_id  # non-empty string


@pytest.mark.asyncio
async def test_pipeline_infer_has_parameterization():
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    assert infer.local_parameterization.graph_hash == build.local_graph.graph_hash()
