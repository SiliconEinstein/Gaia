# Gaia CLI Command Lifecycle

> Related documents:
> - [../review/publish-pipeline.md](../review/publish-pipeline.md)
> - [../review/package-artifact-profiles.md](../review/package-artifact-profiles.md)
> - [../review/service-boundaries.md](../review/service-boundaries.md)
> - [../theory/scientific-ontology.md](../theory/scientific-ontology.md)

> **Status: Current target semantics.** This document aligns to [`../review/publish-pipeline.md`](../review/publish-pipeline.md). The target pipeline has 3 core CLI commands (`build`, `infer`, `publish`) plus 3 agent skills (`self-review`, `graph-construction`, `rebuttal`). The shipped `gaia review` command on `main` is a compatibility bridge for the local self-review step, not part of the long-term minimal core.

## Purpose

This document defines the local-to-shared lifecycle of a Gaia package:

- deterministic package lowering
- optional local self-review and graph construction
- optional local BP preview
- publish-time peer review and registry integration

It answers one product question:

> What is the target package lifecycle from local authoring snapshot to publish-time peer review and global integration?

## Core Judgment

Gaia's target local workflow is:

```text
workspace -> build -> self-review skill -> graph-construction skill -> infer -> verify -> publish
```

In practice on `main`, the self-review step is often materialized via the shipped `gaia review` command, but the architectural boundary remains:

- CLI commands handle deterministic or mechanical data I/O
- agent skills handle judgment-heavy review and graph-construction work
- peer review, identity assignment, and global inference happen after publish

Not:

```text
workspace -> build -> run -> publish
```

## Lifecycle Stages

### Stage 0: Workspace

Before Gaia commands act on a package, the author works in a private workspace:

- read papers
- collect notes
- test hypotheses
- draft candidate claims or refs
- prepare supporting resources

This workspace is intentionally broader and messier than the published Gaia artifact.

### Stage 1: Source Package

At some point the author materializes a structured package:

- knowledge objects
- refs
- reasoning chains
- module/package boundaries
- provenance or resource links

The default authored submission is a `knowledge` package. Downstream review/rebuttal may also be represented as Gaia packages with different profiles, but the local authoring lifecycle normally starts from the `knowledge` profile.

This authored source is the input to `gaia build`.

### Stage 2: Built Package

`gaia build` is the deterministic lowering boundary.

It validates and lowers source into explicit local artifacts, including:

- `.gaia/build/` rendered module Markdown for review
- `.gaia/graph/raw_graph.json`
- `.gaia/graph/local_canonical_graph.json`
- `.gaia/graph/canonicalization_log.json`

The build result is still package-local. It does not assign global identities, search the shared graph, or add review-discovered knowledge into submitted Graph IR.

### Stage 3: Local Review And Graph Construction

After build, the agent may run two local skills:

1. **self-review**
   - assess reasoning quality
   - identify candidate weak points and unrelated refs
   - classify candidates as premise / context / irrelevant
   - write local sidecar judgments
2. **graph-construction**
   - inspect the package-owned raw graph
   - cluster package-owned propositions into a local canonical graph
   - optionally derive local parameterization for preview inference
   - require explicit source edits and rebuilds before any review-discovered knowledge becomes submitted structure

On `main`, the shipped `gaia review` command is the compatibility path that materializes local self-review output under `.gaia/reviews/`.

### Stage 4: Inferred Package

`gaia infer` is the local belief-propagation boundary.

It consumes the package's local Graph IR plus available local review sidecars, derives a local parameterization as a runtime step, and runs local BP. Typical outputs live under `.gaia/inference/`, including local parameterization artifacts and belief previews.

Only closed, truth-apt assertions directly participate in this BP preview. Inquiry artifacts and procedural declarations may still shape structure or workflows, but they are not ordinary domain-BP variables by default.

### Stage 5: Verified Package

> **Not yet implemented.** `gaia verify` remains a future command for execution-backed or reproducibility-backed claims.

`gaia verify` is reserved for claims whose trust depends on replay, execution, or independently checkable evidence rather than textual reasoning or BP alone.

### Stage 6: Published Package

`gaia publish` is the handoff boundary from local package lifecycle to shared package lifecycle.

After publish, the shared system may:

- run peer review against the current registry state
- search for related global knowledge
- assign `CanonicalBinding` records
- update registry-managed `GlobalInferenceState`
- merge approved package content into the global graph

That work is downstream of local CLI authority.

The publish handoff still centers on Gaia packages. Review and rebuttal may later be represented as Gaia-language artifacts as well, but with different artifact profiles and merge semantics.

## Command And Skill Contracts

| Entry | Kind | Role | Determinism | Primary outputs |
|---|---|---|---|---|
| `build` | CLI command | deterministic package lowering | deterministic | `.gaia/build/` + `.gaia/graph/` artifacts |
| `self-review` | agent skill | local reasoning assessment | model-dependent | local review sidecars / judgments |
| `graph-construction` | agent skill | local canonicalization + optional local parameterization | mixed | local canonical graph + optional `.gaia/inference/local_parameterization.json` |
| `infer` | CLI command | local BP preview | deterministic given local artifacts | `.gaia/inference/` artifacts + belief preview |
| `verify` | CLI command | reproducibility / execution checks | execution-dependent | verification evidence sidecars |
| `publish` | CLI command | submission handoff | protocol-driven | Gaia package submission + deterministic artifacts to git / registry-facing pipeline |
| `rebuttal` | agent skill | process peer review findings | model-dependent | revised package source or rebuttal package/projection artifacts |

## Current `main` Compatibility Note

The code on `main` still ships `gaia review`. Treat it as:

- a local compatibility helper for the self-review phase
- not the final architectural review boundary
- not a replacement for publish-time peer review

This distinction matters because `publish-pipeline.md` assigns peer review, canonical binding, and global probability judgments to the shared system after publish.

## Per-Command Responsibilities

### `gaia build`

Responsibilities:

- validate package structure
- resolve refs deterministically
- elaborate review-facing rendered content
- lower package source into package-local Graph IR

`build` does not perform open-world search or author-server alignment.

### `gaia infer`

Responsibilities:

- read local canonical graph artifacts
- consume locally produced review sidecars if present
- derive local parameterization from authored structure plus local review judgments
- run local belief propagation
- emit local preview beliefs

`infer` works on a package-local preview, not on the registry's global graph.

### `gaia publish`

Responsibilities:

- submit the package and its deterministic artifacts
- hand off to peer review and registry-side identity assignment
- preserve the distinction between package-local Graph IR and global registry state
- preserve the distinction between base `knowledge` submissions and later `review` / `rebuttal` / `investigation` package profiles

## Recommended Agent Workflow

1. Author or revise package source.
2. Run `gaia build`.
3. Run self-review.
   On `main`, `gaia review` is the current compatibility path for this step.
4. If review finds a missing premise, context, or external reference that should become part of the package, update source explicitly and rebuild.
5. Run graph construction / local canonicalization.
6. Run `gaia infer` for a local belief preview if needed.
7. Run `gaia publish`.

## Relationship To Other Docs

- [../language/gaia-language-spec.md](../language/gaia-language-spec.md) defines source-language boundaries.
- [../graph-ir.md](../graph-ir.md) defines package-local and global Graph IR semantics.
- [../review/publish-pipeline.md](../review/publish-pipeline.md) defines the target self-review / peer review / publish architecture.
- [../server/architecture.md](../server/architecture.md) defines registry-side identity assignment and global inference.
