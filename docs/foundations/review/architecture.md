# Review Architecture

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Architecture |
| Scope | Subsystem |
| Related | [../contracts/services/service-boundaries.md](../contracts/services/service-boundaries.md), [../contracts/services/review-service.md](../contracts/services/review-service.md), [../contracts/artifacts/review-artifacts.md](../contracts/artifacts/review-artifacts.md), [../contracts/artifacts/investigation-artifacts.md](../contracts/artifacts/investigation-artifacts.md), [../contracts/lifecycles/lkm-package-lifecycle.md](../contracts/lifecycles/lkm-package-lifecycle.md), [../runtime/review-runtime.md](../runtime/review-runtime.md) |

## Purpose

This file is a legacy bridge for the older `review/architecture.md` path.

It no longer serves as the canonical home for review architecture.

## Current Canonical Split

The review subsystem has been split into clearer documents:

- [../contracts/services/service-boundaries.md](../contracts/services/service-boundaries.md)
  - shared-side service ownership boundaries
- [../contracts/services/review-service.md](../contracts/services/review-service.md)
  - what `ReviewService` is responsible for
- [../contracts/artifacts/review-artifacts.md](../contracts/artifacts/review-artifacts.md)
  - what review emits
- [../contracts/artifacts/investigation-artifacts.md](../contracts/artifacts/investigation-artifacts.md)
  - deferred investigation items and related shared-side artifacts
- [../contracts/lifecycles/lkm-package-lifecycle.md](../contracts/lifecycles/lkm-package-lifecycle.md)
  - where review sits in the LKM-side package lifecycle
- [../runtime/review-runtime.md](../runtime/review-runtime.md)
  - how review currently executes in the codebase

## Important Current Corrections

- Review is an LKM-side concern, not part of the canonical CLI lifecycle.
- Current `main` does **not** ship a standalone `gaia review` command in `cli/main.py`.
- Review outputs are structured artifacts, not just an implicit step in a larger narrative pipeline.
- Investigation items are not the same thing as authored `#question` nodes.

## Why This File Is Thin

The older version of this file mixed:

- desired future workflow
- current runtime behavior
- package artifact design
- CLI command assumptions that are no longer current

That content has now been split into canonical homes with narrower scope.

## Migration Note

Use the canonical docs above for current review work.

This file remains only as a bridge for older links and design references.
