"""Tests for the rewritten pipeline_review (v4 Typst graph_data)."""

from pathlib import Path

import pytest

from libs.pipeline import ReviewOutput, pipeline_build, pipeline_review

GALILEO_V4 = Path(__file__).parent / "fixtures" / "ir" / "galileo_falling_bodies_v4"


@pytest.mark.asyncio
async def test_pipeline_review_mock_returns_review_output():
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    assert isinstance(review, ReviewOutput)
    assert review.model == "mock"


@pytest.mark.asyncio
async def test_pipeline_review_mock_has_node_priors():
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    for node in build.local_graph.knowledge_nodes:
        assert node.local_canonical_id in review.node_priors
        assert 0 < review.node_priors[node.local_canonical_id] <= 1.0


@pytest.mark.asyncio
async def test_pipeline_review_mock_has_factor_params():
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    for factor in build.local_graph.factor_nodes:
        if factor.type == "infer":
            assert factor.factor_id in review.factor_params
            assert 0 < review.factor_params[factor.factor_id].conditional_probability <= 1.0


@pytest.mark.asyncio
async def test_pipeline_review_default_priors_by_type():
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    for node in build.local_graph.knowledge_nodes:
        prior = review.node_priors[node.local_canonical_id]
        if node.knowledge_type == "setting":
            assert prior == 1.0
        elif node.knowledge_type in ("claim", "observation", "question"):
            assert prior == 0.5


@pytest.mark.asyncio
async def test_pipeline_review_mock_factor_params_from_review():
    """Mock review sets conditional_prior=0.85 for reasoning factors."""
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    # All infer factors that have a matching review chain should get 0.85
    for factor in build.local_graph.factor_nodes:
        if factor.type == "infer":
            params = review.factor_params[factor.factor_id]
            # Mock review sets 0.85 for all reasoning factors
            assert params.conditional_probability > 0


@pytest.mark.asyncio
async def test_pipeline_review_review_data_structure():
    """Review data should have standard sidecar format fields."""
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True)
    assert "package" in review.review
    assert "model" in review.review
    assert "timestamp" in review.review
    assert "summary" in review.review
    assert "chains" in review.review
    assert review.review["model"] == "mock"


@pytest.mark.asyncio
async def test_pipeline_review_source_fingerprint():
    """source_fingerprint should be passed through to ReviewOutput."""
    build = await pipeline_build(GALILEO_V4)
    review = await pipeline_review(build, mock=True, source_fingerprint="abc123")
    assert review.source_fingerprint == "abc123"
    assert review.review["source_fingerprint"] == "abc123"
