# Foundations Documentation Policy

| 文档属性 | 值 |
|---------|---|
| 版本 | 0.1 |
| 日期 | 2026-03-22 |
| 状态 | **Current canonical** |
| 关联文档 | [README.md](README.md), [product-scope.md](product-scope.md), [system-overview.md](system-overview.md), [graph-ir.md](graph-ir.md) |

## 1. Purpose

This document defines how Gaia foundation docs should be written, updated, split, and superseded.

Its goal is to solve two recurring problems:

- old and new designs getting mixed into one file
- document layers becoming muddled, so high-level docs are too detailed and low-level docs are not precise enough

This policy is the canonical rule set for documentation structure in this repository.

## 2. Core Principles

### 2.1 One document, one primary job

A document should not simultaneously serve as:

- current canonical spec
- target design proposal
- implementation notes
- historical record

If a file is trying to do more than one of those jobs, split it.

### 2.2 One concept, one canonical home

A concept may be mentioned in many docs, but it should have only one canonical place where it is defined.

Examples:

- primary terminology belongs in meaning docs
- authored package syntax belongs in language spec
- structural graph shape belongs in Graph IR
- package review/curation workflow belongs in review docs

Other docs should reference the canonical home rather than silently redefining it.

### 2.3 Current, target, and history must be separated

Do not encode timeline confusion into a single narrative.

- **Current canonical** docs describe the present source of truth
- **Target design** docs describe the intended destination
- **Transitional** docs explicitly separate current runtime from target semantics
- retired or historical material belongs in archive/spec history, not in canonical docs

### 2.4 Product docs and reference docs need different resolutions

Some docs should orient the reader. Others should specify exact structure.

Do not force one document to do both.

## 3. Documentation Axes

Gaia foundation docs should be classified along three axes:

- `Level`: what resolution the document operates at
- `Status`: whether it is current canonical, target design, or transitional
- `Scope`: whether it is repo-wide, subsystem-specific, or component-specific

The most important rule is to keep these axes separate. Project scale should usually expand scope, not invent more levels.

## 4. Levels

Gaia foundation docs should fit into one of four primary levels.

### Overview

Answers:

- what Gaia is
- what Gaia is not
- who the product is for
- what the product boundary is

Should not contain:

- field-by-field schemas
- current runtime workaround details
- low-level storage or BP specifics

Examples:

- `product-scope.md`

### Foundation

Answers:

- what kinds of objects exist
- which objects are truth-apt
- which objects enter BP
- which distinctions are ontological vs workflow-only

Should not contain:

- API details
- storage tables
- command invocation mechanics

Examples:

- `semantics/terminology.md`
- `theory/theoretical-foundation.md`

### Architecture

Answers:

- what a subsystem is responsible for
- what it is not responsible for
- how artifacts move between subsystems
- what the boundary is between neighboring services/layers

Should not contain:

- full field reference tables
- low-level implementation quirks unless explicitly marked transitional

Examples:

- `system-overview.md`
- `server/architecture.md`

### Spec

Answers:

- exact shape of a package / IR / schema / command contract
- field meanings
- invariants
- allowed and disallowed cases

Should be precise enough that an implementer can use it as a reference.

Examples:

- `language/gaia-language-spec.md`
- `graph-ir.md`
- `server/storage-schema.md`
- `cli/command-lifecycle.md`

## 5. Scope

Every substantial doc should also have an explicit scope.

Recommended values:

- `Repo-wide`
- `Subsystem`
- `Component`

When Gaia grows, this axis usually does the scaling work. For example:

- `product-scope.md` is `Repo-wide`
- `server/architecture.md` is `Subsystem`
- a future storage ingestion design doc may be `Component`

## 6. Status Labels

Every substantial foundation doc should have an explicit status.

Recommended values:

- `Current canonical`
- `Target design`
- `Transitional`

If a file cannot clearly state its status, it is probably mixing roles.

### Transitional docs

Some docs need to describe the current implementation and the intended target at the same time.

Those docs should keep one of the four main levels above, but set `Status: Transitional`.

Typical example:

- `bp-on-graph-ir.md`

### Historical docs

Historical or ADR-style docs should not act as the primary source of truth for current semantics.

They should usually be handled by location first, not by active-status labeling:

- `docs/archive/` for archived historical docs
- `docs/superpowers/specs/` for dated proposals and design records

By default, retired docs should leave `docs/foundations/` entirely. If an old path must remain for compatibility, keep only a short redirect note rather than maintaining a long historical body in the active canonical area.

Examples:

- time-stamped specs in `docs/superpowers/specs/`
- archived historical docs

## 7. Audience and Out-of-Scope

For major docs, explicitly state:

- intended audience
- what the doc does define
- what the doc does not define

This prevents abstract docs from drifting into low-level detail and prevents low-level docs from bloating with theory.

## 8. Update Decision Rules

When changing docs, first classify the work:

### 8.1 Clarification

Use when:

- semantics are unchanged
- the doc is already the right canonical home
- wording or examples are just being improved

Action:

- edit the existing canonical doc

### 8.2 Replacement

Use when:

- the doc's core responsibility has changed
- the ontology or contract has materially changed
- keeping the old body would preserve misleading conceptual structure

Action:

- write a new or substantially rewritten canonical doc
- retire the old doc from the active canonical area
- move historical content to `docs/archive/` or keep it in dated specs if that history is still useful
- keep a thin redirect only when compatibility is worth the cognitive cost
- update README / related-doc links

### 8.3 Proposal

Use when:

- the design is not yet accepted
- the implementation is intentionally not yet aligned
- the purpose is exploration or decision-making

Action:

- write a spec / ADR / proposal doc outside the canonical flow
- do not silently turn proposal text into current canonical language

## 9. When to Split a Doc

Split a document when one or more of these is true:

- current runtime and target design have meaningfully diverged
- more than roughly one-third of the document would need to be rewritten to preserve accuracy
- the file is serving multiple levels at once
- a concept is being canonically defined in more than one place

Typical split patterns:

- current runtime reference vs target design
- foundation vs spec
- service boundary vs workflow details
- canonical doc vs archived historical doc

## 10. Retiring an Old Doc

When a doc is no longer the right source of truth:

1. move it out of the active canonical area
2. point to its replacements explicitly
3. preserve history in `docs/archive/` or dated specs when useful
4. keep a compatibility redirect only for especially stable or high-traffic paths
5. update major indexes and related-doc sections

Do not keep editing a retired conceptual model as if it were still active.

## 11. Required Companion Updates

When a canonical foundation doc is added, replaced, or materially re-scoped, also update the relevant index pages and pointers.

Typical companion files:

- `docs/README.md`
- `docs/foundations/README.md`
- `docs/foundations/README.zh-CN.md`
- related-doc headers in neighboring canonical docs
- any archived or compatibility-redirect pages affected by the change

## 12. Gaia-Specific Boundary Rules

These are especially important in this repository:

1. **Ontology is not language syntax.**
   Object classes belong in ontology docs; surface declarations belong in language docs.

2. **Language, Graph IR, and BP are distinct layers.**
   A term should not silently change meaning across those layers.

3. **Review and curation are distinct services.**
   Submission adjudication belongs to `ReviewService`; registry-wide offline maintenance belongs to `CurationService`.

4. **Formal external submissions prefer Gaia packages.**
   Package profile semantics belong with review/workflow docs, not in ad hoc side notes.

5. **Only closed, truth-apt scientific assertions are ordinary domain-BP participants.**
   Workflow artifacts, open questions, and internal curation outputs are not ordinary domain-BP variables by default.

## 13. Practical Writing Tests

### Test A: Is this doc too coarse?

After reading it, can a reader answer in a few sentences:

- what this subsystem is for
- what it is not for
- where its boundaries are

If not, the doc is probably too entangled in detail.

### Test B: Is this doc too vague?

After reading it, can an implementer answer:

- what fields/objects/interfaces are allowed
- what is forbidden
- what happens at edge cases

If not, the doc is probably not yet a true spec/reference.

## 14. Current Working Rule

Before making a non-trivial foundations doc change:

1. identify the doc's level
2. identify its status
3. identify its scope when that is relevant
4. decide whether the change is clarification, replacement, or proposal
5. update companion indexes and redirects in the same branch

If that process is skipped, doc drift is the default outcome.
