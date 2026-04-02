"""LKM API routes — minimal read endpoints for browsing storage."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from gaia.lkm.api.deps import get_storage
from gaia.lkm.storage import StorageManager

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/stats")
async def stats(storage: StorageManager = Depends(get_storage)):
    """Table row counts."""
    tables = [
        "local_variable_nodes",
        "local_factor_nodes",
        "global_variable_nodes",
        "global_factor_nodes",
        "canonical_bindings",
        "prior_records",
        "factor_param_records",
        "param_sources",
    ]
    counts = {}
    for t in tables:
        try:
            counts[t] = await storage.content.count(t)
        except Exception:
            counts[t] = 0
    return counts


@router.get("/variables")
async def list_variables(
    layer: str = "global",
    type: str | None = None,
    visibility: str = "public",
    source_package: str | None = None,
    limit: int = 200,
    storage: StorageManager = Depends(get_storage),
):
    """List variables. layer=global (default) or layer=local."""
    if layer == "local":
        local_vars = (
            await storage.content.get_local_variables_by_package(source_package, merged_only=True)
            if source_package
            else await _list_all_local_vars(storage, type, limit)
        )
        return [v.model_dump() for v in local_vars]
    else:
        global_vars = await storage.content.list_global_variables(
            type_filter=type, visibility=visibility, limit=limit
        )
        results = []
        for gv in global_vars:
            local = await storage.get_local_variable(gv.representative_lcn.local_id)
            results.append(
                {
                    "id": gv.id,
                    "type": gv.type,
                    "visibility": gv.visibility,
                    "content": local.content if local else None,
                    "content_hash": gv.content_hash,
                    "parameters": [p.model_dump() for p in gv.parameters],
                    "local_members": [m.model_dump() for m in gv.local_members],
                    "representative_lcn": gv.representative_lcn.model_dump(),
                }
            )
        return results


async def _list_all_local_vars(storage: StorageManager, type_filter: str | None, limit: int):
    """List all merged local variables across packages."""
    from gaia.lkm.storage._serialization import _q, row_to_local_variable

    table = storage.content._db.open_table("local_variable_nodes")
    where = "ingest_status = 'merged'"
    if type_filter:
        where += f" AND type = '{_q(type_filter)}'"
    results = await storage.content._run(lambda: table.search().where(where).limit(limit).to_list())
    return [row_to_local_variable(r) for r in results]


@router.get("/variables/{gcn_id}")
async def get_variable(
    gcn_id: str,
    storage: StorageManager = Depends(get_storage),
):
    """Get a global variable by gcn_id, with content and connected factors."""
    gvar = await storage.get_global_variable(gcn_id)
    if not gvar:
        raise HTTPException(404, f"Variable {gcn_id} not found")

    local = await storage.get_local_variable(gvar.representative_lcn.local_id)
    content = local.content if local else None

    # Find connected factors
    all_factors = await storage.content.list_global_factors(limit=10000)
    connected_factors = []
    for gf in all_factors:
        if gcn_id in gf.premises or gf.conclusion == gcn_id:
            local_factor = await storage.content.get_local_factor(gf.representative_lfn)
            connected_factors.append(
                {
                    "id": gf.id,
                    "factor_type": gf.factor_type,
                    "subtype": gf.subtype,
                    "premises": gf.premises,
                    "conclusion": gf.conclusion,
                    "steps": [s.model_dump() for s in local_factor.steps]
                    if local_factor and local_factor.steps
                    else None,
                    "role": "premise" if gcn_id in gf.premises else "conclusion",
                }
            )

    bindings = await storage.find_bindings_by_global_id(gcn_id)

    return {
        "id": gvar.id,
        "type": gvar.type,
        "visibility": gvar.visibility,
        "content": content,
        "content_hash": gvar.content_hash,
        "parameters": [p.model_dump() for p in gvar.parameters],
        "representative_lcn": gvar.representative_lcn.model_dump(),
        "local_members": [m.model_dump() for m in gvar.local_members],
        "connected_factors": connected_factors,
        "bindings": [b.model_dump() for b in bindings],
    }


@router.get("/factors")
async def list_factors(
    layer: str = "global",
    factor_type: str | None = None,
    limit: int = 200,
    storage: StorageManager = Depends(get_storage),
):
    """List factors. layer=global (default) or layer=local."""
    if layer == "local":
        local_factors = await _list_all_local_factors(storage, factor_type, limit)
        return [f.model_dump() for f in local_factors]
    else:
        global_factors = await storage.content.list_global_factors(
            factor_type=factor_type, limit=limit
        )
        results = []
        for gf in global_factors:
            local_factor = await storage.content.get_local_factor(gf.representative_lfn)
            results.append(
                {
                    "id": gf.id,
                    "factor_type": gf.factor_type,
                    "subtype": gf.subtype,
                    "premises": gf.premises,
                    "conclusion": gf.conclusion,
                    "source_package": gf.source_package,
                    "steps": [s.model_dump() for s in local_factor.steps]
                    if local_factor and local_factor.steps
                    else None,
                }
            )
        return results


async def _list_all_local_factors(storage: StorageManager, type_filter: str | None, limit: int):
    from gaia.lkm.storage._serialization import _q, row_to_local_factor

    table = storage.content._db.open_table("local_factor_nodes")
    where = "ingest_status = 'merged'"
    if type_filter:
        where += f" AND factor_type = '{_q(type_filter)}'"
    results = await storage.content._run(lambda: table.search().where(where).limit(limit).to_list())
    return [row_to_local_factor(r) for r in results]


@router.get("/factors/{gfac_id}")
async def get_factor(
    gfac_id: str,
    storage: StorageManager = Depends(get_storage),
):
    """Get a global factor by gfac_id, with steps and resolved variable content."""
    gfac = await storage.get_global_factor(gfac_id)
    if not gfac:
        raise HTTPException(404, f"Factor {gfac_id} not found")

    local_factor = await storage.content.get_local_factor(gfac.representative_lfn)
    steps = (
        [s.model_dump() for s in local_factor.steps]
        if local_factor and local_factor.steps
        else None
    )

    async def resolve_var(gcn_id: str) -> dict:
        gv = await storage.get_global_variable(gcn_id)
        if not gv:
            return {"id": gcn_id, "content": None}
        local = await storage.get_local_variable(gv.representative_lcn.local_id)
        return {"id": gcn_id, "type": gv.type, "content": local.content if local else None}

    premises_resolved = [await resolve_var(p) for p in gfac.premises]
    conclusion_resolved = await resolve_var(gfac.conclusion)

    return {
        "id": gfac.id,
        "factor_type": gfac.factor_type,
        "subtype": gfac.subtype,
        "premises": premises_resolved,
        "conclusion": conclusion_resolved,
        "source_package": gfac.source_package,
        "steps": steps,
    }


@router.get("/bindings")
async def list_bindings(
    package_id: str | None = None,
    binding_type: str | None = None,
    limit: int = 200,
    storage: StorageManager = Depends(get_storage),
):
    """List canonical bindings with optional filters."""
    bindings = await storage.content.list_bindings(
        package_id=package_id, binding_type=binding_type, limit=limit
    )
    return [b.model_dump() for b in bindings]


@router.get("/priors")
async def list_priors(
    limit: int = 200,
    storage: StorageManager = Depends(get_storage),
):
    """List all prior records."""
    from gaia.lkm.storage._serialization import row_to_prior

    table = storage.content._db.open_table("prior_records")
    results = await storage.content._run(lambda: table.search().limit(limit).to_list())
    priors = [row_to_prior(r) for r in results]

    # Resolve variable content for display
    out = []
    for pr in priors:
        gv = await storage.get_global_variable(pr.variable_id)
        content = None
        if gv:
            local = await storage.get_local_variable(gv.representative_lcn.local_id)
            content = local.content if local else None
        out.append(
            {
                "variable_id": pr.variable_id,
                "value": pr.value,
                "source_id": pr.source_id,
                "created_at": pr.created_at.isoformat(),
                "content": content,
            }
        )
    return out


@router.get("/param-sources")
async def list_param_sources(
    storage: StorageManager = Depends(get_storage),
):
    """List all parameterization sources."""
    from gaia.lkm.storage._serialization import row_to_param_source

    table = storage.content._db.open_table("param_sources")
    results = await storage.content._run(lambda: table.search().limit(100).to_list())
    return [row_to_param_source(r).model_dump() for r in results]


@router.get("/graph")
async def get_graph(
    storage: StorageManager = Depends(get_storage),
):
    """Get full graph structure for visualization — nodes + edges."""
    global_vars = await storage.content.list_global_variables(limit=10000)
    global_factors = await storage.content.list_global_factors(limit=10000)

    nodes = []
    for gv in global_vars:
        local = await storage.get_local_variable(gv.representative_lcn.local_id)
        nodes.append(
            {
                "id": gv.id,
                "type": "variable",
                "subtype": gv.type,
                "visibility": gv.visibility,
                "content": local.content if local else None,
                "local_members_count": len(gv.local_members),
            }
        )

    edges = []
    for gf in global_factors:
        nodes.append(
            {
                "id": gf.id,
                "type": "factor",
                "subtype": gf.subtype,
                "factor_type": gf.factor_type,
            }
        )
        for p in gf.premises:
            edges.append({"source": p, "target": gf.id, "type": "premise"})
        edges.append({"source": gf.id, "target": gf.conclusion, "type": "conclusion"})

    return {"nodes": nodes, "edges": edges}


@router.get("/graph/subgraph/{gcn_id}")
async def get_subgraph(
    gcn_id: str,
    hops: int = 2,
    storage: StorageManager = Depends(get_storage),
):
    """Get N-hop subgraph around a global variable. Requires Neo4j."""
    result = await storage.get_subgraph(gcn_id, hops)
    if not result["nodes"]:
        return {"nodes": [], "edges": [], "note": "No graph backend or node not found"}
    return result


@router.get("/graph/local/{source_package}")
async def get_local_graph(
    source_package: str,
    storage: StorageManager = Depends(get_storage),
):
    """Get a local graph for a specific package — variables + factors + edges."""
    local_vars = await storage.content.get_local_variables_by_package(source_package)
    from gaia.lkm.storage._serialization import row_to_local_factor

    # Get local factors for this package
    table = storage.content._db.open_table("local_factor_nodes")
    from gaia.lkm.storage._serialization import _q

    escaped = _q(source_package)
    factor_rows = await storage.content._run(
        lambda: (
            table.search()
            .where(f"source_package = '{escaped}' AND ingest_status = 'merged'")
            .limit(10000)
            .to_list()
        )
    )
    local_factors = [row_to_local_factor(r) for r in factor_rows]

    # Get priors and gcn_ids for this package's variables
    prior_map: dict[str, float] = {}
    gcn_map: dict[str, str] = {}
    for lv in local_vars:
        binding = await storage.find_canonical_binding(lv.id)
        if binding:
            gcn_map[lv.id] = binding.global_id
            priors = await storage.get_prior_records(binding.global_id)
            if priors:
                prior_map[lv.id] = priors[0].value

    # Build graph
    nodes = []
    var_ids = {lv.id for lv in local_vars}
    for lv in local_vars:
        label = lv.id.split("::")[-1] if "::" in lv.id else lv.id
        nodes.append(
            {
                "id": lv.id,
                "type": "variable",
                "subtype": lv.type,
                "label": label,
                "content": lv.content[:60] + "..." if len(lv.content) > 60 else lv.content,
                "prior": prior_map.get(lv.id),
                "gcn_id": gcn_map.get(lv.id),
            }
        )

    edges = []
    for lf in local_factors:
        # Factor symbol
        symbol = {
            "noisy_and": "∧",
            "infer": "→",
            "contradiction": "⊗",
            "deduction": "⊢",
            "equivalence": "≡",
            "implication": "⇒",
        }.get(lf.subtype, "f")
        nodes.append(
            {
                "id": lf.id,
                "type": "factor",
                "subtype": lf.subtype,
                "factor_type": lf.factor_type,
                "label": symbol,
            }
        )
        for p in lf.premises:
            if p in var_ids:
                edges.append({"source": p, "target": lf.id, "type": "premise"})
        if lf.background:
            for b in lf.background:
                if b in var_ids:
                    edges.append({"source": b, "target": lf.id, "type": "background"})
        if lf.conclusion in var_ids:
            edges.append({"source": lf.id, "target": lf.conclusion, "type": "conclusion"})

    return {"package_id": source_package, "nodes": nodes, "edges": edges}


@router.get("/packages")
async def list_packages(
    storage: StorageManager = Depends(get_storage),
):
    """List all ingested packages (distinct source_package values)."""

    table = storage.content._db.open_table("local_variable_nodes")
    rows = await storage.content._run(
        lambda: table.search().where("ingest_status = 'merged'").limit(100000).to_list()
    )
    packages = {}
    for r in rows:
        pkg = r["source_package"]
        packages[pkg] = packages.get(pkg, 0) + 1
    return [{"package_id": k, "variable_count": v} for k, v in sorted(packages.items())]
