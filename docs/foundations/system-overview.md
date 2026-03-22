# Gaia System Overview

This document describes the overall architecture and interaction flow of Gaia as a CLI-first, Server-enhanced Large Knowledge Model platform.

For product positioning rationale, see [product-scope.md](product-scope.md).

Related documents:

- [review/publish-pipeline.md](review/publish-pipeline.md)
- [review/service-boundaries.md](review/service-boundaries.md)
- [review/package-artifact-profiles.md](review/package-artifact-profiles.md)
- [language/gaia-language-spec.md](language/gaia-language-spec.md)
- [theory/scientific-ontology.md](theory/scientific-ontology.md)

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
- **Formal external submissions prefer Gaia packages** — base knowledge, review, rebuttal, and intentionally externalized investigations should reuse Gaia package format with different profiles

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
| **Review Service** | submission-scoped package adjudication：validation → canonicalization audit → peer review → gatekeeper 决策 |
| **Storage Service** | 统一存储门面，管理三后端写入 |
| **BP Service** | 离线定期全局信念传播 |
| **Curation Service** | server-internal 离线图维护：相似结论聚类、矛盾发掘、全图结构巡检、图清理 |

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
(author Typst package modules)
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

## Gaia Package Format

Each package is a git repo with this structure:

```
galileo_falling_bodies/
├── typst.toml                   # package manifest
├── gaia.typ                     # runtime import shim
├── lib.typ                      # package entrypoint
├── motivation.typ               # module file
├── reasoning.typ                # module file
├── gaia-deps.yml                # optional external refs
└── .gaia/                       # local artifacts (git-ignored)
    ├── build/                   # rendered review-facing artifacts
    ├── graph/                   # raw/local-canonical Graph IR artifacts
    ├── reviews/                 # local self-review sidecars (compat path on main)
    ├── inference/               # local parameterization + belief preview artifacts
    └── ...
```

The default profile is a `knowledge` package. The same Gaia package substrate may also be used for formal `review`, `rebuttal`, or explicitly externalized `investigation` submissions. Profile changes affect review and merge semantics, not the basic package format.

Typst module files contain typed declarations rather than YAML knowledge objects:

```typst
#import "gaia.typ": *

#setting[
  Consider the tied-bodies thought experiment in still air.
] <setting.thought_experiment_env>

#claim(kind: "observation")[
  Everyday observation suggests that heavier bodies fall faster.
] <aristotle.everyday_observation>

#claim(from: (<aristotle.everyday_observation>, <setting.thought_experiment_env>))[
  The tied pair should fall slower than the heavy body alone.
][
  Under the thought experiment setting @setting.thought_experiment_env,
  Aristotle's premise @aristotle.everyday_observation implies the pair
  should be slowed by the lighter body.
] <reasoning.combined_slower>
```

At the ontology level, only closed, truth-apt scientific assertions directly participate in BP. Questions, workflow declarations, review artifacts, and other meta-level structures may still be part of Gaia packages, but they are not default domain-BP variables.

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

- exact package-level profile metadata layout (`artifact_profile`, `subject_package`, `in_response_to`, etc.)
- exact review output fields and scoring schema
- direct publish contract (`gaia publish --server` without git)
