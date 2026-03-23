# Server Architecture

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Architecture |
| Scope | Subsystem |
| Related | [../runtime/server-architecture.md](../runtime/server-architecture.md), [../contracts/services/service-boundaries.md](../contracts/services/service-boundaries.md), [../contracts/services/api-contract.md](../contracts/services/api-contract.md) |

## Purpose

This file is a legacy bridge for readers coming from the older `server/architecture.md` path.

It no longer acts as the canonical home for current backend/runtime architecture.

## Current Canonical Split

Use these docs instead:

- [../runtime/server-architecture.md](../runtime/server-architecture.md)
  - current backend/runtime architecture that exists in the repository today
- [../contracts/services/service-boundaries.md](../contracts/services/service-boundaries.md)
  - conceptual service boundaries such as `ReviewService` and `CurationService`
- [../contracts/services/api-contract.md](../contracts/services/api-contract.md)
  - what external API commitments are and are not currently stable

## Important Current Corrections

- `Gaia Server` is a runtime/deployment term, not the primary foundation-level name for the shared side.
- `Gaia LKM` is the shared knowledge core.
- Current backend reality is library-first and service-ready, not a fully stabilized externally deployed service platform.
- A stable external API contract is still pending.

## Migration Note

Use the canonical docs above for current server/runtime work.

This file remains only as a compatibility bridge for older architecture links.
