# Review and Curation Service Boundaries

| 文档属性 | 值 |
|---------|---|
| 版本 | 0.1 |
| 日期 | 2026-03-22 |
| 状态 | **Target architecture — foundation baseline** |
| 关联文档 | [publish-pipeline.md](publish-pipeline.md) — package publish contract, [package-artifact-profiles.md](package-artifact-profiles.md) — Gaia package profile semantics, [architecture.md](architecture.md) — historical broader build/review split, [../server/architecture.md](../server/architecture.md) — server architecture, [../theory/scientific-ontology.md](../theory/scientific-ontology.md) — object model for claims, review artifacts, and curation artifacts |

---

## 1. Purpose

This document fixes the boundary between two easily conflated services:

- `ReviewService`
- `CurationService`

The goal is to stop using "review" as an umbrella word for every kind of judgment, graph discovery, and cleanup.

## 2. Core Principle

The boundary is:

- **`ReviewService` decides whether a specific submission is acceptable now**
- **`CurationService` maintains and improves the accepted global graph over time**

These are related, but they are not the same job.

## 3. Scope Table

| | `ReviewService` | `CurationService` |
|---|---|---|
| Primary scope | one submission / package | registry-wide accepted graph |
| Trigger | publish / check / review cycle | offline schedule or server maintenance trigger |
| Time horizon | immediate accept / revise / reject decision | long-lived graph quality and discovery |
| Main question | "Can this package pass now?" | "What should the global graph repair, investigate, or enrich next?" |
| Input context | bounded package environment | full or large-scope global graph |
| Output type | findings, questions, verdict | suggestions, accepted graph changes, internal research jobs |

## 4. `ReviewService`

### 4.1 Responsibility

`ReviewService` is the submission-scoped judgment boundary.

It is responsible for:

- deterministic validation of submitted artifacts
- package-local semantic review
- bounded-context consistency checks
- publish readiness judgment
- conservative identity assignment or identity-related findings

### 4.2 Typical outputs

- `ReviewFinding`
- `ReviewerQuestion`
- `ReviewVerdict`
- `CanonicalBinding` or conservative identity candidates

### 4.3 What it may inspect

`ReviewService` may inspect:

- the package's source and compiled artifacts
- a bounded package environment
- alignment candidates already retrieved for that submission

It may ask:

- does the chain cohere?
- are the premises correctly classified?
- is the package internally self-consistent?
- are obvious nearby duplicates or contradictions relevant to acceptance?

### 4.4 What it must not become

`ReviewService` must not quietly expand into:

- global N:N traversal
- open-ended registry mining
- long-running abstraction / induction discovery
- broad graph cleanup
- speculative graph rewriting outside submission adjudication

## 5. `CurationService`

### 5.1 Responsibility

`CurationService` is the registry-scoped maintenance and enrichment service.

It is responsible for:

- discovering missed duplicates, equivalences, and contradictions
- abstraction / generalization candidate mining
- independent-evidence and loop audits
- graph hygiene and structure repair
- long-lived global consistency improvement

### 5.2 Typical outputs

- `CurationSuggestion`
- `ConflictCandidate`
- `StructureReport`
- `AcceptedCurationChange`
- internal curation audit logs

### 5.3 Default operating mode

`CurationService` is primarily a **server-internal offline service**.

Its jobs are usually satisfiable by:

- graph traversal
- retrieval
- similarity search
- BP diagnostics
- server-side LLM review

Therefore curation work is **not** automatically published as external research tasks.

## 6. Artifact Classes

### 6.1 Review artifacts

Review artifacts belong to the submission flow:

- `ReviewFinding`
- `ReviewerQuestion`
- `Rebuttal`
- `EditorVerdict`

These are package-oriented and tied to a review cycle.

### 6.2 Curation artifacts

Curation artifacts belong to global maintenance:

- `CurationSuggestion`
- `ConflictCandidate`
- `StructureIssue`
- `LoopAuditReport`
- `IndependentEvidenceAudit`

These are not automatically accepted graph truth.

### 6.3 Accepted graph changes

A curation artifact becomes graph truth only after acceptance by the curation workflow.

Examples:

- accepted contradiction relation
- accepted equivalence relation
- accepted merge
- accepted schema / instantiation insertion
- accepted graph completion

## 7. Internal Curation Jobs vs Escalated Investigation

Not every unresolved issue should become an external agent task.

### 7.1 Default: internal curation job

Use `CurationService` directly when the issue can be handled using:

- current graph content
- local graph traversal
- retrieval over registry data
- server-side BP diagnostics
- server-side LLM judgment

Examples:

- duplicate detection
- contradiction candidate triage
- equivalence candidate triage
- loop audit
- dangling-factor repair

### 7.2 Escalated investigation

Escalate beyond internal curation only when the issue requires something outside the current graph and server context, such as:

- new literature search
- new experiment or data collection
- package-author intervention
- open-ended domain research not reducible to graph-local analysis

Escalation is the exception, not the default curation path.

## 8. Relation to Gaia Packages

The default external artifact in Gaia remains the Gaia package.

However, service boundaries stay distinct:

- `ReviewService` judges packages
- `CurationService` maintains the accepted graph

Package profile matters here:

- `knowledge`, `review`, and `rebuttal` are natural package-facing artifacts
- `investigation` is possible when an issue is intentionally externalized
- ordinary internal `CurationSuggestion` outputs are still not Gaia packages by default

If curation eventually needs a formal, reviewable proposal artifact, that proposal may be expressed as a Gaia package or package-like submission, but the service boundary does not collapse.

## 9. Decision Rules

Use these rules when deciding ownership:

1. If the task asks whether a submitted package is acceptable now, it belongs to `ReviewService`.
2. If the task asks what the accepted registry graph should repair, merge, relate, or enrich next, it belongs to `CurationService`.
3. If the issue is satisfiable from the current graph plus server-side tooling, keep it inside `CurationService`.
4. If the issue requires new external evidence or open-ended research, escalate explicitly instead of smuggling it into curation or review.

## 10. Consequences for Other Docs

Later docs should align to this split:

- `publish-pipeline.md` should treat review as a submission workflow, not as a registry-maintenance workflow
- server architecture docs should place curation in offline global maintenance
- language and Graph IR docs should not model internal curation candidates as if they were already accepted knowledge

## 11. Current Direction

For the foundation reset, Gaia should standardize on:

- **`ReviewService`** as the package-facing adjudication service
- **`CurationService`** as the server-internal global maintenance service

This is the minimum clean split needed before deeper work on BP, curation, and investigation workflows.
