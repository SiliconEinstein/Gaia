# Gaia Architecture Re-baseline

> **Note:** Written pre-PR #63. CLI and Kuzu have since shipped. The diagnosis of structural issues in §3 remains relevant.

This document resets the discussion around Gaia's structure based on two inputs:

1. what exists on `main` today
2. what recent implementation attempts exposed as real friction

The goal is not to redesign the system from scratch in theory. The goal is to define a cleaner baseline for the next phase of work so new features do not keep amplifying the same structural problems.

The follow-up execution plan for this reset lives in [foundations/foundation-reset-plan.md](foundations/foundation-reset-plan.md).

## Current Baseline On `main`

Today, `main` is best understood as a server-first reasoning graph system with a dashboard:

- `libs/` contains shared models, embeddings, and storage primitives
- `services/` contains the backend workflows: commit, search, inference, review pipeline, jobs, and FastAPI gateway
- `frontend/` contains the browser and graph exploration UI
- `docs/` contains design notes, examples, and archived planning material

What is not on `main` yet:

- no shipped `cli/` package
- no stable local-package-manager product surface
- no fully documented product-level contract for backend capability parity

That matters because recent feature branches tried to extend Gaia in all three directions at once: storage backend abstraction, local CLI workflows, and richer reasoning semantics.

## What Recent Implementation Attempts Exposed

Recent branches and PRs around `#51`, `#52`, and `#53` surfaced a pattern:

1. large features were introduced before the current boundary model was fully stabilized
2. design docs often ran ahead of the code
3. tests were numerous, but sometimes missed contract-level behavior gaps

The most important lessons from that work are structural, not just bug-level:

### 1. Product scope is not yet cleanly split

Three different products are being discussed in the same repo:

- the server API and dashboard
- a local CLI/package-manager workflow
- pluggable storage backends for local versus deployed use

Those are related, but they are not the same thing. When they move in one PR stream, review becomes noisy and module responsibilities blur.

### 2. The repo lacks a single stable "core" contract

The current code has a usable server stack, but not a sharply defined core platform API that other product surfaces can build on.

Examples:

- `CommitEngine` already owns submit/review/merge workflow
- `review_pipeline` behaves like a subsystem of commit review, but lives as a separate top-level service
- batch APIs are exposed from gateway routes, but their orchestration policy is not isolated as a service
- the proposed CLI work tried to depend on storage and review semantics that were still shifting

### 3. Domain vocabulary is drifting

The same concepts are described with multiple names across docs and code:

- `node`, `proposition`, `claim`
- `edge`, `hyperedge`
- reasoning types such as `paper-extract`, `abstraction`, `axiom`, `premise`

This is not cosmetic. It makes APIs, examples, review output, and planned CLI UX harder to align.

### 4. `libs/models.py` is carrying too many concerns

`libs/models.py` currently mixes:

- graph entities
- commit operation payloads
- validation and review result models
- merge result models
- gateway-facing response shapes

That is a sign the boundary between domain models and transport/workflow DTOs is still too loose.

### 5. Infrastructure assembly is too centralized and too implicit

`services/gateway/deps.py` currently does a lot:

- storage creation
- embedding model selection
- LLM client selection
- review pipeline composition
- commit/search/inference/job service construction

This works, but it means the HTTP layer doubles as the composition root for the whole system. That makes non-HTTP reuse and future CLI reuse harder than it should be.

### 6. Storage abstraction is only partially modeled

Current `main` is clear in practice:

- nodes and metadata live in LanceDB
- graph topology can live behind `GraphStore`, with Neo4j and Kuzu implementations now present on `main`
- vector search is abstracted, but local LanceDB is the only implemented backend

But the surrounding documentation and config already hint at a bigger matrix:

- backend capability parity is not yet clearly specified
- local versus production deployment modes
- ByteHouse-oriented production config that is not actually implemented

That creates a mismatch between "supported now" and "planned eventually."

### 7. Tests are strong on count, weaker on system contracts

The recent PR reviews found several examples where tests were green but the functional contract was still wrong:

- backend initialization paths that passed unit tests but failed in real use
- timeout behavior that returned the wrong user-visible status
- CLI surfaces declared in docs and packaging that were not actually wired end to end

This suggests the next cleanup step should emphasize contract tests and boundary tests, not just more unit coverage.

## Main Structural Problems To Fix

These are the problems worth treating as first-order architecture issues.

### A. Unclear module ownership

Questions that are still implicit:

- Is `review_pipeline` a top-level service, or is it internal to commit review?
- Is async orchestration a gateway concern, a job-manager concern, or a separate application service?
- Should the gateway own service wiring, or only expose HTTP routes?

Until those are answered, new features will keep landing in whichever module is most convenient.

### B. Weak separation between domain, workflow, and transport models

Right now, one file and one namespace carry too many meanings. The result is that review output, commit payloads, stored graph entities, and API responses all feel like the same layer when they are not.

### C. Product layers are being expanded out of order

The server core is still being clarified, but CLI and storage-backend expansion were already being built as if the lower-level contracts were fixed.

That is why seemingly separate bugs kept collapsing back into structure problems.

### D. Documentation hierarchy was not aligned to code reality

Historically, design docs and planning docs were doing some of the work that current architecture docs should have been doing. That made it too easy to mistake future direction for present capability.

## Recommended Reset

The cleanest next step is not a giant rewrite. It is a controlled reset of boundaries.

### 1. Freeze the product baseline

For the next phase, treat Gaia on `main` as:

- a backend reasoning graph service
- plus a dashboard frontend

Treat CLI and alternate graph backends as follow-on layers, not as assumptions built into the current baseline.

### 2. Keep `libs/` small and primitive

`libs/` should contain:

- graph/domain entities
- storage interfaces and adapters
- embedding and model interfaces
- small utility primitives

It should not be the dumping ground for workflow responses or product-facing API schemas.

### 3. Split `libs/models.py` into a package

Recommended direction:

```text
libs/models/
  __init__.py
  graph.py        # Node, HyperEdge
  commit.py       # AddEdgeOp, ModifyNodeOp, Commit, CommitRequest
  review.py       # DetailedReviewResult, BPResults, review-specific DTOs
  api.py          # HTTP response/request schemas that truly need to be shared
```

This is a low-risk cleanup with high readability payoff.

### 4. Make ownership of review explicit

There are two reasonable options:

- Option A: move `services/review_pipeline/` under `services/commit_engine/` and treat it as commit-review internals
- Option B: rename it into a clearly independent review service with its own API and responsibilities

Current code behavior points more strongly to Option A. It is primarily constructed inside commit wiring and used by commit review.

### 5. Move application wiring out of the gateway package

Recommended direction:

```text
services/runtime/
  bootstrap.py    # build storage, engines, llm clients, pipeline, jobs
  settings.py     # environment parsing and runtime config
services/gateway/
  app.py
  routes/
```

The gateway should expose HTTP. It should not remain the only place where the application can be assembled.

### 6. Introduce explicit storage capability boundaries

Before expanding backend abstraction work further, define which capabilities are required by each backend:

- edge CRUD
- subgraph traversal
- typed edge filtering
- update semantics
- schema/bootstrap lifecycle

Then document which product surfaces depend on which capabilities:

- server read APIs
- search topology recall
- inference subgraph loading
- future local CLI mode

Without this, "supports another backend" will keep meaning different things in different parts of the code.

### 7. Separate "current" docs from "future" docs by default

The docs should have three explicit classes:

- current architecture and operational docs
- design/reference docs
- historical plans and proposals

That split is now partly in place, but it should continue into per-module READMEs.

## Proposed Target Structure

The lowest-churn target is:

```text
libs/
  models/
  storage/
  embedding.py

services/
  commit_engine/
    review_pipeline/   # if kept as commit-owned
  search_engine/
  inference_engine/
  job_manager/
  runtime/
  gateway/

frontend/
docs/
tests/
```

This is intentionally conservative:

- it preserves the current top-level repo layout
- it tightens ownership without forcing a full rename of every module
- it gives CLI work a cleaner base later

## Cleanup Sequence

The order matters.

### Phase 1: Clarify without changing behavior

1. Split `libs/models.py`
2. Add short README files for `services/commit_engine/`, `services/gateway/`, `services/search_engine/`, and `services/inference_engine/`
3. Decide and document whether `review_pipeline` is internal or independent
4. Move runtime assembly into `services/runtime/`

### Phase 2: Tighten contracts

1. Add contract tests for commit review, merge, batch status, and subgraph loading
2. Add a storage capability matrix doc
3. Remove or clearly mark unimplemented production/backend config paths

### Phase 3: Re-open expansion work

Only after Phases 1 and 2:

1. continue GraphStore/Kuzu capability and parity work
2. revive CLI/package work
3. extend review semantics and edge-type semantics

## Open Decisions

These decisions should be made explicitly before more large feature PRs:

1. Is Gaia primarily a server platform with optional local tooling, or are server and CLI equal first-class products?
2. Is `review_pipeline` a private subsystem of commit review, or should it become its own stable service surface?
3. Is the production storage story actually going to include ByteHouse in the near term, or should those config paths be removed until real support exists?
4. What is the canonical domain vocabulary: `node` or `claim`, `hyperedge` or `edge`, `proposition` as theory term only or API term too?

## Bottom Line

The project does not need a full rewrite. It does need a sharper baseline.

The main lesson from recent implementation attempts is that Gaia is currently stable enough to keep growing only if it first becomes more explicit about:

- what the core product is
- which module owns which workflow
- which docs describe reality versus intent
- which abstractions are supported now versus merely planned
