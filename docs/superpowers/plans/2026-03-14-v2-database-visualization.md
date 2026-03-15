# V2 Database Visualization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a V2 data browser (7 pages) and Graph IR DAG visualizer to the existing React frontend.

**Architecture:** New backend list/graph endpoints → React Query hooks in `frontend/src/api/v2.ts` → 7 new pages under `frontend/src/pages/v2/`. Backend adds paginated list methods to `LanceContentStore` and `StorageManager`, plus a `/graph` endpoint. Frontend uses existing vis-network with hierarchical layout for the DAG.

**Tech Stack:** Python/FastAPI (backend), React 19 + TypeScript, Ant Design, React Query, React Router, vis-network (frontend)

---

## Chunk 1: Backend List + Graph Endpoints

### File Map

| Action | File |
|--------|------|
| Modify | `libs/storage/lance_content_store.py` — add `list_packages`, `list_modules`, paginated `list_knowledge_paged`, `list_chains_paged`, `get_graph_data` |
| Modify | `libs/storage/manager.py` — expose new methods |
| Modify | `services/gateway/routes/packages.py` — add 5 new GET endpoints |
| Create | `tests/services/test_gateway/test_packages_list_routes.py` |

---

### Task 1: list_packages endpoint

**Files:**
- Modify: `libs/storage/lance_content_store.py`
- Modify: `libs/storage/manager.py`
- Modify: `services/gateway/routes/packages.py`
- Create: `tests/services/test_gateway/test_packages_list_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/services/test_gateway/test_packages_list_routes.py
"""Tests for v2 list API routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from libs.storage.models import Package, Module, Knowledge, Chain
from services.gateway.app import create_app
from services.gateway.deps import deps


class MockStorage:
    async def list_packages(self, page: int = 1, page_size: int = 20):
        pkg = Package(
            package_id="pkg1", name="pkg1", version="1.0.0",
            description="test", modules=[], exports=[],
            submitter="test", submitted_at="2026-01-01T00:00:00Z", status="merged",
        )
        return [pkg], 1

    async def list_knowledge_paged(self, page: int = 1, page_size: int = 20, type_filter: str | None = None):
        from libs.storage.models import Knowledge
        k = Knowledge(
            knowledge_id="k1", version=1, type="claim", content="test content",
            prior=0.5, keywords=[], source_package_id="pkg1",
            source_package_version="1.0.0", source_module_id="pkg1.mod1",
        )
        return [k], 1

    async def list_modules(self, package_id: str | None = None):
        from libs.storage.models import Module
        m = Module(
            module_id="pkg1.mod1", package_id="pkg1", package_version="1.0.0",
            name="mod1", role="reasoning", imports=[], chain_ids=[], export_ids=[],
        )
        return [m]

    async def list_chains_paged(self, page: int = 1, page_size: int = 20, module_id: str | None = None):
        return [], 0

    async def get_graph_data(self, package_id: str | None = None):
        return {"nodes": [], "edges": []}


@pytest.fixture()
def client():
    deps.storage = MockStorage()
    app = create_app()
    c = TestClient(app)
    yield c
    deps.storage = None


def test_list_packages(client):
    r = client.get("/packages")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["package_id"] == "pkg1"
    assert body["page"] == 1
    assert body["size"] == 20


def test_list_packages_pagination(client):
    r = client.get("/packages?page=2&page_size=5")
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 2
    assert body["size"] == 5
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/services/test_gateway/test_packages_list_routes.py::test_list_packages -v
```
Expected: FAIL — `GET /packages` returns 404

- [ ] **Step 3: Add `list_packages` to `LanceContentStore`**

In `libs/storage/lance_content_store.py`, after the existing `list_knowledge` method (around line 903), add:

```python
async def list_packages(self, page: int = 1, page_size: int = 20) -> tuple[list[Package], int]:
    """Return a paginated list of merged packages (visibility-gated)."""
    table = self._db.open_table("packages")
    total_rows = table.count_rows()
    if total_rows == 0:
        return [], 0
    results = table.search().limit(total_rows).to_list()
    # Only return merged packages — consistent with get_package visibility model
    items = [_row_to_package(r) for r in results if r.get("status") == "merged"]
    total = len(items)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size], total
```

- [ ] **Step 4: Add `list_packages` to `StorageManager`**

In `libs/storage/manager.py`, after `list_knowledge` (around line 235):

```python
async def list_packages(self, page: int = 1, page_size: int = 20) -> tuple[list[Package], int]:
    return await self.content_store.list_packages(page=page, page_size=page_size)
```

- [ ] **Step 5: Add `GET /packages` route**

In `services/gateway/routes/packages.py`, before the `POST /packages/ingest` route, add:

```python
class PaginatedPackages(BaseModel):
    items: list[dict]
    total: int
    page: int
    size: int


@router.get("/packages", response_model=PaginatedPackages)
async def list_packages(page: int = 1, page_size: int = 20):
    """List all packages with pagination."""
    mgr = _require_storage()
    items, total = await mgr.list_packages(page=page, page_size=page_size)
    return PaginatedPackages(
        items=[p.model_dump() for p in items],
        total=total,
        page=page,
        size=page_size,
    )
```

**IMPORTANT:** This route must be added BEFORE the `GET /packages/{package_id}` route to avoid routing conflicts.

- [ ] **Step 6: Run tests**

```bash
pytest tests/services/test_gateway/test_packages_list_routes.py::test_list_packages tests/services/test_gateway/test_packages_list_routes.py::test_list_packages_pagination -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add libs/storage/lance_content_store.py libs/storage/manager.py \
  services/gateway/routes/packages.py \
  tests/services/test_gateway/test_packages_list_routes.py
git commit -m "feat: add GET /packages list endpoint with pagination"
```

---

### Task 2: list_knowledge_paged endpoint

**Files:**
- Modify: `libs/storage/lance_content_store.py`
- Modify: `libs/storage/manager.py`
- Modify: `services/gateway/routes/packages.py`
- Modify: `tests/services/test_gateway/test_packages_list_routes.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/services/test_gateway/test_packages_list_routes.py`:

```python
def test_list_knowledge(client):
    r = client.get("/knowledge")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["knowledge_id"] == "k1"


def test_list_knowledge_type_filter(client):
    r = client.get("/knowledge?type_filter=claim")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_list_knowledge_type_filter_no_match(client):
    r = client.get("/knowledge?type_filter=setting")
    assert r.status_code == 200
    # MockStorage ignores filter but route must pass it through
    assert "items" in r.json()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/services/test_gateway/test_packages_list_routes.py::test_list_knowledge -v
```
Expected: FAIL — `GET /knowledge` conflicts with existing `/knowledge/{id}` route

- [ ] **Step 3: Add `list_knowledge_paged` to `LanceContentStore`**

In `libs/storage/lance_content_store.py`, after `list_packages`:

```python
async def list_knowledge_paged(
    self, page: int = 1, page_size: int = 20, type_filter: str | None = None
) -> tuple[list[Knowledge], int]:
    """Return paginated knowledge, optionally filtered by type."""
    committed = await self._get_committed_packages()
    table = self._db.open_table("knowledge")
    total_rows = table.count_rows()
    if total_rows == 0:
        return [], 0
    results = table.search().limit(total_rows).to_list()
    items = [
        _row_to_knowledge(r)
        for r in results
        if self._is_committed(
            r["source_package_id"], r.get("source_package_version", "0.1.0"), committed
        )
    ]
    if type_filter:
        items = [k for k in items if k.type == type_filter]
    total = len(items)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size], total
```

- [ ] **Step 4: Add `list_knowledge_paged` to `StorageManager`**

In `libs/storage/manager.py`, after `list_packages`:

```python
async def list_knowledge_paged(
    self, page: int = 1, page_size: int = 20, type_filter: str | None = None
) -> tuple[list[Knowledge], int]:
    return await self.content_store.list_knowledge_paged(
        page=page, page_size=page_size, type_filter=type_filter
    )
```

- [ ] **Step 5: Add `GET /knowledge` list route**

In `services/gateway/routes/packages.py`, add a new list route BEFORE ALL existing `/knowledge/{...}` parametric routes (i.e., before `/knowledge/{knowledge_id:path}/versions`). The literal `GET /knowledge` route must come first so it isn't swallowed by the path-parameter catch-alls:

```python
class PaginatedKnowledge(BaseModel):
    items: list[dict]
    total: int
    page: int
    size: int


@router.get("/knowledge", response_model=PaginatedKnowledge)
async def list_knowledge(
    page: int = 1,
    page_size: int = 20,
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
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/services/test_gateway/test_packages_list_routes.py -k "knowledge" -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add libs/storage/lance_content_store.py libs/storage/manager.py \
  services/gateway/routes/packages.py \
  tests/services/test_gateway/test_packages_list_routes.py
git commit -m "feat: add GET /knowledge list endpoint with pagination and type filter"
```

---

### Task 3: list_modules, list_chains_paged endpoints

**Files:**
- Modify: `libs/storage/lance_content_store.py`
- Modify: `libs/storage/manager.py`
- Modify: `services/gateway/routes/packages.py`
- Modify: `tests/services/test_gateway/test_packages_list_routes.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/services/test_gateway/test_packages_list_routes.py`:

```python
def test_list_modules(client):
    r = client.get("/modules")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["module_id"] == "pkg1.mod1"


def test_list_modules_filtered(client):
    r = client.get("/modules?package_id=pkg1")
    assert r.status_code == 200


def test_list_chains(client):
    r = client.get("/chains")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/services/test_gateway/test_packages_list_routes.py::test_list_modules -v
```
Expected: FAIL

- [ ] **Step 3: Add `list_modules` to `LanceContentStore`**

In `libs/storage/lance_content_store.py`, after `list_knowledge_paged`:

```python
async def list_modules(self, package_id: str | None = None) -> list[Module]:
    """List modules from committed packages, optionally filtered by package_id."""
    committed = await self._get_committed_packages()
    table = self._db.open_table("modules")
    count = table.count_rows()
    if count == 0:
        return []
    results = table.search().limit(count).to_list()
    modules = [
        _row_to_module(r)
        for r in results
        if self._is_committed(r["package_id"], r.get("package_version", "0.1.0"), committed)
    ]
    if package_id:
        modules = [m for m in modules if m.package_id == package_id]
    return modules


async def list_chains_paged(
    self, page: int = 1, page_size: int = 20, module_id: str | None = None
) -> tuple[list[Chain], int]:
    """Return paginated chains, optionally filtered by module_id."""
    committed = await self._get_committed_packages()
    table = self._db.open_table("chains")
    count = table.count_rows()
    if count == 0:
        return [], 0
    results = table.search().limit(count).to_list()
    chains = [
        _row_to_chain(r)
        for r in results
        if self._is_committed(r["package_id"], r.get("package_version", "0.1.0"), committed)
    ]
    if module_id:
        chains = [c for c in chains if c.module_id == module_id]  # Chain.module_id confirmed in models.py:80
    total = len(chains)
    offset = (page - 1) * page_size
    return chains[offset : offset + page_size], total
```

- [ ] **Step 4: Add to `StorageManager`**

In `libs/storage/manager.py`, after `list_knowledge_paged`:

```python
async def list_modules(self, package_id: str | None = None) -> list[Module]:
    return await self.content_store.list_modules(package_id=package_id)

async def list_chains_paged(
    self, page: int = 1, page_size: int = 20, module_id: str | None = None
) -> tuple[list[Chain], int]:
    return await self.content_store.list_chains_paged(
        page=page, page_size=page_size, module_id=module_id
    )
```

- [ ] **Step 5: Add routes**

In `services/gateway/routes/packages.py`, add BEFORE the existing `/modules/{module_id:path}` routes:

```python
class PaginatedChains(BaseModel):
    items: list[dict]
    total: int
    page: int
    size: int


@router.get("/modules", response_model=list[dict])
async def list_modules(package_id: str | None = None):
    """List all modules, optionally filtered by package."""
    mgr = _require_storage()
    modules = await mgr.list_modules(package_id=package_id)
    return [m.model_dump() for m in modules]


@router.get("/chains", response_model=PaginatedChains)
async def list_chains(
    page: int = 1,
    page_size: int = 20,
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
```

Also add `GET /chains/{chain_id:path}` (single chain lookup, needed by ChainDetail page).

**CRITICAL route ordering:** Both `GET /chains/{chain_id:path}` and `GET /chains/{chain_id:path}/probabilities` use path parameters. FastAPI matches routes in registration order, so the more-specific `/probabilities` suffix route MUST be registered first. The correct order in the file is:

1. `GET /chains` (list — new)
2. `GET /chains/{chain_id:path}/probabilities` (existing — keep in place)
3. `GET /chains/{chain_id:path}` (single item — new, AFTER probabilities)

Add `get_chain` to `LanceContentStore` (after `list_chains_paged`):

```python
async def get_chain(self, chain_id: str) -> Chain | None:
    """Get a single chain by chain_id."""
    committed = await self._get_committed_packages()
    table = self._db.open_table("chains")
    count = table.count_rows()
    if count == 0:
        return None
    results = table.search().limit(count).to_list()
    for r in results:
        if r["chain_id"] == chain_id and self._is_committed(
            r["package_id"], r.get("package_version", "0.1.0"), committed
        ):
            return _row_to_chain(r)
    return None
```

Add to `StorageManager` (after `list_chains_paged`):

```python
async def get_chain(self, chain_id: str) -> Chain | None:
    return await self.content_store.get_chain(chain_id)
```

In `services/gateway/routes/packages.py`, the final route ordering for chains must be:

```python
# 1. List (new)
@router.get("/chains", response_model=PaginatedChains)
async def list_chains(...): ...

# 2. Probabilities sub-route (existing — keep here, BEFORE the catch-all)
@router.get("/chains/{chain_id:path}/probabilities")
async def get_chain_probabilities(...): ...

# 3. Single chain catch-all (new — AFTER probabilities)
@router.get("/chains/{chain_id:path}")
async def get_chain(chain_id: str):
    mgr = _require_storage()
    chain = await mgr.get_chain(chain_id)
    if chain is None:
        raise HTTPException(status_code=404, detail="Chain not found")
    return chain.model_dump()
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/services/test_gateway/test_packages_list_routes.py -v
```
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add libs/storage/lance_content_store.py libs/storage/manager.py \
  services/gateway/routes/packages.py \
  tests/services/test_gateway/test_packages_list_routes.py
git commit -m "feat: add GET /modules and GET /chains list endpoints"
```

---

### Task 4: GET /graph endpoint

**Files:**
- Modify: `libs/storage/lance_content_store.py`
- Modify: `libs/storage/manager.py`
- Modify: `services/gateway/routes/packages.py`
- Modify: `tests/services/test_gateway/test_packages_list_routes.py`

- [ ] **Step 1: Write failing test**

Add to `tests/services/test_gateway/test_packages_list_routes.py`:

```python
def test_get_graph(client):
    r = client.get("/graph")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body
    assert "edges" in body


def test_get_graph_filtered(client):
    r = client.get("/graph?package_id=pkg1")
    assert r.status_code == 200
```

Update `MockStorage` to add:
```python
async def get_graph_data(self, package_id: str | None = None):
    return {"nodes": [], "edges": []}
```
(already in MockStorage above)

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/services/test_gateway/test_packages_list_routes.py::test_get_graph -v
```
Expected: FAIL

- [ ] **Step 3: Add `get_graph_data` to `LanceContentStore`**

In `libs/storage/lance_content_store.py`, after `list_chains_paged`:

```python
async def get_graph_data(self, package_id: str | None = None) -> dict:
    """Return Knowledge nodes + Chain edges for DAG visualization.

    Each Chain step produces edges: each premise → conclusion.
    Node id format: knowledge_id@version
    """
    # Get knowledge items
    items, _ = await self.list_knowledge_paged(page=1, page_size=10_000)
    chains = (await self.list_chains_paged(page=1, page_size=10_000))[0]

    if package_id:
        items = [k for k in items if k.source_package_id == package_id]
        chains = [c for c in chains if c.package_id == package_id]

    # Build node id set for filtering edges
    node_ids = {f"{k.knowledge_id}@{k.version}" for k in items}

    nodes = [
        {
            "id": f"{k.knowledge_id}@{k.version}",
            "knowledge_id": k.knowledge_id,
            "version": k.version,
            "type": k.type,
            "content": k.content,
            "prior": k.prior,
        }
        for k in items
    ]

    edges = []
    for chain in chains:
        for step in chain.steps:
            conc_id = f"{step.conclusion.knowledge_id}@{step.conclusion.version}"
            for premise in step.premises:
                prem_id = f"{premise.knowledge_id}@{premise.version}"
                if prem_id in node_ids and conc_id in node_ids:
                    edges.append({
                        "chain_id": chain.chain_id,
                        "from": prem_id,
                        "to": conc_id,
                        "chain_type": chain.type,
                        "step_index": step.step_index,
                    })

    return {"nodes": nodes, "edges": edges}
```

- [ ] **Step 4: Add to `StorageManager`**

In `libs/storage/manager.py`, after `list_chains_paged`:

```python
async def get_graph_data(self, package_id: str | None = None) -> dict:
    return await self.content_store.get_graph_data(package_id=package_id)
```

- [ ] **Step 5: Add `GET /graph` route**

In `services/gateway/routes/packages.py`, at the end of the file:

```python
@router.get("/graph")
async def get_graph(package_id: str | None = None):
    """Return Knowledge nodes and Chain edges for DAG visualization."""
    mgr = _require_storage()
    return await mgr.get_graph_data(package_id=package_id)
```

- [ ] **Step 6: Run all backend tests**

```bash
pytest tests/services/test_gateway/test_packages_list_routes.py -v
```
Expected: All PASS

```bash
pytest --tb=short -q
```
Expected: All existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add libs/storage/lance_content_store.py libs/storage/manager.py \
  services/gateway/routes/packages.py \
  tests/services/test_gateway/test_packages_list_routes.py
git commit -m "feat: add GET /graph endpoint for Knowledge/Chain DAG data"
```

---

## Chunk 2: Frontend API Client + Types

### File Map

| Action | File |
|--------|------|
| Create | `frontend/src/api/v2-types.ts` — TypeScript types for v2 entities |
| Create | `frontend/src/api/v2.ts` — API fetch functions + React Query hooks |

---

### Task 5: V2 TypeScript types

**Files:**
- Create: `frontend/src/api/v2-types.ts`

- [ ] **Step 1: Create types file**

```typescript
// frontend/src/api/v2-types.ts

export type KnowledgeType = "claim" | "question" | "setting" | "action";
export type ChainType = "deduction" | "induction" | "abstraction" | "contradiction" | "retraction";
export type PackageStatus = "preparing" | "submitted" | "merged" | "rejected";

export interface KnowledgeRef {
  knowledge_id: string;
  version: number;
}

export interface V2Knowledge {
  knowledge_id: string;
  version: number;
  type: KnowledgeType;
  content: string;
  prior: number;
  keywords: string[];
  source_package_id: string;
  source_package_version: string;
  source_module_id: string;
  created_at: string | null;
}

export interface ChainStep {
  step_index: number;
  premises: KnowledgeRef[];
  reasoning: string;
  conclusion: KnowledgeRef;
}

export interface V2Chain {
  chain_id: string;
  module_id: string;
  package_id: string;
  package_version: string;
  type: ChainType;
  steps: ChainStep[];
}

export interface ImportRef {
  knowledge_id: string;
  version: number;
  strength: string;
}

export interface V2Module {
  module_id: string;
  package_id: string;
  package_version: string;
  name: string;
  role: string;
  imports: ImportRef[];
  chain_ids: string[];
  export_ids: string[];
}

export interface V2Package {
  package_id: string;
  name: string;
  version: string;
  description: string;
  modules: string[];
  exports: string[];
  submitter: string;
  submitted_at: string;
  status: PackageStatus;
}

export interface V2ProbabilityRecord {
  chain_id: string;
  step_index: number;
  value: number;
  source: string;
  source_detail: string | null;
  recorded_at: string;
}

export interface V2BeliefSnapshot {
  knowledge_id: string;
  version: number;
  belief: number;
  bp_run_id: string;
  computed_at: string;
}

export interface V2Paginated<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface GraphNode {
  id: string;
  knowledge_id: string;
  version: number;
  type: KnowledgeType;
  content: string;
  prior: number;
}

export interface GraphEdge {
  chain_id: string;
  from: string;
  to: string;
  chain_type: ChainType;
  step_index: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/v2-types.ts
git commit -m "feat: add TypeScript types for v2 entities"
```

---

### Task 6: V2 API client + React Query hooks

**Files:**
- Create: `frontend/src/api/v2.ts`

- [ ] **Step 1: Create API client**

```typescript
// frontend/src/api/v2.ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type {
  V2Package, V2Knowledge, V2Module, V2Chain,
  V2ProbabilityRecord, V2BeliefSnapshot,
  V2Paginated, GraphData,
} from "./v2-types";

// ── Fetch functions ──

export const fetchPackages = (page = 1, pageSize = 20) =>
  apiFetch<V2Paginated<V2Package>>(`/packages?page=${page}&page_size=${pageSize}`);

export const fetchPackage = (id: string) =>
  apiFetch<V2Package>(`/packages/${encodeURIComponent(id)}`);

export const fetchKnowledgeList = (page = 1, pageSize = 20, typeFilter?: string) => {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (typeFilter) params.set("type_filter", typeFilter);
  return apiFetch<V2Paginated<V2Knowledge>>(`/knowledge?${params}`);
};

export const fetchKnowledge = (id: string, version?: number) => {
  const path = version
    ? `/knowledge/${encodeURIComponent(id)}?version=${version}`
    : `/knowledge/${encodeURIComponent(id)}`;
  return apiFetch<V2Knowledge>(path);
};

export const fetchKnowledgeVersions = (id: string) =>
  apiFetch<V2Knowledge[]>(`/knowledge/${encodeURIComponent(id)}/versions`);

export const fetchKnowledgeBeliefs = (id: string) =>
  apiFetch<V2BeliefSnapshot[]>(`/knowledge/${encodeURIComponent(id)}/beliefs`);

export const fetchModules = (packageId?: string) => {
  const params = packageId ? `?package_id=${encodeURIComponent(packageId)}` : "";
  return apiFetch<V2Module[]>(`/modules${params}`);
};

export const fetchModule = (id: string) =>
  apiFetch<V2Module>(`/modules/${encodeURIComponent(id)}`);

export const fetchModuleChains = (moduleId: string) =>
  apiFetch<V2Chain[]>(`/modules/${encodeURIComponent(moduleId)}/chains`);

export const fetchChain = (id: string) =>
  apiFetch<V2Chain>(`/chains/${encodeURIComponent(id)}`);

export const fetchChainProbabilities = (id: string) =>
  apiFetch<V2ProbabilityRecord[]>(`/chains/${encodeURIComponent(id)}/probabilities`);

export const fetchGraphData = (packageId?: string) => {
  const params = packageId ? `?package_id=${encodeURIComponent(packageId)}` : "";
  return apiFetch<GraphData>(`/graph${params}`);
};

// ── React Query hooks ──

export const usePackages = (page = 1, pageSize = 20) =>
  useQuery({ queryKey: ["v2", "packages", page, pageSize], queryFn: () => fetchPackages(page, pageSize) });

export const usePackage = (id: string) =>
  useQuery({ queryKey: ["v2", "package", id], queryFn: () => fetchPackage(id), enabled: !!id });

export const useKnowledgeList = (page = 1, pageSize = 20, typeFilter?: string) =>
  useQuery({
    queryKey: ["v2", "knowledge", page, pageSize, typeFilter],
    queryFn: () => fetchKnowledgeList(page, pageSize, typeFilter),
  });

export const useKnowledge = (id: string) =>
  useQuery({ queryKey: ["v2", "knowledge", id], queryFn: () => fetchKnowledge(id), enabled: !!id });

export const useKnowledgeVersions = (id: string) =>
  useQuery({ queryKey: ["v2", "knowledge-versions", id], queryFn: () => fetchKnowledgeVersions(id), enabled: !!id });

export const useKnowledgeBeliefs = (id: string) =>
  useQuery({ queryKey: ["v2", "knowledge-beliefs", id], queryFn: () => fetchKnowledgeBeliefs(id), enabled: !!id });

export const useModules = (packageId?: string) =>
  useQuery({ queryKey: ["v2", "modules", packageId], queryFn: () => fetchModules(packageId) });

export const useModule = (id: string) =>
  useQuery({ queryKey: ["v2", "module", id], queryFn: () => fetchModule(id), enabled: !!id });

export const useModuleChains = (moduleId: string) =>
  useQuery({ queryKey: ["v2", "module-chains", moduleId], queryFn: () => fetchModuleChains(moduleId), enabled: !!moduleId });

export const useChain = (id: string) =>
  useQuery({ queryKey: ["v2", "chain", id], queryFn: () => fetchChain(id), enabled: !!id });

export const useChainProbabilities = (id: string) =>
  useQuery({ queryKey: ["v2", "chain-probs", id], queryFn: () => fetchChainProbabilities(id), enabled: !!id });

export const useGraphData = (packageId?: string) =>
  useQuery({ queryKey: ["v2", "graph", packageId], queryFn: () => fetchGraphData(packageId) });
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/v2.ts
git commit -m "feat: add v2 API client and React Query hooks"
```

---

## Chunk 3: List Pages + Navigation

### File Map

| Action | File |
|--------|------|
| Create | `frontend/src/pages/v2/PackageList.tsx` |
| Create | `frontend/src/pages/v2/KnowledgeList.tsx` |
| Modify | `frontend/src/components/layout/Sidebar.tsx` — add V2 group |
| Modify | `frontend/src/App.tsx` — add V2 routes |

---

### Task 7: PackageList page + routing + navigation

**Files:**
- Create: `frontend/src/pages/v2/PackageList.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Create PackageList page**

```tsx
// frontend/src/pages/v2/PackageList.tsx
import { useState } from "react";
import { Table, Tag, Typography, Input } from "antd";
import { Link } from "react-router-dom";
import { usePackages } from "../../api/v2";
import type { V2Package } from "../../api/v2-types";

const STATUS_COLORS: Record<string, string> = {
  merged: "green",
  submitted: "blue",
  preparing: "orange",
  rejected: "red",
};

const columns = [
  {
    title: "Package ID",
    dataIndex: "package_id",
    render: (id: string) => <Link to={`/v2/packages/${encodeURIComponent(id)}`}>{id}</Link>,
  },
  { title: "Version", dataIndex: "version", width: 100 },
  {
    title: "Status",
    dataIndex: "status",
    width: 110,
    render: (s: string) => <Tag color={STATUS_COLORS[s] ?? "default"}>{s}</Tag>,
  },
  { title: "Submitter", dataIndex: "submitter", width: 160 },
  { title: "Description", dataIndex: "description", ellipsis: true },
];

export function PackageList() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const PAGE_SIZE = 20;
  const { data, isLoading, error } = usePackages(page, PAGE_SIZE);

  if (error) return <Typography.Text type="danger">Failed to load packages</Typography.Text>;

  const filtered = search
    ? (data?.items ?? []).filter((p) => p.package_id.includes(search) || p.description.includes(search))
    : (data?.items ?? []);

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>Packages</Typography.Title>
      <Input.Search
        placeholder="Search by package ID or description"
        style={{ width: 360, marginBottom: 16 }}
        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        allowClear
      />
      <Table<V2Package>
        rowKey="package_id"
        columns={columns}
        dataSource={filtered}
        loading={isLoading}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: data?.total ?? 0,
          onChange: setPage,
          showTotal: (t) => `${t} packages`,
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Add V2 routes to `App.tsx`**

Add imports and routes to `frontend/src/App.tsx`:

```tsx
// Add imports (after existing imports):
import { PackageList } from "./pages/v2/PackageList";

// Add routes inside <Route element={<AppShell />}>:
<Route path="v2/packages" element={<PackageList />} />
```

- [ ] **Step 3: Update Sidebar**

In `frontend/src/components/layout/Sidebar.tsx`, add to the `items` array:

```tsx
// Add import:
import { DatabaseOutlined } from "@ant-design/icons";

// Add to items array:
{
  key: "v2",
  icon: <DatabaseOutlined />,
  label: "V2",
  children: [
    {
      key: "/v2/packages",
      label: <Link to="/v2/packages">Packages</Link>,
    },
    {
      key: "/v2/knowledge",
      label: <Link to="/v2/knowledge">Knowledge</Link>,
    },
    {
      key: "/v2/graph",
      label: <Link to="/v2/graph">Graph IR</Link>,
    },
  ],
},
```

Also update `selectedKeys` in `Sidebar` to handle sub-paths:
```tsx
selectedKeys={[location.pathname]}
defaultOpenKeys={location.pathname.startsWith("/v2") ? ["v2"] : []}
```

- [ ] **Step 4: Start dev server and verify PackageList renders**

```bash
cd frontend && npm run dev
```
Open http://localhost:5173, click "V2 → Packages" in sidebar. Should show a table (empty or with data depending on backend).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/v2/PackageList.tsx \
  frontend/src/App.tsx \
  frontend/src/components/layout/Sidebar.tsx
git commit -m "feat: add PackageList page with v2 sidebar navigation"
```

---

### Task 8: KnowledgeList page

**Files:**
- Create: `frontend/src/pages/v2/KnowledgeList.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create KnowledgeList page**

```tsx
// frontend/src/pages/v2/KnowledgeList.tsx
import { useState } from "react";
import { Table, Select, Tag, Typography, Space } from "antd";
import { Link } from "react-router-dom";
import { useKnowledgeList } from "../../api/v2";
import type { V2Knowledge, KnowledgeType } from "../../api/v2-types";

const TYPE_COLORS: Record<KnowledgeType, string> = {
  claim: "blue",
  setting: "green",
  question: "orange",
  action: "purple",
};

const KNOWLEDGE_TYPES: KnowledgeType[] = ["claim", "question", "setting", "action"];

const columns = [
  {
    title: "Knowledge ID",
    dataIndex: "knowledge_id",
    ellipsis: true,
    render: (id: string) => (
      <Link to={`/v2/knowledge/${encodeURIComponent(id)}`}>{id}</Link>
    ),
  },
  {
    title: "Type",
    dataIndex: "type",
    width: 100,
    render: (t: KnowledgeType) => <Tag color={TYPE_COLORS[t]}>{t}</Tag>,
  },
  { title: "v", dataIndex: "version", width: 50 },
  { title: "Prior", dataIndex: "prior", width: 70, render: (p: number) => p.toFixed(2) },
  { title: "Content", dataIndex: "content", ellipsis: true },
];

export function KnowledgeList() {
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState<KnowledgeType | undefined>();
  const PAGE_SIZE = 20;
  const { data, isLoading, error } = useKnowledgeList(page, PAGE_SIZE, typeFilter);

  if (error) return <Typography.Text type="danger">Failed to load knowledge</Typography.Text>;

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>Knowledge</Typography.Title>
      <Space style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="Filter by type"
          style={{ width: 160 }}
          options={KNOWLEDGE_TYPES.map((t) => ({ value: t, label: t }))}
          onChange={(v) => { setTypeFilter(v); setPage(1); }}
        />
      </Space>
      <Table<V2Knowledge>
        rowKey={(r) => `${r.knowledge_id}@${r.version}`}
        columns={columns}
        dataSource={data?.items ?? []}
        loading={isLoading}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: data?.total ?? 0,
          onChange: setPage,
          showTotal: (t) => `${t} items`,
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Add route to `App.tsx`**

```tsx
import { KnowledgeList } from "./pages/v2/KnowledgeList";
// inside Routes:
<Route path="v2/knowledge" element={<KnowledgeList />} />
```

- [ ] **Step 3: Verify in browser**

Navigate to V2 → Knowledge. Table with type filter dropdown should render.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/v2/KnowledgeList.tsx frontend/src/App.tsx
git commit -m "feat: add KnowledgeList page with type filter"
```

---

## Chunk 4: Detail Pages

### File Map

| Action | File |
|--------|------|
| Create | `frontend/src/pages/v2/PackageDetail.tsx` |
| Create | `frontend/src/pages/v2/KnowledgeDetail.tsx` |
| Create | `frontend/src/pages/v2/ModuleDetail.tsx` |
| Create | `frontend/src/pages/v2/ChainDetail.tsx` |
| Modify | `frontend/src/App.tsx` |

---

### Task 9: PackageDetail + ModuleDetail pages

**Files:**
- Create: `frontend/src/pages/v2/PackageDetail.tsx`
- Create: `frontend/src/pages/v2/ModuleDetail.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create PackageDetail page**

```tsx
// frontend/src/pages/v2/PackageDetail.tsx
import { Breadcrumb, Card, Descriptions, List, Tag, Typography, Spin } from "antd";
import { Link, useParams } from "react-router-dom";
import { usePackage, useModules } from "../../api/v2";

export function PackageDetail() {
  const { id } = useParams<{ id: string }>();
  const pkgId = decodeURIComponent(id ?? "");
  const { data: pkg, isLoading: pkgLoading } = usePackage(pkgId);
  const { data: modules, isLoading: modLoading } = useModules(pkgId);

  if (pkgLoading) return <Spin />;
  if (!pkg) return <Typography.Text type="danger">Package not found</Typography.Text>;

  return (
    <div>
      <Breadcrumb style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/v2/packages">Packages</Link> },
          { title: pkg.package_id },
        ]}
      />
      <Typography.Title level={3}>{pkg.name}</Typography.Title>
      <Card style={{ marginBottom: 16 }}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="Package ID">{pkg.package_id}</Descriptions.Item>
          <Descriptions.Item label="Version">{pkg.version}</Descriptions.Item>
          <Descriptions.Item label="Status">
            <Tag color={pkg.status === "merged" ? "green" : "orange"}>{pkg.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Submitter">{pkg.submitter}</Descriptions.Item>
          <Descriptions.Item label="Submitted At">{pkg.submitted_at}</Descriptions.Item>
          <Descriptions.Item label="Description" span={2}>{pkg.description}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title={`Modules (${modules?.length ?? 0})`} loading={modLoading}>
        <List
          dataSource={modules ?? []}
          renderItem={(m) => (
            <List.Item>
              <Link to={`/v2/modules/${encodeURIComponent(m.module_id)}`}>{m.module_id}</Link>
              <Tag style={{ marginLeft: 8 }}>{m.role}</Tag>
              <span style={{ marginLeft: 8, color: "#888" }}>
                {m.chain_ids.length} chains · {m.export_ids.length} exports
              </span>
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Create ModuleDetail page**

```tsx
// frontend/src/pages/v2/ModuleDetail.tsx
import { Breadcrumb, Card, Descriptions, List, Tag, Typography, Spin } from "antd";
import { Link, useParams } from "react-router-dom";
import { useModule, useModuleChains } from "../../api/v2";

export function ModuleDetail() {
  const { id } = useParams<{ id: string }>();
  const moduleId = decodeURIComponent(id ?? "");
  const { data: mod, isLoading: modLoading } = useModule(moduleId);
  const { data: chains, isLoading: chainsLoading } = useModuleChains(moduleId);

  if (modLoading) return <Spin />;
  if (!mod) return <Typography.Text type="danger">Module not found</Typography.Text>;

  const pkgId = mod.package_id;

  return (
    <div>
      <Breadcrumb style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/v2/packages">Packages</Link> },
          { title: <Link to={`/v2/packages/${encodeURIComponent(pkgId)}`}>{pkgId}</Link> },
          { title: mod.name },
        ]}
      />
      <Typography.Title level={3}>{mod.module_id}</Typography.Title>
      <Card style={{ marginBottom: 16 }}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="Role">{mod.role}</Descriptions.Item>
          <Descriptions.Item label="Package">
            <Link to={`/v2/packages/${encodeURIComponent(pkgId)}`}>{pkgId}</Link>
          </Descriptions.Item>
          <Descriptions.Item label="Imports">{mod.imports.length}</Descriptions.Item>
          <Descriptions.Item label="Exports">{mod.export_ids.length}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title={`Chains (${chains?.length ?? 0})`} loading={chainsLoading}>
        <List
          dataSource={chains ?? []}
          renderItem={(c) => (
            <List.Item>
              <Link to={`/v2/chains/${encodeURIComponent(c.chain_id)}`}>{c.chain_id}</Link>
              <Tag style={{ marginLeft: 8 }}>{c.type}</Tag>
              <span style={{ marginLeft: 8, color: "#888" }}>{c.steps.length} steps</span>
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Add routes to `App.tsx`**

```tsx
import { PackageDetail } from "./pages/v2/PackageDetail";
import { ModuleDetail } from "./pages/v2/ModuleDetail";
// inside Routes:
<Route path="v2/packages/:id" element={<PackageDetail />} />
<Route path="v2/modules/:id" element={<ModuleDetail />} />
```

- [ ] **Step 4: Verify in browser**

Click a package in the Packages list → PackageDetail should load. Click a module → ModuleDetail should load.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/v2/PackageDetail.tsx \
  frontend/src/pages/v2/ModuleDetail.tsx \
  frontend/src/App.tsx
git commit -m "feat: add PackageDetail and ModuleDetail pages"
```

---

### Task 10: KnowledgeDetail + ChainDetail pages

**Files:**
- Create: `frontend/src/pages/v2/KnowledgeDetail.tsx`
- Create: `frontend/src/pages/v2/ChainDetail.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create KnowledgeDetail page**

```tsx
// frontend/src/pages/v2/KnowledgeDetail.tsx
import { Breadcrumb, Card, Descriptions, List, Table, Tag, Tabs, Typography, Spin } from "antd";
import { Link, useParams } from "react-router-dom";
import { useKnowledge, useKnowledgeVersions, useKnowledgeBeliefs } from "../../api/v2";
import type { V2Knowledge, V2BeliefSnapshot } from "../../api/v2-types";

const TYPE_COLORS: Record<string, string> = {
  claim: "blue", setting: "green", question: "orange", action: "purple",
};

export function KnowledgeDetail() {
  const { id } = useParams<{ id: string }>();
  const knowledgeId = decodeURIComponent(id ?? "");
  const { data: k, isLoading } = useKnowledge(knowledgeId);
  const { data: versions } = useKnowledgeVersions(knowledgeId);
  const { data: beliefs } = useKnowledgeBeliefs(knowledgeId);

  if (isLoading) return <Spin />;
  if (!k) return <Typography.Text type="danger">Knowledge not found</Typography.Text>;

  const beliefColumns = [
    { title: "Belief", dataIndex: "belief", render: (v: number) => v.toFixed(4) },
    { title: "BP Run", dataIndex: "bp_run_id" },
    { title: "Computed At", dataIndex: "computed_at" },
  ];

  const versionColumns = [
    { title: "Version", dataIndex: "version" },
    { title: "Type", dataIndex: "type", render: (t: string) => <Tag color={TYPE_COLORS[t]}>{t}</Tag> },
    { title: "Prior", dataIndex: "prior", render: (p: number) => p.toFixed(2) },
    { title: "Content", dataIndex: "content", ellipsis: true },
  ];

  return (
    <div>
      <Breadcrumb style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/v2/knowledge">Knowledge</Link> },
          { title: k.knowledge_id },
        ]}
      />
      <Typography.Title level={3}>
        <Tag color={TYPE_COLORS[k.type]}>{k.type}</Tag> {k.knowledge_id}
      </Typography.Title>
      <Tabs
        items={[
          {
            key: "content",
            label: "Content",
            children: (
              <Card>
                <Descriptions bordered column={2}>
                  <Descriptions.Item label="Prior">{k.prior.toFixed(2)}</Descriptions.Item>
                  <Descriptions.Item label="Version">{k.version}</Descriptions.Item>
                  <Descriptions.Item label="Package">
                    <Link to={`/v2/packages/${encodeURIComponent(k.source_package_id)}`}>
                      {k.source_package_id}
                    </Link>
                  </Descriptions.Item>
                  <Descriptions.Item label="Module">
                    <Link to={`/v2/modules/${encodeURIComponent(k.source_module_id)}`}>
                      {k.source_module_id}
                    </Link>
                  </Descriptions.Item>
                  <Descriptions.Item label="Keywords" span={2}>
                    {k.keywords.map((kw) => <Tag key={kw}>{kw}</Tag>)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Content" span={2}>
                    <Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>{k.content}</Typography.Paragraph>
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            ),
          },
          {
            key: "versions",
            label: `Versions (${versions?.length ?? 0})`,
            children: (
              <Table<V2Knowledge>
                rowKey={(r) => String(r.version)}
                columns={versionColumns}
                dataSource={versions ?? []}
                pagination={false}
              />
            ),
          },
          {
            key: "beliefs",
            label: `Beliefs (${beliefs?.length ?? 0})`,
            children: (
              <Table<V2BeliefSnapshot>
                rowKey="bp_run_id"
                columns={beliefColumns}
                dataSource={beliefs ?? []}
                pagination={false}
              />
            ),
          },
        ]}
      />
    </div>
  );
}
```

- [ ] **Step 2: Create ChainDetail page**

```tsx
// frontend/src/pages/v2/ChainDetail.tsx
import { Breadcrumb, Card, Descriptions, List, Table, Tag, Typography, Spin } from "antd";
import { Link, useParams } from "react-router-dom";
import { useChain, useChainProbabilities } from "../../api/v2";
import type { ChainStep, V2ProbabilityRecord } from "../../api/v2-types";

export function ChainDetail() {
  const { id } = useParams<{ id: string }>();
  const chainId = decodeURIComponent(id ?? "");
  const { data: chain, isLoading } = useChain(chainId);
  const { data: probs } = useChainProbabilities(chainId);

  if (isLoading) return <Spin />;
  if (!chain) return <Typography.Text type="danger">Chain not found</Typography.Text>;

  const probColumns = [
    { title: "Step", dataIndex: "step_index", width: 60 },
    { title: "Value", dataIndex: "value", render: (v: number) => v.toFixed(4) },
    { title: "Source", dataIndex: "source" },
    { title: "Recorded At", dataIndex: "recorded_at" },
  ];

  return (
    <div>
      <Breadcrumb style={{ marginBottom: 16 }}
        items={[
          { title: <Link to={`/v2/modules/${encodeURIComponent(chain.module_id)}`}>{chain.module_id}</Link> },
          { title: "Chain" },
        ]}
      />
      <Typography.Title level={3}>
        <Tag>{chain.type}</Tag> {chain.chain_id}
      </Typography.Title>
      <List
        header={<Typography.Text strong>Steps ({chain.steps.length})</Typography.Text>}
        dataSource={chain.steps}
        renderItem={(step: ChainStep) => (
          <List.Item>
            <Card style={{ width: "100%" }} size="small"
              title={`Step ${step.step_index}`}>
              <Typography.Text type="secondary">Premises:</Typography.Text>
              <List
                size="small"
                dataSource={step.premises}
                renderItem={(p) => (
                  <List.Item>
                    <Link to={`/v2/knowledge/${encodeURIComponent(p.knowledge_id)}`}>
                      {p.knowledge_id}@{p.version}
                    </Link>
                  </List.Item>
                )}
              />
              {step.reasoning && (
                <Typography.Paragraph style={{ marginTop: 8 }}>
                  <Typography.Text type="secondary">Reasoning: </Typography.Text>
                  {step.reasoning}
                </Typography.Paragraph>
              )}
              <Typography.Text type="secondary">Conclusion: </Typography.Text>
              <Link to={`/v2/knowledge/${encodeURIComponent(step.conclusion.knowledge_id)}`}>
                {step.conclusion.knowledge_id}@{step.conclusion.version}
              </Link>
            </Card>
          </List.Item>
        )}
      />
      {probs && probs.length > 0 && (
        <Card title="Probabilities" style={{ marginTop: 16 }}>
          <Table<V2ProbabilityRecord>
            rowKey={(r) => `${r.step_index}-${r.source}`}
            columns={probColumns}
            dataSource={probs}
            pagination={false}
          />
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add routes to `App.tsx`**

```tsx
import { KnowledgeDetail } from "./pages/v2/KnowledgeDetail";
import { ChainDetail } from "./pages/v2/ChainDetail";
// inside Routes:
<Route path="v2/knowledge/:id" element={<KnowledgeDetail />} />
<Route path="v2/chains/:id" element={<ChainDetail />} />
```

- [ ] **Step 4: Verify in browser**

Click a knowledge item → tabs (Content / Versions / Beliefs) render. Click a chain in ModuleDetail → ChainDetail shows steps with links.

- [ ] **Step 5: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/v2/KnowledgeDetail.tsx \
  frontend/src/pages/v2/ChainDetail.tsx \
  frontend/src/App.tsx
git commit -m "feat: add KnowledgeDetail and ChainDetail pages"
```

---

## Chunk 5: Graph DAG Page

### File Map

| Action | File |
|--------|------|
| Create | `frontend/src/lib/v2-graph-transform.ts` — transform GraphData to vis-network format |
| Create | `frontend/src/pages/v2/GraphViewer.tsx` — DAG page |
| Modify | `frontend/src/App.tsx` |

---

### Task 11: Graph transform utility

**Files:**
- Create: `frontend/src/lib/v2-graph-transform.ts`

- [ ] **Step 1: Create transform utility**

```typescript
// frontend/src/lib/v2-graph-transform.ts
import type { GraphData, GraphNode, GraphEdge, KnowledgeType } from "../api/v2-types";

const TYPE_COLORS: Record<KnowledgeType, string> = {
  claim: "#1677ff",
  setting: "#52c41a",
  question: "#fa8c16",
  action: "#722ed1",
};

export interface VisNode {
  id: string;
  label: string;
  title: string;  // tooltip
  color: { background: string; border: string };
  font: { color: string };
  shape: "box";
}

export interface VisEdge {
  id: string;
  from: string;
  to: string;
  label: string;
  arrows: "to";
  color: { color: string };
  font: { size: number };
}

function truncate(s: string, n = 50): string {
  return s.length > n ? s.slice(0, n) + "…" : s;
}

export function toVisGraph(data: GraphData): { nodes: VisNode[]; edges: VisEdge[] } {
  const nodes: VisNode[] = data.nodes.map((n: GraphNode) => ({
    id: n.id,
    label: truncate(n.content, 50),
    title: `[${n.type}] ${n.content}\nprior: ${n.prior.toFixed(2)}`,
    color: {
      background: TYPE_COLORS[n.type] ?? "#aaa",
      border: "#333",
    },
    font: { color: "#fff" },
    shape: "box",
  }));

  const edgeMap = new Map<string, VisEdge>();
  data.edges.forEach((e: GraphEdge) => {
    const key = `${e.from}->${e.to}`;
    if (!edgeMap.has(key)) {
      edgeMap.set(key, {
        id: `${e.chain_id}:${e.step_index}:${e.from}:${e.to}`,
        from: e.from,
        to: e.to,
        label: e.chain_type,
        arrows: "to",
        color: { color: "#888" },
        font: { size: 10 },
      });
    }
  });

  return { nodes, edges: Array.from(edgeMap.values()) };
}

export const HIERARCHICAL_OPTIONS = {
  layout: {
    hierarchical: {
      enabled: true,
      direction: "UD",
      sortMethod: "directed",
      levelSeparation: 120,
      nodeSpacing: 180,
    },
  },
  physics: { enabled: false },
  interaction: { hover: true, tooltipDelay: 100 },
  nodes: { borderWidth: 1, borderWidthSelected: 2 },
  edges: { smooth: { type: "cubicBezier", forceDirection: "vertical" } },
};
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/v2-graph-transform.ts
git commit -m "feat: add v2 graph transform utility for vis-network DAG layout"
```

---

### Task 12: GraphViewer page

**Files:**
- Create: `frontend/src/pages/v2/GraphViewer.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create GraphViewer page**

```tsx
// frontend/src/pages/v2/GraphViewer.tsx
import { useEffect, useRef, useState } from "react";
import { Card, Select, Typography, Spin, Drawer } from "antd";
import { Network } from "vis-network";
import { DataSet } from "vis-data";
import { useGraphData, usePackages, useKnowledge } from "../../api/v2";
import { toVisGraph, HIERARCHICAL_OPTIONS } from "../../lib/v2-graph-transform";
import { Link } from "react-router-dom";

export function GraphViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const [packageId, setPackageId] = useState<string | undefined>();
  const [selectedKnowledgeId, setSelectedKnowledgeId] = useState<string | null>(null);

  const { data: packages } = usePackages(1, 100);
  const { data: graphData, isLoading } = useGraphData(packageId);

  // Build or update vis-network when data changes
  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    const { nodes, edges } = toVisGraph(graphData);
    const nodeDs = new DataSet(nodes);
    const edgeDs = new DataSet(edges);

    if (networkRef.current) {
      networkRef.current.destroy();
    }

    const net = new Network(
      containerRef.current,
      { nodes: nodeDs, edges: edgeDs },
      HIERARCHICAL_OPTIONS,
    );

    net.on("click", (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0] as string;
        // nodeId format: knowledge_id@version
        const knowledgeId = nodeId.split("@").slice(0, -1).join("@");
        setSelectedKnowledgeId(knowledgeId);
      }
    });

    networkRef.current = net;

    return () => {
      net.destroy();
      networkRef.current = null;
    };
  }, [graphData]);

  const packageOptions = (packages?.items ?? []).map((p) => ({
    value: p.package_id,
    label: p.package_id,
  }));

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>Graph IR</Typography.Title>
      <Card style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="Filter by package (all if empty)"
          style={{ width: 400 }}
          options={packageOptions}
          onChange={(v) => setPackageId(v)}
        />
        <Typography.Text style={{ marginLeft: 16, color: "#888" }}>
          {graphData ? `${graphData.nodes.length} nodes · ${graphData.edges.length} edges` : ""}
        </Typography.Text>
      </Card>
      {isLoading ? (
        <Spin style={{ display: "block", marginTop: 80 }} />
      ) : (
        <div
          ref={containerRef}
          style={{ width: "100%", height: "70vh", border: "1px solid #e8e8e8", borderRadius: 6, background: "#fafafa" }}
        />
      )}
      <Drawer
        title={
          selectedKnowledgeId ? (
            <Link to={`/v2/knowledge/${encodeURIComponent(selectedKnowledgeId)}`}>
              {selectedKnowledgeId}
            </Link>
          ) : "Knowledge"
        }
        open={!!selectedKnowledgeId}
        onClose={() => setSelectedKnowledgeId(null)}
        width={520}
      >
        {selectedKnowledgeId && <KnowledgeDetailInline id={selectedKnowledgeId} />}
      </Drawer>
    </div>
  );
}

function KnowledgeDetailInline({ id }: { id: string }) {
  const { data: k, isLoading } = useKnowledge(id);
  if (isLoading) return <Spin />;
  if (!k) return <Typography.Text type="danger">Not found</Typography.Text>;
  return (
    <div>
      <Typography.Text type="secondary">{k.type}</Typography.Text>
      <Typography.Paragraph style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{k.content}</Typography.Paragraph>
      <Typography.Text>Prior: {k.prior.toFixed(2)}</Typography.Text>
    </div>
  );
}
```

- [ ] **Step 2: Add route to `App.tsx`**

```tsx
import { GraphViewer } from "./pages/v2/GraphViewer";
// inside Routes:
<Route path="v2/graph" element={<GraphViewer />} />
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 4: Verify in browser**

Navigate to V2 → Graph IR. Select a package from the dropdown. DAG should render with nodes flowing top-down. Click a node → right-side drawer shows knowledge content.

- [ ] **Step 5: Run all backend tests one final time**

```bash
pytest --tb=short -q
```
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/v2/GraphViewer.tsx frontend/src/App.tsx
git commit -m "feat: add Graph IR DAG page with hierarchical layout and knowledge detail drawer"
```

---

## Final: Push and Create PR

- [ ] **Push branch and open PR**

```bash
git push -u origin <branch-name>
gh pr create --title "feat: v2 database browser and Graph IR visualizer" \
  --body "Adds 7 new pages for browsing v2 storage (Packages, Knowledge, Modules, Chains) and a DAG view of the knowledge graph. Backend adds list + graph endpoints."
```
