# CLI Command Lifecycle

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Spec |
| Scope | Subsystem |
| Related | [../contracts/lifecycles/cli-lifecycle.md](../contracts/lifecycles/cli-lifecycle.md), [../contracts/lifecycles/lkm-package-lifecycle.md](../contracts/lifecycles/lkm-package-lifecycle.md), [../runtime/review-runtime.md](../runtime/review-runtime.md) |

## Purpose

This file is a legacy bridge for readers who still arrive through the older `cli/command-lifecycle.md` path.

It no longer defines the canonical lifecycle contract.

## Current Canonical Split

The lifecycle model has been split into three clearer homes:

- [../contracts/lifecycles/cli-lifecycle.md](../contracts/lifecycles/cli-lifecycle.md)
  - the canonical local CLI lifecycle
  - `build -> infer -> publish`
- [../contracts/lifecycles/lkm-package-lifecycle.md](../contracts/lifecycles/lkm-package-lifecycle.md)
  - what happens after a package enters Gaia LKM
  - review, rebuttal, decision, integration, investigation handoff
- [../runtime/review-runtime.md](../runtime/review-runtime.md)
  - the current executable review runtime that exists in code today

## Important Current Correction

Current `main` does **not** ship a standalone `gaia review` command in `cli/main.py`.

Older design material that spoke about `gaia review` as a first-class CLI stage should now be read as migration-era workflow framing, not literal current CLI surface.

## Why This File Is Thin

The earlier version of this file mixed together:

- local CLI stages
- shared-side review workflow
- migration-era command ideas

That made the lifecycle boundary hard to read. The newer split keeps:

- local lifecycle in one doc
- shared-side lifecycle in one doc
- current executable runtime in one doc

## Migration Note

Use the three canonical docs above for current work.

This file remains only as a compatibility path for older links and references.
