# Gaia Product Scope

## Purpose

This document defines the current product baseline for Gaia on `main`.

Its job is simple:

- state what Gaia currently is
- state what it currently supports
- state what is not yet part of the supported product surface

If a proposal, PR, or design doc goes beyond this baseline, it should be described as future work rather than current capability.

## Current Product Baseline

Gaia on `main` is currently:

- a backend reasoning-graph service
- plus a dashboard frontend for browsing, graph exploration, and commit workflows

It is not yet a general local package manager or a fully defined multi-surface platform spanning server, CLI, Git workflows, and community review.

## Shared Foundation Direction

In parallel with the current shipped product baseline, Gaia foundation work is now standardizing a shared knowledge-package contract intended to be usable by both:

- future local / CLI package workflows
- future server-side package ingestion and graph integration

Important boundary:

This shared foundation work defines future-facing common contracts. It does not by itself mean that Gaia already ships a supported CLI product surface on `main`.

## Current Supported Product Surfaces

### 1. HTTP server

The primary product surface is the FastAPI service exposed from `services/gateway/`.

Current API areas:

- commit submission, review, merge, and retrieval
- read APIs for nodes, hyperedges, contradictions, subgraphs, and stats
- search APIs for nodes and hyperedges
- batch APIs for commit, read, subgraph, and search flows
- job APIs for async status and result retrieval

This is the main externally addressable product surface today.

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

## Current Product Positioning

The correct way to describe Gaia today is:

- server-first
- API-driven
- dashboard-backed
- graph-reasoning focused
- currently shipping a server product while standardizing shared future package contracts

The incorrect way to describe Gaia today is:

- CLI-first
- package-manager-first
- fully backend-agnostic at product contract level
- already shipping all documented future workflows

## Implications For Future Work

Until this scope changes, large new work should be framed in one of three ways:

1. extend the current server and dashboard product
2. tighten the foundations under the current server and dashboard product
3. propose a new product surface explicitly as future work

That means:

- architecture work should optimize for the current server baseline first
- foundation docs should distinguish current shipped capability from future shared contracts
- CLI and broader backend work should build on explicit contracts, not implied ones

## PR And Documentation Rules

When writing docs or reviewing PRs:

1. If the feature is part of the current product baseline, it can be described as current behavior.
2. If it is implemented in code but not yet fully specified as product contract, call out the limitation explicitly.
3. If it is only planned, label it as proposal, roadmap, or future work.
4. Do not let design docs silently redefine the current product baseline.

## Open Product Decisions

These decisions remain open for later foundation phases:

1. Should Gaia eventually become a dual-surface product: server plus CLI?
2. Should Kuzu be treated as a first-class supported graph backend or primarily as a local/development backend?
3. Should degraded graph-free operation be part of the supported product story, or only an internal fallback mode?
4. Which future workflows, if any, should become official product surfaces beyond server plus dashboard?

Until those questions are answered, the baseline in this document should be treated as authoritative.
