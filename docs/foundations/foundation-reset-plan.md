# Gaia Foundation Reset Plan

## Purpose

Before making more structural code changes, Gaia needs a documented foundation pass that resets the shared understanding of:

- what the current product actually is
- what the core domain model is
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

This plan covers six foundation areas:

1. Product scope
2. Domain model and terminology
3. Graph specification
4. Storage schema and backend capability model
5. Module boundaries and runtime composition
6. API contract

This plan does not include:

- implementing a new CLI surface
- merging alternate graph backends
- changing user-facing reasoning semantics without first updating the foundation docs

## Guiding Principles

1. Document current reality before designing extensions.
2. Separate current capability from future intent.
3. Prefer conservative structure changes that reduce ambiguity without forcing a full rewrite.
4. Make ownership explicit: every workflow should have a clear home.
5. Treat foundation docs as executable constraints for later refactors.

## Work Sequence

### Phase 0: Freeze the baseline

Objective:

- state what Gaia on `main` currently is and is not

Deliverable:

- `product-scope.md`

Key decisions:

- Is Gaia currently server-first, or are server and CLI equal first-class products?
- Which roadmap items are explicitly not current capability?

### Phase 1: Lock the vocabulary and entities

Objective:

- define the canonical domain terms and core entities

Deliverable:

- `domain-model.md`

Key decisions:

- `node` vs `claim` vs `proposition`
- `edge` vs `hyperedge`
- canonical reasoning type names
- difference between `prior`, `belief`, `probability`, and review-derived scores

### Phase 2: Lock the graph semantics

Objective:

- define the graph formally enough that APIs, storage, inference, and future backends can agree on it

Deliverable:

- `graph-spec.md`

Key decisions:

- node and hyperedge fields
- persistent vs derived fields
- contradiction and retraction semantics
- traversal semantics, hop definition, and filtering rules

### Phase 3: Lock the storage model

Objective:

- separate logical schema from physical storage implementation

Deliverable:

- `storage-schema.md`

Key decisions:

- which store is source of truth for which data
- which data are indexes or caches
- backend capability matrix
- handling of unimplemented production-oriented config such as ByteHouse-related fields

### Phase 4: Lock module boundaries

Objective:

- define which module owns which workflow

Deliverable:

- `module-boundaries.md`

Key decisions:

- whether `review_pipeline` is internal to commit review or an independent service
- whether gateway remains the composition root
- where runtime wiring should live
- how shared models should be split

### Phase 5: Lock the API contract

Objective:

- define the stable external behavior of the current server

Deliverable:

- `api-contract.md`

Key decisions:

- synchronous vs asynchronous flows
- job lifecycle contract
- batch API semantics
- review/merge/timeout/cancel behavior

### Phase 6: Convert the foundation into implementation work

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
3. `graph-spec.md`
4. `storage-schema.md`
5. `module-boundaries.md`
6. `api-contract.md`

Each later document should depend on decisions already made in earlier ones.

## Decision Gates

Do not start major code restructuring until the following are explicit:

1. the current product baseline
2. the canonical domain vocabulary
3. the graph/storage contract
4. the ownership of review pipeline and runtime wiring

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
- module ownership questions have explicit answers
- storage and graph semantics are documented at contract level
- API behavior is specified independently of route implementations
- future CLI/backend work can build on these docs instead of redefining the foundations again
