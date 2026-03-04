"""Tests for the Reviewer with pluggable LLM interface."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from libs.models import Commit, AddEdgeOp, NewNode, NodeRef, ReviewResult
from services.commit_engine.reviewer import Reviewer, StubLLMClient, LLMClient


def _make_commit() -> Commit:
    return Commit(
        commit_id="rev-001",
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="p")],
                head=[NodeRef(node_id=1)],
                type="induction",
                reasoning=["test"],
            )
        ],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


async def test_stub_always_approves():
    client = StubLLMClient()
    result = await client.review_commit(_make_commit())
    assert result.approved is True


async def test_reviewer_with_stub():
    reviewer = Reviewer(llm_client=StubLLMClient())
    result = await reviewer.review(_make_commit())
    assert result.approved is True
    assert result.issues == []


async def test_reviewer_no_client_auto_approves():
    reviewer = Reviewer()
    result = await reviewer.review(_make_commit())
    assert result.approved is True


async def test_reviewer_with_rejecting_client():
    mock_client = AsyncMock(spec=LLMClient)
    mock_client.review_commit = AsyncMock(
        return_value=ReviewResult(approved=False, issues=["contradiction detected"])
    )
    reviewer = Reviewer(llm_client=mock_client)
    result = await reviewer.review(_make_commit())
    assert result.approved is False
    assert "contradiction detected" in result.issues


async def test_reviewer_passes_depth():
    """Verify depth parameter is stored/accessible (for future LLM use)."""
    reviewer = Reviewer(llm_client=StubLLMClient())
    # Quick review should still work
    result = await reviewer.review(_make_commit(), depth="quick")
    assert result.approved is True
    # Deep review should still work
    result = await reviewer.review(_make_commit(), depth="deep")
    assert result.approved is True
