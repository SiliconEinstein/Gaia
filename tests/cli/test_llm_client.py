"""Tests for LLM client used in gaia review."""

from cli.llm_client import MockReviewClient, ReviewClient


def test_mock_client_returns_valid_review():
    """MockReviewClient should return a valid review dict from Markdown chain_data."""
    client = MockReviewClient()
    chain_data = {
        "name": "drag_prediction_chain",
        "markdown": (
            "## drag_prediction_chain (deduction)\n\n"
            "**Premise:** heavier_falls_faster (claim, prior=0.7)\n"
            "> 重的物体比轻的物体下落更快。\n\n"
            "**Step 2 — deduce_drag_effect** (prior=0.93)\n\n"
            "在思想实验中...\n\n"
            "- Evidence: heavier_falls_faster (claim, prior=0.7)\n"
            "- Context: thought_experiment_env (setting)\n\n"
            "**Conclusion:** tied_pair_slower_than_heavy (claim, prior=0.5)\n"
        ),
    }
    result = client.review_chain(chain_data)
    assert "chain" in result
    assert result["chain"] == "drag_prediction_chain"
    assert "steps" in result
    assert len(result["steps"]) >= 1
    step = result["steps"][0]
    assert "step" in step
    assert "assessment" in step
    assert "suggested_prior" in step


def test_mock_client_preserves_existing_priors():
    """MockReviewClient should parse priors from Markdown step headers."""
    client = MockReviewClient()
    chain_data = {
        "name": "test_chain",
        "markdown": (
            "## test_chain (deduction)\n\n"
            "**Step 2 — some_action** (prior=0.85)\n\n"
            "Some rendered text.\n"
        ),
    }
    result = client.review_chain(chain_data)
    step = result["steps"][0]
    assert step["suggested_prior"] == 0.85


def test_review_client_interface():
    """ReviewClient should have a review_chain method."""
    client = ReviewClient(model="test")
    assert hasattr(client, "review_chain")


async def test_mock_areview_chain():
    """MockReviewClient.areview_chain should return same structure as sync."""
    client = MockReviewClient()
    chain_data = {
        "name": "test_chain",
        "markdown": (
            "## test_chain (deduction)\n\n"
            "**Step 2 — some_action** (prior=0.85)\n\n"
            "Some rendered text.\n"
        ),
    }
    result = await client.areview_chain(chain_data)
    assert result["chain"] == "test_chain"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["suggested_prior"] == 0.85


def test_prompt_includes_markdown():
    """Prompt should include the Markdown chain section."""
    client = ReviewClient(model="test")
    chain_data = {
        "name": "contradiction_chain",
        "markdown": "## contradiction_chain (contradiction)\n\n**Step 2** (prior=0.97)\n",
    }
    prompt = client._build_prompt(chain_data)
    assert "## contradiction_chain (contradiction)" in prompt
    assert "Review this reasoning chain:" in prompt
    assert "YAML document" in prompt


def test_prompt_fallback_without_markdown():
    """Prompt should fall back gracefully when markdown key is absent."""
    client = ReviewClient(model="test")
    chain_data = {"name": "old_chain"}
    prompt = client._build_prompt(chain_data)
    assert "Review: old_chain" in prompt
