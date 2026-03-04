"""CommitEngine: orchestrates the 3-step commit workflow.

submit  -> validate + dedup + save as pending_review
review  -> pipeline-based async review -> mark reviewed/rejected
merge   -> apply operations to storage -> mark merged
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from libs.models import (
    BPResults,
    Commit,
    CommitRequest,
    CommitResponse,
    DetailedReviewResult,
    JoinTreeResults,
    MergeResult,
    NNCandidate,
    OperationReviewDetail,
)
from libs.storage.manager import StorageManager
from services.job_manager.manager import JobManager
from services.job_manager.models import Job, JobStatus, JobType
from services.review_pipeline.base import Pipeline
from services.review_pipeline.context import PipelineContext

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
        pipeline: Pipeline | None = None,
        job_manager: JobManager | None = None,
        search_engine=None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._storage = storage
        self._store = commit_store
        self._validator = Validator()
        self._reviewer = Reviewer(llm_client=llm_client)
        self._merger = Merger(storage)
        self._pipeline = pipeline
        self.job_manager = job_manager or JobManager()
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

    async def submit_review(self, commit_id: str) -> Job:
        """Submit an async review job for a commit. Returns the Job."""
        commit = await self._store.get(commit_id)
        if not commit:
            raise ValueError(f"Commit {commit_id} not found")
        if commit.status != "pending_review":
            raise ValueError(
                f"Commit {commit_id} is not pending review (status={commit.status})"
            )

        async def run_review(job_id: str) -> dict:
            ctx = PipelineContext.from_commit_request(
                CommitRequest(message=commit.message, operations=commit.operations)
            )
            if self._pipeline:
                ctx = await self._pipeline.execute(ctx)
            result = self._build_review_result(ctx)
            await self._store.update(
                commit_id,
                status="reviewed",
                review_results=result.model_dump(),
                updated_at=datetime.now(timezone.utc),
            )
            return result.model_dump()

        job = await self.job_manager.submit(JobType.REVIEW, commit_id, run_review)
        await self._store.update(commit_id, review_job_id=job.job_id)
        return job

    def _build_review_result(self, context: PipelineContext) -> DetailedReviewResult:
        """Build DetailedReviewResult from pipeline context."""
        operations = []
        for i, node_info in enumerate(context.new_nodes):
            nn_cands = [
                NNCandidate(node_id=str(nid), similarity=sim)
                for nid, sim in context.nn_results.get(i, [])
            ]
            cc_trees = [
                t.model_dump() for t in context.cc_join_trees if t.source_node_index == i
            ]
            cp_trees = [
                t.model_dump() for t in context.cp_join_trees if t.source_node_index == i
            ]
            detail = OperationReviewDetail(
                op_index=node_info.op_index,
                verdict="pass",
                embedding_generated=i in context.embeddings,
                nn_candidates=nn_cands,
                join_trees=JoinTreeResults(cc=cc_trees, cp=cp_trees),
                contradictions=[],
                overlaps=[],
            )
            operations.append(detail)

        bp = None
        if context.bp_results:
            bp = BPResults(
                belief_updates={str(k): v for k, v in context.bp_results.items()},
                iterations=0,
                converged=True,
                affected_nodes=[str(k) for k in context.bp_results],
            )

        return DetailedReviewResult(
            overall_verdict="pass",
            operations=operations,
            bp_results=bp,
        )

    async def review(self, commit_id: str, depth: str = "standard") -> dict:
        """Synchronous-style review for backward compatibility.

        Submits review job and waits for completion. Adds ``approved`` key
        to the result for backward compatibility with code that expects the
        old :class:`ReviewResult` format.
        """
        commit = await self._store.get(commit_id)
        if not commit:
            return {"error": "commit not found"}

        job = await self.submit_review(commit_id)
        # Wait for job completion
        for _ in range(100):
            status = await self.job_manager.get_status(job.job_id)
            if status and status.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            await asyncio.sleep(0.01)

        result = await self.job_manager.get_result(job.job_id)
        if not result:
            return {"error": "review failed"}
        # Backward compat: old ReviewResult had "approved" field
        result.setdefault("approved", result.get("overall_verdict") == "pass")
        return result

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
