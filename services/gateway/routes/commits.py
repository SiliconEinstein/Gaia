from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from libs.models import CommitRequest, CommitResponse, MergeResult
from services.gateway.deps import deps

router = APIRouter(prefix="/commits", tags=["commits"])


class ReviewRequest(BaseModel):
    depth: str = "standard"


class MergeRequest(BaseModel):
    force: bool = False


@router.get("")
async def list_commits():
    commits = await deps.commit_engine.list_commits()
    return [c.model_dump() for c in commits]


@router.post("", response_model=CommitResponse)
async def submit_commit(request: CommitRequest):
    return await deps.commit_engine.submit(request)


@router.get("/{commit_id}")
async def get_commit(commit_id: str):
    commit = await deps.commit_engine.get_commit(commit_id)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    return commit.model_dump()


@router.post("/{commit_id}/review")
async def review_commit(commit_id: str, request: ReviewRequest = ReviewRequest()):
    commit = await deps.commit_engine.get_commit(commit_id)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    result = await deps.commit_engine.review(commit_id, depth=request.depth)
    return result


@router.post("/{commit_id}/merge", response_model=MergeResult)
async def merge_commit(commit_id: str, request: MergeRequest = MergeRequest()):
    commit = await deps.commit_engine.get_commit(commit_id)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    return await deps.commit_engine.merge(commit_id, force=request.force)
