# Gaia Foundation Reset Plan

## Purpose

Before making more structural code changes, Gaia needs a documented foundation pass that resets the shared understanding of:

- what the current product actually is
- what the core domain model is
- how shared knowledge packages are defined
- how the graph is defined
- which storage contracts are real
- how modules are supposed to depend on each other
- which HTTP APIs are stable

This plan exists so future implementation work can build on explicit contracts instead of inferred ones.

## Why This Is Needed

Recent implementation attempts exposed the same pattern repeatedly:

- design scope ran ahead of merged code
- product layers were expanded in parallel before core contracts were stable
- module ownership was implicit
- tests were often green while behavior-level contracts were still wrong

The goal of this plan is to fix that by making the foundational layer explicit first.

## Scope

This plan covers seven foundation areas:

1. Product scope
2. Domain model and terminology
3. Shared knowledge package contracts
4. Graph specification
5. Storage schema and backend capability model
6. Module boundaries and runtime composition
7. API contract

This plan does not include:

- implementing a new CLI surface
- merging alternate graph backends
- changing user-facing reasoning semantics without first updating the foundation docs

> **Note (2025):** The CLI and Kuzu graph backend have since been merged (PR #63). The foundation docs are being updated to reflect current reality.

## Guiding Principles

1. Document current reality before designing extensions.
2. Separate current capability from future intent.
3. Prefer conservative structure changes that reduce ambiguity without forcing a full rewrite.
4. Make ownership explicit: every workflow should have a clear home.
5. Treat foundation docs as executable constraints for later refactors.

## Work Sequence

### Phase 0: Freeze the baseline — ✅ DONE

> `product-scope.md` is written and updated to reflect PR #63 (CLI, language, inference move).

Objective:

- state what Gaia on `main` currently is and is not

Deliverable:

- `product-scope.md`

Key decisions:

- Is Gaia currently server-first, or are server and CLI equal first-class products?
- Which roadmap items are explicitly not current capability?

### Phase 1: Lock the vocabulary and entities — ✅ DONE

> `domain-model.md` is written. Canonical terms established: declaration, chain, module, package.

Objective:

- define the canonical domain terms and core entities

Deliverable:

- `domain-model.md`

Key decisions:

- `node` vs `claim` vs `proposition`
- `edge` vs `hyperedge`
- canonical reasoning type names
- difference between `prior`, `belief`, `probability`, and review-derived scores

### Phase 2: Lock the shared knowledge package contracts — ✅ DONE

> The Gaia Language (PR #63) implements the package model. Actual format uses per-module YAML with `package.yaml` manifest, declaration/chain structure, and `.gaia/` build artifacts. Review output uses YAML sidecar format with per-chain steps.

Objective:

- define the shared package-level representation used by both local tooling and later server ingestion

Deliverables:

- `shared/knowledge-package-static.md`
- `shared/knowledge-package-file-formats.md`

Key decisions:

- `knowledge_artifact` / `chain_step` / `reasoning_chain` / `package`
- how package-local roles relate to globally reusable artifacts
- the standard package manifest, package content file, and review-report sidecar formats

### Phase 3: Lock the graph semantics — ⬜ NOT STARTED

Objective:

- define the graph formally enough that APIs, storage, inference, and future backends can agree on it

Deliverable:

- `graph-spec.md`

Key decisions:

- node and hyperedge fields
- persistent vs derived fields
- contradiction and retraction semantics
- traversal semantics, hop definition, and filtering rules

### Phase 4: Lock the storage model — ⬜ NOT STARTED

Objective:

- separate logical schema from physical storage implementation

Deliverable:

- `storage-schema.md`

Key decisions:

- which store is source of truth for which data
- which data are indexes or caches
- backend capability matrix
- handling of unimplemented production-oriented config such as ByteHouse-related fields

### Phase 5: Lock module boundaries — ⬜ NOT STARTED

Objective:

- define which module owns which workflow

Deliverable:

- `module-boundaries.md`

Key decisions:

- whether `review_pipeline` is internal to commit review or an independent service
- whether gateway remains the composition root
- where runtime wiring should live
- how shared models should be split

### Phase 6: Lock the API contract — ⬜ NOT STARTED

Objective:

- define the stable external behavior of the current server

Deliverable:

- `api-contract.md`

Key decisions:

- synchronous vs asynchronous flows
- job lifecycle contract
- batch API semantics
- review/merge/timeout/cancel behavior

### Phase 7: Convert the foundation into implementation work

Objective:

- derive a code refactor sequence from the foundation docs

Deliverable:

- follow-up implementation plan after Phases 0-5 are accepted

Expected first code changes:

1. split `libs/models.py`
2. move runtime assembly out of `services/gateway/deps.py`
3. document core services with module-level READMEs
4. add contract tests around cross-module behavior

## Recommended Deliverable Order

To keep the work reviewable, build the foundation docs in this order:

1. `product-scope.md`
2. `domain-model.md`
3. `shared/knowledge-package-static.md`
4. `shared/knowledge-package-file-formats.md`
5. `graph-spec.md`
6. `storage-schema.md`
7. `module-boundaries.md`
8. `api-contract.md`

Each later document should depend on decisions already made in earlier ones.

## Decision Gates

Do not start major code restructuring until the following are explicit:

1. the current product baseline
2. the canonical domain vocabulary
3. the shared knowledge package contract
4. the graph/storage contract
5. the ownership of review pipeline and runtime wiring

If those are still ambiguous, code changes should remain narrow and local.

## How Agents Should Use This Plan

When working on the repo:

1. Check whether the task changes a foundation area.
2. If yes, read the relevant doc in `docs/foundations/` first.
3. If the doc does not exist yet, update this plan or add the missing doc before making large structural changes.
4. If implementation and docs disagree, prefer surfacing the mismatch explicitly rather than silently coding around it.

## Success Criteria

This plan is successful when:

- the current architecture can be explained without relying on old planning docs
- local/server-shared knowledge package contracts are documented explicitly
- module ownership questions have explicit answers
- storage and graph semantics are documented at contract level
- API behavior is specified independently of route implementations
- future CLI/backend work can build on these docs instead of redefining the foundations again
