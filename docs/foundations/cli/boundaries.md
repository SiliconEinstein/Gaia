# Gaia CLI Runtime Boundaries

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Architecture |
| Scope | Subsystem |
| Related | [../contracts/lifecycles/cli-lifecycle.md](../contracts/lifecycles/cli-lifecycle.md), [../contracts/authoring/gaia-language-spec.md](../contracts/authoring/gaia-language-spec.md), [../contracts/authoring/graph-ir.md](../contracts/authoring/graph-ir.md), [../runtime/review-runtime.md](../runtime/review-runtime.md), [../runtime/inference-runtime.md](../runtime/inference-runtime.md) |

## Purpose

This file is a legacy bridge for the older `cli/boundaries.md` path.

It no longer defines the canonical CLI boundary model.

## Current Canonical Split

Use these docs instead:

- [../contracts/lifecycles/cli-lifecycle.md](../contracts/lifecycles/cli-lifecycle.md)
  - canonical local lifecycle
- [../contracts/authoring/gaia-language-spec.md](../contracts/authoring/gaia-language-spec.md)
  - authoring boundary
- [../contracts/authoring/graph-ir.md](../contracts/authoring/graph-ir.md)
  - structural lowering boundary
- [../runtime/review-runtime.md](../runtime/review-runtime.md)
  - current embedded/local review runtime
- [../runtime/inference-runtime.md](../runtime/inference-runtime.md)
  - current local inference runtime

## Important Current Corrections

- The canonical local lifecycle is `build -> infer -> publish`.
- Current `main` does **not** ship a standalone `gaia review` command in `cli/main.py`.
- Old references to shared `knowledge_artifact` or `package.yaml` style schemas should not be treated as active contract language.
- CLI boundary docs should describe the local authoring/runtime side, not re-describe shared-side LKM governance.

## Migration Note

Use the canonical docs above for current CLI boundary work.

This file remains only as a bridge for older links and references.
