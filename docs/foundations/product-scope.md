# Gaia Product Scope

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
| **V1 — Deterministic FP core** | Closures (values), inferences (lambdas), chains (composition), modules (with imports/exports), packages | Haskell, OCaml |
| **V3 — Probabilistic layer** | Priors, dependency strength (conditioning), belief propagation (inference) | Church's `flip`/`observe`, Hakaru's `measure` monad, Pyro's `sample`/`observe` |

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
| Probability of what | Random variables (numerical) | Propositions (knowledge closures) |
| Probability means | Frequency / measure over outcomes | Degree of belief in truth |
| Conditioning on | Observed data | Dependency strength (strong/weak) |
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

1. **Functional knowledge structure** (V1) — closures, inferences, chains, modules, packages — a typed, composable knowledge representation inspired by Haskell/OCaml module systems
2. **Epistemic probabilistic reasoning** (V3) — priors, beliefs, dependency strength, contradiction/retraction semantics — grounded in Jaynes' probability-as-logic tradition
3. **Hypergraph belief propagation** — loopy BP on factor graphs derived from the knowledge package structure, computing self-consistent beliefs across the entire LKM

This combination enables the core product: **AI agents write knowledge packages (probabilistic programs), the cloud runs belief propagation (posterior inference), and the result is a Large Knowledge Model where every proposition carries a calibrated degree of belief.**

## Product Direction (Decided)

Gaia is **CLI-first, Server-enhanced**.

- **CLI is the primary product** — AI agents and researchers interact with Gaia through the CLI, working locally with zero server dependency
- **Server provides four optional enhancement services:**
  1. Knowledge integration — merge packages into the global Large Knowledge Model
  2. Global search — cross-package vector + BM25 + topology search
  3. Package preparation and review — server-side compile, package-environment construction, alignment, and review
  4. Large-scale BP — billion-node belief propagation on GPU cluster

The primary interaction path is: **CLI → git push → PR → Server webhook → auto compile/context/alignment/review → merge/reject** (similar to Julia Pkg Registry).

Users can work entirely offline with the CLI. The server is an optional registry and compute backend, not a prerequisite.

## Current Baseline on `main`

What is currently shipped on `main`:

- a backend reasoning-graph service (FastAPI) — this is the server side
- a dashboard frontend for browsing, graph exploration, and commit workflows
- GraphStore ABC with Neo4j and Kuzu implementations
- type-aware belief propagation (contradiction, retraction edges)
- **CLI with 8 commands** (`init`, `build`, `review`, `infer`, `publish`, `show`, `search`, `clean`) — shipped in PR #63
- **Gaia Language** — per-module YAML with knowledge objects, chains, and strong/weak references
- **Inference engine moved to `libs/inference/`** — local belief propagation decoupled from server
- **Build output** — per-module Markdown for LLM review

What is not yet shipped but is on the roadmap:

- target build pipeline expansion (`gaia build compile|context|align`)
- `gaia publish --server` (direct server publish without git)
- GitHub webhook integration for server-side compile/context/alignment/review
- cross-package dependency resolution and `gaia.lock`
- shared knowledge-package contracts (being standardized in this foundation work)

## Current Supported Product Surfaces

### 1. HTTP server

The currently shipped server surface is the FastAPI service exposed from `services/gateway/`.

Current API areas:

- commit submission, review, merge, and retrieval
- read APIs for nodes, hyperedges, contradictions, subgraphs, and stats
- search APIs for nodes and hyperedges
- batch APIs for commit, read, subgraph, and search flows
- job APIs for async status and result retrieval

This is the main externally addressable surface today. Under CLI-first positioning, the server becomes a registry and compute backend that the CLI publishes to.

### 2. Dashboard frontend

The current frontend product is the React dashboard in `frontend/`.

Current UI surfaces include:

- dashboard landing page
- data browser
- graph explorer
- node and edge detail pages
- commit panel

The frontend should be treated as a client of the current server API, not as an independent product line with separate domain contracts.

### 3. Server-side graph and storage runtime

Gaia currently ships a server-side storage/runtime stack with:

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

### 4. Local developer workflow

Gaia currently supports a local development workflow based on:

- editable Python install
- seeded local databases
- running the FastAPI server
- running the Vite frontend
- running the test suite

This is a development and validation workflow, not the same thing as a formal end-user local product experience.

## Explicitly Not In Current Product Scope

The following should not be described as current Gaia product capability on `main` unless they are actually merged and documented separately.

### 1. CLI/package-manager product — NOW SHIPPED (PR #63)

The CLI is shipped on `main` with 8 commands:

| Command | Purpose |
|---------|---------|
| `gaia init` | Initialize a knowledge package |
| `gaia build` | Parse YAML, resolve refs, elaborate templates → per-module Markdown |
| `gaia review` | LLM review of chains → YAML sidecar reports |
| `gaia infer` | Compile factor graph + run local belief propagation |
| `gaia publish` | Publish to git or local databases (LanceDB + Kuzu) |
| `gaia show` | Display knowledge object details + connected chains |
| `gaia search` | Search published nodes in local LanceDB |
| `gaia clean` | Remove build artifacts (`.gaia/` directory) |

Note: the original RFC included `gaia claim` — this was replaced by declarative YAML authoring (per-module YAML files with knowledge objects and chains). `gaia.lock` and cross-package dependency resolution remain deferred.

Still not shipped:

- target build pipeline expansion (`gaia build compile|context|align`)
- `gaia publish --server` (direct server publish)
- GitHub webhook integration
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

Gaia is a **CLI-first, Server-enhanced** Large Knowledge Model platform.

- **CLI** — the primary product surface for creating, building, reviewing, and publishing knowledge packages
- **Server** — an optional registry that provides knowledge integration, global search, package preparation/alignment/review, and large-scale BP
- **Dashboard** — a browser UI for exploring the server-side knowledge graph

The current `main` ships the server, dashboard, and CLI.

## Implications For Future Work

Large new work should be framed in one of these ways:

1. build out the CLI product surface (the primary product)
2. extend the server as a registry and compute backend for the CLI
3. tighten shared foundations that both CLI and server depend on

That means:

- shared contracts (knowledge package schema, domain vocabulary) are the highest priority foundation work
- CLI architecture should drive design decisions, not be an afterthought
- server work should focus on the four enhancement services, not on being the sole product surface

## PR And Documentation Rules

When writing docs or reviewing PRs:

1. If the feature is part of the current product baseline, it can be described as current behavior.
2. If it is implemented in code but not yet fully specified as product contract, call out the limitation explicitly.
3. If it is only planned, label it as proposal, roadmap, or future work.
4. Do not let design docs silently redefine the current product baseline.

## Decided Questions

These have been resolved and should not be reopened:

1. **CLI-first or server-first?** → CLI-first, Server-enhanced.
2. **Primary interaction path?** → CLI → git push → PR → Server webhook → auto compile/context/alignment/review → merge/reject.
3. **Kuzu role?** → CLI's embedded graph backend (local, zero-config). Neo4j is the server-side backend.

## Open Product Decisions

These remain open for later foundation phases:

1. Should degraded graph-free operation be part of the supported product story, or only an internal fallback mode?
2. What is the direct publish (`gaia publish --server`) contract? (deferred)
