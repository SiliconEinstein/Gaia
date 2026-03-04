"""Job persistence — in-memory for now."""

from __future__ import annotations

from services.job_manager.models import Job, JobType


class InMemoryJobStore:
    """In-memory job store."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    async def save(self, job: Job) -> None:
        self._jobs[job.job_id] = job

    async def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def update(self, job: Job) -> None:
        self._jobs[job.job_id] = job

    async def get_by_reference(self, reference_id: str, job_type: JobType) -> Job | None:
        for job in self._jobs.values():
            if job.reference_id == reference_id and job.job_type == job_type:
                return job
        return None
