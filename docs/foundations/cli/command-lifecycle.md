# Gaia CLI Command Lifecycle

> **Status: Partially implemented.** `build`, `review`, `publish` are shipped (PR #63). `infer` was added during implementation and is also shipped. The target `build compile/context/align` subcommands are not yet implemented. Current shipped `build` is still closer to the old deterministic compile/elaboration step. This document defines the target lifecycle.

## Purpose

This document defines the intended semantic boundary of the core Gaia CLI lifecycle commands:

- `gaia build` — shipped, target semantics expanding
- `gaia review` — shipped, target semantics expanding
- `gaia infer` — shipped
- `gaia verify` — future
- `gaia publish` — shipped

It answers a product question rather than a grammar question:

> What is the lifecycle of a Gaia package from local research snapshot to published knowledge integrated into the Large Knowledge Model?

This document assumes the higher-level language spec from
[../language/gaia-language-spec.md](../language/gaia-language-spec.md)
and the build/review architecture from
[../review/architecture.md](../review/architecture.md).

## Core Judgment

Gaia's target local workflow should be:

```text
workspace -> build -> review -> infer -> verify -> publish
```

Where `build` is itself a shortcut over:

```text
compile -> context -> align
```

The advanced equivalent is:

```text
workspace -> build compile -> build context -> build align -> review -> infer -> verify -> publish
```

Not:

```text
workspace -> build -> run -> review -> publish
```

The reason is architectural:

- Gaia's primary artifact is a reviewable knowledge package, not an executable script
- local preparation should make package structure and context explicit before final judgment
- model-based review should happen after context has been gathered and aligned
- local execution that exists should serve reproducibility or inference, not become the central user model

## The Lifecycle

### Stage 0: Private Workspace

Before Gaia CLI commands act on a package, the author works in a private local workspace.

Typical workspace activity:

- reading papers
- collecting notes
- running exploratory tools
- testing hypotheses
- drafting candidate claims
- writing package snapshots or reports

This workspace is intentionally broader and messier than the published Gaia artifact.

### Stage 1: Draft Package Snapshot

At some point the author materializes a structured package snapshot.

That snapshot should already contain explicit package content:

- claims
- settings
- questions
- actions
- refs
- reasoning structure
- provenance or resource references

This draft package is the input to `gaia build`.

### Stage 2: Built Package

`gaia build` prepares the package for downstream judgment.

In the target architecture it is a shortcut for:

1. `gaia build compile`
2. `gaia build context`
3. `gaia build align`

The result is a prepared package with:

- compiled deterministic artifacts
- a package environment
- alignment sidecars

### Stage 3: Reviewed Package

`gaia review` performs the final package assessment after build has already prepared:

- compiled artifacts
- the package environment
- alignment results

This stage adds review artifacts rather than redefining the package's normative content.

### Stage 4: Inferred Package

`gaia infer` compiles the factor graph from build and review outputs and runs local belief propagation.

If a package environment is available, inference may use it for a more accurate local preview.

### Stage 5: Verified Package

> **Not yet implemented.** `gaia verify` remains a future command for external execution checks.

`gaia verify` checks reproducible or executable claims whose truth depends on external execution rather than textual reasoning or BP alone.

### Stage 6: Published Package

`gaia publish` sends the stable package to the shared collaboration path:

- git / GitHub
- later server-side compile, context construction, alignment, and review
- later ingestion into the LKM

## The Core Commands

## 1. `gaia build`

### Role

`build` is the local preparation boundary.

Its job is to turn package source into a prepared local artifact suitable for:

- structural inspection
- context gathering
- open-world alignment
- later review
- later inference
- later publish

### Build shortcut semantics

The target shortcut is:

```text
gaia build == gaia build compile -> gaia build context -> gaia build align
```

### Build subcommands

#### `gaia build compile`

Deterministic, fast, and non-LLM.

Responsibilities:

- schema validation
- elaboration
- local ref resolution
- deterministic lowering into explicit internal form

#### `gaia build context`

Retrieves candidate external context and materializes the package environment.

Responsibilities:

- choose context source: `local`, `remote`, or `both`
- retrieve semantic candidates
- expand structural context
- materialize the package environment
- update environment lock metadata

Flag intent:

- `--frozen` reuses the currently locked package environment and fails if the required lock/runtime artifacts are missing
- `--refresh` ignores the currently locked package environment and rebuilds context from the selected source

#### `gaia build align`

Runs open-world relation discovery over the compiled package plus package environment.

Responsibilities:

- cluster retrieved candidates
- discover duplicate / equivalence / contradiction / subsumption candidates
- verify and filter alignment findings
- write alignment sidecars

### What `build` should not do

- produce the final package judgment
- compute belief propagation
- silently rewrite scientific meaning
- directly mutate the shared knowledge model

## 2. `gaia review`

### Role

`review` is the final package assessment boundary.

Its job is to judge the package after build has already prepared:

- deterministic compiled artifacts
- package environment
- alignment findings

### Responsibilities

- assess reasoning quality in context
- judge whether discovered external relations are acceptable
- identify unresolved conflicts, overlaps, or weak justifications
- issue readiness judgments for infer/publish
- write review sidecars

### What `review` should not do

- gather context itself
- perform open-world candidate retrieval
- perform alignment clustering itself
- compute belief propagation
- silently mutate package source

### Review output

Review output is an assessment of the package in context, not the package itself.

## 3. `gaia infer`

### Role

`infer` is the belief-propagation boundary.

Its job is to compute beliefs from the package's graph structure using available build and review artifacts.

### Responsibilities

- compile the local factor graph
- consume build outputs and review outputs
- optionally incorporate package-environment context
- compute local beliefs

### What `infer` should not do

- gather external context
- make the final package judgment
- replace reproducibility checks

## 4. `gaia verify`

### Role

`verify` is the reproducibility and execution boundary.

Its job is to check claims whose trust depends on external execution, replay, or reproducible evidence.

Typical responsibilities:

- execute tool-backed or replayable steps when supported
- rerun computations or deterministic procedures behind executable claims
- capture verification evidence, outputs, and environment metadata as sidecars

`verify` remains distinct from `review`:

- `review` judges reasoning quality and package readiness
- `verify` checks whether executable or reproducible claims actually hold

## 5. `gaia publish`

### Role

`publish` is the handoff boundary from local package lifecycle to shared package lifecycle.

Its job is to submit a stable package for independent server-side evaluation and possible integration into the LKM.

### Server-side follow-up

After publish, the server may:

- recompile the package under managed policy
- rebuild context against current shared state
- realign the package against that context
- review the package in aligned context
- canonicalize identities
- merge into the global LKM
- run larger-scale BP

That work is downstream of publish, not part of local CLI authority.

## Why There Is No Core `gaia run`

Gaia may still have internal execution steps, but `run` should not be the primary conceptual command.

The intended model is:

- structure and prepare the package
- review it in context
- infer beliefs
- verify reproducible parts
- publish the package

## The Command Contract Table

| Command | Main mode | Determinism | Primary output | Primary question | Status |
|---|---|---|---|---|---|
| `build` | preparation shortcut | mixed | compiled package + environment + alignment artifacts | "Is the package prepared for final review?" | shipped, target semantics expanding |
| `review` | contextual package assessment | model-dependent | review sidecars and readiness judgments | "Given the prepared context, how credible and ready is this package?" | shipped, target semantics expanding |
| `infer` | belief propagation | deterministic | belief scores on declarations | "What should we believe given the package plus available context?" | shipped |
| `verify` | reproduction | execution-dependent | verification evidence | "Does the executable/reproducible claim actually hold?" | future |
| `publish` | handoff | protocol-driven | shared package submission | "Is this package ready for independent shared evaluation?" | shipped |

## Recommended Agent Workflow

The target local workflow is:

1. work privately in local workspace
2. author YAML modules
3. run `gaia build`
4. run `gaia review`
5. run `gaia infer`
6. revise the package based on the results
7. repeat until stable
8. run `gaia publish`
9. let server-side compile/context/alignment/review/integration decide whether the package enters the LKM

Advanced equivalent:

1. run `gaia build compile`
2. run `gaia build context --source local|remote|both`
3. run `gaia build align`
4. run `gaia review`
5. run `gaia infer`

## Design Implications

### 1. Build must own package preparation

Deterministic compile, context gathering, and alignment belong to build, not to final review.

### 2. Review must happen after build

Final package judgment should consume the current environment and alignment findings, not run before they exist.

### 3. Review output must remain a sidecar

Review may influence local inference and agent iteration, but it should not silently overwrite package truth.

### 4. Verification must be evidence-producing

`verify` is not just another score. It should leave a reproducible trail.

### 5. Publish must not trust local results blindly

Local build, review, infer, and verify are preparation steps. The shared system still needs independent authority.

## Relationship to Other Docs

- [../review/architecture.md](../review/architecture.md) defines the target build/context/alignment/review architecture
- [boundaries.md](boundaries.md) defines the CLI architectural layering
- [../language/gaia-language-spec.md](../language/gaia-language-spec.md) defines Gaia Language's lifecycle and layer model

## Summary

Gaia CLI should center on five lifecycle commands:

- `build`
- `review`
- `infer`
- `verify`
- `publish`

And `build` should internally decompose into:

- `build compile`
- `build context`
- `build align`

That gives Gaia a package lifecycle oriented around:

- deterministic preparation
- context gathering
- alignment
- contextual review
- local belief propagation
- reproducibility
- shared publication
