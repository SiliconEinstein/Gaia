# Curation Service

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Architecture |
| Scope | Component |
| Related | [service-boundaries.md](service-boundaries.md), [../artifacts/investigation-artifacts.md](../artifacts/investigation-artifacts.md), [../lifecycles/lkm-package-lifecycle.md](../lifecycles/lkm-package-lifecycle.md), [../../system-overview.md](../../system-overview.md) |

## Purpose

This document defines the responsibilities and boundaries of `CurationService`.

Its job is to make clear how Gaia LKM handles longer-lived shared-state maintenance and investigation work without confusing that work with ordinary package review.

## Core Responsibility

`CurationService` owns shared-state maintenance and investigation-oriented follow-up work inside Gaia LKM.

Its primary question is:

> What longer-lived issues, inconsistencies, opportunities, or follow-up tasks arise from the evolving shared knowledge state?

## Inputs

`CurationService` primarily consumes:

- integrated shared knowledge state
- accepted package consequences
- deferred issues from review
- contradiction, equivalence, or independent-evidence concerns
- investigation work items and related maintenance signals

Unlike review, curation is not centered on one submitted package. It is centered on the state of the LKM as a whole.

## Outputs

`CurationService` primarily emits:

- investigation work items
- contradiction or equivalence audits
- hidden-premise and independent-evidence audits
- curation findings and follow-up recommendations
- maintenance-oriented updates or proposals around shared knowledge state

These outputs connect most directly to [../artifacts/investigation-artifacts.md](../artifacts/investigation-artifacts.md).

## What CurationService Owns

`CurationService` owns:

- shared-state maintenance
- issue discovery beyond ordinary package review
- investigation queue creation and handling
- longer-horizon reconciliation and cleanup work
- routing of deeper knowledge-maintenance tasks

## What CurationService Does Not Own

`CurationService` does not own:

- ordinary accept/reject verdicts for a newly submitted package
- rebuttal adjudication as part of package review
- the canonical local CLI lifecycle
- low-level algorithm implementation details

It may inform those areas, but it should not swallow them.

## Curation Is Not Just Review By Another Name

Curation differs from review in both scope and time horizon.

### Review

- centered on one submitted package
- seeks an adjudicative decision
- bounded by a concrete submission thread

### Curation

- centered on the shared state of Gaia LKM
- seeks maintenance, investigation, and follow-up understanding
- may continue long after any one submission decision

This difference is why the two should remain separate services even if they currently run inside the same runtime.

## Internal Investigation First

The current architecture direction assumes that most curation work is handled internally by Gaia LKM rather than automatically exposed as an external agent marketplace.

That means:

- curation may generate investigation items
- those items may still be processed within the shared system
- an external investigation surface can remain optional rather than foundational

This aligns with the current goal of keeping curation as server-side or LKM-side maintenance work.

## Relationship To Investigation Artifacts

`CurationService` is the natural owner of investigation-style artifacts such as:

- contradiction audit items
- independent-evidence audit items
- hidden-premise searches
- other research-agenda style tasks that are not ordinary knowledge nodes

Those artifacts are defined structurally in [../artifacts/investigation-artifacts.md](../artifacts/investigation-artifacts.md).

## Relationship To ReviewService

`CurationService` may receive handoffs from `ReviewService`, but it does not merely continue package review under another name.

Typical handoff pattern:

1. review encounters an issue that exceeds ordinary adjudication
2. the issue is deferred or routed
3. curation takes ownership of the longer-lived investigation or maintenance problem

## Relationship To Runtime

`CurationService` is a service boundary, not a commitment to one deployment shape.

The current runtime may realize curation through one backend process, scheduled jobs, internal LLM assistance, or other mechanisms. Those are runtime concerns, not the service definition itself.

## Relationship To Other Docs

- [service-boundaries.md](service-boundaries.md) defines the overall service split inside Gaia LKM.
- [../artifacts/investigation-artifacts.md](../artifacts/investigation-artifacts.md) defines the main investigation-side artifact classes.
- [../lifecycles/lkm-package-lifecycle.md](../lifecycles/lkm-package-lifecycle.md) explains how curation appears as a later shared-side handoff after package processing.

## Out Of Scope

This document does not define:

- review verdict semantics
- detailed job scheduling
- BP formulas
- low-level runtime orchestration

## Migration Note

This document replaces the earlier placeholder-only curation description and makes explicit that curation is shared-state maintenance and investigation ownership, not just a vague extension of review.
