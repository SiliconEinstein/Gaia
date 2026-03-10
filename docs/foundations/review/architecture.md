# Gaia Review Architecture

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
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
- what local BP effects are likely if this package is integrated?

### 2.4 Local review is preview, server review is authoritative

Local integration review is a preview run against a materialized integration environment.

Server review is authoritative because it can use:

- the current shared registry state
- stronger retrieval and search context
- managed model policy
- final integration and large-scale BP

The two sides must still share the same core contracts and semantics.

### 2.5 Review never rewrites package source

Review produces reports, scores, and suggestions.

Review does **not** silently mutate the package's normative source.

Package source remains the canonical artifact. Review output remains sidecar/runtime data.

---

## 3. Review Scopes

| Scope | Inputs | Context model | Main output | Typical caller |
|------|--------|---------------|-------------|----------------|
| `package` | built package | closed-world | `PackageReviewReport` | CLI, server |
| `integration` | built package + integration environment | open-world | `IntegrationReviewReport` | CLI preview, server |
| `all` | same as above | package first, then integration | combined report | CLI, server |

### 3.1 CLI surface

The target command surface is:

```text
gaia review [PATH]
gaia review [PATH] --scope package
gaia review [PATH] --scope integration
gaia review [PATH] --scope all
```

Default scope is `package`.

`all` is ordered and means:

```text
package review -> integration review
```

Integration review may be run by itself as an explicit dry-run, but it should not replace package review as the normal gate.

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

## 4. Shared Review Contracts

CLI and server should call the same review core:

```python
review(
    request: ReviewRequest,
    context: ReviewContext,
    policy: ReviewPolicy,
) -> ReviewReport
```

Recommended core objects:

```python
ReviewRequest
ReviewContext
ReviewPolicy
ReviewReport
PackageReviewReport
IntegrationReviewReport
```

### 4.1 Contract invariants

These are hard requirements:

- local and server review must use the same request and report schema
- the same request, context, and policy should produce the same class of result locally and on server
- server may add richer context, stronger models, and stricter policy, but must not invent a different report language
- `PackageReviewReport` is package-scoped and can be stored as a local sidecar
- `IntegrationReviewReport` is environment-scoped and must be treated as time/version dependent

### 4.2 Package review report

A package review report is stable with respect to package content and build artifacts.

It may contain:

- per-chain findings
- step-level dependency assessments
- suggested priors
- local package verdicts
- package-internal relation candidates

It should be suitable for local storage under `.gaia/reviews/`.

### 4.3 Integration review report

An integration review report depends on a concrete integration environment.

It may contain:

- duplicate or canonicalization candidates
- cross-package contradiction/equivalence candidates
- join/merge suggestions
- environment-scoped BP preview
- integration-specific verdicts

It is not a stable part of the package source. It should be labeled with its environment identity.

---

## 5. Review Core and Runners

### 5.1 Review Core

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

### 5.2 CLI runner

The CLI runner should:

1. load the local package and build artifacts
2. create `ReviewRequest`
3. create package-only or integration-aware `ReviewContext`
4. call the shared review core
5. write sidecar artifacts locally

CLI review remains advisory and preview-oriented.

### 5.3 Server runner

The server runner should:

1. accept submitted packages
2. enrich context with shared registry state
3. call the same review core
4. persist review results
5. gate integration and downstream workflows

The server wrapper may live as a worker/service, but it should not fork review semantics from the CLI.

### 5.4 Legacy server pipeline mapping

Existing server-side operators such as NN search, `join-cc`, `join-cp`, abstraction verification, and integration-time BP belong conceptually to **Integration Review**, not to package-internal review.

That means the old `review_pipeline` should eventually be reinterpreted as:

- package review operators
- integration review operators
- plus server orchestration around them

---

## 6. Integration Environment

### 6.1 Purpose

Local integration review should not require loading the entire shared knowledge system.

Instead, Gaia should materialize an **integration environment**:

- a package-scoped working set
- derived from the package plus relevant external context
- sufficient for integration review and local BP preview

### 6.2 What it contains

An integration environment should include:

- the candidate package under review
- a snapshot/revision identifier for the shared registry state
- retrieved semantic neighbors
- retrieved structural neighbors
- candidate duplicate/canonicalization targets
- local BP configuration
- an environment fingerprint

Internally this may be implemented by pulling a related subgraph, but the user-facing concept should be **environment**, not "graph snapshot".

### 6.3 Why environment terminology matters

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

### 6.4 Local preview semantics

Local integration review and local BP over the environment are preview-only.

They are useful because they let the author answer:

- what would likely happen if I publish this package now?
- what existing knowledge will this collide with?
- what local belief shifts are likely?

They are not authoritative global results.

### 6.5 Authoritative server semantics

After publish, the server may run:

- the same integration review model against fresher shared state
- larger-scope or global BP
- final merge/canonicalization decisions

Differences between local preview and server outcome are acceptable. They should be explainable through environment identity, policy version, and current shared state.

---

## 7. Package and Environment Management

Gaia should separate three artifact classes:

1. **Package source**
2. **Environment lock**
3. **Runtime artifacts**

### 7.1 Package source

Package source is the canonical author-maintained artifact.

Today that is centered on:

- `package.yaml`
- module YAML files

A future `Gaia.toml` may replace or wrap parts of that manifest story, but the architectural split remains the same.

### 7.2 Environment lock

Gaia should have a package-level lockfile, tentatively:

```text
gaia.lock
```

It should lock both:

- dependency resolution
- integration environment identity

Illustrative shape:

```yaml
dependencies:
  ...

integration_environment:
  revision: ...
  retrieval_policy: ...
  review_policy: ...
  bp_config: ...
  environment_fingerprint: ...
```

Internal field names may still include graph-specific details such as `graph_revision` or `materialized_nodes`, but the external concept should remain "environment lock".

### 7.3 Runtime artifacts

Runtime and cache artifacts belong under `.gaia/`.

Examples:

- build outputs
- review sidecars
- materialized integration environment contents
- cached inference outputs

These are useful for iteration, but they are not the package's normative source definition.

---

## 8. Inference Relationship

Review and inference are related, but they are not the same phase.

### 8.1 Package review and inference

Package review may suggest priors, dependency labels, or relation candidates that later affect BP.

But package review itself is still an audit step, not inference execution.

### 8.2 Integration review and local BP

Integration review may include local BP preview over the materialized integration environment.

That BP run is:

- subgraph-scoped
- environment-scoped
- preview-only

### 8.3 Server BP

The server remains responsible for authoritative larger-scope computation after review and integration.

This may include:

- subgraph BP for decision support
- deferred large-scale BP
- final belief persistence

---

## 9. Lifecycle

### 9.1 Local authoring loop

The target local loop is:

```text
workspace
-> gaia build
-> gaia review --scope package
-> gaia review --scope integration
-> local infer / inspect
-> edit package
-> repeat
-> gaia publish
```

### 9.2 Server publish loop

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

## 10. Non-Goals

This document does not yet define:

- the final YAML/JSON schema for review reports
- the final retrieval policy for building integration environments
- the final server API route layout
- the final local command set for environment management
- whether package review and integration review should use one combined file or multiple sidecar files

Those are follow-up design tasks.

## 11. Immediate Follow-Ups

The next architectural follow-ups should be:

1. define the structured review report schema
2. extract or define a shared `review_core`
3. define the integration environment lockfile format
4. align CLI command semantics with review scopes
5. align server ingestion architecture with package review plus integration review

