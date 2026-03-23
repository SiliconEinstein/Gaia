# Inference Theory

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Foundation |
| Scope | Repo-wide |
| Related | [../semantics/gaia-reasoning-model.md](../semantics/gaia-reasoning-model.md), [../semantics/knowledge-relations.md](../semantics/knowledge-relations.md), [../runtime/inference-runtime.md](../runtime/inference-runtime.md), [../runtime/loop-analysis.md](../runtime/loop-analysis.md) |

## Purpose

This file is a legacy bridge for the older `theory/inference-theory.md` path.

It no longer acts as the canonical home for Gaia's inference semantics.

## Current Canonical Split

Use these docs instead:

- [../semantics/gaia-reasoning-model.md](../semantics/gaia-reasoning-model.md)
  - Gaia-level reasoning families such as deduction, induction, abduction, abstraction, and instantiation
- [../semantics/knowledge-relations.md](../semantics/knowledge-relations.md)
  - the core semantic relation families between Gaia knowledge items
- [../runtime/inference-runtime.md](../runtime/inference-runtime.md)
  - the current executable inference runtime and current-vs-target divergence
- [../runtime/loop-analysis.md](../runtime/loop-analysis.md)
  - loop handling and basis-style diagnostic views

## Important Current Corrections

- Semantic reasoning families and runtime BP details are no longer defined in one mixed document.
- Loopy BP is allowed; loop analysis is diagnostic rather than a mandatory DAG rewrite step.
- Jaynes-style update behavior should be read as part of Gaia's reasoning model and runtime operator behavior, not as a standalone surface-language taxonomy.

## Migration Note

Use the canonical docs above for current work.

This file remains only as a bridge for older links and references.
