# V1 Dynamic Shared Knowledge Package Contracts

## Purpose

This document defines the V1 dynamic shared contracts used to construct, review, and optionally revise Gaia reasoning artifacts.

It covers:

1. how raw material is turned into package candidates
2. how reasoning chains are canonicalized
3. how review operates on reasoning chains
4. how optional revised packages may later be materialized

It assumes the V1 static structure defined in [knowledge-package-static.md](knowledge-package-static.md).

It does not cover:

- global Gaia graph integration
- cross-package identity resolution policy
- contradiction / retraction semantics
- prior / belief propagation
- BP

Those belong to later layers:

- V2: global Gaia graph integration
- V3: probabilistic semantics and propagation

## Dynamic Boundary

V1 dynamic is about shared artifact construction and shared artifact review contracts.

The main outputs are:

- package candidates
- knowledge artifact candidates
- review reports
- optional revised package candidates

These contracts are shared across local and server runtimes. Concrete implementations may differ by runtime, but they should produce and consume the same artifact shapes.

## Core Pipeline

The V1 dynamic pipeline is:

```text
draft input
-> canonicalization
-> review
-> optional revised package materialization
```

This is a logical pipeline, not necessarily a mandatory runtime sequence.

In particular:

- multiple review reports may exist for the same base package candidate
- revised packages are optional
- a package candidate may be stored and reused without immediate revision

## 1. Draft Input

Draft input may contain:

- article text
- notes
- code
- formal proof material
- tool outputs
- figures, tables, or datasets via external refs
- explicit questions
- statement-form problems or gaps
- partially implicit reasoning chains

At this stage, the material is not yet required to match the V1 static schema.

## 2. Canonicalization

Canonicalization converts raw material into a package candidate that follows the V1 static schema.

Conceptually:

```text
canonicalize(draft) -> package_candidate
```

### Canonicalization responsibilities

Canonicalization should:

1. identify candidate knowledge artifacts
2. classify candidate knowledge artifacts as `claim`, `question`, `setting`, or `action`
3. organize local reasoning into one or more reasoning chains
4. represent each reasoning chain as an ordered main path of chain steps
5. record only explicit or clearly recoverable non-main-path dependencies as `extra_inputs[]`
6. assign package-level roles such as motivations, key claims, follow-up questions, and shared settings

### Canonicalization principles

#### 1. Prefer the coarsest reasoning-chain segmentation that still preserves reviewable structure

Canonicalization should not over-fragment reasoning.

Create a new reasoning chain or a new action artifact only when it is needed to preserve:

- a distinct output claim or question
- an important process step such as a tool call
- a meaningful local reasoning boundary

#### 2. Do not over-infer hidden dependencies

Canonicalization should record:

- the ordered main path of the reasoning chain
- explicit extra dependencies when they are clearly present in the source

It should not aggressively invent hidden premises, contexts, or support relations. Those belong primarily to review.

#### 3. Use knowledge artifact typing conservatively

Use the following rules:

- if the content is a truth-apt result, use `claim`
- if the content is a genuine inquiry, use `question`
- if the content primarily sets background assumptions or interpretation, use `setting`
- if the content primarily expresses a process step, use `action`

#### 4. Treat statement-form problems as claims

Examples:

- "Current methods do not explain X." -> `claim`
- "Why does X happen?" -> `question`

#### 5. Keep package roles separate from knowledge artifact identity

Canonicalization may assign:

- `motivation_artifact_ids[]`
- `key_claim_ids[]`
- `follow_up_question_ids[]`
- `shared_setting_ids[]`

But these are package-level roles, not knowledge-artifact-level identity.

### Canonicalization output

The output is a package candidate whose reasoning chains, chain steps, and knowledge artifacts match the V1 static schema.

V1 does not require canonicalization to fully resolve whether a newly extracted knowledge artifact is identical to an already known global knowledge artifact. Exact cross-package identity resolution is deferred to later layers.

## 3. Review

Review operates on a canonicalized package candidate.

Conceptually:

```text
review(package_candidate) -> review_report
```

Review does not silently mutate the package candidate.

### Review unit

The primary review unit is the `reasoning_chain`.

The main object of evaluation is usually the final output of the reasoning chain:

- if the last chain step is a `claim`, review evaluates that output claim relative to the reasoning chain
- if the last chain step is a `question`, review evaluates whether the question is well-motivated by the reasoning chain

### Review of claim-output reasoning chains

For a reasoning chain whose final output is a `claim`, review should:

1. inspect the ordered main path and any `extra_inputs[]`
2. assign a local `conditional_prior` to the output claim
3. identify weak points in the reasoning chain
4. when possible, externalize a weak point into a candidate `claim` or `setting`
5. classify the resulting dependency as `strong` or `weak`

### Meaning of `conditional_prior`

`conditional_prior` means:

the probability that the output claim is correct, assuming the directly used earlier chain steps and explicitly used extra inputs are correct.

This is a local reasoning-chain-level score. It is not the same as a future global belief score.

### Weak points

A weak point is any part of the reasoning chain that materially limits confidence in the output claim.

A weak point may correspond to:

- a hidden but externalizable statement
- a missing setting
- a weak inference step
- a tool-use concern
- an over-strong output claim

When a weak point can be turned into an object, review should prefer:

- candidate `claim`
- or candidate `setting`

When it cannot be cleanly externalized, it should remain a rationale-only review note.

### Strong vs weak dependency

If the extracted weak point were made explicit:

- `strong` means the reasoning chain would largely fail without it
- `weak` means the reasoning chain would still partly stand, but with reduced strength, scope, or interpretability

### Review of question-output reasoning chains

For a reasoning chain whose final output is a `question`, review does not need the same claim-style `conditional_prior`.

Instead, review should focus on:

- whether the question is well-motivated by the preceding reasoning chain
- whether the question follows from the observed gap or tension
- whether the question is too broad, too vague, or mismatched to the preceding material

### Minimal review report

```text
review_report {
  review_id
  package_id
  chain_reviews[]
  notes?
  metadata?
}
```

```text
chain_review {
  chain_id
  output_artifact_id
  output_artifact_kind
  conditional_prior?      # claim-output reasoning chains
  weak_points[]?
  notes?
}
```

```text
weak_point {
  target_step_id
  proposed_artifact_kind? # claim | setting
  proposed_content?
  dependency_strength?    # strong | weak
  rationale
}
```

### Multiple review reports

Multiple review reports may coexist for the same package candidate.

V1 does not require a single authoritative review result.

Later revision may:

- choose one review report
- combine several compatible review reports
- or defer conflicting review reports to later adjudication

## 4. Optional Revised Package Materialization

Revision is optional at the V1 dynamic layer.

Conceptually:

```text
materialize_revised_package(base_package, selected_review_reports) -> revised_package
```

This step is not required after every review.

### Possible revision actions

Optional revision may:

- insert newly externalized weak points as explicit `claim` or `setting` artifacts
- add corresponding chain steps into one or more reasoning chains
- update `extra_inputs[]` to reflect the new explicit dependency
- split an over-compressed reasoning chain into multiple reasoning chains
- rewrite or replace an output claim
- rewrite or replace an output question
- update package-level roles such as motivations, key claims, or follow-up questions

### Revision rule

Revision should preserve provenance.

It should not silently erase the structure of the base package. It should produce a revised package candidate that can itself be reviewed again.

## What Canonicalization Must Not Do

Canonicalization should not:

- over-infer hidden dependencies that are not clearly grounded in the source material
- over-fragment the draft into many tiny reasoning chains or action artifacts
- force package-level roles into knowledge artifact identity
- assume that every problem-like statement must be a `question`

## What Review Must Not Do

Review should not:

- silently mutate the package candidate
- confuse local reasoning-chain-level conditional scores with global belief
- force every weak point into an externalized knowledge artifact when that is not natural
- treat package-level roles as if they were knowledge artifact identity

## Deferred Topics

The following topics are intentionally deferred:

- exact graph-level identity resolution
- global support / contradiction / retraction semantics
- prior / belief propagation
- BP
- cross-package belief aggregation

Those belong to later documents.
