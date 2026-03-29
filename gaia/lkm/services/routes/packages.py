"""Package ingest and retrieval."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from gaia.core.local_params import LocalParameterization
from gaia.models.graph_ir import LocalCanonicalGraph
from gaia.lkm.pipelines.run_ingest import run_ingest
from gaia.lkm.services import deps as deps_module

router = APIRouter(tags=["packages"])


class IngestRequest(BaseModel):
    package_id: str
    version: str
    local_graph: LocalCanonicalGraph
    local_params: LocalParameterization | None = None


class IngestResponse(BaseModel):
    package_id: str
    version: str
    new_global_nodes: int
    bindings: int
    global_factors: int


@router.post("/packages/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    local_params = req.local_params or LocalParameterization(graph_hash=req.local_graph.graph_hash)
    result = await run_ingest(
        local_graph=req.local_graph,
        local_params=local_params,
        package_id=req.package_id,
        version=req.version,
        storage=deps_module.deps.storage,
        embedding_model=deps_module.deps.embedding,
    )
    return IngestResponse(
        package_id=req.package_id,
        version=req.version,
        new_global_nodes=len(result.new_global_nodes),
        bindings=len(result.bindings),
        global_factors=len(result.global_factors),
    )
