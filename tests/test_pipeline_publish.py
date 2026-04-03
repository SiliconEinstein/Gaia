"""Tests for pipeline_publish (Chunk 5 — Typst v4 LocalCanonicalGraph converter)."""

from pathlib import Path

import pytest

from libs.pipeline import pipeline_build, pipeline_infer, pipeline_publish, pipeline_review

pytestmark = pytest.mark.usefixtures("fresh_lancedb_loop")

GALILEO_V4 = (
    Path(__file__).parent / "fixtures" / "ir" / "galileo_falling_bodies_v4"
)


@pytest.mark.asyncio
async def test_pipeline_publish_to_lancedb(tmp_path):
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    result = await pipeline_publish(build, review, infer, db_path=str(tmp_path / "db"))
    assert result.package_id == "galileo_falling_bodies"
    assert result.stats["knowledge_items"] > 0


@pytest.mark.asyncio
async def test_pipeline_publish_has_chains(tmp_path):
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    result = await pipeline_publish(build, review, infer, db_path=str(tmp_path / "db"))
    assert result.stats["chains"] > 0


@pytest.mark.asyncio
async def test_pipeline_publish_does_not_persist_local_belief_previews(tmp_path):
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    db_path = str(tmp_path / "db")
    result = await pipeline_publish(build, review, infer, db_path=db_path)
    assert result.stats["belief_snapshots"] == 0

    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager

    config = StorageConfig(lancedb_path=db_path, graph_backend="kuzu", kuzu_path=f"{db_path}/kuzu")
    mgr = StorageManager(config)
    await mgr.initialize()
    try:
        history = await mgr.get_belief_history("galileo_falling_bodies/composite_is_slower")
        assert history == []
    finally:
        await mgr.close()


@pytest.mark.asyncio
async def test_pipeline_publish_probability_records_match_chain_ids(tmp_path):
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    db_path = str(tmp_path / "db")
    result = await pipeline_publish(build, review, infer, db_path=db_path)
    assert result.stats["probabilities"] > 0

    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager

    config = StorageConfig(lancedb_path=db_path, graph_backend="kuzu", kuzu_path=f"{db_path}/kuzu")
    mgr = StorageManager(config)
    await mgr.initialize()
    try:
        chains, _ = await mgr.list_chains_paged(page=1, page_size=100)
        chain_ids = {chain.chain_id for chain in chains}
        assert "galileo_falling_bodies.default.galileo.composite_is_slower" in chain_ids

        probabilities = await mgr.get_probability_history(
            "galileo_falling_bodies.default.galileo.composite_is_slower"
        )
        assert probabilities
        assert all(p.chain_id in chain_ids for p in probabilities)

        import lancedb

        db = lancedb.connect(db_path)
        raw_probs = db.open_table("probabilities").search().limit(1000).to_list()
        assert raw_probs
        for row in raw_probs:
            assert row["chain_id"] in chain_ids
    finally:
        await mgr.close()


@pytest.mark.asyncio
async def test_pipeline_publish_idempotent(tmp_path):
    db_path = str(tmp_path / "db")
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    await pipeline_publish(build, review, infer, db_path=db_path)
    result = await pipeline_publish(build, review, infer, db_path=db_path)
    assert result.stats["knowledge_items"] > 0
