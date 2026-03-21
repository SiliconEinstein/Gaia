"""Tests for pipeline_publish (Chunk 5 — Typst v3 LocalCanonicalGraph converter)."""

from pathlib import Path

import pytest

from libs.pipeline import pipeline_build, pipeline_infer, pipeline_publish, pipeline_review

GALILEO_V3 = (
    Path(__file__).parent / "fixtures" / "gaia_language_packages" / "galileo_falling_bodies_v3"
)


@pytest.mark.asyncio
async def test_pipeline_publish_to_lancedb(tmp_path):
    build = await pipeline_build(GALILEO_V3)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    result = await pipeline_publish(build, review, infer, db_path=str(tmp_path / "db"))
    assert result.package_id == "galileo_falling_bodies"
    assert result.stats["knowledge_items"] > 0


@pytest.mark.asyncio
async def test_pipeline_publish_has_chains(tmp_path):
    build = await pipeline_build(GALILEO_V3)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    result = await pipeline_publish(build, review, infer, db_path=str(tmp_path / "db"))
    assert result.stats["chains"] > 0


@pytest.mark.asyncio
async def test_pipeline_publish_has_belief_snapshots(tmp_path):
    build = await pipeline_build(GALILEO_V3)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    result = await pipeline_publish(build, review, infer, db_path=str(tmp_path / "db"))
    assert result.stats["belief_snapshots"] > 0


@pytest.mark.asyncio
async def test_pipeline_publish_idempotent(tmp_path):
    db_path = str(tmp_path / "db")
    build = await pipeline_build(GALILEO_V3)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    await pipeline_publish(build, review, infer, db_path=db_path)
    result = await pipeline_publish(build, review, infer, db_path=db_path)
    assert result.stats["knowledge_items"] > 0
