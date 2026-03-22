# Review Service

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Architecture |
| Scope | Component |
| Related | [service-boundaries.md](service-boundaries.md), [../artifacts/review-artifacts.md](../artifacts/review-artifacts.md), [../lifecycles/lkm-package-lifecycle.md](../lifecycles/lkm-package-lifecycle.md), [../../review/publish-pipeline.md](../../review/publish-pipeline.md) |

## Purpose

This document defines the responsibilities and boundaries of `ReviewService`.

Its job is to make clear what package review owns inside Gaia LKM, what artifacts it consumes and emits, and what it must not silently absorb from curation or runtime internals.

## Core Responsibility

`ReviewService` owns submission-scoped adjudication.

Its primary question is:

> Is this package acceptable in its current form, and if not, what concrete findings or responses are needed before a decision can be made?

## Inputs

`ReviewService` primarily consumes:

- submitted Gaia packages
- package profile and target references
- prior review context for the same submission thread
- rebuttal packages or equivalent response artifacts
- bounded shared context needed to judge the submission

The key boundary is that review works with a concrete submission and its immediate context. It does not own open-ended global graph maintenance.

## Outputs

`ReviewService` primarily emits review-side artifacts such as:

- findings
- verdicts
- requests for clarification or revision
- rebuttal hooks
- decision-ready review outputs

Those artifacts are defined more explicitly in [../artifacts/review-artifacts.md](../artifacts/review-artifacts.md).

## What ReviewService Owns

`ReviewService` owns:

- package-level evaluation
- structured review findings
- adjudicative review verdicts
- re-evaluation after rebuttal
- the accept / reject / revise / defer decision path for a submitted package

## What ReviewService Does Not Own

`ReviewService` does not own:

- long-horizon shared-state maintenance
- contradiction or equivalence mining across the whole LKM
- curation backlog management
- deep investigation queues as an independent long-running subsystem

If package review surfaces issues that exceed submission-scoped adjudication, it may hand them off, but it does not thereby become the owner of curation.

## Review Scope Is Bounded

Review may use shared context, but it remains bounded by the submission problem.

That means review should not silently become:

- global curation
- endless open-world research
- generic graph mining

It should answer the package decision question first.

## Relationship To Rebuttal

Rebuttal is part of the review-owned package loop.

That means `ReviewService` should be prepared to:

- receive rebuttal packages or equivalent response artifacts
- reconsider earlier findings in light of those responses
- update verdicts accordingly

This makes rebuttal part of the same adjudication surface rather than a separate curation concern.

## Relationship To CurationService

`ReviewService` and `CurationService` interact, but they are not substitutes.

`ReviewService` may route issues into curation when:

- the issue is not resolvable within ordinary submission review
- it requires longer-lived investigation
- it concerns shared-state maintenance beyond the immediate submission

But once that handoff occurs, the problem is no longer owned by review in the same way.

## Relationship To Runtime

`ReviewService` is a service boundary, not a claim about one specific runtime implementation.

The current backend may implement review in one server process, but the service contract should remain stable even if the runtime architecture changes.

## Relationship To Other Docs

- [service-boundaries.md](service-boundaries.md) defines where `ReviewService` sits relative to other LKM services.
- [../artifacts/review-artifacts.md](../artifacts/review-artifacts.md) defines the main artifact classes emitted by review.
- [../lifecycles/lkm-package-lifecycle.md](../lifecycles/lkm-package-lifecycle.md) defines the shared-side package flow that review participates in.

## Out Of Scope

This document does not define:

- curation responsibilities
- runtime implementation details
- BP algorithm internals
- low-level API endpoints

## Migration Note

This document replaces the earlier placeholder-only statement of `ReviewService` and makes package adjudication the explicit center of the service boundary.
