# Gaia Package Artifact Profiles

| 文档属性 | 值 |
|---------|---|
| 版本 | 0.1 |
| 日期 | 2026-03-22 |
| 状态 | **Target architecture — foundation baseline** |
| 关联文档 | [publish-pipeline.md](publish-pipeline.md) — publish workflow, [service-boundaries.md](service-boundaries.md) — review/curation split, [../language/gaia-language-spec.md](../language/gaia-language-spec.md) — Gaia package surface, [../theory/scientific-ontology.md](../theory/scientific-ontology.md) — ontology boundary |

---

## 1. Purpose

This document defines which formal external artifacts in Gaia should be represented as Gaia packages, and how their semantics differ.

Its core claim is:

- **formal, reviewable external submissions should prefer Gaia packages**
- **internal service artifacts do not automatically need to be Gaia packages**

## 2. Core Principle

Gaia packages are not only for ordinary research knowledge.

They are the preferred artifact format for any submission that must be:

- reviewed
- rebutted
- versioned
- cited
- merged or rejected

The main distinction between artifact kinds should therefore live in a **package profile**, not in a completely separate submission format.

## 3. Profile Table

| Profile | Typical producer | Main purpose | Merge behavior |
|---|---|---|---|
| `knowledge` | author / research agent | publish substantive scientific knowledge | accepted content may enter the LKM directly |
| `investigation` | author / research agent responding to an explicit investigation target | submit targeted follow-up evidence, candidate relations, or focused research results | accepted portions may inform review or later be promoted into accepted knowledge |
| `review` | review engine / reviewer | express findings, objections, and review-side structured arguments | does not merge as ordinary knowledge; attaches to the reviewed package |
| `rebuttal` | author / submitting agent | respond to review findings with revisions or counter-arguments | does not merge as ordinary knowledge by itself; informs the review verdict and any revised package |

These profiles share the same language surface. What changes is:

- review policy
- expected provenance
- integration behavior
- whether accepted content enters the main knowledge graph directly

## 4. `knowledge` Packages

`knowledge` is the default profile.

It is used for:

- papers or paper replacements
- structured scientific arguments
- explicit claims, settings, questions, actions, and relations intended as substantive package content

When accepted, its package-owned knowledge may be integrated into the LKM under the usual publish pipeline.

## 5. `investigation` Packages

`investigation` is for targeted research outputs, not for routine global curation.

Typical use cases:

- responding to an explicit investigation request
- submitting a focused contradiction audit result
- presenting newly found evidence relevant to an existing dispute
- proposing a candidate relation or missing premise with supporting argument

Important boundary:

- an `investigation` package is still a formal submission
- it is **not** the default output of `CurationService`

Internal curation work should usually remain internal. `investigation` is for cases where an external or agent-authored submission should enter a formal review/rebuttal path.

## 6. `review` Packages

`review` packages make structured review first-class without confusing them with accepted base knowledge.

They may contain:

- findings
- structured objections
- suggested revisions
- candidate mappings or relation concerns

Their semantics are:

- attached to a target submission
- reviewable and rebuttable
- not automatically merged into the LKM as ordinary domain knowledge

They belong to the review fiber over a package, not to the package's base scientific content.

## 7. `rebuttal` Packages

`rebuttal` packages are the formal author response to `review` artifacts.

They may include:

- acceptance of requested revisions
- explicit counter-arguments
- proposed alternative relation interpretation
- clarifications about intended scope

A `rebuttal` package may coexist with a revised `knowledge` package version, or it may primarily carry response structure. The exact workflow can vary, but the profile clarifies that the artifact is part of the review loop rather than ordinary base knowledge.

## 8. Package-Level Metadata

Packages should eventually record profile-level metadata such as:

- `artifact_profile`
- `subject_package`
- `subject_version`
- `in_response_to`
- `task_ref`
- `disposition`

Examples:

- `knowledge` usually has no `in_response_to`
- `review` points at the submitted package under review
- `rebuttal` points at one or more review artifacts
- `investigation` may point at an investigation target or open issue

The exact manifest location is deferred. The foundation commitment is to the **conceptual metadata**, not yet to a concrete TOML/YAML field layout.

## 9. BP and Integration Rules

Artifact profile affects how package content participates in later system stages.

Default rule:

- accepted `knowledge` content may be lowered into the shared knowledge graph and later BP
- `review` and `rebuttal` artifacts are structured meta-knowledge and do not directly participate in ordinary domain BP by default
- `investigation` content is case-dependent and usually requires explicit acceptance or promotion before becoming ordinary graph truth

So "written in Gaia language" does **not** automatically imply "immediately BP-bearing in the main graph."

## 10. Relation to `ReviewService` and `CurationService`

This profile system does not collapse service boundaries.

- `ReviewService` judges package submissions across these profiles
- `CurationService` remains primarily server-internal and offline

Most internal curation outputs should stay as internal curation artifacts, not formal package submissions.

Only when an issue is intentionally externalized into a formal submission should it become an `investigation` or related Gaia package.

## 11. Consequences

This profile model gives Gaia one consistent answer to a recurring question:

- **Yes, formal submissions should prefer Gaia packages**
- **No, not every internal report or curation suggestion should immediately be one**

That is the minimum clean rule set needed to keep:

- one dominant external artifact format
- clean review/rebuttal workflows
- clean service boundaries
- a clear distinction between knowledge, meta-knowledge, and internal maintenance state
