# Loop Analysis

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Architecture |
| Scope | Component |
| Related | [inference-runtime.md](inference-runtime.md), [../semantics/gaia-reasoning-model.md](../semantics/gaia-reasoning-model.md), [../bp-on-graph-ir.md](../bp-on-graph-ir.md) |

## Purpose

This document defines how Gaia treats loops in inference runtime and curation-time diagnostics.

Its main job is to prevent a recurring confusion: Gaia's inference model is intentionally loopy. Loops are not, by themselves, evidence that the graph must be rewritten into a DAG before BP can run.

## Core Judgment

Gaia uses loopy belief propagation as a first-class runtime model.

Therefore:

- loops are allowed
- loops are expected in shared reasoning structure
- DAG conversion is not a prerequisite for inference

This applies both to:

- package-local preview inference
- shared-side graph analysis

## What A Loop Means In Gaia

A loop means that support or constraint information can circulate through more than one path.

That is not automatically a bug. In Gaia, loops arise naturally from:

- mutually reinforcing support structures
- constraint relations
- schema/instance patterns
- shared substructure reused across multiple chains

The right response is therefore not "remove loops by default", but:

- run loopy BP with damping
- inspect instability where needed
- surface diagnostics when a loop behaves pathologically

## Current Runtime Behavior

### Local inference

Local inference in [`libs/inference/bp.py`](../../../libs/inference/bp.py) runs directly on loopy factor graphs.

The runtime already provides:

- synchronous message updates
- damping
- convergence checks
- diagnostics collection

There is no mandatory preprocessing step that rewrites the graph into a DAG.

### Curation-time analysis

The current curation runtime in [`libs/curation/scheduler.py`](../../../libs/curation/scheduler.py) also treats loops as analyzable structure rather than invalid structure.

It currently uses:

- BP diagnostics for oscillation-style conflict surfacing
- sensitivity-style probing for conflict candidates

In other words, loop-heavy regions are currently handled as:

- diagnostic targets
- conflict-discovery targets

not as input that must be normalized away before reasoning can proceed.

## Basis Views And Axiom Bases

Gaia may still use basis-style views, but they should be understood correctly.

An `axiom basis`, `assumption basis`, or similar view should be treated as:

- an explanation aid
- a diagnostic cut through a loopy region
- a possible conditioning or audit artifact

It should not be treated as:

- the true semantic form of the graph
- a mandatory preprocessing step before BP
- a silent rewrite of the source or canonical graph

So the right conceptual status is:

- graph semantics stay loopy
- basis views are optional runtime artifacts

## Current Implemented Diagnostics

The repository already has the beginnings of loop-aware diagnostics:

- `BeliefPropagation.run_with_diagnostics(...)`
- Level-1 oscillation detection in [`libs/curation/conflict.py`](../../../libs/curation/conflict.py)
- Level-2 sensitivity analysis in [`libs/curation/conflict.py`](../../../libs/curation/conflict.py)

These are still narrower than a full basis-view system, but they already establish the main runtime direction:

- detect problematic loop behavior
- analyze it after or alongside BP
- do not require DAG rewriting

## What Is Not Yet Implemented

The following ideas are important, but not yet first-class runtime artifacts:

- explicit `BasisView` objects
- explicit `LoopReport` or `CutsetReport` persisted in storage
- stable user-facing explanation views built around basis decomposition

Those are future extensions, not current runtime requirements.

## Why This Document Is Transitional

This document is `Transitional` because the long-term explanation layer is not fully settled yet.

What is already settled:

- loopy BP is primary
- loop diagnosis is legitimate
- basis views are optional aids rather than semantic rewrites

What is still evolving:

- exact artifact shape for loop reports
- whether basis views become explicit persisted objects
- how strongly loop diagnostics integrate with review and curation outputs

## Relationship To Other Docs

- [inference-runtime.md](inference-runtime.md) defines the executable BP runtime.
- [../semantics/gaia-reasoning-model.md](../semantics/gaia-reasoning-model.md) defines the reasoning-level meaning of deduction, induction, abduction, abstraction, and instantiation.
- [../contracts/artifacts/investigation-artifacts.md](../contracts/artifacts/investigation-artifacts.md) defines the kinds of investigation items that loop analysis may eventually surface.

## Out Of Scope

This document does not define:

- general scientific reasoning philosophy
- package workflows
- storage tables
- authoring syntax
