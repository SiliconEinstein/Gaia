"""Reviewer with pluggable LLM interface for commit review.

Phase 1 uses a StubLLMClient that always approves.
Future phases will plug in real LLM clients for semantic review.
"""

from abc import ABC, abstractmethod

from libs.models import Commit, ReviewResult


class LLMClient(ABC):
    """Abstract LLM client for review."""

    @abstractmethod
    async def review_commit(self, commit: Commit) -> ReviewResult: ...


class StubLLMClient(LLMClient):
    """Always approves. For testing and Phase 1."""

    async def review_commit(self, commit: Commit) -> ReviewResult:
        return ReviewResult(approved=True)


class Reviewer:
    """Reviews commits using a pluggable LLM client.

    If no LLM client is provided, defaults to StubLLMClient (auto-approve).
    """

    def __init__(self, llm_client: LLMClient | None = None):
        self._client = llm_client or StubLLMClient()

    async def review(self, commit: Commit, depth: str = "standard") -> ReviewResult:
        """Review a commit using LLM.

        Args:
            commit: The commit to review.
            depth: Review depth — "quick" | "standard" | "deep".
                   Reserved for future LLM-based review strategies.

        Returns:
            ReviewResult with approval status, issues, and suggestions.
        """
        return await self._client.review_commit(commit)
