import pytest

from services.job_manager.models import Job, JobType
from services.job_manager.store import InMemoryJobStore


@pytest.fixture
def store():
    return InMemoryJobStore()


async def test_save_and_get(store):
    job = Job(job_type=JobType.REVIEW, reference_id="c1")
    await store.save(job)
    loaded = await store.get(job.job_id)
    assert loaded is not None
    assert loaded.job_id == job.job_id


async def test_get_missing_returns_none(store):
    assert await store.get("nonexistent") is None


async def test_update(store):
    job = Job(job_type=JobType.REVIEW, reference_id="c1")
    await store.save(job)
    job.status = "running"
    await store.update(job)
    loaded = await store.get(job.job_id)
    assert loaded.status == "running"


async def test_get_by_reference(store):
    job = Job(job_type=JobType.REVIEW, reference_id="commit_abc")
    await store.save(job)
    loaded = await store.get_by_reference("commit_abc", JobType.REVIEW)
    assert loaded is not None
    assert loaded.job_id == job.job_id
