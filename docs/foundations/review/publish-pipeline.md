# Publish Pipeline

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Spec |
| Scope | Subsystem |
| Related | [../contracts/lifecycles/cli-lifecycle.md](../contracts/lifecycles/cli-lifecycle.md), [../contracts/lifecycles/lkm-package-lifecycle.md](../contracts/lifecycles/lkm-package-lifecycle.md), [../contracts/artifacts/package-profiles.md](../contracts/artifacts/package-profiles.md), [../contracts/artifacts/review-artifacts.md](../contracts/artifacts/review-artifacts.md) |

## Purpose

This file is a legacy bridge for the older `review/publish-pipeline.md` path.

It no longer defines the canonical publish contract by itself.

## Current Canonical Split

The older broad "publish pipeline" framing has been split into:

- [../contracts/lifecycles/cli-lifecycle.md](../contracts/lifecycles/cli-lifecycle.md)
  - the local CLI handoff boundary
- [../contracts/lifecycles/lkm-package-lifecycle.md](../contracts/lifecycles/lkm-package-lifecycle.md)
  - the shared-side lifecycle after package intake
- [../contracts/artifacts/package-profiles.md](../contracts/artifacts/package-profiles.md)
  - what kinds of packages exist
- [../contracts/artifacts/review-artifacts.md](../contracts/artifacts/review-artifacts.md)
  - what review produces once a package is in Gaia LKM

## Important Current Corrections

- The canonical CLI lifecycle is `build -> infer -> publish`.
- Shared-side review is downstream of `publish`, not an extra CLI stage.
- Current `main` does **not** ship a standalone `gaia review` command in `cli/main.py`.
- `gaia publish --server` is not a current stable shipped CLI contract in this repository.
- Active authoring is Typst package source, not `package.yaml` plus module YAML files.

## Migration Note

Use the canonical docs above for current publish semantics.

This file remains only to keep older references from landing on a completely dead path.
