# Gaia CLI Command Lifecycle

> **Status: Partially implemented.** `build`, `review`, `publish` are shipped (PR #63). `infer` was added during implementation (not in original RFC) and is also shipped. `verify` remains future. `clean`, `init`, `show`, `search` are shipped utility commands not covered by this lifecycle doc.

## Purpose

This document defines the intended semantic boundary of the core Gaia CLI lifecycle commands:

- `gaia build` — shipped
- `gaia review` — shipped
- `gaia infer` — shipped (added during implementation, not in original RFC)
- `gaia verify` — future
- `gaia publish` — shipped

It answers a product question rather than a grammar question:

> What is the lifecycle of a Gaia package from local research snapshot to published knowledge integrated into the Large Knowledge Model?

This document assumes the higher-level language spec from
[../language/gaia-language-spec.md](../language/gaia-language-spec.md)
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
3. infer beliefs via local belief propagation
4. verify reproducible or executable claims (future)
5. publish the stable package for independent server review and integration

> **Implementation note — `infer` vs `verify`:** `infer` computes beliefs from the package's factor graph structure using loopy belief propagation. It is a deterministic computation over the graph. `verify` (future) would check claims via external execution or replay — e.g., rerunning a computation to confirm its output. They are complementary: `infer` answers "what should we believe given the reasoning structure?", `verify` answers "does this executable claim actually hold?"

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

### Stage 3.5: Inferred Package

`gaia infer` compiles the factor graph from build/review outputs and runs local belief propagation to compute self-consistent belief scores across all declarations.

This stage is shipped. It sits between review and verify in the lifecycle.

### Stage 4: Verified Package

> **Not yet implemented.** Local belief propagation is handled by `gaia infer`. `gaia verify` remains a future command for external execution checks.

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
- per-module Markdown output for downstream review

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

| Command | Main mode | Determinism | Primary output | Primary question | Status |
|---|---|---|---|---|---|
| `build` | normalization | deterministic | grounded local core | "Is the package structurally valid and explicit?" | shipped |
| `review` | audit | model-dependent | review sidecars and scores | "How credible is the reasoning?" | shipped |
| `infer` | belief propagation | deterministic | belief scores on declarations | "What should we believe given the reasoning structure?" | shipped |
| `verify` | reproduction | execution-dependent | verification evidence | "Does the executable/reproducible claim actually hold?" | future |
| `publish` | handoff | protocol-driven | shared package submission | "Is this package ready for independent shared review?" | shipped |

## Recommended Agent Workflow

For the target agentic research use case, the current shipped flow is:

1. work privately in local workspace
2. author YAML modules (declarations + chains)
3. run `gaia build` — structural validation, ref resolution, per-module Markdown
4. run `gaia review` — LLM critique of reasoning chains
5. run `gaia infer` — local belief propagation over the factor graph
6. revise the package based on the results
7. repeat until stable
8. run `gaia publish` — publish to git or local databases
9. let server-side review decide whether the package enters the LKM

> **Note:** `gaia verify` (future) would be an optional step between `infer` and `publish` for executable/reproducible claims. The current flow is `build → review → infer → publish`.

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
- [../language/gaia-language-spec.md](../language/gaia-language-spec.md) defines Gaia Language's lifecycle and layer model
- Package and review sidecar exchange formats (planned, not yet documented)

## Summary

Gaia CLI should center on five lifecycle commands:

- `build` — shipped
- `review` — shipped
- `infer` — shipped
- `verify` — future
- `publish` — shipped

Together they define a package lifecycle oriented around:

- normalization
- audit
- reproducibility
- shared publication

That lifecycle matches Gaia's role as a system for verifiable research packages and long-term knowledge integration better than a script-first `run` model.
