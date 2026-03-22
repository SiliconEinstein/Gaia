# Review Artifacts

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Spec |
| Scope | Repo-wide |
| Related | [../services/review-service.md](../services/review-service.md), [package-profiles.md](package-profiles.md), [../../review/publish-pipeline.md](../../review/publish-pipeline.md) |

## Purpose

This document defines the main artifact classes emitted by review-side workflows in Gaia LKM.

It answers the question: what concrete artifacts does review produce around a submitted package?

## Core Principle

Review is not just a hidden internal judgment. It produces structured artifacts that can be:

- read
- answered
- stored
- referenced in later package lifecycle steps

## Main Review Artifact Classes

### Findings

A `finding` is a structured statement about a problem, concern, or required clarification in a submission.

Typical finding categories may include:

- structural problems
- scope or regime ambiguity
- weak support
- missing clarification
- integration concerns

### Verdicts

A `verdict` is the adjudicative output of a review step.

Typical examples include:

- accepted
- revision required
- rejected
- deferred

The exact verdict set may evolve, but review artifacts must support explicit verdict recording rather than leaving the result implicit in free text.

### Rebuttal Hooks

A `rebuttal hook` is a structured pointer to the issue or finding that a rebuttal should answer.

This matters because rebuttal should respond to structured review outputs, not to an unstructured blob of comments.

### Review-Carrying Packages Or Equivalent Artifacts

Some review outputs may be represented as full package-level artifacts, especially when the system uses package profiles such as `review`.

Other deployments may project the same information into internal report formats. The important contract is the semantics of the artifact, not one storage format.

## Relationship To ReviewService

These artifacts are primarily owned by [../services/review-service.md](../services/review-service.md).

Review service produces them as part of submission-scoped adjudication.

## Relationship To Package Profiles

Review artifacts are closely related to the `review` package profile defined in [package-profiles.md](package-profiles.md), but the two are not identical:

- a package profile classifies the package artifact as a whole
- review artifacts are the finer-grained outputs carried within or around that package flow

## Out Of Scope

This document does not define:

- who owns review responsibilities
- curation-only artifacts
- runtime implementation details
- deeper investigation queues

## Migration Note

This document replaces the earlier placeholder-only treatment of review outputs and makes clear that review emits structured artifacts rather than a purely implicit process result.
