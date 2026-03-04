import asyncio

import pytest

from services.job_manager.manager import JobManager
from services.job_manager.models import JobStatus, JobType
from services.job_manager.store import InMemoryJobStore


@pytest.fixture
def manager():
    return JobManager(store=InMemoryJobStore())


async def test_submit_job(manager):
    async def work(job_id: str):
        return {"answer": 42}

    job = await manager.submit(
        job_type=JobType.REVIEW,
        reference_id="commit_1",
        work_fn=work,
    )
    assert job.status == JobStatus.RUNNING
    await asyncio.sleep(0.1)
    result = await manager.get_result(job.job_id)
    assert result == {"answer": 42}


async def test_cancel_job(manager):
    async def slow_work(job_id: str):
        await asyncio.sleep(10)
        return {}

    job = await manager.submit(
        job_type=JobType.REVIEW,
        reference_id="commit_2",
        work_fn=slow_work,
    )
    cancelled = await manager.cancel(job.job_id)
    assert cancelled is True
    loaded = await manager.get_status(job.job_id)
    assert loaded.status == JobStatus.CANCELLED


async def test_get_status(manager):
    async def work(job_id: str):
        return {"done": True}

    job = await manager.submit(
        job_type=JobType.REVIEW,
        reference_id="c3",
        work_fn=work,
    )
    status = await manager.get_status(job.job_id)
    assert status is not None


async def test_failed_job(manager):
    async def failing_work(job_id: str):
        raise ValueError("something broke")

    job = await manager.submit(
        job_type=JobType.REVIEW,
        reference_id="c4",
        work_fn=failing_work,
    )
    await asyncio.sleep(0.1)
    loaded = await manager.get_status(job.job_id)
    assert loaded.status == JobStatus.FAILED
    assert "something broke" in loaded.error
