# Package Profiles

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Spec |
| Scope | Repo-wide |
| Related | [../lifecycles/lkm-package-lifecycle.md](../lifecycles/lkm-package-lifecycle.md), [review-artifacts.md](review-artifacts.md), [investigation-artifacts.md](investigation-artifacts.md), [../../review/publish-pipeline.md](../../review/publish-pipeline.md) |

## Purpose

This document defines the semantic profiles of Gaia packages.

It answers the question: when a Gaia package is submitted or exchanged, what kind of package is it, and how should Gaia LKM interpret it?

## Core Principle

A Gaia package is the formal artifact unit of the system, but not every package serves the same role.

Some packages contribute scientific knowledge directly. Others carry review, rebuttal, or investigation material around that knowledge.

That difference should be explicit at the package level rather than inferred ad hoc from the contents.

## Package Profile Table

| Profile | Primary purpose | Typical author | Typical LKM effect |
|---|---|---|---|
| `knowledge` | Contribute scientific knowledge content | researcher or agent author | candidate for direct knowledge integration |
| `review` | Evaluate another package or its claims | reviewer, review agent, or editorial process | contributes review findings and verdict context |
| `rebuttal` | Respond to review or investigation results | original author or supporting agent | contributes response context and clarifications |
| `investigation` | Submit deeper research or audit results | investigation agent or researcher | contributes investigation results, evidence bundles, or follow-up proposals |

## Knowledge Packages

A `knowledge` package is the default knowledge-bearing submission profile.

Its purpose is to contribute scientific content such as:

- claims
- laws
- observations
- hypotheses
- predictions
- explicit relations between those items

If accepted, a knowledge package is the profile most likely to contribute directly to shared knowledge state inside Gaia LKM.

## Review Packages

A `review` package records evaluative judgment about some other package or submission subject.

Its purpose is not to contribute ordinary scientific knowledge in the same way a knowledge package does. Its primary role is to contribute:

- findings
- objections
- acceptance or rejection rationale
- requests for clarification

Review packages may contain claims and structured evidence, but their semantics are review-oriented rather than direct knowledge contribution.

## Rebuttal Packages

A `rebuttal` package is a response artifact tied to prior review or investigation outputs.

Its purpose is to:

- answer findings
- clarify scope
- dispute incorrect objections
- add missing context or evidence

Like review packages, rebuttal packages may contain structured claims, but their primary meaning is procedural and argumentative within the shared-side adjudication lifecycle.

## Investigation Packages

An `investigation` package carries the results of deeper research work that is not well modeled as ordinary package review.

Typical examples include:

- contradiction audits
- independent-evidence audits
- hidden-premise investigations
- equivalence or abstraction investigations

An investigation package may produce:

- evidence bundles
- structured conclusions
- proposed follow-up knowledge packages
- proposed relation or integration changes

But the package profile remains investigation-focused rather than ordinary knowledge submission.

## Why Profiles Are Artifact Contracts, Not Workflow Stages

Profiles describe what a package *is*.

They do not by themselves say:

- when the package arrives
- who processes it first
- what state transitions it undergoes

Those questions belong to lifecycle docs such as [../lifecycles/lkm-package-lifecycle.md](../lifecycles/lkm-package-lifecycle.md).

## Profiles Do Not Dictate Surface Syntax

This document does not require that each package profile have a different surface language.

The same Gaia package language may be used across profiles. The profile changes:

- how the artifact is interpreted
- what review rules apply
- how accepted content is integrated into Gaia LKM

## Relationship To Other Docs

- [../lifecycles/lkm-package-lifecycle.md](../lifecycles/lkm-package-lifecycle.md) defines what happens to these packages after they arrive in Gaia LKM.
- [review-artifacts.md](review-artifacts.md) defines the finer-grained review-side outputs associated with review packages.
- [investigation-artifacts.md](investigation-artifacts.md) defines the finer-grained investigation-side outputs associated with investigation packages.

## Out Of Scope

This document does not define:

- review service internals
- current server runtime behavior
- authored package syntax
- detailed state transitions after intake

## Migration Note

This document supersedes the earlier placeholder `package types` framing. The important issue here is not static type theory, but the semantic profile of a package artifact inside Gaia workflows.
