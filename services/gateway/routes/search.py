from fastapi import APIRouter
from pydantic import BaseModel
from services.gateway.deps import deps
from services.search_engine.models import NodeFilters, EdgeFilters

router = APIRouter(prefix="/search", tags=["search"])


class SearchNodesRequest(BaseModel):
    text: str
    k: int = 20
    filters: NodeFilters | None = None
    paths: list[str] | None = None


class SearchEdgesRequest(BaseModel):
    text: str
    k: int = 20
    filters: EdgeFilters | None = None
    paths: list[str] | None = None


@router.post("/nodes")
async def search_nodes(request: SearchNodesRequest):
    results = await deps.search_engine.search_nodes(
        text=request.text,
        k=request.k,
        filters=request.filters,
        paths=request.paths,
    )
    return [r.model_dump() for r in results]


@router.post("/hyperedges")
async def search_hyperedges(request: SearchEdgesRequest):
    results = await deps.search_engine.search_edges(
        text=request.text,
        k=request.k,
        filters=request.filters,
        paths=request.paths,
    )
    return [r.model_dump() for r in results]
