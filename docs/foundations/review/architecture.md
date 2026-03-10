# Gaia Build, Alignment, and Review Architecture

| 文档属性 | 值 |
|---------|---|
| 版本 | 4.0 |
| 日期 | 2026-03-10 |
| 状态 | **Draft — foundation design** |
| 关联文档 | [../README.md](../README.md), [../cli/command-lifecycle.md](../cli/command-lifecycle.md), [../server/architecture.md](../server/architecture.md), [../language/gaia-language-spec.md](../language/gaia-language-spec.md) |

> **Note:** This document defines the target architecture shared by Gaia CLI and Gaia Server. It does not describe the current implementation on `main` literally. Current code still has a simpler `gaia build`, a local chain-review path, and a legacy server-side `review_pipeline` attached to `/commits/*`.
>
> The file remains under `review/architecture.md` because this directory is the shared home for package-environment, alignment, and review semantics. The broader path rename, if any, is deferred; the architectural scope is defined by this document's title and contents.

---

## 1. Problem

Gaia currently blurs four different concerns:

- deterministic package lowering
- candidate context retrieval from existing knowledge
- open-world relation discovery against that context
- final package judgment

Those should not live under one overloaded word such as "review".

The result today is architectural drift:

- package-internal critique and open-world knowledge alignment are mixed together
- local and server review do not share a stable contract
- old server operators such as `join-cc` and `join-cp` appear under "review" even though they are alignment-time relation discovery
- the package environment contract is not explicit enough to make local preview reproducible
- `build`, `review`, and `infer` do not yet form a clean staged pipeline

This document fixes that boundary.

## 2. Core Judgments

### 2.1 Gaia has a three-stage build pipeline before review

Before final package review, Gaia should prepare the package through three stages:

1. **Compile**
2. **Context**
3. **Align**

The user-facing shortcut for that preparation pipeline is:

```text
gaia build
```

Advanced users may run the stages separately as build subcommands.

### 2.2 `gaia build compile` is deterministic

`gaia build compile` is the fast, local, non-LLM step.

It performs:

- parse
- elaboration
- local ref resolution
- deterministic lowering into explicit internal form

This is the part of "build" closest to the old shipped meaning.

### 2.3 `gaia build context` constructs the package environment

`gaia build context` retrieves candidate external context from local, remote, or combined knowledge sources and materializes the **package environment**.

It is a high-recall step.

Its job is not to make final judgments. Its job is to gather the working set that later stages need.

### 2.4 `gaia build align` performs open-world relation discovery

`gaia build align` operates over:

- the compiled package
- the current package environment

It uses model-assisted clustering, verification, and relation discovery to answer:

- does this package duplicate existing knowledge?
- should new declarations be merged, canonicalized, or linked?
- what contradiction, equivalence, or subsumption candidates appear?

This is not a final package judgment. It is open-world alignment.

### 2.5 `gaia review` is the final package assessment boundary

`gaia review` should run **after** build has already produced:

- compiled package artifacts
- the current package environment
- alignment results

It answers:

- given the discovered context, how credible is this package?
- are the package's chains and priors still reasonable in context?
- are the discovered duplicates, contradictions, equivalences, or subsumptions acceptable?
- is the package ready for local inference or later publish?

### 2.6 Build, review, and inference are separate phases

Build prepares the package and its context.

Review judges the prepared package.

Inference computes beliefs from build and review outputs.

Belief propagation belongs to **inference** (`gaia infer` locally, `BPService` on server), not to build or review.

### 2.7 Local build/review are preview, server build/review are authoritative

Local build and review are preview runs.

Server-side context construction, alignment, and review are authoritative because they can use:

- the current shared registry state
- managed retrieval and model policy
- the final integration path
- final larger-scope inference

The two sides must still share the same core contracts and semantics.

### 2.8 Build and review never rewrite package source

Build and review produce:

- compiled artifacts
- package environments
- alignment results
- review reports

They do **not** silently mutate the package's normative source.

Package source remains the canonical artifact.

---

## 3. Command Surfaces

### 3.1 CLI surface

The target command surface is:

```text
gaia build [PATH]
gaia build compile [PATH]
gaia build context [PATH]
gaia build align [PATH]
gaia review [PATH]
gaia infer [PATH]
gaia publish [PATH]
```

Build context selection should use one source flag, not multiple booleans:

```text
gaia build --source local|remote|both
gaia build context --source local|remote|both
gaia build context --frozen
gaia build context --refresh
```

Flag intent:

- `--frozen` means reuse the currently locked package environment and fail if the required lock/runtime artifacts are missing
- `--refresh` means ignore the currently locked package environment and rebuild context from the chosen source under the current policy

Recommended default:

- bare `gaia build` runs `compile -> context -> align`
- default `--source` is `local`
- `remote` and `both` are explicit opt-ins

### 3.2 CLI command roles

| Command | Role | Main output |
|---|---|---|
| `gaia build` | preparation shortcut over compile/context/align | compiled package + environment + alignment sidecars |
| `gaia build compile` | deterministic lowering | compiled package artifacts |
| `gaia build context` | candidate retrieval and environment construction | package environment |
| `gaia build align` | open-world relation discovery | alignment report |
| `gaia review` | final package assessment in context | review report |
| `gaia infer` | belief propagation | belief outputs |
| `gaia publish` | handoff to shared system | publish submission |

### 3.3 Server surface

The server should use the same conceptual phases internally, but the concrete lifecycle, transport shape, and externally visible status model are defined in [../server/architecture.md](../server/architecture.md).

From the perspective of this document, the only server requirement is semantic reuse:

- server-side preparation still follows `compile -> context -> align -> review`
- server-side integration happens only after those phases
- server-side authoritative BP remains downstream of integration

---

## 4. Policies and Configs

### 4.1 CompileConfig

Compile is deterministic and does not need an LLM policy, but it may still have a config:

```python
@dataclass
class CompileConfig:
    elaborate: bool = True
    resolve_local_refs: bool = True
```

### 4.2 ContextPolicy

Context construction needs retrieval policy and source selection:

```python
@dataclass
class ContextPolicy:
    source: Literal["local", "remote", "both"] = "local"
    embedding: EmbeddingConfig
    retrieval: RetrievalConfig      # semantic_top_k, structural_max_hops,
                                    # max_environment_nodes
```

### 4.3 AlignmentPolicy

Alignment needs models for clustering, abstraction judgment, and verification:

```python
@dataclass
class AlignmentPolicy:
    abstraction_model: LLMModelConfig
    verify_model: LLMModelConfig
    checks: list[str]               # e.g. duplicate_detection, contradiction_scan,
                                    #      subsumption_detection
    thresholds: AlignmentThresholds
```

### 4.4 ReviewPolicy

Review is a final model-based package assessment over aligned context:

```python
@dataclass
class ReviewPolicy:
    model: LLMModelConfig
    checks: list[str]               # e.g. chain_coherence, prior_reasonableness,
                                    #      alignment_consistency, publish_readiness
    thresholds: ReviewThresholds
```

`ReviewPolicy` does not discover external relations itself. It consumes the `AlignmentReport` produced by `align_package(...)` and judges whether those discovered relations are credible, acceptable, and compatible with the package's final readiness verdict.

### 4.5 Mapping to current pipeline operators

The existing `review_pipeline` operators map to build context/alignment, not to final review:

| Phase | Current operator | Current role |
|---|---|---|
| `build context` | `EmbeddingOperator` | embed package declarations |
| `build context` | `NNSearchOperator` | retrieve semantic neighbors |
| `build align` | `CCAbstractionOperator` | discover conclusion-conclusion relations |
| `build align` | `CPAbstractionOperator` | discover conclusion-premise relations |
| `build align` | `AbstractionTreeVerifyOperator` | first-pass verification |
| `build align` | `VerifyAgainOperator` | second-pass verification |

The current `BPOperator` does **not** belong to build or review. It belongs to inference.

### 4.6 Local vs server differences

| Dimension | Local (CLI) | Server |
|---|---|---|
| Context source | local by default; remote/both optional | live shared registry |
| Context embedding | user/local profile | managed profile |
| Alignment models | user-configured | managed |
| Review model | user-configured, may be lightweight | managed, may be stronger |
| Gate authority | advisory only | can reject or block integration |

---

## 5. Shared Contracts

CLI and server should use the same conceptual contracts:

```python
compile_package(
    source: PackageSource,
    config: CompileConfig,
) -> CompiledPackage

build_context(
    compiled: CompiledPackage,
    policy: ContextPolicy,
    environment_lock: EnvironmentLock | None = None,
) -> PackageEnvironment

align_package(
    compiled: CompiledPackage,
    environment: PackageEnvironment,
    policy: AlignmentPolicy,
) -> AlignmentReport

review_package(
    compiled: CompiledPackage,
    environment: PackageEnvironment,
    alignment: AlignmentReport,
    policy: ReviewPolicy,
) -> ReviewReport

@dataclass
class BuildResult:
    compiled: CompiledPackage
    environment: PackageEnvironment
    alignment: AlignmentReport
```

### 5.1 Contract invariants

These are hard requirements:

- the same phase must use the same request/report schema locally and on server
- the same compiled package, environment lock, and policy should produce the same class of result locally and on server
- server may add richer context and stricter policy, but must not invent a different report language
- `CompiledPackage` is deterministic and package-scoped
- `PackageEnvironment`, `AlignmentReport`, and `ReviewReport` are environment-scoped whenever they depend on external context
- if `gaia infer` consumes an environment, that environment must be identifiable and reproducible

### 5.2 Compiled package artifact

A compiled package artifact is stable with respect to package source and compile config.

It should contain:

- explicit lowered declarations
- elaborated forms
- resolved local refs
- deterministic structural artifacts for downstream phases

### 5.3 Package environment

A package environment depends on:

- compiled package contents
- context source selection
- retrieval policy
- current local or remote registry state

It should be labeled with environment identity and source metadata.

### 5.4 Alignment report

An alignment report depends on a concrete package environment.

It may contain:

- duplicate or canonicalization candidates
- contradiction, equivalence, or subsumption candidates
- join/merge suggestions
- verification results with quality metrics
- alignment-specific verdicts

### 5.5 Review report

A review report depends on:

- compiled package artifacts
- the current package environment
- the latest alignment results

It may contain:

- per-chain findings
- step-level dependency assessments
- context-aware issues
- assessments of discovered relations
- final readiness verdicts for infer/publish

---

## 6. Build and Review Core

### 6.1 Compile belongs to the language/build layer

Deterministic compile should remain in the Gaia Language build layer, not in `review_core`.

Conceptually:

```text
libs/lang/        # parse, elaborate, local ref resolution, lowering
libs/review_core/ # context, align, review
```

### 6.2 `review_core` responsibilities

The shared review subsystem should own:

- package-environment construction
- alignment logic
- final review logic
- shared request/report types
- policy application
- LLM/model adapters

It should **not** own:

- CLI command parsing
- HTTP routing
- job lifecycle
- package persistence
- belief propagation

### 6.3 CLI runner

The CLI runner should:

1. run `gaia build compile`
2. run `gaia build context`
3. run `gaia build align`
4. run `gaia review`
5. write sidecar artifacts locally
6. update `gaia.lock` when the package environment changes

Bare `gaia build` is a shortcut over steps 1-3.

### 6.4 Server runner

Server-specific orchestration is defined in [../server/architecture.md](../server/architecture.md).

At the contract level, the server runner must:

1. reuse the same `compile_package`, `build_context`, `align_package`, and `review_package` semantics
2. run those phases against shared registry state rather than local preview state
3. persist the resulting artifacts or summaries as part of server-side ingestion
4. gate integration and downstream workflows based on those outputs

### 6.5 Legacy server pipeline mapping

The existing `review_pipeline` mainly corresponds to:

- `build context`
- `build align`

No existing operator corresponds cleanly to final context-aware review. The CLI's current chain-level review (`cli/llm_client.py` → `ReviewClient`) is the closest precursor and should evolve into `review_package(...)`.

---

## 7. Package Environment

### 7.1 Purpose

Context construction needs external knowledge beyond the package itself. That external working set is the **package environment**.

A package environment may later be used by:

- `gaia build align`
- `gaia review`
- `gaia infer`

### 7.2 What it contains

A package environment should include:

- a snapshot/revision identifier for the underlying knowledge source
- the selected external nodes/documents used as context
- retrieved semantic neighbors
- retrieved structural neighbors
- candidate duplicate/canonicalization targets
- an environment fingerprint
- the source mode: `local`, `remote`, or `both`

### 7.3 Source selection

Context construction should support:

- `local`: local embedded database only
- `remote`: remote shared registry only
- `both`: merge local and remote candidates

Default should be `local` to preserve offline CLI usability.

### 7.4 Retrieval and materialization strategy

Building a package environment should proceed roughly as:

1. **Compile first** so retrieval works over explicit declarations.
2. **Choose source**: local, remote, or both.
3. **Embed** the package declarations that should participate in open-world matching.
4. **Retrieve semantic candidates** from the chosen source(s).
5. **Expand structurally** from both:
   - explicit refs to known external objects
   - semantic hits from the previous step
6. **Dedup and cap** the working set.
7. **Load content and metadata** for all selected items.
8. **Materialize** environment identity, selected nodes, and retrieval metadata into lock/runtime artifacts.

The result should be sufficient for local alignment and later local inference preview without loading the entire registry.

### 7.5 Why environment terminology matters

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

### 7.6 Local preview semantics

Local package environments are preview-only.

They help the author answer:

- what existing knowledge will this package collide with?
- what relations are likely?
- what environment should later review and inference consume?

### 7.7 Authoritative server semantics

After publish, the server may rebuild context against fresher shared state and therefore produce a different package environment than the author's local preview.

That is acceptable as long as the difference is explainable through:

- source mode
- registry revision
- retrieval policy
- policy/model versions

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

### 8.2 Environment lock

Gaia should have a package-level lockfile, tentatively:

```text
gaia.lock
```

The lock must be complete enough to reproduce:

- local context construction
- local alignment
- environment-aware local review and inference

It should lock:

- dependency resolution
- source mode
- package environment identity
- selected external context
- retrieval policy
- model identities used for alignment and review
- policy versions and key thresholds

This is intentionally stronger than a typical package-manager lock. Gaia's lockfile is not only a dependency-resolution record; it is also a reproducibility record for the materialized package environment used in local preview. Locking selected external context is therefore deliberate: it makes `context -> align -> review -> infer` reproducible against a concrete working set rather than only against a coarse registry revision.

Illustrative shape:

```yaml
dependencies:
  ...

environment:
  source: local
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
    review_model: gpt-5-mini
  policy_versions:
    context_policy: context-v1
    alignment_policy: align-v1
    review_policy: review-v2
  thresholds:
    duplicate_similarity: 0.92
    subsumption_min_score: 0.75
  fingerprint: ...
```

Alignment and review sidecars should also record the policy/model identifiers they were produced with.

### 8.3 Runtime artifacts

Runtime and cache artifacts belong under `.gaia/`.

Examples:

- compile outputs
- context cache / materialized package environment
- alignment sidecars
- review sidecars
- cached inference outputs

---

## 9. Inference Relationship

Build, review, and inference are related, but they are not the same phase.

### 9.1 Build and review

Build prepares:

- compiled package artifacts
- the package environment
- alignment results

Review then judges the package in that prepared context.

### 9.2 Review and inference

Review may accept, reject, or contextualize alignment findings before inference consumes them.

### 9.3 Local inference (`gaia infer`)

`gaia infer` compiles the factor graph from build outputs plus available review artifacts and runs local belief propagation.

If a package environment is available, inference may incorporate it for a more accurate local preview.

### 9.4 Server inference (`BPService`)

The server remains responsible for authoritative larger-scope computation after integration.

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
-> gaia infer
-> edit package
-> repeat
-> gaia publish
```

Advanced equivalent:

```text
workspace
-> gaia build compile
-> gaia build context --source local|remote|both
-> gaia build align
-> gaia review
-> gaia infer
-> gaia publish
```

### 10.2 Server publish loop

The target server publish loop is intentionally specified in [../server/architecture.md](../server/architecture.md), not duplicated here.

From the review architecture perspective, publish only requires that the server:

- rebuild preparation against shared state
- run authoritative alignment and review
- integrate only after those phases succeed
- run larger-scope BP after integration

---

## 11. Non-Goals

This document does not yet define:

- the final YAML/JSON schema for compiled package artifacts
- the final YAML/JSON schema for alignment and review reports
- the exact server API route layout
- the exact storage format for materialized package environments

Those are follow-up design tasks.

## 12. Immediate Follow-Ups

The next architectural follow-ups should be:

1. define the artifact schemas for compile/context/alignment/review
2. extract or define a shared `review_core` module for context, alignment, and review
3. design the package environment lockfile and sidecar layout
4. align CLI command semantics around `build`, `build compile/context/align`, `review`, `infer`, and `publish`
5. align server ingestion architecture around `compile -> context -> align -> review -> integrate`
