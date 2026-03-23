# Review Runtime

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Architecture |
| Scope | Component |
| Related | [../contracts/services/review-service.md](../contracts/services/review-service.md), [../contracts/artifacts/review-artifacts.md](../contracts/artifacts/review-artifacts.md), [../contracts/lifecycles/lkm-package-lifecycle.md](../contracts/lifecycles/lkm-package-lifecycle.md), [server-architecture.md](server-architecture.md), [../review/publish-pipeline.md](../review/publish-pipeline.md) |

## Purpose

This document defines how review currently executes in code, as distinct from the abstract responsibility contract of `ReviewService`.

## Current Runtime Shape

Today, review runtime is mostly a reusable library path rather than a fully separated deployed service.

The core execution entry is:

- `pipeline_review(...)` in [`libs/pipeline.py`](../../../libs/pipeline.py)

This function is the practical runtime center of review behavior on current `main`.

## Review Inputs And Outputs

At runtime, `pipeline_review(...)` consumes:

- a `BuildResult`
- a review mode (`mock` or model-backed)
- optional review model metadata

It produces a `ReviewOutput` containing:

- raw review payload
- `node_priors`
- `factor_params`
- model metadata
- optional source fingerprint

This means current review runtime is already structured enough to feed inference and publish, even though the richer multi-stage shared-side review loop is still only partially implemented.

## Review Clients In Current Code

Current runtime review uses one of two client paths:

- `MockReviewClient`
- `ReviewClient`

`MockReviewClient` is heavily used in current local CLI and test flows.

`ReviewClient` represents model-backed review, but it still plugs into the same library pipeline shape rather than a distinct long-lived review daemon.

## Local Execution Today

In current shipped CLI behavior:

- `gaia infer` performs build → mock review → infer
- `gaia publish --local` performs build → mock review → infer → publish

So review already exists at runtime, but it is embedded inside local author-side flows.

Important current fact:

- there is no standalone `gaia review` command in the current shipped CLI entrypoint

This is one reason review runtime must be documented separately from older combined pipeline design docs.

## Shared-Side Runtime Gap

The contract model for `ReviewService` is richer than the currently implemented runtime.

What exists today:

- reusable review pipeline logic
- review clients
- `ReviewOutput` as a structured bridge to inference and publish

What does not yet exist as a stable runtime shell:

- a full authoritative LKM review service process
- a stable external review API
- a fully implemented peer-review / rebuttal / editor loop in running code

So the current review runtime should be read as:

- operationally real for local preview and pipeline composition
- not yet fully realized as the final shared-side review platform

## Runtime Relationship To Inference

Review runtime currently feeds inference runtime directly.

Specifically:

- `ReviewOutput.node_priors` becomes the local prior layer
- `ReviewOutput.factor_params` becomes the local factor-parameter layer
- inference then adapts these into executable BP inputs

This makes review runtime an operational upstream stage for local preview inference, even though review and inference remain conceptually distinct.

## Runtime Relationship To Publish

Publish runtime currently uses review output as one of its inputs.

At publish time, current code uses review-derived probability information to build:

- `ProbabilityRecord`s

But it does not turn local review into a full shared-side adjudication workflow automatically.

That larger review lifecycle is still described at the contract level in [../contracts/lifecycles/lkm-package-lifecycle.md](../contracts/lifecycles/lkm-package-lifecycle.md).

## Out Of Scope

This document does not define:

- abstract review responsibility boundaries
- authored package types
- BP internals unrelated to review execution

## Migration Note

This document intentionally separates current runtime truth from older architecture drafts. Review is real in the codebase today, but it is currently embedded, library-first runtime logic rather than a fully deployed standalone LKM review service.
