from services.job_manager.models import Job, JobStatus, JobType


def test_job_creation():
    job = Job(job_type=JobType.REVIEW, reference_id="commit_abc123")
    assert job.status == JobStatus.PENDING
    assert job.job_id.startswith("job_")
    assert job.reference_id == "commit_abc123"
    assert job.progress == {}
    assert job.result is None


def test_job_status_transitions():
    job = Job(job_type=JobType.REVIEW, reference_id="x")
    job.status = JobStatus.RUNNING
    assert job.status == JobStatus.RUNNING
    job.status = JobStatus.COMPLETED
    assert job.status == JobStatus.COMPLETED
