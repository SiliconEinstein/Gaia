"""Package API routes — ingest + read endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from libs.storage.models import (
    BeliefSnapshot,
    Chain,
    Knowledge,
    KnowledgeEmbedding,
    Module,
    Package,
    ProbabilityRecord,
)
from services.gateway.deps import deps

router = APIRouter(tags=["packages"])


def _require_storage():
    if deps.storage is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    return deps.storage


# ── Ingest ──


class PaginatedPackages(BaseModel):
    items: list[dict]
    total: int
    page: int
    size: int


class PaginatedKnowledge(BaseModel):
    items: list[dict]
    total: int
    page: int
    size: int


class PaginatedChains(BaseModel):
    items: list[dict]
    total: int
    page: int
    size: int


class IngestRequest(BaseModel):
    package: dict
    modules: list[dict]
    knowledge: list[dict]
    chains: list[dict]
    probabilities: list[dict] = []
    beliefs: list[dict] = []
    embeddings: list[dict] = []


class IngestResponse(BaseModel):
    package_id: str
    status: str
    knowledge_count: int
    chain_count: int


@router.post("/packages/ingest", response_model=IngestResponse, status_code=201)
async def ingest_package(request: IngestRequest):
    """Ingest a complete package into v2 storage."""
    mgr = _require_storage()

    pkg = Package.model_validate(request.package)
    modules = [Module.model_validate(m) for m in request.modules]
    knowledge_items = [Knowledge.model_validate(k) for k in request.knowledge]
    chains = [Chain.model_validate(c) for c in request.chains]
    embeddings = (
        [KnowledgeEmbedding.model_validate(e) for e in request.embeddings]
        if request.embeddings
        else None
    )

    await mgr.ingest_package(
        package=pkg,
        modules=modules,
        knowledge_items=knowledge_items,
        chains=chains,
        embeddings=embeddings,
    )

    if request.probabilities:
        records = [ProbabilityRecord.model_validate(p) for p in request.probabilities]
        await mgr.add_probabilities(records)
    if request.beliefs:
        snapshots = [BeliefSnapshot.model_validate(b) for b in request.beliefs]
        await mgr.write_beliefs(snapshots)

    return IngestResponse(
        package_id=pkg.package_id,
        status="ingested",
        knowledge_count=len(knowledge_items),
        chain_count=len(chains),
    )


@router.get("/packages", response_model=PaginatedPackages)
async def list_packages(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all packages with pagination."""
    mgr = _require_storage()
    items, total = await mgr.list_packages(page=page, page_size=page_size)
    return PaginatedPackages(
        items=[p.model_dump() for p in items],
        total=total,
        page=page,
        size=page_size,
    )


# ── Read: Package ──


@router.get("/packages/{package_id}")
async def get_package(package_id: str):
    mgr = _require_storage()
    pkg = await mgr.get_package(package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg.model_dump()


@router.get("/knowledge", response_model=PaginatedKnowledge)
async def list_knowledge(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    type_filter: str | None = None,
):
    """List knowledge items with pagination and optional type filter."""
    mgr = _require_storage()
    items, total = await mgr.list_knowledge_paged(
        page=page, page_size=page_size, type_filter=type_filter
    )
    return PaginatedKnowledge(
        items=[k.model_dump() for k in items],
        total=total,
        page=page,
        size=page_size,
    )


# ── Read: Knowledge ──
# NOTE: Sub-path routes must come BEFORE the catch-all {knowledge_id:path}


@router.get("/knowledge/{knowledge_id:path}/versions")
async def get_knowledge_versions(knowledge_id: str):
    mgr = _require_storage()
    versions = await mgr.get_knowledge_versions(knowledge_id)
    return [v.model_dump() for v in versions]


@router.get("/knowledge/{knowledge_id:path}/beliefs")
async def get_knowledge_beliefs(knowledge_id: str):
    mgr = _require_storage()
    beliefs = await mgr.get_belief_history(knowledge_id)
    return [b.model_dump() for b in beliefs]


@router.get("/knowledge/{knowledge_id:path}")
async def get_knowledge(knowledge_id: str):
    mgr = _require_storage()
    k = await mgr.get_knowledge(knowledge_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return k.model_dump()


@router.get("/modules", response_model=list[dict])
async def list_modules(package_id: str | None = None):
    """List all modules, optionally filtered by package."""
    mgr = _require_storage()
    modules = await mgr.list_modules(package_id=package_id)
    return [m.model_dump() for m in modules]


# ── Read: Module ──
# NOTE: Sub-path routes must come BEFORE the catch-all {module_id:path}


@router.get("/modules/{module_id:path}/chains")
async def get_module_chains(module_id: str):
    mgr = _require_storage()
    chains = await mgr.get_chains_by_module(module_id)
    return [c.model_dump() for c in chains]


@router.get("/modules/{module_id:path}")
async def get_module(module_id: str):
    mgr = _require_storage()
    m = await mgr.get_module(module_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return m.model_dump()


@router.get("/chains", response_model=PaginatedChains)
async def list_chains(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    module_id: str | None = None,
):
    """List chains with pagination, optionally filtered by module."""
    mgr = _require_storage()
    items, total = await mgr.list_chains_paged(
        page=page, page_size=page_size, module_id=module_id
    )
    return PaginatedChains(
        items=[c.model_dump() for c in items],
        total=total,
        page=page,
        size=page_size,
    )


# ── Read: Chain ──


@router.get("/chains/{chain_id:path}/probabilities")
async def get_chain_probabilities(chain_id: str):
    mgr = _require_storage()
    probs = await mgr.get_probability_history(chain_id)
    return [p.model_dump() for p in probs]


@router.get("/chains/{chain_id:path}")
async def get_chain(chain_id: str):
    """Get a single chain by ID."""
    mgr = _require_storage()
    chain = await mgr.get_chain(chain_id)
    if chain is None:
        raise HTTPException(status_code=404, detail="Chain not found")
    return chain.model_dump()
