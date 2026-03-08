"""Tests for LLM client used in gaia review."""

from cli.llm_client import MockReviewClient, ReviewClient


def test_mock_client_returns_valid_review():
    """MockReviewClient should return a valid review dict for any chain."""
    client = MockReviewClient()
    chain_data = {
        "name": "drag_prediction_chain",
        "steps": [
            {"step": 2, "action": "deduce_drag_effect", "prior": 0.93,
             "args": [
                 {"ref": "heavier_falls_faster", "dependency": "direct"},
                 {"ref": "thought_experiment_env", "dependency": "indirect"},
             ]},
        ],
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
    """MockReviewClient should echo back priors and dependency types."""
    client = MockReviewClient()
    chain_data = {
        "name": "test_chain",
        "steps": [
            {"step": 2, "action": "some_action", "prior": 0.85,
             "args": [{"ref": "claim_a", "dependency": "direct"}]},
        ],
    }
    result = client.review_chain(chain_data)
    step = result["steps"][0]
    assert step["suggested_prior"] == 0.85
    assert step["dependencies"][0]["suggested"] == "direct"


def test_review_client_interface():
    """ReviewClient should have a review_chain method."""
    client = ReviewClient(model="test")
    assert hasattr(client, "review_chain")


async def test_mock_areview_chain():
    """MockReviewClient.areview_chain should return same structure as sync."""
    client = MockReviewClient()
    chain_data = {
        "name": "test_chain",
        "steps": [
            {"step": 2, "action": "some_action", "prior": 0.85,
             "args": [{"ref": "claim_a", "dependency": "direct"}]},
        ],
    }
    result = await client.areview_chain(chain_data)
    assert result["chain"] == "test_chain"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["suggested_prior"] == 0.85


def test_prompt_includes_chain_type():
    """Prompt should include chain type when context is provided."""
    client = ReviewClient(model="test")
    chain_data = {
        "name": "contradiction_chain",
        "steps": [{"step": 2, "action": "expose", "args": [], "prior": 0.97}],
        "context": {"edge_type": "contradiction", "premise_refs": [], "conclusion_refs": []},
    }
    prompt = client._build_prompt(chain_data)
    assert "Chain type: contradiction" in prompt


def test_prompt_shows_arg_content():
    """Prompt should display arg content, type, and prior."""
    client = ReviewClient(model="test")
    chain_data = {
        "name": "test_chain",
        "steps": [{
            "step": 2,
            "action": "deduce",
            "rendered": "test rendered",
            "prior": 0.93,
            "args": [
                {"ref": "claim_a", "dependency": "direct", "content": "Test claim content",
                 "decl_type": "claim", "prior": 0.7},
                {"ref": "env_b", "dependency": "indirect", "content": "Test setting",
                 "decl_type": "setting", "prior": None},
            ],
        }],
    }
    prompt = client._build_prompt(chain_data)
    assert "Evidence (direct):" in prompt
    assert "Context (indirect):" in prompt
    assert "claim_a" in prompt
    assert "Test claim content" in prompt
    assert "prior=0.7" in prompt


def test_prompt_handles_missing_context():
    """Prompt should work when context key is absent (backward compat)."""
    client = ReviewClient(model="test")
    chain_data = {
        "name": "old_chain",
        "steps": [{"step": 1, "action": "test", "args": []}],
    }
    prompt = client._build_prompt(chain_data)
    assert "Review this reasoning chain: old_chain" in prompt
    assert "Chain type:" not in prompt
