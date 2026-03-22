# Investigation Artifacts

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Spec |
| Scope | Repo-wide |
| Related | [../services/curation-service.md](../services/curation-service.md), [package-profiles.md](package-profiles.md), [../../theory/corroboration-and-conditional-independence.md](../../theory/corroboration-and-conditional-independence.md) |

## Purpose

This document defines the main investigation-side artifacts used for open questions, deferred audits, and research-agenda style follow-up inside Gaia LKM.

It answers the question: when an issue is too large or too open-ended for ordinary package review, what artifact does Gaia create to keep that issue visible and actionable?

## Core Principle

Not every unresolved issue should become:

- a normal scientific knowledge node
- a review finding
- an immediate external task for a human or external agent

Gaia needs a separate class of investigation artifacts for longer-lived shared-side questions.

## Main Investigation Artifact Classes

### Investigation Item

An `investigation item` is the generic open-question or queued follow-up artifact.

It records that some issue remains unresolved and should stay visible inside Gaia LKM.

### Contradiction Audit

A contradiction audit item tracks a suspected incompatibility that needs deeper analysis beyond ordinary submission review.

It is not the same as the semantic relation `contradiction` itself. It is a workflow artifact about whether, where, and how contradiction should be established or investigated.

### Independent-Evidence Audit

An independent-evidence audit item tracks the question of whether multiple supporting paths are genuinely independent.

This corresponds to the broader corroboration discussion, but here it is treated as an investigation artifact rather than as a core semantic relation.

### Hidden-Premise Search

A hidden-premise search item records the need to look for missing assumptions, missing shared causes, or omitted background conditions.

### Other Research-Agenda Items

Gaia may also use investigation artifacts for broader research-agenda style follow-up, provided those items are still tied to the shared knowledge system and not confused with ordinary scientific claims.

## Investigation Artifacts Are Not Knowledge Relations

These artifacts are about the management of unresolved issues.

They are not themselves:

- contradiction relations
- equivalence relations
- ordinary support edges

They live at the workflow and maintenance layer, not at the base semantics layer.

## Relationship To CurationService

These artifacts are most naturally owned by [../services/curation-service.md](../services/curation-service.md).

Curation may:

- create them
- manage them
- consume them in longer-lived maintenance work

## Relationship To Package Profiles

Investigation artifacts relate closely to the `investigation` package profile defined in [package-profiles.md](package-profiles.md), but again the distinction matters:

- package profile classifies a whole package
- investigation artifacts are the finer-grained queued or emitted objects inside that broader workflow

## Internal First, External Optional

The current foundations direction assumes these artifacts are primarily internal to Gaia LKM.

They may eventually be exposed to external research-agent surfaces, but that is not required by the current contract.

## Out Of Scope

This document does not define:

- the high-level semantics of contradiction itself
- service ownership details beyond the curation tie-in
- runtime scheduling implementation
- low-level queue implementation

## Migration Note

This document replaces the earlier placeholder-only framing and makes the "open question list" idea explicit as a family of investigation artifacts rather than as ordinary semantic nodes or ad hoc comments.
