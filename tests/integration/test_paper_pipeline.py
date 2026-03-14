"""E2E test: XML → YAML → build → review(mock) → infer → publish → verify storage."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure repo root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


PAPER_DIR = Path("tests/fixtures/papers/10.1038332139a0_1988_Natu")


@pytest.mark.asyncio
async def test_paper_e2e_pipeline(tmp_path):
    """Full pipeline: XML → YAML → build → review(mock) → infer → publish → verify."""
    from scripts.xml_to_yaml import convert_paper, write_package

    from libs.pipeline import pipeline_build, pipeline_infer, pipeline_publish, pipeline_review
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager

    # ── 1. Convert XML fixture to YAML ──
    data = convert_paper(PAPER_DIR)
    assert data is not None, f"No combine XMLs in {PAPER_DIR}"

    yaml_dir = tmp_path / "yaml_packages"
    pkg_dir = write_package(data, yaml_dir)
    assert (pkg_dir / "package.yaml").exists()
    assert (pkg_dir / "setting.yaml").exists()
    assert (pkg_dir / "reasoning.yaml").exists()

    # ── 2. pipeline_build ──
    build = await pipeline_build(pkg_dir)
    assert build.package.name == data["slug"]
    assert len(build.package.loaded_modules) == 2
    assert len(build.markdown) > 0
    assert len(build.raw_graph.knowledge_nodes) > 0
    assert len(build.local_graph.factor_nodes) > 0
    assert len(build.source_files) == 3  # package.yaml, setting.yaml, reasoning.yaml

    # ── 3. pipeline_review (mock) ──
    review = await pipeline_review(build, mock=True)
    assert review.model == "mock"
    assert len(review.review.get("chains", [])) > 0
    assert review.merged_package is not build.package  # deep copy

    # ── 4. pipeline_infer ──
    infer = await pipeline_infer(build, review)
    assert len(infer.beliefs) > 0
    assert infer.bp_run_id
    # All beliefs should be valid probabilities
    for name, belief in infer.beliefs.items():
        assert 0.0 <= belief <= 1.0, f"Invalid belief for {name}: {belief}"

    # ── 5. pipeline_publish ──
    db_path = str(tmp_path / "lancedb")
    result = await pipeline_publish(build, review, infer, db_path=db_path)
    assert result.package_id == data["slug"]
    assert result.stats["knowledge_items"] > 0
    assert result.stats["chains"] > 0
    assert result.stats["factors"] > 0
    assert result.stats["probabilities"] > 0

    # ── 6. Verify storage ──
    config = StorageConfig(
        lancedb_path=db_path,
        graph_backend="kuzu",
        kuzu_path=f"{db_path}/kuzu",
    )
    mgr = StorageManager(config)
    await mgr.initialize()

    try:
        # 6a. Package exists
        pkg = await mgr.content_store.get_package(data["slug"])
        assert pkg is not None
        assert len(pkg.modules) == 2

        # 6b. Knowledge items match expected count
        knowledge_items = await mgr.content_store.list_knowledge()
        assert len(knowledge_items) == result.stats["knowledge_items"]

        # 6c. Chains exist with correct count
        chains = await mgr.content_store.list_chains()
        assert len(chains) == result.stats["chains"]
        # Each chain should have at least one step
        for chain in chains:
            assert len(chain.steps) > 0

        # 6d. Factors exist (from Graph IR, not fallback)
        factors = await mgr.content_store.list_factors()
        assert len(factors) == result.stats["factors"]
        assert len(factors) > 0  # Graph IR factors, not empty

        # 6e. Probabilities exist for chain steps
        has_probabilities = False
        for chain in chains:
            probs = await mgr.content_store.get_probability_history(chain.chain_id)
            if probs:
                has_probabilities = True
                for prob in probs:
                    assert 0.0 < prob.value <= 1.0
        assert has_probabilities, "Expected at least some chains to have probabilities"

        # 6f. Submission artifact exists
        artifact = await mgr.content_store.get_submission_artifact(data["slug"], "in-memory")
        assert artifact is not None
        assert artifact.package_name == data["slug"]
        assert len(artifact.source_files) == 3
    finally:
        await mgr.close()
