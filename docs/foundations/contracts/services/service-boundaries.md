# Service Boundaries

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Architecture |
| Scope | Repo-wide |
| Related | [../lifecycles/lkm-package-lifecycle.md](../lifecycles/lkm-package-lifecycle.md), [../artifacts/review-artifacts.md](../artifacts/review-artifacts.md), [../artifacts/investigation-artifacts.md](../artifacts/investigation-artifacts.md), [review-service.md](review-service.md), [curation-service.md](curation-service.md), [../../system-overview.md](../../system-overview.md) |

## Purpose

This document defines the major service boundaries inside Gaia LKM.

Its job is to make clear which responsibilities belong to which service, how artifacts move between those services, and which concerns should not be collapsed into a single catch-all "server" concept.

## First Principle

Inside Gaia LKM, a `service` is a responsibility boundary, not just a process or code module.

This means a service should be named when all three of the following are true:

- it owns a distinct class of decisions or state transitions
- it consumes and emits identifiable artifact types
- its boundary matters even if the current implementation runs inside one backend process

## Primary LKM Services

The current conceptual service split inside Gaia LKM is:

- `ReviewService`
- `CurationService`

Other runtime pieces may exist, but these are the key service-level responsibility boundaries in the current foundations model.

## ReviewService

`ReviewService` owns submission-scoped adjudication.

Its job is to answer questions like:

- is this package acceptable in its current form?
- what findings block acceptance?
- what rebuttal or clarification is needed before a decision?

The unit of work is a submitted package and its immediate review context.

`ReviewService` is therefore the main owner of:

- package review evaluation
- review findings
- review verdicts
- rebuttal intake and reconsideration
- decision-ready outputs for package acceptance or rejection

## CurationService

`CurationService` owns longer-lived shared-state maintenance and deeper investigation work.

Its job is to answer questions like:

- what global inconsistencies or opportunities exist in shared knowledge state?
- what needs a contradiction audit, equivalence audit, or hidden-premise search?
- which issues should become investigation work items?

The unit of work is not just one submitted package. It is the evolving shared state of Gaia LKM.

`CurationService` is therefore the main owner of:

- shared-state maintenance
- contradiction and equivalence investigations
- independent-evidence and hidden-premise audits
- longer-lived research agenda and investigation queues
- downstream cleanup or maintenance work after integration

## Artifact Flow Between Services

The most important handoff pattern is:

1. A package enters Gaia LKM.
2. `ReviewService` evaluates it in a submission-scoped way.
3. The result may be:
   - accepted
   - rejected
   - sent back through rebuttal handling
   - deferred into an investigation-oriented path
4. Issues that exceed ordinary submission review can be handed to `CurationService`.

This means `ReviewService` and `CurationService` are connected, but they are not interchangeable.

## What Does Not Define A Service Boundary

Several things are important but should not be confused with services:

- `engine`
  - algorithmic component such as belief propagation
- `server`
  - the runtime/backend process hosting services
- `package profile`
  - artifact classification such as `knowledge`, `review`, or `investigation`
- `lifecycle stage`
  - intake, review, rebuttal, integration, or curation handoff

These matter, but they answer different questions from service ownership.

## Why Review And Curation Must Stay Separate

Review and curation are related but fundamentally different kinds of work.

### Review is submission-scoped

It is primarily about a concrete incoming package:

- evaluate
- comment
- request response
- decide acceptability

### Curation is shared-state-scoped

It is primarily about the state of the LKM as a whole:

- maintain
- investigate
- reconcile
- discover deeper follow-up work

Collapsing the two would make package adjudication and long-horizon knowledge maintenance interfere with each other.

## Internal Versus External Investigation

The current foundation direction assumes that most curation and investigation work is internal to Gaia LKM rather than automatically pushed out to external agent surfaces.

That means:

- `CurationService` may internally generate and process investigation work items
- a future external investigation surface is possible, but not required by the current service model

This keeps curation aligned with the shared knowledge system rather than prematurely turning every open issue into an external workflow.

## Relationship To Other Docs

- [review-service.md](review-service.md) defines `ReviewService` in more detail.
- [curation-service.md](curation-service.md) defines `CurationService` in more detail.
- [../lifecycles/lkm-package-lifecycle.md](../lifecycles/lkm-package-lifecycle.md) defines the shared-side package flow those services participate in.
- [../artifacts/review-artifacts.md](../artifacts/review-artifacts.md) and [../artifacts/investigation-artifacts.md](../artifacts/investigation-artifacts.md) define the major artifact classes those services handle.

## Out Of Scope

This document does not define:

- detailed runtime process composition
- algorithm internals
- package syntax
- low-level API route design

## Migration Note

This document now supersedes the earlier placeholder-only service split. It establishes `ReviewService` and `CurationService` as first-class service boundaries inside Gaia LKM rather than loose labels attached to one backend runtime.
