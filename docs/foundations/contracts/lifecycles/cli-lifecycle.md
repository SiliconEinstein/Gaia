# CLI Lifecycle

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Spec |
| Scope | Subsystem |
| Related | [../../system-overview.md](../../system-overview.md), [../../semantics/terminology.md](../../semantics/terminology.md), [lkm-package-lifecycle.md](lkm-package-lifecycle.md), [../../cli/command-lifecycle.md](../../cli/command-lifecycle.md) |

## Purpose

This document defines the canonical local lifecycle of Gaia CLI.

It answers one question: what are the local, author-side lifecycle stages that Gaia CLI owns before shared-side processing begins?

## Core Judgment

The canonical Gaia CLI lifecycle is:

- `build`
- `infer`
- `publish`

Nothing after that belongs to the CLI lifecycle as such.

In particular:

- shared-side review is not a CLI lifecycle stage
- rebuttal is not a CLI lifecycle stage
- LKM integration is not a CLI lifecycle stage

## Why The Boundary Matters

Gaia intentionally separates:

- local author-side artifact production and preview
- shared-side adjudication and integration

Without this boundary, the CLI would become a vague mixture of author tooling, review workflow, and shared-state governance.

## Stage 1: Build

`build` is the deterministic lowering boundary from authored package source into explicit local artifacts.

Its job is to:

- validate and elaborate the local package
- lower authored structure into Graph IR artifacts
- produce review- and inference-ready local outputs

Typical outputs include artifacts under `.gaia/`, such as:

- build-oriented rendered outputs
- raw graph artifacts
- local canonical graph artifacts
- canonicalization logs

The exact file layout may evolve, but the contract is stable: `build` produces deterministic local structural artifacts.

## Stage 2: Infer

`infer` is the local inference and preview boundary.

Its job is to:

- consume local structural artifacts
- derive or consume local author-side inference inputs
- run local belief-oriented inference as a preview
- emit local inference outputs for the author

Important boundary:

- local preview inference is not shared-side truth
- local inference outputs are for author-side preview and iteration
- shared-side review and integration remain downstream

## Stage 3: Publish

`publish` is the handoff boundary from Gaia CLI to Gaia LKM.

Its job is to:

- package the relevant local artifact set for submission or local publication target
- hand off deterministic package artifacts outward
- stop at the submission boundary

Once publish completes, the next lifecycle belongs to [lkm-package-lifecycle.md](lkm-package-lifecycle.md).

## Inputs And Outputs By Stage

| Stage | Primary inputs | Primary outputs |
|---|---|---|
| `build` | Typst package source | deterministic local build and graph artifacts |
| `infer` | local build/graph artifacts plus author-local inference inputs | local preview inference artifacts |
| `publish` | package source plus deterministic local artifacts chosen for submission | submitted package artifact / handoff to LKM |

## What Is Not In The Canonical CLI Lifecycle

The following may exist in older design docs, local workflows, or future tooling, but they are not part of the canonical three-stage CLI lifecycle:

- a separate `gaia review` stage
- shared-side peer review
- rebuttal exchange
- editorial decisions
- LKM integration

Current code does not ship a standalone `gaia review` command in the main CLI entrypoint. Review logic currently appears as embedded preview runtime inside local infer and local publish flows rather than as a fourth canonical lifecycle stage.

## Relationship To Other Docs

- [../authoring/graph-ir.md](../authoring/graph-ir.md) defines the structural artifacts produced by `build`.
- [lkm-package-lifecycle.md](lkm-package-lifecycle.md) defines what happens after `publish`.
- [../../cli/command-lifecycle.md](../../cli/command-lifecycle.md) remains a useful migration-era reference for older combined lifecycle framing.

## Out Of Scope

This document does not define:

- shared-side review or rebuttal
- server runtime architecture
- BP implementation internals
- low-level command-line UX details

## Migration Note

This document replaces the older tendency to let the CLI lifecycle bleed into publish-time review. The active contract is now simple: the CLI owns `build`, `infer`, and `publish`; Gaia LKM owns what comes next.
