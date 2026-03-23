# API Contract

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Spec |
| Scope | Subsystem |
| Related | [service-boundaries.md](service-boundaries.md), [../../runtime/server-architecture.md](../../runtime/server-architecture.md), [../lifecycles/lkm-package-lifecycle.md](../lifecycles/lkm-package-lifecycle.md) |

## Purpose

This document defines the current state of external API contract commitments for Gaia LKM.

## Current Contract Judgment

Gaia LKM does **not** currently expose a fully stabilized external network API contract in this repository.

That is the current canonical answer.

This matters because older architecture drafts can otherwise be misread as evidence that a frozen server API already exists.

## What Is Stable Today

The stable interfaces today are primarily:

- the CLI surface
- the reusable library pipeline surface
- the storage/runtime interfaces used internally by those pipelines

In other words, the repository is already service-shaped, but its strongest public contracts are still:

- package source contracts
- Graph IR contracts
- lifecycle contracts

not a versioned HTTP API.

## What Is Not Yet Stable

The following should not be treated as a frozen external API contract yet:

- package submission endpoints
- review endpoints
- rebuttal endpoints
- investigation queue endpoints
- shared search or subgraph endpoints

These may exist in design documents or future plans, but they are not yet stable contractual surfaces.

## Why This Matters

Without this clarification, "server architecture" language can accidentally be read as "public API already exists and is frozen".

The correct current interpretation is:

- service boundaries are conceptually real
- runtime modules exist
- a stable external API layer is still pending

## Expected Future API Areas

When Gaia LKM does grow a stable API surface, the main areas are likely to align with existing contracts:

- package intake
- package and artifact lookup
- search and subgraph access
- review and rebuttal exchange
- investigation item access

But that future shape should be documented only once it becomes an actual contractual commitment.

## Out Of Scope

This document does not define:

- internal service wiring
- storage schema
- local CLI command semantics
- speculative endpoint-by-endpoint design that is not yet committed
