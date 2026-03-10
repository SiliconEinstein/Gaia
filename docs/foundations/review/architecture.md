# Gaia Review Architecture

| 文档属性 | 值 |
|---------|---|
| 版本 | 2.0 |
| 日期 | 2026-03-10 |
| 状态 | **Draft — foundation design** |
| 关联文档 | [../README.md](../README.md), [../cli/command-lifecycle.md](../cli/command-lifecycle.md), [../server/architecture.md](../server/architecture.md), [../language/gaia-language-spec.md](../language/gaia-language-spec.md) |

> **Note:** This document defines the target review architecture shared by Gaia CLI and Gaia Server. It does not describe the current implementation on `main` literally. Current code still contains a local CLI chain review path and a legacy server-side `review_pipeline` attached to `/commits/*`.

---

## 1. Problem

Gaia currently has two things called "review":

- local `gaia review`, which audits package reasoning and writes sidecar reports
- server-side review jobs, which already mix package critique with global search, join, verify, and BP-style integration analysis

Those are related, but they are not the same layer.

The result is architectural drift:

- local and server review do not share a stable request/response contract
- package-internal review and global knowledge integration are blurred together
- old server operators such as `join-cc` and `join-cp` appear under "review" even though they are really integration-time reasoning
- it is unclear whether local review should attempt whole-graph BP or only preview its likely integration effects

This document fixes that boundary.

## 2. Core Judgments

### 2.1 One review architecture, two review scopes

Gaia should define a single review architecture with two explicit scopes:

1. **Package Review**
2. **Integration Review**

`gaia review` is the umbrella command. Scope selects which phase is run.

### 2.2 Package review is closed-world

Package review inspects a package using only package-local artifacts plus deterministic build output.

It answers:

- is the package internally well-formed and auditable?
- are chain steps coherent?
- are dependency labels and priors reasonable?
- are there package-internal contradiction or equivalence candidates?

### 2.3 Integration review is open-world

Integration review inspects how a package would interact with the shared knowledge system.

It answers:

- does this package duplicate existing knowledge?
- should new declarations be merged, canonicalized, or linked?
- what cross-package contradiction or equivalence candidates appear?
- what subsumption relationships exist between new and existing declarations?

### 2.4 Review and inference are separate phases

Review discovers relations and audits reasoning quality. It does **not** compute beliefs.

Belief propagation belongs to the **inference** phase (`gaia infer` locally, `BPService` on server), which runs after review. This separation is already reflected in the CLI lifecycle: `build → review → infer → publish`.

### 2.5 Local review is preview, server review is authoritative

Local integration review is a preview run against a materialized package environment.

Server review is authoritative because it can use:

- the current shared registry state
- stronger retrieval and search context
- managed model policy
- final integration path

The two sides must still share the same core contracts and semantics.

### 2.6 Review never rewrites package source

Review produces reports, scores, and suggestions.

Review does **not** silently mutate the package's normative source.

Package source remains the canonical artifact. Review output remains sidecar/runtime data.

---

## 3. Review Scopes

| Scope | Inputs | Context model | Main output | Typical caller |
|------|--------|---------------|-------------|----------------|
| `package` | built package | closed-world | `PackageReviewReport` | CLI, server |
| `integration` | built package + package environment | open-world | `IntegrationReviewReport` | CLI preview, server |
| `all` | same as above | package first, then integration | combined report | CLI, server |

### 3.1 CLI surface

The target command surface is:

```text
gaia review [PATH]
gaia review [PATH] --scope package
gaia review [PATH] --scope integration
gaia review [PATH] --scope all
```

Default scope is `all`. This runs package review first, then integration review. The user should see the full picture by default.

`--scope package` or `--scope integration` can be used to run a single phase when iterating on a specific concern.

### 3.2 Server surface

The server should use the same scope model internally:

```text
validate
-> package review
-> integration review
-> integrate
-> authoritative BP/update
```

External API design may expose that as one submit endpoint or multiple review endpoints, but the domain model should keep the two review phases distinct.

---

## 4. Review Policies

Package review and integration review are fundamentally different processes. Their policies are separate.

### 4.1 PackageReviewPolicy

Package review is a closed-world LLM audit. It needs one model and package-local thresholds.

```python
@dataclass
class PackageReviewPolicy:
    """Closed-world audit — only needs an LLM for chain critique."""

    model: LLMModelConfig           # LLM for chain-level reasoning critique
    checks: list[str]               # e.g. chain_coherence, prior_reasonableness,
                                    #      dependency_label_validation
    thresholds: PackageThresholds   # min_chain_score, min_prior_range
```

### 4.2 IntegrationReviewPolicy

Integration review is an open-world process. It needs embedding, retrieval, and multiple LLM models for different stages.

```python
@dataclass
class IntegrationReviewPolicy:
    """Open-world integration — needs embedding, retrieval, and LLMs."""

    # ── Embedding ──
    embedding: EmbeddingConfig      # provider, api_url, access_key, dim

    # ── Retrieval (builds the package environment) ──
    retrieval: RetrievalConfig      # semantic_top_k, structural_max_hops,
                                    # max_environment_nodes

    # ── Abstraction discovery (join-cc, join-cp) ──
    abstraction_model: LLMModelConfig

    # ── Verification (two-pass) ──
    verify_model: LLMModelConfig

    # ── Checks & thresholds ──
    checks: list[str]               # e.g. duplicate_detection, contradiction_scan,
                                    #      subsumption_detection
    thresholds: IntegrationThresholds  # max_overlap_similarity, ...
```

### 4.3 Mapping to current pipeline operators

The existing `review_pipeline` operators map to `IntegrationReviewPolicy` fields:

| Policy field | Current operator | Current default |
|---|---|---|
| `embedding` | `EmbeddingOperator(DashScopeEmbeddingModel)` | dim=512, max_rps=600 |
| `retrieval.semantic_top_k` | `NNSearchOperator(k=)` | k=20 |
| `retrieval.structural_max_hops` | not yet implemented | — |
| `abstraction_model` | `CCAbstractionOperator` + `CPAbstractionOperator` (shared) | dptech_internal/gpt-5-mini |
| `verify_model` | `AbstractionTreeVerifyOperator` + `VerifyAgainOperator` (shared) | same as above |

The current `BPOperator` in the pipeline does **not** belong to review. It should be moved to the inference phase (see §8).

### 4.4 Policy differences between local and server

| Dimension | Local (CLI) | Server |
|---|---|---|
| Package review model | user-configured, may be lightweight | managed, may be stronger |
| Integration embedding | same provider | same provider |
| Integration retrieval | against package environment (snapshot) | against live registry |
| Integration LLMs | user-configured | managed |
| Gate authority | advisory only | can reject/block integration |

---

## 5. Shared Review Contracts

CLI and server should call the same review core, but with scope-specific signatures:

```python
# Package review
package_review(
    request: ReviewRequest,
    policy: PackageReviewPolicy,
) -> PackageReviewReport

# Integration review
integration_review(
    request: ReviewRequest,
    environment: PackageEnvironment,
    policy: IntegrationReviewPolicy,
) -> IntegrationReviewReport
```

### 5.1 Contract invariants

These are hard requirements:

- local and server review must use the same request and report schema
- the same request, environment, and policy should produce the same class of result locally and on server
- server may add richer context, stronger models, and stricter policy, but must not invent a different report language
- `PackageReviewReport` is package-scoped and can be stored as a local sidecar
- `IntegrationReviewReport` is environment-scoped and must be treated as time/version dependent

### 5.2 Package review report

A package review report is stable with respect to package content and build artifacts.

It may contain:

- per-chain findings
- step-level dependency assessments
- suggested priors
- local package verdicts
- package-internal relation candidates

It should be suitable for local storage under `.gaia/reviews/`.

### 5.3 Integration review report

An integration review report depends on a concrete package environment.

It may contain:

- duplicate or canonicalization candidates (from join-cc, join-cp)
- cross-package contradiction/equivalence/subsumption candidates
- join/merge suggestions
- verification results with quality metrics (tightness, substantiveness, union error)
- integration-specific verdicts

It is not a stable part of the package source. It should be labeled with its environment identity.

---

## 6. Review Core and Runners

### 6.1 Review Core

Gaia should have one shared review module, conceptually:

```text
libs/review_core/
```

This module owns:

- shared request/report types
- review operators
- policy application
- LLM/model adapters
- package review logic
- integration review logic

It does **not** own:

- CLI command parsing
- HTTP routing
- job lifecycle
- package persistence
- belief propagation (that belongs to inference)

### 6.2 CLI runner

The CLI runner should:

1. load the local package and build artifacts
2. create `ReviewRequest`
3. create package-only or environment-aware `ReviewContext`
4. call the shared review core
5. write sidecar artifacts locally

CLI review remains advisory and preview-oriented.

### 6.3 Server runner

The server runner should:

1. accept submitted packages
2. enrich context with shared registry state
3. call the same review core
4. persist review results
5. gate integration and downstream workflows

The server wrapper may live as a worker/service, but it should not fork review semantics from the CLI.

### 6.4 Legacy server pipeline mapping

The existing `review_pipeline` operators belong to **Integration Review**:

| Current operator | Integration review role |
|---|---|
| `EmbeddingOperator` | Generate embeddings for new declarations |
| `NNSearchOperator` | Retrieve semantic neighbors (build package environment) |
| `CCAbstractionOperator` (join-cc) | Discover conclusion-conclusion relations |
| `CPAbstractionOperator` (join-cp) | Discover conclusion-premise relations |
| `AbstractionTreeVerifyOperator` | First-pass verification of discovered relations |
| `RefineOperator` | Placeholder (Phase 2) |
| `VerifyAgainOperator` | Second-pass verification, collect verified relations |

The current `BPOperator` should be removed from the review pipeline and handled by the inference phase.

No existing operator corresponds to **Package Review**. The CLI's current chain-level LLM review (`cli/llm_client.py` → `ReviewClient`) is the closest to package review logic and should be extracted into `review_core`.

---

## 7. Package Environment

### 7.1 Purpose

Integration review needs external context beyond the package itself. That context is the **package environment**.

A package environment is not limited to integration review — it is the general context a package exists in. It may be used by:

- `gaia review --scope integration` — open-world relation discovery
- `gaia infer` — more accurate local BP with external context
- future operations that need awareness of the shared knowledge system

### 7.2 What it contains

A package environment should include:

- the candidate package under review
- a snapshot/revision identifier for the shared registry state
- retrieved semantic neighbors (via embedding similarity)
- retrieved structural neighbors (via graph topology)
- candidate duplicate/canonicalization targets
- an environment fingerprint

Internally this may be implemented by pulling a related subgraph, but the user-facing concept should be **environment**, not "graph snapshot".

### 7.3 Retrieval strategy

Building a package environment requires retrieving relevant external context. The retrieval process is:

1. **Embed** all declarations in the package (claims, conclusions of chains) using the configured embedding model.
2. **Semantic retrieval**: for each embedding, find the top-k nearest neighbors from the shared registry (default k=20). This surfaces potentially duplicate, equivalent, or related declarations.
3. **Structural retrieval** (when graph is available): starting from any declarations that reference existing registry nodes, traverse up to N hops (default 2) to pull in structurally connected context.
4. **Dedup and cap**: merge semantic and structural results, deduplicate by node ID, cap at `max_environment_nodes` (default 200).
5. **Load content**: fetch full content and metadata for all retrieved nodes from the content store.

The result is a self-contained working set sufficient for integration review without loading the entire registry.

### 7.4 Why environment terminology matters

For local UX, Gaia should feel closer to package managers such as Cargo than to a raw graph tool.

The user-facing concepts should be:

- package
- dependency
- environment
- lockfile

Not:

- graph snapshot
- subgraph extraction
- topology slice

Those remain implementation details.

### 7.5 Local preview semantics

Local integration review over the package environment is preview-only.

It is useful because it lets the author answer:

- what would likely happen if I publish this package now?
- what existing knowledge will this collide with?
- what relations (equivalence, contradiction, subsumption) are likely?

It is not an authoritative global result.

### 7.6 Authoritative server semantics

After publish, the server may run:

- the same integration review against fresher shared state
- final merge/canonicalization decisions

Differences between local preview and server outcome are acceptable. They should be explainable through environment identity, policy version, and current shared state.

---

## 8. Package and Environment Management

Gaia should separate three artifact classes:

1. **Package source**
2. **Environment lock**
3. **Runtime artifacts**

### 8.1 Package source

Package source is the canonical author-maintained artifact.

Today that is centered on:

- `package.yaml`
- module YAML files

A future `Gaia.toml` may replace or wrap parts of that manifest story, but the architectural split remains the same.

### 8.2 Environment lock

Gaia should have a package-level lockfile, tentatively:

```text
gaia.lock
```

It should lock both:

- dependency resolution
- package environment identity

Illustrative shape:

```yaml
dependencies:
  ...

environment:
  registry_revision: ...
  retrieval_policy:
    semantic_top_k: 20
    structural_max_hops: 2
    max_environment_nodes: 200
  fingerprint: ...
```

### 8.3 Runtime artifacts

Runtime and cache artifacts belong under `.gaia/`.

Examples:

- build outputs
- review sidecars
- materialized package environment contents
- cached inference outputs

These are useful for iteration, but they are not the package's normative source definition.

---

## 9. Inference Relationship

Review and inference are related, but they are not the same phase.

### 9.1 Package review and inference

Package review may suggest priors, dependency labels, or relation candidates that later affect BP.

But package review itself is still an audit step, not inference execution.

### 9.2 Integration review and inference

Integration review discovers relations (equivalence, contradiction, subsumption) between the package and existing knowledge. It does **not** run BP.

The discovered relations become inputs to inference: once integrated, they form new edges in the factor graph that BP uses to compute beliefs.

### 9.3 Local inference (`gaia infer`)

`gaia infer` compiles the factor graph from build/review outputs and runs local belief propagation. If a package environment is available, it may include environment context for more accurate local BP.

### 9.4 Server inference (`BPService`)

The server remains responsible for authoritative larger-scope computation after review and integration.

This may include:

- subgraph BP for decision support
- deferred large-scale BP
- final belief persistence

---

## 10. Lifecycle

### 10.1 Local authoring loop

The target local loop is:

```text
workspace
-> gaia build
-> gaia review                  (default: --scope all)
-> gaia infer
-> edit package
-> repeat
-> gaia publish
```

### 10.2 Server publish loop

The target server loop is:

```text
submit package
-> validate
-> package review
-> integration review
-> integrate
-> authoritative BP/update
-> result
```

The server may expose that as one asynchronous job or several endpoints, but those phases should remain explicit in the domain model.

---

## 11. Non-Goals

This document does not yet define:

- the final YAML/JSON schema for review reports
- the final server API route layout
- the final local command set for environment management
- whether package review and integration review should use one combined file or multiple sidecar files

Those are follow-up design tasks.

## 12. Immediate Follow-Ups

The next architectural follow-ups should be:

1. define the structured review report schema (unifying CLI and server report formats)
2. extract or define a shared `review_core` module (from CLI chain review + server pipeline operators)
3. design the package environment lockfile format (coordinate with Issue #68 package management)
4. align CLI command semantics with review scopes (`--scope` flag)
5. align server ingestion architecture with package review plus integration review
