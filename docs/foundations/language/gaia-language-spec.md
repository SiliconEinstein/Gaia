# Gaia Language Spec

## Purpose

This document defines the role of Gaia Language in the overall Gaia system.

It is not the detailed grammar spec. Instead, it answers the higher-level questions that the grammar depends on:

- what Gaia Language is for
- which lifecycle stages it must support
- which responsibilities belong to the language, the local runtime, and the server
- which architectural direction should guide V1

For the detailed language design, see [gaia-language-design.md](gaia-language-design.md).

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

- control layer metadata for local execution

Examples of minimal acceptable V1 control:

- `entry`
- `depends_on`
- explicit staged execution metadata

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

However, the current draft still needs framework-level clarification in these areas:

### 1. Package artifact vs runtime artifact

The current draft mixes a publishable package surface with an executable local runtime surface, but the boundary is not yet explicit.

### 2. Control layer

The draft defines `chain_expr`, but package-level execution semantics are still underspecified.

### 3. Package-to-LKM integration

The draft defines local names and refs, but not yet the full canonicalization path into the global LKM.

### 4. Review and publish lifecycle

The draft focuses on language structure, but Gaia's product flow also depends on git, PR review, sidecar reports, and publish-time integration.

### 5. Scientific evidence modeling

The current type system is a good kernel, but scientific knowledge may later need richer first-class forms such as observations, experiments, datasets, or protocol-like resources.

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
