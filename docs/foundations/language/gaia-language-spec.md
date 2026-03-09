# Gaia Language Spec

## Purpose

This document defines the role of Gaia Language in the overall Gaia system.

It is not the detailed grammar listing. Instead, it defines the semantic and architectural contract that the grammar depends on:

- what Gaia Language is for
- which lifecycle stages it must support
- which responsibilities belong to the language, the local runtime, and the server
- which architectural direction should guide V1

For the detailed language design, see [gaia-language-design.md](gaia-language-design.md).

## Status and Normative Scope

This document is the normative spec for:

- Gaia Language's lifecycle model
- the boundary between source package, local runtime artifacts, and server/LKM integration
- the current V1 package surface on `main`
- language-level conformance rules for well-formed packages
- versioning and extension policy

This document is not the sole source of concrete syntax examples.

- [gaia-language-design.md](gaia-language-design.md) is normative for the current abstract syntax and YAML surface where this document references them.
- [design-rationale.md](design-rationale.md) is explanatory, not normative.
- When surrounding docs give simplified examples, this document and the detailed language design take precedence for the language surface.

## Problem

Gaia Language is currently being asked to serve several different goals at once:

1. agent-verifiable long-term memory
2. formalized scientific knowledge representation
3. a publishable artifact that can replace or complement papers and project summaries
4. a machine-writable language that AI agents can execute and validate
5. an input substrate for the global Large Knowledge Model (LKM)

Those goals are related, but they are not the same layer.

If Gaia Language is treated as only one of the following, the design becomes distorted:

- only a package exchange format
- only an agent execution script
- only a graph ingestion schema
- only a paper-like authoring format

The framework therefore needs explicit layering.

## Design Goals

Gaia Language should support the following product goals:

### 1. Verifiable Agent Memory

Gaia should let agents externalize reasoning into explicit, reviewable artifacts rather than opaque context-window state.

This requires:

- structured knowledge objects
- explicit reasoning steps
- reviewable intermediate conclusions
- local and global belief updates
- traceable provenance

### 2. Formalized Scientific Knowledge

Gaia should represent scientific knowledge in a form that is:

- typed
- modular
- composable
- uncertainty-aware
- stable enough for long-term integration

### 3. Publishable Research Artifact

Gaia packages should be able to act as:

- a research project summary
- a paper replacement or paper companion
- a structured note or knowledge bundle
- a reviewable git artifact

This requires clear package boundaries, stable serialization, and sidecar review artifacts.

### 4. Agent-Friendly Execution

Gaia should be easy for agents to generate, validate, and run locally.

This requires:

- machine-parsable syntax
- deterministic validation
- explicit runtime boundaries
- local execution support for LLM and tool-backed steps

### 5. Clean Path to Global LKM Integration

Gaia packages must eventually map into a global knowledge graph with:

- canonical identity
- provenance tracking
- contradiction and retraction handling
- large-scale belief propagation

## Non-Goals

The language framework should explicitly avoid these confusions:

### 1. Gaia is not the agent's entire workspace

Gaia should not try to store every speculative draft or exploratory branch the agent considers before submission.

Local workspace activity is allowed and necessary, but the published package is the stable artifact, not the full private thought process.

### 2. Gaia is not a general-purpose workflow engine

Gaia may need minimal control-flow constructs for execution, but V1 should not attempt to become a full orchestration language.

### 3. Gaia package names are not global identity

Local names exist for authoring convenience. Canonical identity belongs to publish-time or ingest-time integration, not to initial authorship.

### 4. The published package is not the same thing as the server's canonical graph IR

The package is the authoring and exchange artifact. The server may derive a different internal representation for graph integration and inference.

## Lifecycle Model

Gaia should be designed around three distinct lifecycle stages.

### Stage A: Local Workspace

This is where the agent works locally.

Typical activities:

- read existing packages and claims
- draft new reasoning
- run local tools
- execute local LLM-backed inference steps
- perform dry-run validation
- inspect local belief updates

This stage is exploratory and may contain transient state.

### Stage B: Published Package

This is the stable artifact that enters git, PR review, and long-term sharing.

It should be:

- serializable
- diff-friendly
- reviewable
- readable by humans and agents
- stable enough to serve as a research artifact

This is the primary language exchange surface.

### Stage C: Canonical LKM Integration

This is where published packages are ingested into the global Large Knowledge Model.

Typical activities:

- canonicalize identities
- preserve provenance
- merge equivalent knowledge
- attach contradiction and retraction structure
- run larger-scale BP across packages

This stage belongs primarily to the server or registry layer, not to the authoring surface.

## Layer Model

The framework should separate at least five semantic layers.

### 1. Knowledge Layer

Defines what exists as reusable knowledge.

Examples:

- `claim`
- `question`
- `setting`
- `action`
- `ref`

This layer is the core substrate shared across local runtime and server ingestion.

### 2. Reasoning Layer

Defines how local reasoning is expressed.

Examples:

- `chain_expr`
- named action application
- lambda-like inline reasoning steps

This layer describes a reasoning structure, not yet the full execution plan of a package.

### 3. Control Layer

Defines how multiple reasoning units are scheduled and executed.

Examples:

- package entrypoint
- explicit chain dependencies
- staged execution
- optional future guarded execution

This layer should exist primarily for runtime coordination, not as hidden YAML ordering semantics.

### 4. Probabilistic Layer

Defines uncertainty and inference semantics.

Examples:

- `prior`
- posterior belief
- dependency strength
- factor graph compilation
- belief propagation

### 5. Integration Layer

Defines how a published package enters the global LKM.

Examples:

- canonical identity assignment
- provenance registration
- cross-package linking
- deduplication
- cross-package BP participation

## Artifact Surfaces

Gaia should distinguish four artifact surfaces.

| Surface | Primary user | Purpose | Stability |
|---|---|---|---|
| Local workspace state | agent + local runtime | exploration, dry-run, temporary execution state | low |
| Published package | author, reviewer, agent, git | stable exchange and review artifact | high |
| Review sidecars | reviewer, agent, CI/server | external evaluation of package quality | medium |
| Canonical graph IR | server/LKM runtime | internal integration and large-scale inference | internal |

The published package is the most important author-facing artifact.

## Current V1 Package Surface

The current Gaia Language surface on `main` is file-based YAML, not a single monolithic package blob.

### Package layout

A conforming package on `main` consists of:

- one `package.yaml` manifest at the package root
- one module file `<module>.yaml` for each entry in `package.yaml.modules`
- optional runtime artifacts under `.gaia/`, which are not part of the normative package surface

The current language surface does not require:

- `Gaia.toml`
- `gaia.lock`
- a separate package-management manifest

Those remain deferred package-management concerns rather than part of the current language contract.

### Package manifest surface

`package.yaml` is the normative package manifest on current `main`.

Required fields:

- `name`

Optional fields currently supported on `main`:

- `modules` (defaults to empty; a package with no modules is structurally valid)
- `version`
- `manifest`
- `dependencies`
- `export`

### Module surface

Each module file is a YAML document with:

- required `type`
- required `name`
- optional `declarations` (defaults to empty; a module with no declarations is structurally valid)
- optional `export`

Reasoning is expressed inside `declarations` via `chain_expr`.

Gaia Language does not currently use a top-level module `chains:` key. Any simplified example that suggests otherwise should be treated as explanatory shorthand rather than normative syntax.

### Declaration surface

The current declaration kinds on `main` are:

- `claim`
- `question`
- `setting`
- `infer_action`
- `toolcall_action`
- `chain_expr`
- `ref`

`chain_expr.steps` currently admit exactly three step forms:

- `ref`
- `apply`
- `lambda`

These are the shapes consumed by the current loader and runtime. The loader also accepts declaration types not in this list — unknown types are loaded as generic `Declaration` objects so the LLM runtime can interpret their semantics during build and review.

## Conformance and Well-Formedness

Gaia uses an LLM as its runtime CPU. This means conformance should be **structurally strict but semantically permissive**: the loader enforces file-level and graph-compilation constraints that an LLM cannot self-heal, while semantic interpretation of declaration content and unknown types is intentionally left to the LLM runtime.

### Runtime-enforced conformance on current `main`

A package is ill-formed for the current runtime if any of the following hold:

- `package.yaml` is missing
- a module listed in `package.yaml.modules` does not have a matching `<module>.yaml` file
- a `chain_expr` step is not one of `ref`, `apply`, or `lambda` (these are compiled into a factor graph for BP)
- a `ref.target` cannot be resolved to a non-`ref` declaration using `module_name.declaration_name`

These are structural constraints — they block loading or factor-graph compilation and cannot be recovered by LLM interpretation.

### Semantically permissive by design

The following are intentionally accepted by the current runtime:

- declaration types not in `DECLARATION_TYPE_MAP` — loaded as generic `Declaration` objects and interpreted by the LLM during build/review
- packages with an empty `modules` list
- modules with an empty `declarations` list

This permissiveness is a design choice: since the LLM runtime can understand author intent from content and context, the loader should not reject valid-looking YAML that simply uses unfamiliar type names.

### Recommended lint rules

The following should be treated as language-level quality rules even where the current runtime does not reject them:

- declaration names should be unique within a module
- exported names should refer to declarations that actually exist in the package
- package/module naming should avoid ambiguity between local aliases and resolved targets
- package examples in docs should use the same surface as the real loader
- unknown declaration types should be documented in the module or package manifest when used intentionally

## Operational Semantics Boundary

Gaia Language source files define the package artifact. CLI commands operate on that artifact but also produce non-language runtime outputs.

### `build`

`build` is a normalization and elaboration stage.

It currently:

- loads `package.yaml` and module files
- resolves refs
- elaborates `chain_expr` steps into rendered prompts
- writes per-module Markdown under `.gaia/build/`

It does not make `.gaia/build/` part of the language surface, and it does not define the package's long-term canonical representation.

### `review`

`review` consumes build artifacts and emits sidecar review reports under `.gaia/reviews/`.

Review outputs are runtime artifacts, not source syntax. They must not silently redefine the meaning of the source package.

### `infer`

`infer` compiles a factor graph from the source package plus review sidecars and then runs local belief propagation.

Belief scores are derived runtime outputs. They are semantically downstream of the language, not part of the authored source syntax.

### `publish`

`publish` hands the package to git, local storage backends, or future server integration paths.

Publish-time storage records, canonical IDs, and merged graph state are outside the normative author-facing language surface.

## Versioning and Extension Policy

The current implementation uses a layered language story without an explicit in-file `schema_version` marker.

Current practical rule on `main`:

- V1 core covers the typed declaration system, modules, `ref`, and `chain_expr`
- current optional package metadata (`version`, `manifest`, `dependencies`) live in `package.yaml`
- current optional probabilistic annotations (`prior`, dependency strength, `edge_type`) extend the same YAML surface rather than a separate file format

Deferred items include:

- `Gaia.toml`
- `gaia.lock`
- explicit schema negotiation and migration metadata
- stable backward-compatibility policy across future grammar revisions

Until an explicit schema marker exists, breaking surface changes should be treated as repo-level design changes that require synchronized updates to the spec, examples, and loader/runtime.

## Provenance and Evidence Hooks

Gaia's goals require traceability even before first-class evidence/object kinds are added.

Current rule:

- authored knowledge lives in declarations and `chain_expr`
- review and belief outputs stay in sidecars or runtime outputs
- provenance, citations, and external resources may be attached via declaration `metadata`

Deferred for later language versions:

- first-class `observation`
- first-class `experiment`
- first-class `dataset`
- richer evidence schemas and reproducibility records

## Major Architecture Directions

There are several possible ways to center the Gaia Language design.

### Option 1: Package-First Language

The language is primarily a stable package and publication format.

Pros:

- best fit for paper replacement and project sharing
- easiest to review in git and PRs
- stable exchange format
- clean separation between package content and review sidecars

Cons:

- runtime semantics can become vague
- local agent execution may rely on convention rather than explicit control
- harder to support replay, checkpointing, and local tool orchestration

### Option 2: Runtime-First Language

The language is primarily an executable instruction language for agents.

Pros:

- best fit for local automation
- execution order is explicit
- easier checkpointing, retries, and runtime observability
- natural place for tool calls and LLM-backed steps

Cons:

- publishable artifact becomes process-heavy
- review target becomes "program plus environment plus run result"
- weaker fit for paper-like long-term knowledge sharing

### Option 3: Graph-First Language

The language is primarily a direct authoring surface for the global graph model.

Pros:

- easiest path into server ingestion
- identity and BP semantics are central from the start
- close to current node/hyperedge infrastructure

Cons:

- poor authoring ergonomics
- weak narrative structure
- poor fit for paper replacement
- local reasoning and package modularity are under-expressed

### Option 4: Layered Split

The language framework explicitly separates:

- local runtime execution
- published package representation
- global graph integration

Pros:

- best fit for Gaia's combined goals
- supports agent execution without turning the published artifact into a raw script
- supports paper-like package structure without losing runtime semantics
- keeps the LKM ingest layer clean

Cons:

- highest design complexity
- requires careful boundary definitions

## Recommended Direction

The recommended architecture is Option 4: Layered Split.

The core principle is:

> Gaia's published package is the stable knowledge artifact.
> Gaia's local runtime is the execution environment that helps agents produce and validate that artifact.
> Gaia's server or registry is the integration layer that turns packages into global LKM structure.

This gives Gaia a clean separation of concerns:

### Local Runtime Responsibilities

- load and validate packages
- resolve refs and dependencies
- schedule local execution
- call LLM executors for `infer_action`
- call tool executors for `toolcall_action`
- run local BP
- support dry-run and local inspection

### Published Package Responsibilities

- declare knowledge objects
- declare reasoning structure
- declare package/module boundaries
- expose stable exports
- remain reviewable in git
- remain understandable as a research artifact

### Server / LKM Responsibilities

- canonicalize and merge packages
- attach global identity and provenance
- run large-scale review and inference
- expose global search and integration services

## Recommended Execution Principle

The control layer should be implemented primarily by interpreter software, not by the LLM itself.

The recommended execution split is:

- interpreter software controls package-level flow
- LLM executes local cognitive steps
- tools execute deterministic external actions

In short:

> the LLM should not define the package-level control semantics;
> the LLM should execute the reasoning steps delegated to it by the runtime.

This improves:

- determinism
- replayability
- error handling
- checkpointing
- observability
- cost control

## V1 Scope Recommendation

V1 should stay intentionally narrow.

### What V1 should include

- a stable package artifact
- typed knowledge objects
- explicit modules and exports
- local reasoning via `chain_expr`
- sidecar review artifacts
- local and server validation
- probabilistic annotations and BP compilation

### What V1 should include only in minimal form

- package-level control metadata for local execution

Current status on `main`:

- package-level control metadata is not yet standardized in source YAML
- runtime command staging (`build -> review -> infer -> publish`) exists, but is not itself a language grammar
- future fields such as `entry` or `depends_on` should not be treated as part of the current source surface until they are specified in concrete syntax and supported by the runtime

### What V1 should defer

- general `if / else`
- general loops
- full workflow-engine semantics
- rich theorem-proving or dependent typing
- complete cross-package graph canonicalization in author-facing syntax

## Design Rules for the Detailed Language

The detailed language design should follow these rules.

### 1. Keep the published package as the normative author-facing artifact

This is the main object that should be committed, reviewed, shared, and cited.

### 2. Keep local runtime semantics explicit

If execution order matters, it should be modeled explicitly rather than smuggled in through YAML declaration order.

### 3. Keep narrative order separate from execution order

A package may have:

- reading order
- chain step order
- chain scheduling order
- probabilistic dependency order

These should not be collapsed into one notion of "order".

### 4. Keep local names separate from global identity

Package-local and module-local naming are authoring conveniences. Global identity belongs to integration.

### 5. Keep review separate from content

Review reports should remain sidecar artifacts rather than mutating package content files.

### 6. Keep workspace and published knowledge distinct

The local workspace may be richer, messier, and more executable than the published package.

## Relationship to the Current Language Draft

The current detailed language draft already establishes several important pieces correctly:

- Gaia is treated as a language, not merely an API payload
- the core knowledge object set is small and coherent
- reasoning structure is represented with `chain_expr`
- module types can encode editorial intent such as motivation, setting, reasoning, and follow-up
- probabilistic semantics are recognized as part of the language rather than an afterthought

This spec resolves several framework-level questions for the current draft:

### 1. Package artifact vs runtime artifact

Source YAML is the normative package artifact. `.gaia/` build products, review sidecars, local DB state, and BP results are runtime artifacts layered on top.

### 2. Control layer

`chain_expr` is part of the language. Package-level control metadata remains deferred until concrete syntax and runtime behavior are specified together.

### 3. Package-to-LKM integration

Local names and refs are authoring conveniences. Canonical IDs, cross-package merge policy, and global provenance remain integration-layer concerns.

### 4. Review and publish lifecycle

Review reports remain sidecars, and publish-time integration remains downstream of the source package.

### 5. Scientific evidence modeling

The current type system is intentionally minimal; richer first-class evidence kinds remain future extensions rather than hidden assumptions in V1.

## Practical Guidance

When extending Gaia Language, ask these questions first:

1. Is this feature for local runtime, published package, or global integration?
2. Does this belong in the normative package surface, or only in the interpreter/runtime?
3. Is this defining knowledge structure, execution control, or integration semantics?
4. Does this make the package easier to review and share, or does it merely make local execution easier?
5. Can this be deferred to a later layer without weakening V1?

If those questions are answered explicitly, the detailed language grammar becomes much easier to design coherently.

## Theoretical Foundation

Gaia is a **proof assistant for probabilistic defeasible reasoning** — borrowing Lean's architecture, Bayesian networks' semantics, and belief revision's knowledge model.

The full theoretical analysis is in [design-rationale.md](design-rationale.md). Key findings:

- **InferAction is a Tactic, not a function call.** The LLM constructs reasoning content (untrusted); BP independently computes beliefs from formal structure.
- **Gaia has two kernels.** BP checks structure (graph topology, probabilities). Review checks content (reasoning text quality). Both are required for complete verification.
- **BeliefState is Gaia's ProofState.** Open claims are analogous to Lean's goals (metavariables). Tactics fill holes; InferActions ground claims.
- **Gaia is not "probabilistic Lean."** It takes Lean's architecture but not its type theory. Gaia's knowledge is defeasible (retraction, contradiction); Lean's proofs are permanent.
- **Gaia is the intersection of three traditions:** Lean (architecture), probabilistic graphical models (semantics), and non-monotonic logic (knowledge model).

## Summary

Gaia Language should be treated as a layered language system with three lifecycle stages:

1. local workspace execution
2. published package exchange
3. canonical LKM integration

The published package should remain the central author-facing artifact.

The local runtime should help agents produce and validate that artifact.

The server should integrate that artifact into the global Large Knowledge Model.

That separation is the clearest way to satisfy Gaia's combined goals without forcing one syntax layer to carry every responsibility at once.
