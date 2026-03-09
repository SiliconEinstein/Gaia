# Gaia Historical Plans

This directory contains planning snapshots, API drafts, and implementation notes from the initial build-out of Gaia.

These files are still useful for historical context, but they are not the current source of truth for repo structure. For the current layout, start with [../../module-map.md](../../module-map.md).

## Historical Roadmap Snapshot

```
Phase 1 (v2) ✅ Done
  └─ Models → Storage → Search → Commit → Inference → Gateway

Plan 1 ✅ Done (PR #4)
  └─ Review Pipeline Operators (embedding, NN search, abstraction, verify, BP)

Plan A ✅ Done
  └─ Shared fixtures (#17), Edge type rename (#25), Job infrastructure (#5)

Plan D ✅ Done
  └─ Test rewrites: commit (#18), search (#19), inference (#20),
     review pipeline (#21)

Plan B ✅ Done
  └─ Async review pipeline (#6, #7)
  └─ Search embedding internalization (#8)
  └─ Enhanced read routes (#12, #13, #14)

Plan C 🔵 Active
  └─ Part 1: Storage test enhancement (#22)
  └─ Part 2: Batch APIs: commits (#9), read (#10), search (#11)

Future
  └─ Retraction support (#23)
  └─ Type-aware BP (#24)
  └─ Agent Verifiable Memory (#27)
  └─ Text auto-structuring (#28)
  └─ RLVR verification + parameter learning (#30)
  └─ Knowledge Package Manager (#35, #37, #38)
```

The roadmap above reflects how the project was planned in early March 2026. Some items marked "Active" in those snapshots may already be implemented, changed, or superseded by later work.

## Plan Documents

### Historical planning threads

| Document | Scope | Issues |
|----------|-------|--------|
| [API Design v3](2026-03-03-lkm-api-design-v3.md) | Target API spec | — |
| [Plan C: Batch + Storage Tests](2026-03-05-plan-c-batch-and-storage-tests.md) | Storage test enhancement + batch APIs | #9-#11, #22 |

### Completed

| Document | Scope |
|----------|-------|
| [Plan B: Feature Enhancements](2026-03-04-plan-b-feature-enhancements.md) | Async review, search embedding, read enhancements (#6-#8, #12-#14) |
| [Plan A: Foundation](2026-03-04-plan-a-foundation.md) | Fixtures, edge rename, Job infra (#5, #17, #25) |
| [Plan D: Test Rewrite](2026-03-04-plan-d-test-rewrite.md) | Mock → real storage tests (#18-#21) |
| [Plan 1: Operator Layer](2026-03-03-plan1-operator-layer.md) | Review pipeline operators (PR #4) |
| [Implementation Plan](2026-03-02-gaia-implementation-plan.md) | Phase 1 task breakdown |
| [API Gateway Design](2026-03-02-api-gateway-design.md) | Gateway routes + DI |
| [Commit Engine Design](2026-03-02-commit-engine-design.md) | 3-step commit workflow |
| [Inference Engine Design](2026-03-02-inference-engine-design.md) | Loopy BP |
| [Search Engine Design](2026-03-02-search-engine-design.md) | Multi-path recall |
| [Storage Layer Design](2026-03-02-storage-layer-design.md) | LanceDB + Neo4j + Vector |

### Superseded

| Document | Replaced by |
|----------|-------------|
| [API Design v2](2026-03-02-lkm-api-design-v2.md) | API Design v3 |
| [Plan 2: Single-Input APIs](2026-03-03-plan2-single-input-apis.md) | Plan A (Job infra); rest → Plan B |
| [Plan 3: Batch APIs](2026-03-03-plan3-batch-processing.md) | Plan C (consolidated with #22) |
