# Gaia System Overview

This document describes the overall architecture and interaction flow of Gaia as a CLI-first, Server-enhanced Large Knowledge Model platform.

For product positioning rationale, see [product-scope.md](product-scope.md).

## Three Product Layers

```
┌─────────────────────────────────────────────────────┐
│  Research Agent (AI agent, primary user)             │
│  ↕ bash + JSON                                      │
├─────────────────────────────────────────────────────┤
│  Gaia CLI (gaia-cli)                                │
│  Local-complete, zero-config                        │
│  LanceDB + Kuzu (embedded) + local BP               │
├──────────────┬──────────────────────────────────────┤
│   git/GitHub │  gaia publish --server               │
│   (版本控制)  │  (知识整合)                            │
├──────────────┴──────────────────────────────────────┤
│  Gaia Server — Large Knowledge Model (LKM)          │
│  Neo4j + LanceDB + ByteHouse + GPU BP               │
│  知识整合 · 全局搜索 · Context/Align/Review · 大尺度 BP │
└─────────────────────────────────────────────────────┘
```

### Gaia CLI

The primary product surface. AI agents and researchers use the CLI to create, validate, review, and publish knowledge packages.

Key properties:

- **Agent-first** — AI agents are the primary users, calling CLI via bash and parsing JSON output
- **Local-complete** — embedded LanceDB + Kuzu + BP engine, fully offline, zero server dependency
- **1 package = 1 git repo** — can be hosted directly on GitHub
- **Gaia does not wrap git** — version control is completely delegated to git

Core commands:

> **Note:** `gaia build` and `gaia review` are shipped today, but their target semantics are broader than the current implementation. On `main`, shipped `build` is still closer to deterministic parse/elaboration, and shipped `review` is still closer to package-internal chain audit. The target architecture expands `build` into `gaia build compile`, `gaia build context`, and `gaia build align`, then lets `review` become the final context-aware assessment step.

| Command | Purpose |
|---------|---------|
| `gaia init [name]` | Initialize a knowledge package |
| `gaia build` | Prepare the package for downstream review and inference; target shortcut over `compile + context + align` |
| `gaia review [PATH]` | Review the package and emit YAML sidecar reports; target semantics expand to final context-aware assessment |
| `gaia infer` | Compile factor graph + run local belief propagation |
| `gaia publish` | Publish to git or local databases (LanceDB + Kuzu) |
| `gaia show <name>` | Display a declaration + connected chains |
| `gaia search "query"` | Search published nodes in local LanceDB |
| `gaia clean` | Remove build artifacts (`.gaia/` directory) |

For CLI architecture details, see [cli/boundaries.md](cli/boundaries.md).

### Git / GitHub

Version control and collaboration layer. Gaia delegates all versioning to git and does not reimpose its own VCS.

- Each knowledge package is a git repo
- Collaboration happens through standard git workflows (branches, PRs)
- Server integration uses GitHub webhooks on the registry repo

### Gaia Server (Large Knowledge Model)

An optional registry and compute backend. Provides four enhancement services:

| Service | Purpose |
|---------|---------|
| **Knowledge integration** | Merge packages into the global knowledge graph |
| **Global search** | Cross-package vector + BM25 + topology search |
| **Package preparation and review** | Server-side compile, package-environment construction, alignment, and review |
| **Large-scale BP** | Billion-node belief propagation on GPU cluster |

The server is analogous to Julia's General Registry or crates.io — it consumes packages read-only and provides centralized services.

## Primary Interaction Path: Git + Server Webhook

The main interaction flow, similar to Julia Pkg Registry:

```
Agent (local)            Git / GitHub             Gaia Server
─────────────           ──────────────           ───────────

gaia init
(author YAML modules)
gaia build
gaia review

git add + commit
git push ──────────→  PR to registry repo
                      webhook notify ─────────→  auto compile + context + align + review
                                                 │
                                                 ├─ pass → merge into LKM
                                                 │         PR comment: ✅
                                                 │
                                                 └─ fail → PR comment: ❌
                                                           + alignment/review report

Agent reads result ←── PR comments
├─ pass: done
└─ fail: modify based on report
         → push → triggers review again
```

Key properties of this flow:

- **Server never modifies the package** — it is a read-only consumer
- **Alignment and review results appear as PR comments** — standard GitHub collaboration model
- **Agent autonomy** — agents can read alignment/review reports and self-correct without human intervention
- **Fully async** — push triggers webhook, agent polls or watches for results

## Knowledge Package Format

Each package is a git repo with this structure:

```
galileo_tied_balls/              # = 1 git repo = 1 knowledge package
├── package.yaml                 # manifest (name, version, modules list)
├── gaia.lock                    # (deferred) cross-package dependency lock
├── aristotle_physics.yaml       # per-module YAML — knowledge objects + chains
├── thought_experiment.yaml
├── ...
└── .gaia/                       # build artifacts (git-ignored)
    ├── build/                   # per-module Markdown for LLM review
    ├── context/                 # materialized package environment + retrieval metadata
    ├── reviews/                 # YAML sidecar package-review reports
    ├── alignment/               # YAML sidecar alignment reports
    └── ...
```

Module YAML with knowledge objects, including `chain_expr` reasoning:

```yaml
type: reasoning_module
name: reasoning

knowledge:
  - type: ref
    name: heavier_falls_fast
    target: aristotle.heavier_falls_faster

  - type: setting
    name: thought_experiment_env
    content: "Consider the tied-bodies thought experiment in still air."

  - type: claim
    name: combined_slower
    content: "The tied pair should fall slower than the heavy body alone."
    prior: 0.3

  - type: infer_action
    name: tied_bodies_analysis
    params:
      - name: premise
        type: claim
      - name: env
        type: setting
    return_type: claim
    content: "Analyze the tied-bodies scenario under the given premise and environment."

  - type: chain_expr
    name: tied_bodies_contradiction
    edge_type: deduction
    steps:
      - step: 1
        ref: heavier_falls_fast
      - step: 2
        apply: tied_bodies_analysis
        args:
          - ref: heavier_falls_fast
            dependency: direct
          - ref: thought_experiment_env
            dependency: indirect
        prior: 0.85
      - step: 3
        ref: combined_slower
```

- **Strong reference (`args[].dependency: direct`):** if this is wrong, the conclusion cannot stand. Modeled as a load-bearing BP dependency.
- **Weak reference (`args[].dependency: indirect`):** provides background. Conclusion can stand without it. Used as context rather than a load-bearing BP edge.

For the language spec, see [language/gaia-language-spec.md](language/gaia-language-spec.md).

## Technology Stack

| Component | CLI (local) | Server |
|-----------|-------------|--------|
| Graph store | Kuzu (embedded) | Neo4j |
| Content store | LanceDB (embedded) | LanceDB (distributed) |
| Vector search | LanceDB | ByteHouse (planned) |
| BP engine | Local (single-machine) | GPU cluster |
| LLM alignment/review | User-chosen model via API key | Server-managed model |

Both CLI and server share the same core libraries (`libs/`) and inference engine (`libs/inference/`). The `GraphStore` ABC abstracts the graph backend difference.

## Long-Term Repo Structure

| Repo | Contents | Analogy |
|------|----------|---------|
| **gaia-core** | Shared models, BP algorithm, storage ABCs, serialization | Rust stdlib |
| **gaia-cli** | CLI + embedded LanceDB/Kuzu + local BP | cargo |
| **gaia-server** | FastAPI registry + Neo4j + distributed storage + LLM alignment/review | crates.io |

Current monorepo mapping:

- `libs/` → future gaia-core
- `cli/` → future gaia-cli
- `services/` + `frontend/` → future gaia-server

## Deferred Design Decisions

The following are explicitly deferred and will be addressed in later foundation phases:

- Review output format (the exact fields and scoring schema)
- Direct publish contract (`gaia publish --server` without git)
- `observation` and `assumption` artifact kinds (V2 of domain model)
