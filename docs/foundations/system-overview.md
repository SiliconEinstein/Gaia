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
│  知识整合 · 全局搜索 · Peer Review · Registry · 大尺度 BP │
└─────────────────────────────────────────────────────┘
```

### Gaia CLI

The primary product surface. AI agents and researchers use the CLI to create, build, preview, and publish knowledge packages.

Key properties:

- **Agent-first** — AI agents are the primary users, calling CLI via bash and parsing JSON output
- **Local-complete** — embedded LanceDB + Kuzu + BP engine, fully offline, zero server dependency
- **1 package = 1 git repo** — can be hosted directly on GitHub
- **Gaia does not wrap git** — version control is completely delegated to git

Target core pipeline:

> **Note:** The current foundations baseline follows [`review/publish-pipeline.md`](review/publish-pipeline.md): core CLI commands are `gaia build`, `gaia infer`, and `gaia publish`; self-review, graph construction, and rebuttal are agent skills. The shipped `gaia review` command on `main` is a local compatibility bridge for self-review sidecars, not the long-term core review boundary.

| Command | Purpose |
|---------|---------|
| `gaia init [name]` | Initialize a knowledge package |
| `gaia build` | Deterministically validate/lower package source into `.gaia/build/` and `.gaia/graph/` artifacts |
| `gaia review [PATH]` | Current shipped compatibility path for local self-review sidecars under `.gaia/reviews/` |
| `gaia infer` | Derive local parameterization from local Graph IR + local review sidecars, then run local BP |
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

An optional registry and compute backend. Server 架构采用 **Write Side / Read Side 分离**：

**Write Side（数据入库 + 离线维护）：**

| Service | Purpose |
|---------|---------|
| **Review Service** | Package 审查流程：validation → canonicalization → multiple agent review → gatekeeper 准入 |
| **Storage Service** | 统一存储门面，管理三后端写入 |
| **BP Service** | 离线定期全局信念传播 |
| **Curation Service** | 离线定期图维护：相似结论聚类、矛盾发掘、全图结构巡检、图清理 |

BP Service 和 Curation Service 构成离线图维护机制：Curation 先做结构维护，BP 再跑推理更新。

**Read Side（数据消费）：**

| Service | Purpose |
|---------|---------|
| **Query Service** | 面向 AI agents 的知识搜索、子图探索，核心用例是 research |

The server is analogous to Julia's General Registry or crates.io — it consumes packages read-only and provides centralized services.

## Primary Interaction Path: Git + Server Webhook

The main interaction flow, similar to Julia Pkg Registry:

```
Agent (local)            Git / GitHub             Gaia Server
─────────────           ──────────────           ───────────

gaia init
(author YAML modules)
gaia build
agent self-review / graph construction
gaia infer   (optional local preview)

git add + commit
git push ──────────→  PR to registry repo
                      webhook notify ─────────→  auto peer review + search + identity matching
                                                 │
                                                 ├─ pass → merge into LKM
                                                 │         PR comment: ✅
                                                 │
                                                 └─ fail → PR comment: ❌
                                                           + peer review / editor report

Agent reads result ←── PR comments
├─ pass: done
└─ fail: modify based on report
         → push → triggers review again
```

Key properties of this flow:

- **Server never modifies the package** — it is a read-only consumer
- **Peer review results appear as PR comments** — standard GitHub collaboration model
- **Agent autonomy** — agents can read peer review findings and self-correct without human intervention
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
└── .gaia/                       # local artifacts (git-ignored)
    ├── build/                   # per-module Markdown for LLM review
    ├── graph/                   # raw/local-canonical Graph IR artifacts
    ├── reviews/                 # local self-review sidecars (compat path on main)
    ├── inference/               # local parameterization + belief preview artifacts
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

- **Direct dependency (`args[].dependency: direct`):** semantic role `premise`. If this is wrong, the conclusion cannot stand. Across package boundaries this requires exported knowledge.
- **Indirect dependency (`args[].dependency: indirect`):** semantic role `context`. Provides background rather than a load-bearing BP edge. Across package boundaries, non-exported external knowledge is context-only.

For the language spec, see [language/gaia-language-spec.md](language/gaia-language-spec.md).

## Technology Stack

| Component | CLI (local) | Server |
|-----------|-------------|--------|
| Graph store | Kuzu (embedded) | Neo4j |
| Content store | LanceDB (embedded) | LanceDB (distributed) |
| Vector search | LanceDB | ByteHouse (planned) |
| BP engine | Local (single-machine) | GPU cluster |
| LLM review | User-chosen model via API key / agent skills | Server-managed peer review |

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
