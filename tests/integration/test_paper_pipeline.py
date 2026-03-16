"""E2E test: build → review(mock) → infer → publish → verify storage."""

from __future__ import annotations

from pathlib import Path

import pytest


# Use a committed YAML package fixture (no XML fixtures required)
PAPER_PKG_DIR = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "gaia_language_packages"
    / "paper_10_1038332139a0_1988_natu"
)


@pytest.mark.asyncio
async def test_paper_e2e_pipeline(tmp_path):
    """Full pipeline: build → review(mock) → infer → publish → verify."""
    from libs.pipeline import pipeline_build, pipeline_infer, pipeline_publish, pipeline_review
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager

    assert PAPER_PKG_DIR.is_dir(), f"Fixture not found: {PAPER_PKG_DIR}"

    # ── 1. pipeline_build ──
    build = await pipeline_build(PAPER_PKG_DIR)
    assert build.package.name == "paper_10_1038332139a0_1988_natu"
    assert len(build.package.loaded_modules) >= 2
    assert len(build.markdown) > 0
    assert len(build.raw_graph.knowledge_nodes) > 0
    assert len(build.local_graph.factor_nodes) > 0
    assert len(build.source_files) >= 2

    # ── 2. pipeline_review (mock) ──
    review = await pipeline_review(build, mock=True)
    assert review.model == "mock"
    assert len(review.review.get("chains", [])) > 0
    assert review.merged_package is not build.package

    # ── 3. pipeline_infer ──
    infer = await pipeline_infer(build, review)
    assert len(infer.beliefs) > 0
    assert infer.bp_run_id
    for name, belief in infer.beliefs.items():
        assert 0.0 <= belief <= 1.0, f"Invalid belief for {name}: {belief}"

    # ── 4. pipeline_publish ──
    db_path = str(tmp_path / "lancedb")
    result = await pipeline_publish(build, review, infer, db_path=db_path)
    assert result.package_id == build.package.name
    assert result.stats["knowledge_items"] > 0
    assert result.stats["chains"] > 0
    assert result.stats["factors"] > 0
    assert result.stats["probabilities"] > 0

    # ── 5. Verify storage ──
    config = StorageConfig(
        lancedb_path=db_path,
        graph_backend="kuzu",
        kuzu_path=f"{db_path}/kuzu",
    )
    mgr = StorageManager(config)
    await mgr.initialize()

    try:
        # Package exists
        pkg = await mgr.content_store.get_package(build.package.name)
        assert pkg is not None
        assert len(pkg.modules) >= 2

        # Knowledge items match expected count
        knowledge_items = await mgr.content_store.list_knowledge()
        assert len(knowledge_items) == result.stats["knowledge_items"]

        # Chains exist with at least one step each
        chains = await mgr.content_store.list_chains()
        assert len(chains) == result.stats["chains"]
        for chain in chains:
            assert len(chain.steps) > 0

        # Graph IR factors exist
        factors = await mgr.content_store.list_factors()
        assert len(factors) == result.stats["factors"]
        assert len(factors) > 0

        # At least some chains have probabilities
        has_probabilities = False
        for chain in chains:
            probs = await mgr.content_store.get_probability_history(chain.chain_id)
            if probs:
                has_probabilities = True
                for prob in probs:
                    assert 0.0 < prob.value <= 1.0
        assert has_probabilities

        # Submission artifact exists
        artifact = await mgr.content_store.get_submission_artifact(build.package.name, "in-memory")
        assert artifact is not None
        assert artifact.package_name == build.package.name
        assert len(artifact.source_files) >= 2
    finally:
        await mgr.close()
