# Gaia Product Scope

## Purpose

This document defines Gaia's product positioning and current baseline on `main`.

Its job is simple:

- state the decided product direction
- state what is currently shipped on `main`
- state what is not yet shipped but is on the roadmap

## Product Direction (Decided)

Gaia is **CLI-first, Server-enhanced**.

- **CLI is the primary product** — AI agents and researchers interact with Gaia through the CLI, working locally with zero server dependency
- **Server provides four optional enhancement services:**
  1. Knowledge integration — merge packages into the global Large Knowledge Model
  2. Global search — cross-package vector + BM25 + topology search
  3. LLM Review Engine — server-side automated review triggered by webhook
  4. Large-scale BP — billion-node belief propagation on GPU cluster

The primary interaction path is: **CLI → git push → PR → Server webhook → auto review → merge/reject** (similar to Julia Pkg Registry).

Users can work entirely offline with the CLI. The server is an optional registry and compute backend, not a prerequisite.

## Current Baseline on `main`

What is currently shipped on `main`:

- a backend reasoning-graph service (FastAPI) — this is the server side
- a dashboard frontend for browsing, graph exploration, and commit workflows
- GraphStore ABC with Neo4j and Kuzu implementations
- type-aware belief propagation (contradiction, retraction edges)

What is not yet shipped but is on the roadmap:

- `cli/` package (the primary product surface — in design, not yet on `main`)
- Git-backed package workflows and webhook integration
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

### 1. CLI/package-manager product

Gaia does not currently ship a supported `cli/` package or command-line product surface on `main`.

That means the following are out of current scope:

- `gaia init`
- `gaia claim`
- `gaia build`
- `gaia review`
- `gaia publish`
- Git-backed package workflows
- lockfile-based local knowledge package management

Related design work may exist, but it is not the current product baseline.

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
- **Server** — an optional registry that provides knowledge integration, global search, LLM review, and large-scale BP
- **Dashboard** — a browser UI for exploring the server-side knowledge graph

The current `main` ships the server and dashboard. The CLI is the next major deliverable.

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
2. **Primary interaction path?** → CLI → git push → PR → Server webhook → auto review → merge/reject.
3. **Kuzu role?** → CLI's embedded graph backend (local, zero-config). Neo4j is the server-side backend.

## Open Product Decisions

These remain open for later foundation phases:

1. Should degraded graph-free operation be part of the supported product story, or only an internal fallback mode?
2. What is the review output format? (deferred)
3. What is the direct publish (`gaia publish --server`) contract? (deferred)
