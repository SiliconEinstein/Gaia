# Gaia Review and Alignment Architecture

| 文档属性 | 值 |
|---------|---|
| 版本 | 3.0 |
| 日期 | 2026-03-10 |
| 状态 | **Draft — foundation design** |
| 关联文档 | [../README.md](../README.md), [../cli/command-lifecycle.md](../cli/command-lifecycle.md), [../server/architecture.md](../server/architecture.md), [../language/gaia-language-spec.md](../language/gaia-language-spec.md) |

> **Note:** This document defines the target architecture shared by Gaia CLI and Gaia Server. It does not describe the current implementation on `main` literally. Current code still contains a local CLI chain review path and a legacy server-side `review_pipeline` attached to `/commits/*`.

---

## 1. Problem

Gaia currently has two different activities partly living under the name "review":

- local `gaia review`, which audits package reasoning and writes sidecar reports
- server-side review jobs, which already mix package critique with global search, join, verify, and relation discovery against existing knowledge

Those are related, but they are not the same operation.

The result is architectural drift:

- package-internal critique and open-world knowledge alignment are blurred together
- local and server review do not share a stable request/report contract
- old server operators such as `join-cc` and `join-cp` appear under "review" even though they are really alignment-time relation discovery
- the package environment contract is not yet explicit enough to make local preview reproducible
- review, alignment, and inference are too easy to mix together conceptually

This document fixes that boundary.

## 2. Core Judgments

### 2.1 Gaia has two adjacent phases, not one overloaded review

Gaia should define two explicit phases after `build`:

1. **Package Review**
2. **Package Alignment**

They are adjacent in workflow, but they are not the same operation.

### 2.2 `gaia review` is closed-world

`gaia review` inspects a package using only package-local artifacts plus deterministic build output.

It answers:

- is the package internally well-formed and auditable?
- are chain steps coherent?
- are dependency labels and priors reasonable?
- are there package-internal contradiction or equivalence candidates?

### 2.3 `gaia align` is open-world

`gaia align` inspects how a package relates to existing shared knowledge.

It answers:

- does this package duplicate existing knowledge?
- should new declarations be merged, canonicalized, or linked?
- what cross-package contradiction, equivalence, or subsumption candidates appear?
- what package environment is relevant enough for local preview and later inference?

This is not just "review with more context". It is automated relation discovery and context construction.

### 2.4 `gaia align` constructs or refreshes the package environment

Alignment is the natural boundary where Gaia materializes a **package environment**:

- a package-scoped working set
- derived from the package plus relevant external context
- reusable by `gaia align`, `gaia infer`, and future environment-aware operations

### 2.5 Review, alignment, and inference are separate phases

Review audits package-internal reasoning quality.

Alignment discovers open-world relations and constructs the package environment.

Inference computes beliefs from build outputs plus review/alignment results.

Belief propagation belongs to **inference** (`gaia infer` locally, `BPService` on server), not to review or alignment.

### 2.6 Local review/alignment are preview, server review/alignment are authoritative

Local review and alignment are preview runs.

Server-side review/alignment are authoritative because they can use:

- the current shared registry state
- managed retrieval and model policy
- the final integration path
- final larger-scope inference

The two sides must still share the same core contracts and semantics.

### 2.7 Review and alignment never rewrite package source

Review and alignment produce reports, scores, discovered relations, and environment materialization.

They do **not** silently mutate the package's normative source.

Package source remains the canonical artifact. Review/alignment outputs remain sidecar/runtime data.

---

## 3. Command Surfaces

### 3.1 CLI surface

The target command surface is:

```text
gaia review [PATH]
gaia align [PATH]
gaia infer [PATH]
gaia publish [PATH]
```

With optional alignment controls:

```text
gaia align [PATH] --frozen
gaia align [PATH] --refresh-env
```

The command roles are:

| Command | Scope | Main output |
|---|---|---|
| `gaia review` | closed-world package audit | `PackageReviewReport` |
| `gaia align` | open-world relation discovery + environment materialization | `AlignmentReport` + `PackageEnvironment` |
| `gaia infer` | belief propagation over local graph inputs | belief outputs |
| `gaia publish` | handoff to shared system | publish submission |

### 3.2 Server surface

The server should use the same conceptual phases internally:

```text
validate
-> package review
-> align package against shared knowledge
-> integrate
-> authoritative BP/update
```

External API design may expose that as one submit endpoint or multiple status endpoints, but the domain model should keep those phases distinct.

---

## 4. Policies

Package review and package alignment are fundamentally different processes. Their policies are separate.

### 4.1 PackageReviewPolicy

Package review is a closed-world LLM audit. It needs one model and package-local thresholds.

```python
@dataclass
class PackageReviewPolicy:
    """Closed-world audit — package-internal reasoning critique only."""

    model: LLMModelConfig
    checks: list[str]               # e.g. chain_coherence, prior_reasonableness,
                                    #      dependency_label_validation
    thresholds: PackageThresholds
```

### 4.2 AlignmentPolicy

Alignment is an open-world process. It needs embedding, retrieval, and multiple LLM models for discovery and verification.

```python
@dataclass
class AlignmentPolicy:
    """Open-world alignment — environment construction plus relation discovery."""

    embedding: EmbeddingConfig
    retrieval: RetrievalConfig      # semantic_top_k, structural_max_hops,
                                    # max_environment_nodes
    abstraction_model: LLMModelConfig
    verify_model: LLMModelConfig
    checks: list[str]               # e.g. duplicate_detection, contradiction_scan,
                                    #      subsumption_detection
    thresholds: AlignmentThresholds
```

### 4.3 Mapping to current pipeline operators

The existing `review_pipeline` operators map to **alignment**, not to package review:

| Policy field | Current operator | Current default |
|---|---|---|
| `embedding` | `EmbeddingOperator(DashScopeEmbeddingModel)` | dim=512, max_rps=600 |
| `retrieval.semantic_top_k` | `NNSearchOperator(k=)` | k=20 |
| `retrieval.structural_max_hops` | not yet implemented | — |
| `abstraction_model` | `CCAbstractionOperator` + `CPAbstractionOperator` (shared) | dptech_internal/gpt-5-mini |
| `verify_model` | `AbstractionTreeVerifyOperator` + `VerifyAgainOperator` (shared) | same as above |

The current `BPOperator` in the pipeline does **not** belong to review or alignment. It belongs to inference.

### 4.4 Policy differences between local and server

| Dimension | Local (CLI) | Server |
|---|---|---|
| Package review model | user-configured, may be lightweight | managed, may be stronger |
| Alignment embedding | user/local profile | managed profile |
| Alignment retrieval | against frozen or refreshed package environment | against live registry |
| Alignment LLMs | user-configured | managed |
| Gate authority | advisory only | can reject or block integration |

---

## 5. Shared Contracts

CLI and server should call the same core subsystem, but with separate review and alignment entry points:

```python
# Package review
package_review(
    request: ReviewRequest,
    policy: PackageReviewPolicy,
) -> PackageReviewReport

# Package alignment
align_package(
    request: AlignmentRequest,
    policy: AlignmentPolicy,
    environment_lock: EnvironmentLock | None = None,
) -> AlignmentResult

@dataclass
class AlignmentResult:
    environment: PackageEnvironment
    report: AlignmentReport
```

### 5.1 Contract invariants

These are hard requirements:

- local and server must use the same request and report schema for the same phase
- the same request, environment lock, and policy should produce the same class of result locally and on server
- server may add richer context, stronger models, and stricter policy, but must not invent a different report language
- `PackageReviewReport` is package-scoped and can be stored as a local sidecar
- `AlignmentReport` and `PackageEnvironment` are environment-scoped and must be treated as time/version dependent
- if `gaia infer` consumes an environment, that environment must be identifiable and reproducible

### 5.2 Package review report

A package review report is stable with respect to package content and build artifacts.

It may contain:

- per-chain findings
- step-level dependency assessments
- suggested priors
- local package verdicts
- package-internal relation candidates

It should be suitable for local storage under `.gaia/reviews/`.

### 5.3 Alignment report

An alignment report depends on a concrete package environment.

It may contain:

- duplicate or canonicalization candidates
- cross-package contradiction, equivalence, or subsumption candidates
- join/merge suggestions
- verification results with quality metrics
- alignment-specific verdicts

It is not a stable part of the package source. It should be labeled with its environment identity.

---

## 6. Review Core and Runners

### 6.1 Shared core

Gaia should have one shared subsystem, conceptually:

```text
libs/review_core/
```

This module owns:

- shared request/report types
- package review logic
- alignment logic
- environment materialization logic
- policy application
- LLM/model adapters

It does **not** own:

- CLI command parsing
- HTTP routing
- job lifecycle
- package persistence
- belief propagation

### 6.2 CLI runner

The CLI runner should:

1. load the local package and build artifacts
2. run `package_review(...)`
3. optionally resolve or refresh the package environment
4. run `align_package(...)`
5. write sidecar artifacts locally
6. update `gaia.lock` when the package environment changes

CLI review and alignment remain advisory and preview-oriented.

### 6.3 Server runner

The server runner should:

1. accept submitted packages
2. run package review against shared server policy
3. align the package against the current registry state
4. persist review and alignment results
5. gate integration and downstream workflows

### 6.4 Legacy server pipeline mapping

The existing `review_pipeline` operators belong to **alignment**:

| Current operator | Alignment role |
|---|---|
| `EmbeddingOperator` | generate embeddings for new declarations |
| `NNSearchOperator` | retrieve semantic neighbors for environment construction |
| `CCAbstractionOperator` (`join-cc`) | discover conclusion-conclusion relations |
| `CPAbstractionOperator` (`join-cp`) | discover conclusion-premise relations |
| `AbstractionTreeVerifyOperator` | first-pass verification of discovered relations |
| `VerifyAgainOperator` | second-pass verification and filtering |

The current `BPOperator` should be removed from the review pipeline and handled by inference.

No existing operator corresponds cleanly to package review. The CLI's current chain-level LLM review (`cli/llm_client.py` → `ReviewClient`) is the closest existing package-review logic and should be extracted into the shared core.

---

## 7. Package Environment

### 7.1 Purpose

Alignment needs external context beyond the package itself. That context is the **package environment**.

A package environment is not limited to alignment. It is the general environment a package exists in and may later be used by:

- `gaia align`
- `gaia infer`
- future environment-aware operations

### 7.2 What it contains

A package environment should include:

- the candidate package under review
- a snapshot/revision identifier for the shared registry state
- retrieved semantic neighbors
- retrieved structural neighbors
- candidate duplicate/canonicalization targets
- an environment fingerprint

Internally this may be implemented by pulling a related subgraph, but the user-facing concept should be **environment**, not "graph snapshot".

### 7.3 Retrieval and materialization strategy

Building a package environment requires retrieving relevant external context. The retrieval process is:

1. **Embed** all declarations in the package that should participate in open-world matching.
2. **Semantic retrieval**: for each embedding, find the top-k nearest neighbors from the shared registry.
3. **Structural retrieval**: expand from both:
   - explicit package references to existing registry objects
   - semantic retrieval hits from step 2
4. **Dedup and cap**: merge semantic and structural results, deduplicate by node ID, and cap at `max_environment_nodes`.
5. **Load content**: fetch full content and metadata for all selected nodes.
6. **Materialize**: write environment identity, selected nodes, and retrieval metadata into the lock/runtime artifacts.

The result is a self-contained working set sufficient for local alignment and later local inference preview without loading the entire registry.

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

Local alignment over the package environment is preview-only.

It helps the author answer:

- what existing knowledge will this package collide with?
- what relations are likely?
- what local environment should `gaia infer` use?

It is not an authoritative global result.

### 7.6 Authoritative server semantics

After publish, the server may run:

- the same alignment logic against fresher shared state
- final merge/canonicalization decisions
- larger-scope inference after integration

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

The lock must be complete enough to reproduce local alignment and environment-aware local inference.

It should lock:

- dependency resolution
- package environment identity
- selected external context
- retrieval policy
- model identities used to construct or verify alignment
- policy versions and key thresholds

Illustrative shape:

```yaml
dependencies:
  ...

environment:
  registry_revision: ...
  selected_node_ids:
    - ...
  content_snapshot_ids:
    - ...
  retrieval_policy:
    semantic_top_k: 20
    structural_max_hops: 2
    max_environment_nodes: 200
  model_profile:
    embedding_model: text-embedding-3-large
    alignment_model: gpt-5-mini
    verify_model: gpt-5-mini
  policy_versions:
    package_review_policy: review-v1
    alignment_policy: align-v1
  thresholds:
    duplicate_similarity: 0.92
    subsumption_min_score: 0.75
  fingerprint: ...
```

Review and alignment sidecars should also record the policy/model identifiers they were produced with.

### 8.3 Runtime artifacts

Runtime and cache artifacts belong under `.gaia/`.

Examples:

- build outputs
- review sidecars
- alignment sidecars
- materialized package environment contents
- cached inference outputs

These are useful for iteration, but they are not the package's normative source definition.

---

## 9. Inference Relationship

Review, alignment, and inference are related, but they are not the same phase.

### 9.1 Package review and inference

Package review may suggest priors, dependency labels, or package-internal relation candidates that later affect inference.

But package review itself is still an audit step, not inference execution.

### 9.2 Alignment and inference

Alignment discovers open-world relations and constructs the package environment.

Those relations and that environment become inputs to inference.

### 9.3 Local inference (`gaia infer`)

`gaia infer` compiles the factor graph from build outputs plus available review/alignment artifacts and runs local belief propagation.

If a package environment is available, it may incorporate that environment for more accurate local preview.

### 9.4 Server inference (`BPService`)

The server remains responsible for authoritative larger-scope computation after alignment and integration.

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
-> gaia review
-> gaia align
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
-> align package against shared knowledge
-> integrate
-> authoritative BP/update
-> result
```

The server may expose that as one asynchronous job or several endpoints, but those phases should remain explicit in the domain model.

---

## 11. Non-Goals

This document does not yet define:

- the final YAML/JSON schema for review and alignment reports
- the final server API route layout
- the final local command set for environment inspection
- the exact storage format for materialized package environments

Those are follow-up design tasks.

## 12. Immediate Follow-Ups

The next architectural follow-ups should be:

1. define the structured report schemas for package review and alignment
2. extract or define a shared `review_core` module for both package review and alignment
3. design the package environment lockfile and sidecar layout
4. align CLI command semantics around `review`, `align`, `infer`, and `publish`
5. align server ingestion architecture around `review -> align -> integrate`
