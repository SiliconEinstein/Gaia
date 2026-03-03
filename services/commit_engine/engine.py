"""CommitEngine: orchestrates the 3-step commit workflow.

submit  -> validate + dedup + save as pending_review
review  -> LLM review -> mark reviewed/rejected
merge   -> apply operations to storage -> mark merged
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from libs.models import Commit, CommitRequest, CommitResponse, MergeResult
from libs.storage.manager import StorageManager
from .merger import Merger
from .reviewer import LLMClient, Reviewer
from .store import CommitStore
from .validator import Validator


class CommitEngine:
    """Orchestrates the full commit lifecycle: submit -> review -> merge."""

    def __init__(
        self,
        storage: StorageManager,
        commit_store: CommitStore,
        search_engine=None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._storage = storage
        self._store = commit_store
        self._validator = Validator()
        self._reviewer = Reviewer(llm_client=llm_client)
        self._merger = Merger(storage)
        self._search_engine = search_engine

    # ------------------------------------------------------------------
    # Step 1: Submit
    # ------------------------------------------------------------------

    async def submit(self, request: CommitRequest) -> CommitResponse:
        """Validate operations, save commit, and return response.

        If validation fails, the commit is saved with status ``rejected``.
        Otherwise it is saved as ``pending_review``.
        """
        results = await self._validator.validate(request.operations)
        has_errors = any(not r.valid for r in results)

        now = datetime.now(timezone.utc)
        commit = Commit(
            commit_id=str(uuid.uuid4()),
            message=request.message,
            operations=request.operations,
            status="rejected" if has_errors else "pending_review",
            check_results={"validations": [r.model_dump() for r in results]},
            created_at=now,
            updated_at=now,
        )
        await self._store.save(commit)

        return CommitResponse(
            commit_id=commit.commit_id,
            status=commit.status,
            check_results=commit.check_results,
        )

    # ------------------------------------------------------------------
    # Step 2: Review
    # ------------------------------------------------------------------

    async def review(self, commit_id: str, depth: str = "standard") -> dict:
        """Run LLM review on a commit and update its status.

        Returns the review result as a dict, or an error dict if the commit
        is not found.
        """
        commit = await self._store.get(commit_id)
        if not commit:
            return {"error": "commit not found"}

        result = await self._reviewer.review(commit, depth=depth)
        new_status = "reviewed" if result.approved else "rejected"

        await self._store.update(
            commit_id,
            status=new_status,
            review_results=result.model_dump(),
            updated_at=datetime.now(timezone.utc),
        )
        return result.model_dump()

    # ------------------------------------------------------------------
    # Step 3: Merge
    # ------------------------------------------------------------------

    async def merge(self, commit_id: str, force: bool = False) -> MergeResult:
        """Apply commit operations to storage.

        The commit must have status ``reviewed`` unless *force* is ``True``.
        """
        commit = await self._store.get(commit_id)
        if not commit:
            return MergeResult(success=False, errors=["commit not found"])

        if not force and commit.status != "reviewed":
            return MergeResult(
                success=False,
                errors=[f"commit status is {commit.status}, must be reviewed"],
            )

        result = await self._merger.merge(commit)

        if result.success:
            await self._store.update(
                commit_id,
                status="merged",
                merge_results=result.model_dump(),
                updated_at=datetime.now(timezone.utc),
            )
        return result

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_commit(self, commit_id: str) -> Commit | None:
        """Retrieve a commit by its ID."""
        return await self._store.get(commit_id)

    async def list_commits(self) -> list[Commit]:
        """List all commits."""
        return await self._store.list_commits()
