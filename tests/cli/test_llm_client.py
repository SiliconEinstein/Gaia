"""Tests for the review client."""

from cli.llm_client import MockReviewClient, ReviewClient


def test_mock_review_uses_chain_scoped_step_ids():
    """Mock review should produce step IDs like 'chain_name.N'."""
    md = """### Chain: test_chain [chain:test_chain] (deduction)

**[step:test_chain.2]** (prior=0.9)

**Direct references:**
> **[claim] some_claim** (prior=0.8)
> Some content.

**Reasoning:**
> Some reasoning text.

**Conclusion:** [claim] result (prior=0.5)
> Result content.
"""
    client = MockReviewClient()
    result = client.review_chain({"name": "test_chain", "markdown": md})

    assert result["chain"] == "test_chain"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["step"] == "test_chain.2"
    assert result["steps"][0]["conditional_prior"] == 0.9
    assert result["steps"][0]["weak_points"] == []


def test_mock_review_produces_summary():
    """Mock review should include a summary field."""
    md = """### Chain: c1 [chain:c1] (deduction)
**[step:c1.2]** (prior=0.85)
**Reasoning:**
> text
**Conclusion:** [claim] x (prior=0.5)
"""
    client = MockReviewClient()
    result = client.review_package({"package": "test_pkg", "markdown": md})

    assert "summary" in result
    assert "chains" in result


def test_mock_review_extracts_multiple_chains():
    """Mock review should extract steps from multiple chains."""
    md = """### Chain: chain_a [chain:chain_a] (deduction)
**[step:chain_a.2]** (prior=0.8)
**Reasoning:** > text
**Conclusion:** [claim] x (prior=0.5)

### Chain: chain_b [chain:chain_b] (deduction)
**[step:chain_b.2]** (prior=0.95)
**[step:chain_b.3]** (prior=0.7)
**Reasoning:** > text
**Conclusion:** [claim] y (prior=0.5)
"""
    client = MockReviewClient()
    result = client.review_package({"package": "test_pkg", "markdown": md})

    assert len(result["chains"]) == 2
    chain_names = {c["chain"] for c in result["chains"]}
    assert chain_names == {"chain_a", "chain_b"}
    chain_b = next(c for c in result["chains"] if c["chain"] == "chain_b")
    assert len(chain_b["steps"]) == 2


def test_mock_review_chain_returns_empty_for_old_format():
    """Mock review_chain should return empty steps for old-format markdown."""
    md = (
        "## test_chain (deduction)\n\n"
        "**Step 2 — some_action** (prior=0.85)\n\n"
        "Some rendered text.\n"
    )
    client = MockReviewClient()
    result = client.review_chain({"name": "test_chain", "markdown": md})
    assert result["chain"] == "test_chain"
    assert result["steps"] == []


def test_review_client_interface():
    """ReviewClient should have review_chain and review_package methods."""
    client = ReviewClient(model="test")
    assert hasattr(client, "review_chain")
    assert hasattr(client, "review_package")


def test_review_client_loads_system_prompt():
    """ReviewClient should load the system prompt from file."""
    client = ReviewClient(model="test")
    assert "scientific reasoning reviewer" in client._system_prompt


async def test_mock_areview_chain():
    """MockReviewClient.areview_chain should return same structure as sync."""
    md = """### Chain: test_chain [chain:test_chain] (deduction)
**[step:test_chain.2]** (prior=0.85)
**Reasoning:**
> Some rendered text.
**Conclusion:** [claim] result (prior=0.5)
"""
    client = MockReviewClient()
    result = await client.areview_chain({"name": "test_chain", "markdown": md})
    assert result["chain"] == "test_chain"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["conditional_prior"] == 0.85


async def test_mock_areview_package():
    """MockReviewClient.areview_package should return same structure as sync."""
    md = """### Chain: c1 [chain:c1] (deduction)
**[step:c1.2]** (prior=0.9)
**Reasoning:** > text
**Conclusion:** [claim] x (prior=0.5)
"""
    client = MockReviewClient()
    result = await client.areview_package({"package": "test_pkg", "markdown": md})
    assert "summary" in result
    assert "chains" in result
    assert len(result["chains"]) == 1


def test_review_client_parses_flat_step_map_response():
    """Real-model flat YAML keyed by step ID should normalize into chain entries."""
    client = ReviewClient(model="test")
    raw = """
summary: Overall package review.
drag_prediction_chain.2:
  weak_points:
    - proposition: The tethered system must fall more slowly.
      classification: direct
  conditional_prior: 0.6
verdict_chain.2:
  weak_points:
    - proposition: The contradiction really refutes the doctrine.
      classification: direct
  conditional_prior: 0.7
"""
    result = client._parse_response(raw)
    assert result["summary"] == "Overall package review."
    assert len(result["chains"]) == 2
    by_name = {chain["chain"]: chain for chain in result["chains"]}
    assert by_name["drag_prediction_chain"]["steps"][0]["step"] == "drag_prediction_chain.2"
    assert by_name["drag_prediction_chain"]["steps"][0]["conditional_prior"] == 0.6
    assert by_name["verdict_chain"]["steps"][0]["step"] == "verdict_chain.2"


def test_review_client_parses_fenced_yaml():
    """Responses wrapped in ```yaml fences should still be parsed."""
    client = ReviewClient(model="test")
    raw = """```yaml
chains:
  - chain: synthesis_chain
    steps:
      - step: synthesis_chain.2
        conditional_prior: 0.85
        weak_points: []
        explanation: ok
```"""
    result = client._parse_response(raw)
    assert len(result["chains"]) == 1
    assert result["chains"][0]["chain"] == "synthesis_chain"
    assert result["chains"][0]["steps"][0]["step"] == "synthesis_chain.2"
