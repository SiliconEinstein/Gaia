# Inference Runtime

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Architecture |
| Scope | Subsystem |
| Related | [../semantics/gaia-reasoning-model.md](../semantics/gaia-reasoning-model.md), [../contracts/lifecycles/cli-lifecycle.md](../contracts/lifecycles/cli-lifecycle.md), [loop-analysis.md](loop-analysis.md), [../bp-on-graph-ir.md](../bp-on-graph-ir.md), [../theory/inference-theory.md](../theory/inference-theory.md) |

## Purpose

This document defines how inference currently runs in Gaia's implementation.

It is a runtime reference, not a pure semantic spec. The semantic model lives in [../semantics/gaia-reasoning-model.md](../semantics/gaia-reasoning-model.md). This document explains how today's code turns local graphs and local parameterization into actual BP runs, and where the current runtime still diverges from the target semantics.

## Runtime Position

Inference runtime currently exists in three main forms:

- local CLI preview inference
- reusable library pipelines used by CLI and batch-style execution
- partial shared-side and curation-time BP utilities

There is not yet a single always-on "Gaia LKM inference service" in the repository. The current codebase is still library-first.

## Local Inference Path

The canonical local execution path is:

1. `pipeline_build(pkg_path)`
2. `pipeline_review(build, ...)`
3. `pipeline_infer(build, review)`

The current CLI path in [`cli/main.py`](../../../cli/main.py) runs this sequence through:

- `gaia build`
- `gaia infer`
- `gaia publish --local`

`gaia infer` currently rebuilds the package, derives a review output, then runs BP. It does not rely on a long-lived review daemon or an external server.

## Runtime Inputs

At local runtime, BP consumes:

- a `LocalCanonicalGraph`
- a `LocalParameterization`

In the current implementation, `LocalParameterization` is assembled from `ReviewOutput`:

- `node_priors`
- `factor_params`

The runtime flow is:

1. `pipeline_review(...)` produces `ReviewOutput`
2. `pipeline_infer(...)` converts that into `LocalParameterization`
3. `adapt_local_graph_to_factor_graph(...)` lowers the local graph to an executable `FactorGraph`
4. `BeliefPropagation.run(...)` computes beliefs

The local result is an `InferResult` containing:

- named beliefs
- `bp_run_id`
- the adapted factor graph view
- the local parameterization used for the run

## Review Inputs At Runtime

Today, local inference does not wait for shared-side review.

The current CLI path uses:

- `MockReviewClient` in the default local flow

The general pipeline also supports:

- `ReviewClient(model=...)`

So the runtime already distinguishes between:

- deterministic graph construction
- review-derived local priors and factor parameters
- actual BP execution

But in shipped local flows this remains author-side preview logic, not authoritative LKM judgment.

## Lowering To Executable Factor Graphs

The current lowering path is:

- `LocalCanonicalGraph`
- `LocalParameterization`
- `libs.graph_ir.adapter.adapt_local_graph_to_factor_graph(...)`
- `libs.inference.factor_graph.FactorGraph`
- `libs.inference.bp.BeliefPropagation`

This runtime lowering is where Graph IR structure becomes executable BP structure.

Important current properties:

- inference runs on a factor graph, not directly on authored package source
- local preview uses package-local graph structure
- factor probabilities are supplied externally rather than embedded in Graph IR
- damping and convergence thresholds are runtime concerns, not authored semantics

## Current Shared-Side Runtime State

The repository already contains shared-side storage and global-state runtime pieces:

- `CanonicalBinding`
- `GlobalCanonicalNode`
- `GlobalInferenceState`
- persistent `FactorNode`
- curation-time factor-graph construction from stored nodes and factors

However, the full shared-side inference story is still incomplete as a runtime system:

- there is no stable always-on inference API
- there is no complete end-to-end LKM BP service shell in the repo
- package publish does not currently schedule or persist a shared-side BP update end-to-end

So the current shared-side inference runtime should be understood as:

- storage model support exists
- curation-time BP utilities exist
- a full LKM inference service is still an integration task

## Publish Boundary

The current runtime keeps a strict distinction between local preview inference and published artifacts.

In particular:

- local BP beliefs are preview artifacts
- `pipeline_publish(...)` does not publish local belief snapshots
- publish uses review-derived probability records, but not local preview beliefs as shared truth

This matches the current foundations direction: local inference is preview, not shared-state commitment.

## Runtime Divergences From Target Semantics

This document is `Transitional` because the current BP runtime still lags the target semantic model in several places.

Most importantly:

- the current kernel in [`libs/inference/bp.py`](../../../libs/inference/bp.py) still reflects legacy factor semantics in places
- the target `noisy-AND + leak` reasoning model is not fully landed as the runtime default
- relation-factor handling is still migrating away from older gate-oriented assumptions

So the runtime is already structurally correct in the sense that it uses:

- explicit factor graphs
- loopy BP
- external parameterization overlays

But its detailed factor semantics are still in transition.

## Relationship To Loop Analysis

Loop handling is part of the inference runtime, but it deserves its own runtime document because it combines:

- BP behavior on loopy graphs
- diagnostics
- conflict surfacing
- future basis-view style explanation support

That material is defined in [loop-analysis.md](loop-analysis.md).

## Out Of Scope

This document does not define:

- the higher-level philosophy of scientific reasoning
- authored package syntax
- shared-side package lifecycle rules
- storage schema details

## Migration Note

This document replaces the earlier placeholder-only runtime note. It makes the current inference runtime explicit: Gaia is already factor-graph-and-BP based, but the exact semantics of several factor families are still converging toward the newer reasoning model.
