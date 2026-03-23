# Gaia Product Scope

> **Status: Transitional.** This file remains useful as a product-direction narrative, but the newer foundation split is now:
>
> - [`foundation/gaia-overview.md`](foundation/gaia-overview.md)
> - [`foundation/scientific-reasoning-foundation.md`](foundation/scientific-reasoning-foundation.md)
> - [`semantics/terminology.md`](semantics/terminology.md)
>
> This older document still carries legacy wording such as "probabilistic functional programming language" and some older cloud-centric framing. Prefer the newer foundation docs for current canonical positioning.

## Purpose

This document defines Gaia's product positioning, theoretical foundation, and current baseline on `main`.

Its job is:

- state the theoretical foundation — why Gaia exists and why existing tools cannot replace it
- state the decided product direction
- state what is currently shipped on `main`
- state what is not yet shipped but is on the roadmap

## Theoretical Foundation

### The goal: a Large Knowledge Model

Gaia's goal is to build a **Large Knowledge Model (LKM)** — a billion-scale reasoning hypergraph where propositions are nodes and reasoning relationships are hyperedges. The LKM is constructed automatically by AI agents on the cloud, not manually by humans.

This requires a **machine-readable, machine-writable knowledge representation** that supports:

1. **Structured reasoning** — not free-text, but typed knowledge objects (claims, questions, settings, actions) connected by explicit inference steps
2. **Probabilistic belief** — knowledge is not true/false but carries degrees of belief, because scientific knowledge is inherently uncertain
3. **Composable modules** — knowledge must be packaged, exported, imported, and composed, like code in a programming language
4. **Automated inference** — the system must propagate beliefs through the graph automatically when new evidence arrives

These requirements together define a programming language. Gaia is that language.

### Gaia as a probabilistic functional programming language

Gaia is a **probabilistic functional programming language** specialized for knowledge representation and epistemic inference.

It follows the standard architecture of probabilistic PLs: a **deterministic host language** with a **probabilistic layer** on top.

| Layer | What it provides | PL analogy |
|-------|-----------------|------------|
| **V1 — Deterministic FP core** | Knowledge (values), inferences (lambdas), chains (composition), modules (with imports/exports), packages | Haskell, OCaml |
| **V3 — Probabilistic layer** | Priors, dependency roles (`direct`/`indirect` surface syntax; `premise`/`context` semantics), belief propagation (inference) | Church's `flip`/`observe`, Hakaru's `measure` monad, Pyro's `sample`/`observe` |

The theoretical positioning:

- **Pólya** (*Mathematics and Plausible Reasoning*, 1954) — reasoning extends beyond deductive proof to plausible inference
- **Jaynes** (*Probability Theory: The Logic of Science*, 2003) — probability is the logic of plausible reasoning, a generalization of deductive logic to degrees of belief
- **Cox's theorem** — any consistent system of plausible reasoning is isomorphic to probability theory

Gaia aspires to be **Curry-Howard for plausible reasoning**: just as functional programming languages (Haskell, Lean) are grounded in the Curry-Howard correspondence between proofs and programs, Gaia extends this from deductive certainty to plausible belief. This is an open research direction, not an established theorem — the full Curry-Howard correspondence for probabilistic computation remains an active area of study (cf. "Curry and Howard Meet Borel", LICS 2022).

### Why existing tools cannot replace Gaia

**Why not existing probabilistic PLs (Pyro, Stan, Church, Hakaru)?**

These languages model **statistical probability** — distributions over random variables for data modeling. Gaia models **epistemic probability** — degrees of belief in the truth of propositions.

| | Statistical probability (Pyro/Stan) | Epistemic probability (Gaia) |
|---|---|---|
| Probability of what | Random variables (numerical) | Propositions (knowledge objects) |
| Probability means | Frequency / measure over outcomes | Degree of belief in truth |
| Conditioning on | Observed data | Dependency role (`direct` / `indirect`; semantics `premise` / `context`) |
| Graph model | DAG (Bayesian network) | Hypergraph (multi-premise → multi-conclusion) |
| Inference computes | Posterior distribution | Belief scores on propositions |
| Inference algorithm | MCMC, variational inference | Loopy BP on hypergraphs |

The mathematical foundation is the same (Bayesian probability), but the domain structure is fundamentally different — like SQL and Haskell both being grounded in set theory, but SQL exists because relational data needs its own language.

**Why not existing FP languages (Haskell, OCaml)?**

These provide the deductive logic layer but have no built-in probabilistic reasoning. You could build Gaia on top of Haskell, but you would need to add the entire probabilistic layer (priors, belief propagation, conditioning semantics, hypergraph inference) — at which point you have built a new language.

**Why not existing knowledge graphs (Neo4j, OWL, RDF)?**

These provide graph storage and deterministic querying, but have no probabilistic inference. They can tell you "A is connected to B" but not "how much should you believe B given evidence for A?" Gaia uses graph databases (Neo4j, Kuzu) as storage backends, but the knowledge representation and inference layers are what make Gaia a language, not just a database.

### Gaia's unique combination

Gaia combines three capabilities that no existing tool provides together:

1. **Functional knowledge structure** (V1) — knowledge objects, inferences, chains, modules, packages — a typed, composable knowledge representation inspired by Haskell/OCaml module systems
2. **Epistemic probabilistic reasoning** (V3) — priors, beliefs, dependency roles, contradiction/retraction semantics — grounded in Jaynes' probability-as-logic tradition
3. **Hypergraph belief propagation** — loopy BP on factor graphs derived from the knowledge package structure, computing self-consistent beliefs across the entire LKM

This combination enables the core product: **AI agents write knowledge packages (probabilistic programs), the cloud runs belief propagation (posterior inference), and the result is a Large Knowledge Model where every proposition carries a calibrated degree of belief.**

## Product Direction (Decided)

Gaia is **CLI-first, Server-enhanced**.

- **CLI is the primary product** — AI agents and researchers interact with Gaia through the CLI, working locally with zero server dependency
- **The target local pipeline** is `build -> self-review skill -> graph-construction skill -> infer -> publish`
- **Server provides four optional enhancement services:**
  1. Knowledge integration — merge approved packages into the global Large Knowledge Model
  2. Global search — cross-package vector + BM25 + topology search
  3. Peer review and registry integration — independent review, editorial decisions, identity assignment
  4. Large-scale BP — billion-node belief propagation on GPU cluster

The target shared interaction path is: **CLI → git push / publish → peer review → rebuttal / editor cycle → merge or reject** (similar to an academic publishing workflow).

Users can work entirely offline with the CLI. The server is an optional registry and compute backend, not a prerequisite.

## Current Baseline on `main`

What is currently shipped on `main`:

- a Typst-based Gaia CLI surface
- reusable pipeline functions for build, review, infer, and publish
- storage abstractions with LanceDB-backed content storage and optional graph backends
- local publish into storage-backed runtime state
- local factor-graph belief propagation in `libs/inference/`
- offline curation modules in `libs/curation/`
- build output under `.gaia/`, including graph artifacts and rendered review-oriented outputs

What is **not** currently shipped as a stable product surface on `main`:

- a standalone `gaia review` command in the main CLI entrypoint
- a stable external FastAPI-style LKM API surface in this repository
- `gaia publish --server`
- a complete end-to-end peer-review / rebuttal / editor loop

What is not yet shipped but is on the roadmap:

- `gaia publish --server` (direct server publish without git)
- GitHub webhook integration for publish-time peer review
- rebuttal / editor publish cycle
- registry-side `CanonicalBinding` + `GlobalInferenceState` end-to-end flow
- cross-package dependency resolution and `gaia.lock`
- shared knowledge-package contracts (being standardized in this foundation work)

## Current Supported Product Surfaces

### 1. Local CLI surface

The current shipped end-user surface is primarily the CLI in [`cli/main.py`](../../cli/main.py), including:

- `gaia init`
- `gaia build`
- `gaia infer`
- `gaia publish`
- `gaia search`
- `gaia clean`

This is the clearest current product surface.

### 2. Shared-side storage and graph runtime

Gaia currently ships a shared-side storage/runtime stack with:

- LanceDB for node content and metadata
- a vector search layer with a local LanceDB-backed implementation
- a graph backend abstraction (`GraphStore`)
- Neo4j and Kuzu graph backend implementations

Current backend modes on `main`:

- `graph_backend="neo4j"`: default server-oriented graph backend
- `graph_backend="kuzu"`: embedded graph backend available in current code
- `graph_backend="none"`: degraded mode for cases where graph operations are unavailable

Important boundary:

The existence of multiple graph backends in code does not yet mean Gaia has a fully specified product contract for backend parity. The capability matrix still needs to be documented explicitly.

### 3. Local developer workflow

Gaia currently supports a local development workflow based on:

- editable Python install
- seeded local databases
- running the FastAPI server
- running the Vite frontend
- running the test suite

This is a development and validation workflow, not the same thing as a formal end-user local product experience.

## Explicitly Not In Current Product Scope

The following should not be described as current Gaia product capability on `main` unless they are actually merged and documented separately.

### 1. CLI/package-manager product

The CLI is shipped on `main` with these primary commands:

| Command | Purpose |
|---------|---------|
| `gaia init` | Initialize a Typst knowledge package |
| `gaia build` | Build package-local Graph IR and related `.gaia/` artifacts |
| `gaia infer` | Derive local preview review inputs and run local belief propagation |
| `gaia publish` | Publish to git or local databases (LanceDB + Kuzu) |
| `gaia search` | Search published knowledge in local storage |
| `gaia clean` | Remove build artifacts (`.gaia/` directory) |

The canonical CLI lifecycle is now documented as `build -> infer -> publish`. Older docs that speak about a shipped `gaia review` command should be read as migration-era workflow framing rather than literal current CLI surface.

Still not shipped:

- `gaia publish --server` (direct server publish)
- GitHub webhook integration
- publish-time peer review / rebuttal / editor loop
- `gaia.lock` / cross-package dependency resolution

### 2. Production ByteHouse-backed deployment

The config still contains ByteHouse-oriented fields, but ByteHouse is not a fully implemented current product storage path.

Until that changes, ByteHouse should be treated as planned or reserved, not supported current deployment.

### 3. Fully specified backend interchangeability

Gaia now has more than one graph backend implementation, but it does not yet have a fully documented, stable product-level guarantee that every backend supports every graph-dependent feature identically.

Until a capability matrix exists, claims about backend parity should be avoided.

### 4. GitHub-native review/publish ecosystem

Gaia does not currently ship a complete product story for:

- GitHub bot review
- PR-native reasoning package validation
- federated or community review workflows
- publish-to-Git as a supported end-user path

These remain design directions, not current baseline capability.

## Product Positioning Summary

Gaia is a **Gaia CLI + Gaia LKM** system.

- **Gaia CLI** — the primary local product surface for authoring, building, previewing, and publishing Gaia packages
- **Gaia LKM** — the shared-side knowledge core that owns intake, review, integration, curation, and shared inference concerns
- **Gaia Cloud** — a deployment or product alias for LKM-side capabilities, not a separate foundation-level concept

Current `main` most clearly ships:

- the CLI
- reusable shared-side library/runtime pieces
- storage-backed local and shared-state execution components

It does **not** yet ship a fully stabilized external LKM product shell with fixed API, review marketplace, and browser product surface all frozen as contract.

## Implications For Future Work

Large new work should be framed in one of these ways:

1. build out the CLI product surface (the primary product)
2. extend Gaia LKM as the shared registry and compute side
3. tighten shared foundations that both CLI and LKM depend on

That means:

- shared contracts (knowledge package schema, domain vocabulary) are the highest priority foundation work
- CLI architecture should drive design decisions, not be an afterthought
- shared-side work should focus on LKM capabilities and explicit service boundaries, not on vague "server-first" positioning

## PR And Documentation Rules

When writing docs or reviewing PRs:

1. If the feature is part of the current product baseline, it can be described as current behavior.
2. If it is implemented in code but not yet fully specified as product contract, call out the limitation explicitly.
3. If it is only planned, label it as proposal, roadmap, or future work.
4. Do not let design docs silently redefine the current product baseline.

## Decided Questions

These have been resolved and should not be reopened:

1. **Primary top-level split?** → `Gaia CLI` and `Gaia LKM`.
2. **Canonical local lifecycle?** → `build -> infer -> publish`.
3. **Shared-side review location?** → review belongs to Gaia LKM, not to the canonical CLI lifecycle.

## Open Product Decisions

These remain open for later foundation phases:

1. Should degraded graph-free operation be part of the supported product story, or only an internal fallback mode?
2. What exact stable external LKM API should exist, if any, in this repository?
