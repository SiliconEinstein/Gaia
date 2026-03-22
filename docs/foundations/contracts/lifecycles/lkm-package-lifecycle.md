# LKM Package Lifecycle

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Spec |
| Scope | Repo-wide |
| Related | [../artifacts/package-profiles.md](../artifacts/package-profiles.md), [../services/service-boundaries.md](../services/service-boundaries.md), [../../review/publish-pipeline.md](../../review/publish-pipeline.md), [../../system-overview.md](../../system-overview.md) |

## Purpose

This document defines the shared-side lifecycle of packages after they arrive in Gaia LKM.

It answers the question: after local `publish`, what happens to a package inside the shared knowledge system?

## Core Principle

The canonical CLI lifecycle ends at `publish`.

Everything after that belongs to Gaia LKM.

That shared-side lifecycle includes:

- intake
- review
- rebuttal handling
- acceptance or rejection decisions
- integration
- curation and investigation handoff

## High-Level Flow

At a high level, the LKM-side package lifecycle looks like this:

1. A package arrives from Gaia CLI or another accepted shared-side channel.
2. Gaia LKM records the package and its declared profile.
3. The package enters shared-side review or investigation handling as appropriate.
4. The package may receive review findings, rebuttals, or requests for further work.
5. A decision is made: accept, reject, defer, or route to further investigation.
6. If accepted, the package is integrated according to its profile.
7. Post-decision curation or maintenance work may continue around the resulting shared state.

## Intake

Intake is the point at which a package becomes visible to Gaia LKM as a shared-side artifact.

The intake step should at least establish:

- package identity
- package profile
- subject or target references if the package is review-, rebuttal-, or investigation-oriented
- enough metadata to route the package into the correct shared-side path

## Profile-Aware Routing

The LKM lifecycle is profile-aware.

Different package profiles enter the shared side with different intended semantics:

- `knowledge` packages usually enter knowledge review and possible integration
- `review` packages attach to an existing submission or decision context
- `rebuttal` packages respond to prior review or investigation outputs
- `investigation` packages carry deeper audit or research outputs

This routing is why package profile is an artifact contract, not merely a descriptive label.

## Review

Review is the shared-side adjudication step that determines whether a package is acceptable in its current form.

Review belongs to Gaia LKM, not to the canonical Gaia CLI lifecycle.

For `knowledge` packages, review commonly evaluates:

- structural validity
- claim clarity
- support quality
- scope and regime clarity
- integration readiness

For other profiles, review may instead focus on:

- correctness of findings
- adequacy of response
- sufficiency of evidence
- suitability for downstream action

## Rebuttal

Rebuttal is the shared-side response path for addressing review or investigation outputs.

Its role is to let authors or agents:

- answer findings
- correct misunderstandings
- provide missing context
- narrow or revise claims

Rebuttal is not a side note. It is part of the core LKM package lifecycle because Gaia treats scientific knowledge as revisable and contestable.

## Decision

At some point the package receives a shared-side decision.

Typical decision outcomes include:

- accepted
- rejected
- deferred pending further work
- routed to additional investigation

The precise decision model can evolve, but the important contract is that the shared side owns this decision boundary, not the local CLI.

## Integration

If a package is accepted, Gaia LKM integrates it according to its profile.

### Knowledge package integration

For `knowledge` packages, integration may contribute directly to shared knowledge state.

### Review package integration

For `review` packages, integration typically contributes to decision records and review context rather than ordinary knowledge-state growth.

### Rebuttal package integration

For `rebuttal` packages, integration typically contributes response history and adjudication context.

### Investigation package integration

For `investigation` packages, integration may contribute investigation records, evidence bundles, and possible follow-up proposals rather than immediate direct knowledge-state growth.

## Curation And Investigation Handoff

Not every issue can or should be resolved inside the initial review pass.

Some issues are better handed off to longer-lived shared-side work such as:

- curation
- contradiction audits
- independent-evidence audits
- hidden-premise investigations

This handoff is still part of the LKM-side lifecycle, but it belongs to service-level ownership beyond the initial submission verdict.

## Relationship To Services

- `ReviewService` owns submission-scoped adjudication responsibilities.
- `CurationService` owns longer-lived shared-state maintenance and deeper investigation routing.

This document defines the lifecycle contract. Service ownership is defined more explicitly in [../services/service-boundaries.md](../services/service-boundaries.md).

## Relationship To Other Docs

- [../artifacts/package-profiles.md](../artifacts/package-profiles.md) defines what kinds of packages enter this lifecycle.
- [../services/service-boundaries.md](../services/service-boundaries.md) defines which services own which parts of the shared-side flow.
- [../../review/publish-pipeline.md](../../review/publish-pipeline.md) remains a useful migration-era reference for older shared-side workflow framing.

## Out Of Scope

This document does not define:

- local CLI steps before publish
- server deployment topology
- low-level API details
- runtime process composition

## Migration Note

This document supersedes the earlier, too-broad `LKM lifecycle` placeholder. The real contract is the lifecycle of packages inside Gaia LKM after publish, not an abstract lifecycle of the LKM in general.
