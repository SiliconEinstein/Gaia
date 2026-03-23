# BP On Graph IR

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Spec |
| Scope | Subsystem |
| Related | [runtime/inference-runtime.md](runtime/inference-runtime.md), [runtime/loop-analysis.md](runtime/loop-analysis.md), [semantics/gaia-reasoning-model.md](semantics/gaia-reasoning-model.md), [contracts/authoring/graph-ir.md](contracts/authoring/graph-ir.md) |

## Purpose

This file is a legacy bridge for the older `bp-on-graph-ir.md` path.

It no longer serves as the canonical home for current BP/runtime documentation.

## Current Canonical Split

Use these docs instead:

- [runtime/inference-runtime.md](runtime/inference-runtime.md)
  - current executable inference runtime and current-vs-target divergence
- [runtime/loop-analysis.md](runtime/loop-analysis.md)
  - how loops and basis-style diagnostics should be understood
- [semantics/gaia-reasoning-model.md](semantics/gaia-reasoning-model.md)
  - Gaia-level reasoning families and their intended meaning
- [contracts/authoring/graph-ir.md](contracts/authoring/graph-ir.md)
  - the structural Graph IR contract

## Important Current Corrections

- Loopy BP is the active reasoning model; loops are not treated as an error requiring mandatory DAG rewrite.
- Axiom-basis or basis-style decomposition is diagnostic/explanatory, not a prerequisite for local inference.
- Graph IR is structural; BP semantics belong to runtime and reasoning-model docs, not to one monolithic mixed document.

## Migration Note

Use the canonical docs above for current work.

This file remains only as a compatibility bridge for older links and citations.
