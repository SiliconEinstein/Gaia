"""Inference — trigger and query BP runs."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from gaia.libs.models.parameterization import ResolutionPolicy
from gaia.lkm.pipelines.run_global_bp import run_global_bp
from gaia.lkm.services import deps as deps_module

router = APIRouter(tags=["inference"])


class RunBPRequest(BaseModel):
    resolution_policy: str = "latest"
    source_id: str | None = None


@router.post("/inference/run")
async def trigger_bp(req: RunBPRequest):
    if req.resolution_policy == "latest":
        policy = ResolutionPolicy(strategy="latest")
    else:
        policy = ResolutionPolicy(strategy="source", source_id=req.source_id)

    belief_state = await run_global_bp(storage=deps_module.deps.storage, policy=policy)
    return belief_state.model_dump(mode="json")


@router.get("/beliefs")
async def list_beliefs(limit: int = 10):
    states = await deps_module.deps.storage.get_belief_states(limit=limit)
    return [s.model_dump(mode="json") for s in states]
