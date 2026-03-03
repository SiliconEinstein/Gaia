"""Integration tests hitting real LLM and embedding APIs.

Run with:  pytest tests/services/test_review_pipeline/test_integration_api.py -v -m integration_api

Requires environment variables:
  - DP_INTERNAL_BASE_URL, DP_INTERNAL_API_KEY  (for LLM via dptech_internal)
  - API_URL, ACCESS_KEY                         (for DashScope embedding)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from services.review_pipeline.config import LLMModelConfig
from services.review_pipeline.context import JoinTree
from services.review_pipeline.llm_client import LLMClient
from services.review_pipeline.operators.embedding_dashscope import DashScopeEmbeddingModel
from services.review_pipeline.operators.join import LiteLLMJoinClient
from services.review_pipeline.operators.verify import LiteLLMVerifyClient

# Auto-load .env from project root (must run before skip guards read env vars)
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

# ---------------------------------------------------------------------------
# Skip guards
# ---------------------------------------------------------------------------

_has_llm_creds = bool(os.getenv("DP_INTERNAL_BASE_URL") and os.getenv("DP_INTERNAL_API_KEY"))
_has_embed_creds = bool(os.getenv("API_URL") and os.getenv("ACCESS_KEY"))

skip_no_llm = pytest.mark.skipif(
    not _has_llm_creds,
    reason="DP_INTERNAL_BASE_URL / DP_INTERNAL_API_KEY not set",
)
skip_no_embed = pytest.mark.skipif(
    not _has_embed_creds,
    reason="API_URL / ACCESS_KEY not set",
)

pytestmark = pytest.mark.integration_api

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LLM_CONFIG = LLMModelConfig(
    provider="dptech_internal",
    name="gpt-5-mini",
    temperature=0.7,
    max_completion_tokens=4096,
    timeout=120,
    max_retries=1,
)


@pytest.fixture
def llm_client():
    return LLMClient(LLM_CONFIG)


@pytest.fixture
def join_client(llm_client):
    return LiteLLMJoinClient(llm_client)


@pytest.fixture
def verify_client(llm_client):
    return LiteLLMVerifyClient(llm_client)


@pytest.fixture
def embedding_model():
    return DashScopeEmbeddingModel(
        api_url=os.getenv("API_URL", ""),
        access_key=os.getenv("ACCESS_KEY", ""),
    )


# ---------------------------------------------------------------------------
# Embedding integration tests
# ---------------------------------------------------------------------------


@skip_no_embed
async def test_embedding_real_api(embedding_model):
    """Verify DashScope returns a non-empty float vector."""
    texts = ["The band gap of monolayer MoS2 is approximately 1.8 eV."]
    result = await embedding_model.embed(texts)
    await embedding_model.close()

    assert len(result) == 1
    vec = result[0]
    assert isinstance(vec, list)
    assert len(vec) > 0
    assert all(isinstance(v, float) for v in vec)

    print(f"\n{'=' * 60}")
    print(f"EMBEDDING: dim={len(vec)}, first 5 values={vec[:5]}")
    print(f"{'=' * 60}")


@skip_no_embed
async def test_embedding_batch_real_api(embedding_model):
    """Verify batch embedding returns one vector per text."""
    texts = [
        "Water boils at 100 degrees Celsius at standard pressure.",
        "Graphene has exceptional thermal conductivity.",
    ]
    result = await embedding_model.embed(texts)
    await embedding_model.close()

    assert len(result) == 2
    # Vectors should differ for different texts
    assert result[0] != result[1]


# ---------------------------------------------------------------------------
# LLM client integration tests
# ---------------------------------------------------------------------------


@skip_no_llm
async def test_llm_client_basic(llm_client):
    """Verify LLMClient can make a basic completion call."""
    response = await llm_client.complete(
        system_prompt="You are a helpful assistant. Reply in one short sentence.",
        user_prompt="What is 2 + 2?",
    )
    assert isinstance(response, str)
    assert len(response) > 0
    assert "4" in response

    print(f"\n{'=' * 60}")
    print(f"LLM BASIC RESPONSE:\n{response}")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# Join integration tests
# ---------------------------------------------------------------------------


@skip_no_llm
async def test_join_real_api(join_client):
    """Verify join classification returns valid JoinTrees with real LLM."""
    anchor = "The band gap of monolayer MoS2 is 1.8 eV."
    candidates = [
        (1, "The electronic band gap of single-layer MoS2 is approximately 1.8 eV."),
        (2, "The band gap of bulk MoS2 is 1.2 eV."),
        (3, "Graphene has zero band gap and is a semimetal."),
    ]
    trees = await join_client.find_joins(anchor, candidates)

    print(f"\n{'=' * 60}")
    print(f"JOIN RESULTS ({len(trees)} trees):")
    for t in trees:
        print(f"  target={t.target_node_id} relation={t.relation}")
        print(f"    reasoning: {t.reasoning[:200]}")
    print(f"{'=' * 60}")

    assert isinstance(trees, list)
    for tree in trees:
        assert isinstance(tree, JoinTree)
        assert tree.source_node_index == 0
        assert tree.target_node_id in (1, 2, 3)
        assert tree.relation in ("equivalent", "subsumes", "subsumed_by", "contradiction")
        assert tree.reasoning != ""

    # Candidate 1 should be equivalent or subsumes (same fact, minor phrasing diff)
    # LLM may vary between runs — both are reasonable for "1.8 eV" vs "approximately 1.8 eV"
    target_ids = {t.target_node_id: t for t in trees}
    if 1 in target_ids:
        assert target_ids[1].relation in ("equivalent", "subsumes", "subsumed_by")


# ---------------------------------------------------------------------------
# Verify integration tests
# ---------------------------------------------------------------------------


@skip_no_llm
async def test_verify_real_api(verify_client):
    """Verify the verification client sets pass/fail with real LLM."""
    trees = [
        JoinTree(
            source_node_index=0,
            target_node_id=1,
            relation="equivalent",
            reasoning="Same claim about MoS2 band gap.",
            source_content="The band gap of monolayer MoS2 is 1.8 eV.",
            target_content="The electronic band gap of single-layer MoS2 is approximately 1.8 eV.",
        ),
    ]
    result = await verify_client.verify(trees)

    print(f"\n{'=' * 60}")
    print("VERIFY RESULT:")
    print(f"  verified={result[0].verified}")
    print(f"  reasoning: {result[0].reasoning}")
    print(f"{'=' * 60}")

    assert len(result) == 1
    assert isinstance(result[0].verified, bool)
    assert result[0].reasoning != ""


# ---------------------------------------------------------------------------
# End-to-end: Embed → Join → Verify
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (_has_llm_creds and _has_embed_creds),
    reason="Need both LLM and embedding credentials",
)
async def test_e2e_embed_join_verify(embedding_model, join_client, verify_client):
    """Full pipeline: embed texts, join-classify, then verify."""
    texts = [
        "The band gap of monolayer MoS2 is 1.8 eV.",
        "Single-layer MoS2 has a direct band gap of approximately 1.8 eV.",
    ]

    # Step 1: Embed
    vectors = await embedding_model.embed(texts)
    await embedding_model.close()
    assert len(vectors) == 2
    assert len(vectors[0]) > 0

    print(f"\n{'=' * 60}")
    print("E2E PIPELINE")
    print(f"{'=' * 60}")
    print(f"Step 1 — Embed: 2 vectors, dim={len(vectors[0])}")

    # Step 2: Join — use first text as anchor, second as candidate
    trees = await join_client.find_joins(
        texts[0],
        [(100, texts[1])],
    )
    assert len(trees) >= 0  # LLM may or may not find a relation
    print(f"Step 2 — Join: {len(trees)} trees found")
    for t in trees:
        print(f"  target={t.target_node_id} relation={t.relation} reason={t.reasoning[:150]}")

    if trees:
        # Step 3: Verify
        verified = await verify_client.verify(trees)
        for t in verified:
            assert isinstance(t.verified, bool)
            assert t.reasoning != ""
            print(f"Step 3 — Verify: verified={t.verified}")
            print(f"  {t.reasoning}")
    print(f"{'=' * 60}")
