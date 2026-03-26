"""Knowledge retrieval."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gaia.lkm.services import deps as deps_module

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge/{node_id}")
async def get_knowledge(node_id: str):
    node = await deps_module.deps.storage.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node.model_dump(mode="json")


@router.get("/knowledge/{node_id}/beliefs")
async def get_beliefs(node_id: str):
    states = await deps_module.deps.storage.get_belief_states(limit=10)
    beliefs = []
    for s in states:
        if node_id in s.beliefs:
            beliefs.append(
                {
                    "bp_run_id": s.bp_run_id,
                    "belief": s.beliefs[node_id],
                    "converged": s.converged,
                    "created_at": s.created_at.isoformat(),
                }
            )
    return beliefs
