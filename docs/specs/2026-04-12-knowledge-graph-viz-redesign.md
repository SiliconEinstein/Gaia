# Knowledge Graph Visualization Redesign

**Status:** Superseded
**Date:** 2026-04-12
**Scope:** `gaia render --target github` docs app only

> **Superseded by v0.5 cleanup (2026-05-16):** the React/Vite GitHub Pages docs app was removed. The GitHub target now keeps README/wiki/data/assets output only.

## Problem

The current React+Cytoscape visualization in `.github-output/docs/` breaks down at real-world scale (47+ nodes):

1. **Layout collapse** — dagre with `nodeSep:50, rankSep:80` produces overlapping labels at 47 nodes; unusable at 100+
2. **Invisible reasoning** — strategies are edge attributes, not intermediate nodes; the premise→strategy→conclusion chain is flattened to premise→conclusion
3. **No semantic shapes** — all nodes are 40×40 circles, differentiated only by belief color; settings, claims, questions look identical
4. **No module structure** — 47 nodes rendered flat; no way to focus on a single reasoning thread
5. **No chain navigation** — clicking a node shows details but doesn't highlight its upstream reasoning chain

## Users & Constraints

- **Primary user:** Paper author self-reviewing knowledge package structure and reasoning completeness
- **Scale target:** 50–200 nodes per package
- **Core interaction:** Reasoning chain tracing — click a conclusion, see its full upstream premise chain

## Design

### Two-Level Navigation

**Level 1 — Module Overview:**
- Each module rendered as a labeled box showing name, node count, strategy count
- Inter-module arrows show cross-module reasoning dependencies (derived from strategies where premise.module ≠ conclusion.module)
- Click any module → drill into Level 2

**Level 2 — Module Subgraph:**
- Full reasoning DAG for the selected module: knowledge nodes + strategy intermediate nodes + operator nodes
- Breadcrumb navigation: `← All Modules / module_name`
- External premise nodes from other modules shown as dashed boxes with clickable links
- ELK layered layout: settings at top → premises → strategies → conclusions at bottom

### Node Visual System

| Type | Shape | Color | Notes |
|------|-------|-------|-------|
| setting | Rectangle (sharp corners) | Gray `#f0f0f0` | Given premises, no belief |
| claim | Rounded rectangle | Blue `#ddeeff` | Shows belief badge |
| question | Ellipse | Yellow `#fff3dd` | Research question |
| strategy | Hexagon | Green `#e8f5e9` (deterministic) / Yellow dashed (weak) | Intermediate reasoning step |
| operator | Circle | White | Logic symbol (∧ ∨ ⊗ ≡) |
| external ref | Dashed rounded rect | White | Cross-module reference, clickable |

**Belief color encoding:** Red (<0.4), Orange (0.4–0.7), Green (≥0.7), Gray (null). Badge in node top-right corner; hover shows prior→belief delta.

**Edge styles:**
- Solid arrow: premise → strategy
- Dashed arrow: background → strategy
- Red dashed (no arrow): contradiction

### Interactions

1. **Click node** → BFS upstream highlights entire reasoning chain; non-chain nodes dimmed to 20% opacity; DetailPanel slides in from right
2. **Click external ref** → navigate to source module, auto-highlight the referenced node
3. **Hover node** → tooltip with prior→belief change
4. **Minimap** → corner viewport indicator for orientation in large subgraphs

### Layout Engine

Replace `cytoscape` + `cytoscape-dagre` with `elkjs`:
- ELK's layered algorithm is purpose-built for hierarchical DAGs with compound nodes
- Handles 200+ nodes (used by Eclipse IDE internally)
- Layout computed in web worker to avoid UI blocking
- ~180KB gzipped bundle size

No React Flow — direct SVG rendering with React for full control over node shapes.

## Data Layer Changes

### graph.json Schema (new)

```json
{
  "modules": [
    { "id": "motivation", "order": 0, "node_count": 5, "strategy_count": 0 }
  ],
  "cross_module_edges": [
    { "from_module": "s2_laser", "to_module": "s3_band", "count": 2 }
  ],
  "nodes": [
    { "id": "pkg::label", "type": "setting", "module": "motivation", ... },
    { "id": "strat_0", "type": "strategy", "strategy_type": "deduction",
      "module": "s2_laser", "reason": "..." }
  ],
  "edges": [
    { "source": "pkg::premise", "target": "strat_0", "role": "premise" },
    { "source": "strat_0", "target": "pkg::conclusion", "role": "conclusion" }
  ]
}
```

Key changes from current schema:
- Strategy/operator promoted from edge attribute to real node
- Each strategy edge split into N premise edges + 1 conclusion edge
- New `role` field on edges: `"premise" | "background" | "conclusion"`
- New top-level `modules` array and `cross_module_edges`

### Python Changes

| File | Scope | Detail |
|------|-------|--------|
| `_graph_json.py` | Rewrite | Strategy/operator as nodes, edges with roles, modules array, cross_module_edges |
| `_github.py` | Minor | Pass `module_order` to `generate_graph_json()` |
| Template `pages/` | Replace | New React app with ELK, no cytoscape |

### React Component Architecture

```
App
├── Header (package name, breadcrumb)
├── GraphView
│   ├── ModuleOverview        ← Level 1
│   └── ModuleSubgraph        ← Level 2
│       ├── KnowledgeNode[]
│       ├── StrategyNode[]
│       ├── OperatorNode[]
│       └── ExternalRef[]
├── DetailPanel
│   ├── NodeInfo
│   ├── ReasoningChain
│   └── AbductionComparison
├── ChainHighlighter (BFS state)
└── Minimap
```

Hooks: `useGraphData`, `useElkLayout` (web worker), `useChainHighlight` (BFS traversal).

### Dependencies

- **Remove:** `cytoscape`, `cytoscape-dagre`
- **Add:** `elkjs`
- **Keep:** `react`, `react-dom`, `react-markdown`, `remark-gfm`

## What Does NOT Change

- IR format (`.gaia/ir.json`) — read-only data source
- Compile pipeline (`gaia compile`)
- Inference / BP (`gaia infer`)
- Storage layer (LanceDB, Neo4j)
- API layer
- README mermaid generation (`_render_coarse_mermaid`)
- Wiki generation (`generate_all_wiki`)
- Obsidian vault generation (`_obsidian.py`)
- beliefs.json / parameterization.json format

## Testing

- **Python:** Test new `generate_graph_json()` output — verify strategy nodes exist, edges have roles, modules array correct, cross_module_edges computed
- **React (vitest):** Test `useChainHighlight` BFS traversal, `useGraphData` parsing, node filtering by module
- **Manual:** Run `gaia render` on rydberg-qh-gaia package, `npm run dev`, verify two-level navigation and chain highlighting work
