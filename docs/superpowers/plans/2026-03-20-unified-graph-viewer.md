# Unified Graph Viewer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace three separate graph tabs (Graph Explorer, Graph IR Viewer, Global Graph) with one unified Graph Viewer that reads knowledge + factors from DB and renders a factor graph with package filtering.

**Architecture:** One backend endpoint `GET /graph` returns `{knowledge_nodes, factor_nodes}` from DB (LanceDB knowledge + factors tables). One frontend component renders the factor graph (premise → factor → conclusion) using vis-network, with a package selector to filter scope. The existing `GraphIRViewer.tsx` vis-network rendering code is reused as the rendering engine.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/vis-network/Ant Design (frontend)

---

## Current State (what exists today)

### Three graph tabs:
| Tab | Route | Data source | Has factors? |
|-----|-------|-------------|-------------|
| Graph Explorer | `/graph` | `GET /graph` → DB (knowledge + chain edges) | No — knowledge-to-knowledge edges only |
| Graph IR Viewer | `/v2/graph-ir` | `GET /graph-ir/{slug}/local` → **local fixture files** | Yes |
| Global Graph | `/v2/global-graph` | `GET /graph-ir/global` → **local fixture file** | Yes |

### Problems:
1. Graph Explorer has no factor nodes (flat knowledge-to-knowledge edges)
2. Graph IR Viewer reads from **local fixture files**, not DB
3. Global Graph reads from **local fixture file**, not DB
4. Three separate components with duplicated vis-network code

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `services/gateway/routes/packages.py` | **Modify** | Change `GET /graph` to return `{knowledge_nodes, factor_nodes}` from DB |
| `libs/storage/lance_content_store.py` | **Modify** | Rewrite `get_graph_data()` to return knowledge nodes + factor nodes (not chain edges) |
| `frontend/src/pages/v2/GraphViewer.tsx` | **Rewrite** | Unified graph viewer: package selector, factor graph rendering, node detail drawer |
| `frontend/src/App.tsx` | **Modify** | Remove old graph routes, point `/v2/graph` to unified viewer |
| `frontend/src/components/layout/Sidebar.tsx` | **Modify** | Remove Graph IR Viewer and Global Graph menu items |

### Files to delete after migration:
| File | Reason |
|------|--------|
| `frontend/src/pages/v2/GraphIRViewer.tsx` | Replaced by unified viewer |
| `frontend/src/pages/v2/GlobalGraphViewer.tsx` | Replaced by unified viewer |
| `frontend/src/pages/GraphExplorer.tsx` | Old v1 graph, replaced |
| `frontend/src/lib/v2-graph-transform.ts` | Only used by old GraphViewer |
| `services/gateway/routes/graph_ir.py` | Read from fixture files, no longer needed |

---

## Chunk 1: Backend — Unified `/graph` API

### Task 1: Rewrite `get_graph_data()` to return knowledge + factors

**Files:**
- Modify: `libs/storage/lance_content_store.py:995-1039`
- Modify: `services/gateway/routes/packages.py:247-251`

The current `get_graph_data()` returns `{nodes, edges}` built from chains. Replace with `{knowledge_nodes, factor_nodes}` read directly from the `knowledge` and `factors` tables.

- [ ] **Step 1: Rewrite `get_graph_data` in lance_content_store.py**

```python
async def get_graph_data(self, package_id: str | None = None) -> dict:
    """Return knowledge nodes + factor nodes for factor graph visualization.

    Returns:
        {
            "knowledge_nodes": [{knowledge_id, version, type, kind, content, prior, source_package_id, source_module_id}, ...],
            "factor_nodes": [{factor_id, type, premises, contexts, conclusion, package_id, metadata}, ...],
        }
    """
    items, _ = await self.list_knowledge_paged(page=1, page_size=10_000)
    factors = await self.list_factors()

    if package_id:
        items = [k for k in items if k.source_package_id == package_id]
        factors = [f for f in factors if f.package_id == package_id]

    knowledge_nodes = [
        {
            "knowledge_id": k.knowledge_id,
            "version": k.version,
            "type": k.type,
            "kind": k.kind,
            "content": k.content,
            "prior": k.prior,
            "source_package_id": k.source_package_id,
            "source_module_id": k.source_module_id,
        }
        for k in items
    ]

    factor_nodes = [
        {
            "factor_id": f.factor_id,
            "type": f.type,
            "premises": f.premises,
            "contexts": f.contexts,
            "conclusion": f.conclusion,
            "package_id": f.package_id,
            "metadata": f.metadata,
        }
        for f in factors
    ]

    return {"knowledge_nodes": knowledge_nodes, "factor_nodes": factor_nodes}
```

- [ ] **Step 2: Verify `/graph` route in packages.py still works**

The route at `packages.py:247-251` already calls `mgr.get_graph_data(package_id=package_id)` — no changes needed to the route itself, just the return shape changed.

- [ ] **Step 3: Test the API**

```bash
curl -s http://localhost:8000/graph | python -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d[\"knowledge_nodes\"])} nodes, {len(d[\"factor_nodes\"])} factors')"
curl -s "http://localhost:8000/graph?package_id=paper_10_1038332139a0_1988_natu" | python -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d[\"knowledge_nodes\"])} nodes, {len(d[\"factor_nodes\"])} factors')"
```

- [ ] **Step 4: Commit**

```bash
git add libs/storage/lance_content_store.py
git commit -m "feat: /graph API returns knowledge_nodes + factor_nodes from DB"
```

---

## Chunk 2: Frontend — Unified Graph Viewer

### Task 2: Rewrite GraphViewer.tsx as unified factor graph viewer

**Files:**
- Rewrite: `frontend/src/pages/v2/GraphViewer.tsx`

Reuse the vis-network rendering approach from `GraphIRViewer.tsx` (the `buildVisGraph` function and `FactorGraphPanel` component), but read from the unified `/graph` API.

Key behavior:
- Package selector at top (dropdown, "All packages" by default)
- Factor graph: knowledge nodes as colored boxes, factor nodes as small gray boxes
- Edges: premise → factor (no arrow), factor → conclusion (arrow)
- Click node → drawer with knowledge/factor details
- Prior values shown on nodes
- Color by knowledge type (claim=blue, setting=green, question=orange)

- [ ] **Step 1: Define types and API hook**

```typescript
interface KnowledgeNode {
  knowledge_id: string;
  version: number;
  type: string;
  kind: string | null;
  content: string;
  prior: number;
  source_package_id: string;
  source_module_id: string;
}

interface FactorNode {
  factor_id: string;
  type: string;
  premises: string[];
  contexts: string[];
  conclusion: string | null;
  package_id: string;
  metadata: Record<string, unknown> | null;
}

interface GraphData {
  knowledge_nodes: KnowledgeNode[];
  factor_nodes: FactorNode[];
}

// API hook
const useGraphData = (packageId?: string) =>
  useQuery({
    queryKey: ["graph", packageId ?? "all"],
    queryFn: () => {
      const params = packageId ? `?package_id=${packageId}` : "";
      return apiFetch<GraphData>(`/graph${params}`);
    },
  });
```

- [ ] **Step 2: Build vis-network transform**

Reuse the rendering pattern from `GraphIRViewer.tsx:buildVisGraph` (lines 111-233):
- Knowledge nodes: `id = knowledge_id`, colored box, label = truncated name + prior
- Factor nodes: `id = factor_id`, small gray box, label = factor type
- Edges: premise → factor (no arrow), context → factor (dashed), factor → conclusion (arrow)

Key difference from GraphIRViewer: node IDs use `knowledge_id` (not `local_canonical_id`).

- [ ] **Step 3: Build the page component**

```
┌──────────────────────────────────────────────┐
│ Factor Graph           [Package selector ▼]  │
│                        132 nodes · 35 factors │
├──────────────────────────────────────────────┤
│                                              │
│            vis-network canvas                │
│     (knowledge nodes + factor nodes)         │
│                                              │
└──────────────────────────────────────────────┘
```

Click on node → opens Drawer with:
- Knowledge node: type, content, prior, package, module
- Factor node: type, premises list, conclusion, conditional probability

- [ ] **Step 4: Test in browser**

Start backend + frontend, navigate to `/v2/graph`, verify:
- All 132 knowledge nodes + 35 factors visible
- Package filter works
- Click on knowledge node shows details
- Click on factor node shows premise/conclusion info

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/v2/GraphViewer.tsx
git commit -m "feat: unified graph viewer with knowledge + factor nodes from DB"
```

---

## Chunk 3: Cleanup — Remove old graph components

### Task 3: Remove old graph pages and routes

**Files:**
- Delete: `frontend/src/pages/v2/GraphIRViewer.tsx`
- Delete: `frontend/src/pages/v2/GlobalGraphViewer.tsx`
- Delete: `frontend/src/pages/GraphExplorer.tsx`
- Delete: `frontend/src/lib/v2-graph-transform.ts`
- Delete: `services/gateway/routes/graph_ir.py`
- Modify: `frontend/src/App.tsx` — remove old routes
- Modify: `frontend/src/components/layout/Sidebar.tsx` — simplify menu
- Modify: `services/gateway/app.py` — remove graph_ir router

- [ ] **Step 1: Update App.tsx routes**

Remove:
```
<Route path="graph" element={<GraphExplorer />} />
<Route path="v2/graph-ir" element={<GraphIRViewer />} />
<Route path="v2/global-graph" element={<GlobalGraphViewer />} />
```

Keep only:
```
<Route path="v2/graph" element={<GraphViewer />} />
```

Also add a redirect from `/graph` → `/v2/graph` for backward compat.

Remove unused imports: `GraphExplorer`, `GraphIRViewer`, `GlobalGraphViewer`.

- [ ] **Step 2: Simplify Sidebar.tsx**

Replace the three graph menu items with one:

```typescript
{
  key: "/v2/graph",
  icon: <DeploymentUnitOutlined />,
  label: <Link to="/v2/graph">Graph</Link>,
}
```

Remove old `/graph`, `/v2/graph-ir`, `/v2/global-graph` entries.

- [ ] **Step 3: Remove graph_ir router from app.py**

In `services/gateway/app.py`, remove:
```python
from services.gateway.routes.graph_ir import router as graph_ir_router
app.include_router(graph_ir_router)
```

- [ ] **Step 4: Delete old files**

```bash
rm frontend/src/pages/v2/GraphIRViewer.tsx
rm frontend/src/pages/v2/GlobalGraphViewer.tsx
rm frontend/src/pages/GraphExplorer.tsx
rm frontend/src/lib/v2-graph-transform.ts
rm services/gateway/routes/graph_ir.py
```

- [ ] **Step 5: Verify frontend builds**

```bash
cd frontend && npx tsc --noEmit && npx vite build
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove old graph viewers, unified into single Graph page"
```

---

## Execution Order

1. **Chunk 1** (Task 1): Backend API change — must be done first
2. **Chunk 2** (Task 2): Frontend unified viewer — depends on new API shape
3. **Chunk 3** (Task 3): Cleanup — after new viewer is verified working
