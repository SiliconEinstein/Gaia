# V2 Database Visualization — Design Spec

**Date:** 2026-03-14
**Status:** Approved

## Overview

Add a V2 data browser and Graph IR visualizer to the existing React frontend. Users can browse all v2 storage tables (Packages, Modules, Knowledge, Chains) with pagination and drill-down detail pages, plus an interactive DAG view of the Knowledge→Chain reasoning graph.

## Pages

| Route | Purpose |
|-------|---------|
| `/v2/packages` | Package list with search and pagination |
| `/v2/packages/:id` | Package detail: info, modules list, exports |
| `/v2/knowledge` | Knowledge list with type filter and pagination |
| `/v2/knowledge/:id` | Knowledge detail: content, version history, beliefs, related chains |
| `/v2/modules/:id` | Module detail: chains list, imports, exports |
| `/v2/chains/:id` | Chain detail: steps with premises→conclusion, probabilities |
| `/v2/graph` | Graph IR DAG visualization |

Navigation: add a "V2" group to the existing sidebar with Packages and Knowledge as top-level entries.

## Backend — New API Endpoints

All new endpoints added to `services/gateway/routes/packages.py`.

| Endpoint | Params | Purpose |
|----------|--------|---------|
| `GET /packages` | `page`, `page_size` | Paginated package list |
| `GET /knowledge` | `page`, `page_size`, `type?` | Paginated knowledge list with optional type filter |
| `GET /modules` | `package_id?` | Module list, filterable by package |
| `GET /chains` | `module_id?` | Chain list, filterable by module |
| `GET /graph` | `package_id?` | Graph data: Knowledge nodes + Chain edges |

`GET /graph` response shape:
```json
{
  "nodes": [
    { "id": "kid@1", "knowledge_id": "...", "version": 1, "type": "claim", "content": "..." }
  ],
  "edges": [
    { "chain_id": "...", "from": "premise_kid@1", "to": "conclusion_kid@1", "chain_type": "deduction" }
  ]
}
```

## Frontend Architecture

**New files:**
- `frontend/src/pages/v2/` — all V2 pages
- `frontend/src/api/v2.ts` — API client functions + React Query hooks for all v2 endpoints

**Reused infrastructure:** React Query, Ant Design, React Router, vis-network, existing `node-styles.ts`

### List Pages (Packages, Knowledge)
- Ant Design `Table` with server-side pagination
- Search/filter bar at top (Knowledge adds a `type` dropdown)
- Row click navigates to detail page

### Detail Pages
- Breadcrumb navigation reflecting hierarchy: Package → Module → Chain
- Related entities rendered as links for drill-down navigation
- Knowledge detail has three tabs: Content / Version History / Beliefs

### Graph DAG Page
- vis-network with `hierarchical` layout (`direction: 'UD'`, `sortMethod: 'directed'`)
- Package dropdown to filter graph scope
- Nodes colored by Knowledge type (reuses `node-styles.ts` palette)
- Edges labeled with Chain type (deduction, induction, abstraction, etc.)
- Click node → right-side panel shows Knowledge detail inline

## Storage Layer

The new list endpoints require `StorageManager` to expose list/scan methods. These will use LanceDB's native scan with limit/offset for pagination.

## Out of Scope

- Editing or mutating any data
- Vector search UI
- Belief propagation controls
- V1 data (nodes/edges) — existing pages unchanged
