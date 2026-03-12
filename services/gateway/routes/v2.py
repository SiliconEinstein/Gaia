"""V2 storage API routes — package ingest + read endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Knowledge,
    KnowledgeEmbedding,
    Module,
    Package,
    ProbabilityRecord,
)
from services.gateway.deps import deps

router = APIRouter(prefix="/v2", tags=["v2"])


def _require_v2():
    if deps.storage_v2 is None:
        raise HTTPException(status_code=503, detail="V2 storage not initialized")
    return deps.storage_v2


# ── Ingest ──


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
    mgr = _require_v2()

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


# ── Read: Package ──


@router.get("/packages/{package_id}")
async def get_package(package_id: str):
    mgr = _require_v2()
    pkg = await mgr.get_package(package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg.model_dump()


# ── Read: Knowledge ──
# NOTE: Sub-path routes must come BEFORE the catch-all {knowledge_id:path}


@router.get("/knowledge/{knowledge_id:path}/versions")
async def get_knowledge_versions(knowledge_id: str):
    mgr = _require_v2()
    versions = await mgr.get_knowledge_versions(knowledge_id)
    return [v.model_dump() for v in versions]


@router.get("/knowledge/{knowledge_id:path}/beliefs")
async def get_knowledge_beliefs(knowledge_id: str):
    mgr = _require_v2()
    beliefs = await mgr.get_belief_history(knowledge_id)
    return [b.model_dump() for b in beliefs]


@router.get("/knowledge/{knowledge_id:path}")
async def get_knowledge(knowledge_id: str):
    mgr = _require_v2()
    k = await mgr.get_knowledge(knowledge_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return k.model_dump()


# ── Read: Module ──
# NOTE: Sub-path routes must come BEFORE the catch-all {module_id:path}


@router.get("/modules/{module_id:path}/chains")
async def get_module_chains(module_id: str):
    mgr = _require_v2()
    chains = await mgr.get_chains_by_module(module_id)
    return [c.model_dump() for c in chains]


@router.get("/modules/{module_id:path}")
async def get_module(module_id: str):
    mgr = _require_v2()
    m = await mgr.get_module(module_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return m.model_dump()


# ── Read: Chain ──


@router.get("/chains/{chain_id:path}/probabilities")
async def get_chain_probabilities(chain_id: str):
    mgr = _require_v2()
    probs = await mgr.get_probability_history(chain_id)
    return [p.model_dump() for p in probs]
