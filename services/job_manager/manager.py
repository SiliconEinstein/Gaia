"""JobManager — submit, cancel, and track async jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

from services.job_manager.models import Job, JobStatus, JobType
from services.job_manager.store import InMemoryJobStore


class JobManager:
    """Manages async job lifecycle."""

    def __init__(self, store: InMemoryJobStore | None = None) -> None:
        self._store = store or InMemoryJobStore()
        self._tasks: dict[str, asyncio.Task] = {}

    async def submit(
        self,
        job_type: JobType,
        reference_id: str,
        work_fn: Callable[[str], Coroutine[Any, Any, dict]],
    ) -> Job:
        """Submit an async job. work_fn receives job_id and returns result dict."""
        job = Job(job_type=job_type, reference_id=reference_id)
        job.status = JobStatus.RUNNING
        await self._store.save(job)
        task = asyncio.create_task(self._run(job.job_id, work_fn))
        self._tasks[job.job_id] = task
        return job

    async def _run(
        self,
        job_id: str,
        work_fn: Callable[[str], Coroutine[Any, Any, dict]],
    ) -> None:
        job = await self._store.get(job_id)
        if not job:
            return
        try:
            result = await work_fn(job_id)
            job.status = JobStatus.COMPLETED
            job.result = result
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
        job.updated_at = datetime.now(timezone.utc)
        await self._store.update(job)
        self._tasks.pop(job_id, None)

    async def cancel(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            job = await self._store.get(job_id)
            if job:
                job.status = JobStatus.CANCELLED
                job.updated_at = datetime.now(timezone.utc)
                await self._store.update(job)
            return True
        return False

    async def get_status(self, job_id: str) -> Job | None:
        return await self._store.get(job_id)

    async def get_result(self, job_id: str) -> dict | None:
        job = await self._store.get(job_id)
        if job and job.status == JobStatus.COMPLETED:
            return job.result
        return None
