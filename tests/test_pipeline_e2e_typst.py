"""End-to-end test: build -> review(mock) -> infer -> publish for Typst v3 packages."""

from pathlib import Path

import pytest

from libs.pipeline import pipeline_build, pipeline_infer, pipeline_publish, pipeline_review

GALILEO_V3 = (
    Path(__file__).parent / "fixtures" / "gaia_language_packages" / "galileo_falling_bodies_v3"
)


@pytest.mark.asyncio
async def test_typst_v3_full_pipeline(tmp_path):
    """Galileo v3: build -> review(mock) -> infer -> publish."""
    db_path = str(tmp_path / "db")

    # Build
    build = await pipeline_build(GALILEO_V3)
    assert build.graph_data["package"] == "galileo_falling_bodies"
    assert len(build.local_graph.knowledge_nodes) > 0

    # Review (mock)
    review = await pipeline_review(build, mock=True)
    assert review.model == "mock"
    assert len(review.node_priors) == len(build.local_graph.knowledge_nodes)

    # Infer
    infer = await pipeline_infer(build, review)
    assert len(infer.beliefs) > 0

    # Publish
    result = await pipeline_publish(build, review, infer, db_path=db_path)
    assert result.package_id == "galileo_falling_bodies"
    assert result.stats["knowledge_items"] > 0
    assert result.stats["chains"] > 0

    # Verify data in LanceDB
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager

    config = StorageConfig(lancedb_path=db_path, graph_backend="kuzu", kuzu_path=f"{db_path}/kuzu")
    mgr = StorageManager(config)
    await mgr.initialize()
    try:
        pkg = await mgr.content_store.get_package("galileo_falling_bodies")
        assert pkg is not None
        assert pkg.name == "galileo_falling_bodies"
    finally:
        await mgr.close()


@pytest.mark.asyncio
async def test_typst_v3_beliefs_are_reasonable(tmp_path):
    """Beliefs should be between 0 and 1."""
    build = await pipeline_build(GALILEO_V3)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)

    for name, belief in infer.beliefs.items():
        assert 0.0 <= belief <= 1.0, f"Belief for {name} out of range: {belief}"
