# Gaia CLI Command Lifecycle

## Purpose

This document defines the intended semantic boundary of the four core Gaia CLI commands:

- `gaia build`
- `gaia review`
- `gaia verify`
- `gaia publish`

It answers a product question rather than a grammar question:

> What is the lifecycle of a Gaia package from local research snapshot to published knowledge integrated into the Large Knowledge Model?

This document assumes the higher-level DSL framework from
[../DSL/gaia-dsl-framework.md](../DSL/gaia-dsl-framework.md)
and the CLI layering from
[boundaries.md](boundaries.md).

## Core Judgment

Gaia's primary local workflow should be:

```text
workspace -> build -> review -> verify -> publish
```

Not:

```text
workspace -> build -> run -> review -> publish
```

The reason is architectural:

- Gaia's primary artifact is a reviewable knowledge package, not an executable script
- LLMs should primarily audit and critique reasoning, not define the package-level control semantics
- local execution that exists should serve validation and reproducibility, not become the central user model

Therefore the core command set should be:

1. build the package into a grounded, auditable form
2. review the reasoning quality
3. verify reproducible or executable claims
4. publish the stable package for independent server review and integration

## The Lifecycle

### Stage 0: Private Workspace

Before Gaia CLI commands act on a package, the agent works in a private local workspace.

Typical workspace activity:

- reading papers
- collecting notes
- running exploratory tools
- testing hypotheses
- drafting candidate claims
- writing package snapshots or reports

This workspace is intentionally broader and messier than the published Gaia artifact.

It is not the shared truth surface.

### Stage 1: Draft Package Snapshot

At some point the agent materializes a structured package snapshot.

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

`gaia build` turns the draft package into a grounded, validated, auditable local artifact.

This is the first stage where Gaia CLI should treat the package as structurally meaningful rather than as raw authoring material.

### Stage 3: Reviewed Package

`gaia review` performs model-based critique of the built package.

This stage adds assessment artifacts rather than redefining the package's normative content.

Its outputs should be review sidecars and local audit results.

### Stage 4: Verified Package

`gaia verify` checks reproducible or executable claims whose truth depends on external execution rather than purely textual reasoning review.

This stage adds verification evidence and execution reports.

### Stage 5: Published Package

`gaia publish` sends the stable package to the shared collaboration path:

- git / GitHub
- server-side review
- later ingestion into the LKM

## The Four Commands

## 1. `gaia build`

### Role

`build` is the deterministic normalization boundary.

Its job is to take a package in authoring form and produce a grounded core form suitable for:

- structural inspection
- local BP compilation
- later review
- later publish

### Responsibilities

- schema validation
- local reference resolution
- package consistency checks
- instantiation of statically known parameters
- elaboration of templates or meta-level authoring sugar
- explicit lowering into a grounded local core
- factor graph compilation
- optional local BP precomputation

### What `build` should not do

- perform open-ended LLM reasoning generation
- assign final reasoning quality scores
- replace independent review
- perform authoritative server-side integration
- silently rewrite scientific meaning

### Build output

The result of `build` should be a deterministic artifact or cacheable internal form with these properties:

- no unresolved refs
- no unbound parameters
- no hidden template expansion left unresolved
- explicit reasoning structure
- explicit BP inputs

In effect:

> `build` turns package source into grounded local core.

### Programming language analogy

`gaia build` is closest to:

- elaboration
- grounding
- partial evaluation of statically known structure

It is not primarily analogous to "run the program".

## 2. `gaia review`

### Role

`review` is the model-based audit boundary.

Its job is to critique reasoning quality after the package has already been built into explicit form.

### Responsibilities

- review reasoning edges or chains step by step
- estimate edge reliability or conditional probability
- validate premise/context assignment
- identify hidden premises
- identify weak or invalid reasoning jumps
- produce review reports as sidecar artifacts
- optionally feed local BP with review-derived edge scores

### What `review` should not do

- redefine the package schema
- silently mutate the normative package contents
- act as the final server-controlled publish gate
- replace reproducibility checks for tool-backed claims

### Review output

Review should produce sidecar artifacts such as:

- reasoning scores
- issues
- suggested premise/context adjustments
- abstraction warnings
- local verdict summaries

Review output is an audit of the package, not the package itself.

### Abstraction and review

Abstraction analysis belongs more naturally inside `review` than inside `build`.

Reason:

- abstraction is not purely structural normalization
- abstraction can introduce semantic weakening or generalization
- abstraction therefore requires quality judgment, not just deterministic expansion

Typical review-time abstraction questions:

- are two claims equivalent?
- is one claim a special case of another?
- does a proposed summary over-generalize?
- does a parent claim contain union error?

So the correct relationship is:

> `build` normalizes explicit structure.
> `review` critiques reasoning and abstraction.

## 3. `gaia verify`

### Role

`verify` is the reproducibility and execution boundary.

Its job is to check claims whose trust depends on external execution, replay, or reproducible evidence rather than purely textual reasoning audit.

### Responsibilities

- execute `toolcall_action`-like steps when supported
- replay computational derivations
- rerun scripts, proofs, or deterministic procedures
- check that claimed outputs match observed outputs
- attach verification evidence to the package as sidecars or local reports

### What `verify` should not do

- act as a generic workflow runner
- replace review of natural-language reasoning
- replace publish-time independent server review

### Verification output

Verification should produce explicit evidence artifacts such as:

- pass/fail execution results
- captured outputs
- hashes, metrics, or checkpoints
- environment metadata
- reproducibility notes

### Why `verify` is separate from `review`

Review asks:

- "Is this reasoning step credible?"

Verify asks:

- "If we actually execute or replay this step, does it hold?"

They are complementary but not the same.

## 4. `gaia publish`

### Role

`publish` is the handoff boundary from local package lifecycle to shared package lifecycle.

Its job is to submit a stable package for independent server-side evaluation and possible integration into the LKM.

### Responsibilities

- package the stable local artifact
- push or submit through the supported collaboration path
- preserve sidecar review and verification artifacts as appropriate
- trigger server-side review
- expose publish status to the user or agent

### What `publish` should not do

- trust local review as authoritative
- bypass server-controlled review policy
- directly mutate the global LKM without review

### Server-side follow-up

After publish, the server may:

- rerun review using server-controlled models and prompts
- perform integration-time abstraction analysis
- canonicalize identities
- merge into the global LKM
- run larger-scale BP

That work is downstream of publish, not part of local CLI authority.

## Why There Is No Core `gaia run`

Gaia may still have internal execution steps, but `run` should not be the primary conceptual command.

### Why not

- the package is not primarily an executable script
- the package should be reviewable before any open-ended model execution
- "run" suggests program execution semantics, which is not the main Gaia product surface
- the most important user-visible lifecycle is audit and publication, not free-form execution

### What would be misleading about `run`

If a user sees:

```text
gaia build
gaia run
gaia review
```

the implied model is:

- build the program
- execute the program
- inspect the result

That is too close to notebook or agent-script semantics.

Gaia's intended model is instead:

- structure the knowledge package
- audit the package
- verify reproducible parts
- publish the package

## The Command Contract Table

| Command | Main mode | Determinism | Primary output | Primary question |
|---|---|---|---|---|
| `build` | normalization | deterministic | grounded local core | "Is the package structurally valid and explicit?" |
| `review` | audit | model-dependent | review sidecars and scores | "How credible is the reasoning?" |
| `verify` | reproduction | execution-dependent | verification evidence | "Does the executable/reproducible claim actually hold?" |
| `publish` | handoff | protocol-driven | shared package submission | "Is this package ready for independent shared review?" |

## Recommended Agent Workflow

For the target agentic research use case, the intended flow is:

1. work privately in local workspace
2. periodically write a draft package snapshot or report
3. run `gaia build`
4. run `gaia review`
5. run `gaia verify` for executable or reproducible claims when needed
6. revise the package based on the results
7. repeat until stable
8. run `gaia publish`
9. let server-side review decide whether the package enters the LKM

This preserves the critical boundary:

> Local Gaia helps the agent produce a better package.
> Shared Gaia decides whether that package becomes part of the shared knowledge model.

## Design Implications

The four-command model implies several design rules.

### 1. Package content must be explicit before review

Review should critique an explicit package, not fill in most of its content from scratch.

### 2. Build must be strong enough to remove structural ambiguity

If package meaning depends on unresolved templates, hidden refs, or implicit local ordering, `build` is too weak.

### 3. Review output must remain a sidecar

Review may influence local BP and agent iteration, but it should not silently overwrite package truth.

### 4. Verification must be evidence-producing

`verify` is not just another score. It should leave a reproducible trail.

### 5. Publish must not trust local results blindly

Local build, review, and verify are preparation steps. The shared system still needs independent review authority.

## Relationship to Other Docs

- [boundaries.md](boundaries.md) defines the CLI architectural layering
- [../DSL/gaia-dsl-framework.md](../DSL/gaia-dsl-framework.md) defines Gaia DSL's lifecycle and layer model
- [../shared/knowledge-package-file-formats.md](../shared/knowledge-package-file-formats.md) defines package and review sidecar exchange formats

## Summary

Gaia CLI should center on four commands:

- `build`
- `review`
- `verify`
- `publish`

Together they define a package lifecycle oriented around:

- normalization
- audit
- reproducibility
- shared publication

That lifecycle matches Gaia's role as a system for verifiable research packages and long-term knowledge integration better than a script-first `run` model.
