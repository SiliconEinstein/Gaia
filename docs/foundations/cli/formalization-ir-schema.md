# Gaia Formalization IR Schema

| 文档属性 | 值 |
|---------|---|
| 版本 | 0.1 |
| 日期 | 2026-03-13 |
| 状态 | **Draft — target local schema** |
| 关联文档 | [formalization-skill.md](formalization-skill.md), [boundaries.md](boundaries.md), [command-lifecycle.md](command-lifecycle.md), [../language/gaia-language-spec.md](../language/gaia-language-spec.md), [../language/gaia-language-design.md](../language/gaia-language-design.md) |

> **Note:** This document defines the local artifacts used by conclusion-first formalization skills. Models should produce a structural `draft_ir` and a later `semantic_annotation`; deterministic code should emit current Gaia YAML source from those artifacts. Neither artifact is a new authored language surface, and neither is submitted as package Graph IR.

---

## 1. Purpose

The formalization schema exists to separate:

- structural reconstruction of an article or other source bundle
- later semantic annotation of support roles and probabilities
- deterministic source emission
- build validation and repair

Without this separation, formalization collapses into one-shot YAML generation, which makes provenance, auditability, and repair loops too brittle.

The contract is:

```text
input adapters / extraction
    -> formalization draft IR
    -> semantic annotation
    -> deterministic YAML emitter
    -> gaia build
```

## 2. Scope

This schema covers local formalization artifacts only.

It defines:

- normalized source-bundle references
- package and module drafts
- knowledge-unit drafts
- chain drafts
- semantic annotation records
- issue and repair metadata
- emission-related constraints

It does **not** define:

- Gaia authored source syntax itself
- Graph IR
- server-side review artifacts
- registry-side identity assignment

## 3. Design Principles

### 3.1 Provenance-first

Every emitted semantic unit should be backed by source spans or explicitly labeled as inferred.

### 3.2 Conclusion-first structure

For article-like inputs, the structural draft should begin from motivation, conclusions, open questions, and conclusion chains, not from an undifferentiated bag of extracted propositions.

### 3.3 Annotation after structure

The draft IR should describe what the article is arguing and what support points matter. The later semantic-annotation stage should decide which support points are `premise` vs `context` and what priors / conditional probabilities they receive.

### 3.4 Repair-friendly

The artifacts must support small updates. A repair step should be able to modify one unit, one chain, one annotation, or one issue without rewriting the entire package.

### 3.5 Deterministic emission

The emitter should not make semantic decisions that were absent from the artifacts. If emission requires a semantic choice, that choice belongs in either `draft_ir` or `semantic_annotation`.

### 3.6 Conservative semantics

The artifacts should preserve uncertainty about support level and unresolved gaps rather than silently pretending they are solved.

### 3.7 Minimal V1 artifacts

V0.1 should stay close to the authored surface.

- `draft_ir` should record only the structure needed to emit modules, knowledge units, and chains.
- `semantic_annotation` should record only dependency-role and probability judgments.
- the emitter should be a thin transliteration layer, not a second planner.

## 4. Artifact Relationship

The formalization workflow writes a set of sidecars:

```text
.gaia/formalize/
  source_bundle.json
  draft_ir.json
  semantic_annotation.json
  source_map.json
  critic_report.json
  repair_log.json
  run_summary.json
```

This document defines the schema for:

- `source_bundle.json`
- `draft_ir.json`
- `semantic_annotation.json`
- the shared record shapes reused by `source_map.json`, `critic_report.json`, and `repair_log.json`

## 5. ID Namespaces

Each entity type has its own stable prefix.

| Entity | Prefix | Example |
|---|---|---|
| Source bundle | `src_` | `src_01H...` |
| Source document | `doc_` | `doc_01H...` |
| Source block | `blk_` | `blk_01H...` |
| Module draft | `mod_` | `mod_01H...` |
| Knowledge unit draft | `ku_` | `ku_01H...` |
| Chain draft | `ch_` | `ch_01H...` |
| Issue | `issue_` | `issue_01H...` |
| Repair step | `repair_` | `repair_01H...` |

IDs must be stable across repair rounds unless the entity is materially replaced.

## 6. Source Bundle Schema

### 6.1 Top-level object

```yaml
schema_version: formalize.source_bundle.v0.1
bundle_id: src_...
kind: paper | webpage | thought_trace | markdown | plain_text | mixed
created_at: "2026-03-13T12:34:56Z"
documents: [...]
metadata:
  title: "..."
  language: "en"
  ingestion_notes: "..."
```

### 6.2 `SourceDocument`

```yaml
document_id: doc_...
kind: paper | webpage | thought_trace | markdown | plain_text | note
title: "..."
uri: "..."
authors: ["..."]
published_at: "..."
metadata:
  source_format: "html"
  venue: "..."
blocks: [...]
```

### 6.3 `SourceBlock`

```yaml
block_id: blk_...
order: 17
section: "Methods"
text: "..."
metadata:
  page: 4
  paragraph_label: "2.3"
```

### 6.4 Invariants

- `documents[*].document_id` must be unique within the bundle.
- `blocks[*].block_id` must be unique within the bundle.
- `order` must be strictly increasing inside each document.
- `text` may be empty only for structural placeholder blocks; these should be rare.

## 7. Draft IR Top-Level Schema

### 7.1 `FormalizationDraftIR`

```yaml
schema_version: formalize.draft_ir.v0.1
bundle_id: src_...
policy:
  mode: grounded_only | interpretive
  allow_inferred_in_source: false
  max_inferred_ratio: 0.15
  require_semantic_annotation: true
  default_conclusion_prior: 0.5
package_draft: {...}
modules: [...]
knowledge_units: [...]
chains: [...]
issues: [...]
summary:
  package_title: "..."
  package_description: "..."
  unresolved_count: 3
```

### 7.2 Top-level invariants

- `bundle_id` must refer to an existing `SourceBundle.bundle_id`.
- all `module_id`, `unit_id`, `chain_id`, and `issue_id` values must be unique.
- every referenced unit/module/chain must exist.
- no dependency role or probability judgment should appear in `draft_ir`.
- no emitted package should depend on implied ordering that is absent from explicit fields.

## 8. Package Draft Schema

### 8.1 `PackageDraft`

```yaml
name: falling_bodies_formalized
version: "0.1.0"
description: "Formalized package derived from source bundle src_..."
module_order: [mod_motivation, mod_reasoning, mod_setting, mod_follow_up]
exports: [ku_main_conclusion]
metadata:
  formalization_kind: paper
  source_bundle_id: src_...
  title_hint: "Galileo on Falling Bodies"
```

### 8.2 Invariants

- `name` must be a valid package identifier under current package rules.
- `module_order` must include every emitted module exactly once.
- `exports` must reference emitted knowledge units only.

## 9. Module Draft Schema

### 9.1 `ModuleDraft`

```yaml
module_id: mod_reasoning
name: reasoning
role: reasoning | setting | motivation | follow_up_question | other
knowledge_unit_ids: [ku_01, ku_02]
chain_ids: [ch_01]
exports: [ku_02]
metadata:
  rationale: "Core reasoning extracted from result and discussion sections"
```

### 9.2 Invariants

- each `knowledge_unit_id` must exist in `knowledge_units`.
- each `chain_id` must exist in `chains`.
- a unit may appear in multiple modules only if later versions explicitly allow shared materialization; v0.1 disallows this.
- `exports` must be a subset of `knowledge_unit_ids`.

## 10. Knowledge Unit Schema

### 10.1 `KnowledgeUnitDraft`

```yaml
unit_id: ku_main_claim
kind: claim | setting | question | infer_action | ref
name_hint: main_claim
content: "Objects in vacuum fall at the same rate regardless of mass."
support_level: explicit | paraphrased | inferred
source_spans:
  - document_id: doc_main
    block_id: blk_17
    start_char: 12
    end_char: 96
    quote: "..."
confidence: 0.91
status: proposed | accepted | rejected | deferred
metadata:
  section_role: result
  structural_role: motivation | conclusion | open_question | support | intermediate | other
  extraction_notes: "..."
```

### 10.2 `SourceSpanRef`

```yaml
document_id: doc_main
block_id: blk_17
start_char: 12
end_char: 96
quote: "..."
```

### 10.3 Field rules

| Field | Meaning |
|---|---|
| `kind` | maps directly to the current Gaia authored surface, except `infer_action` uses the authored subtype rather than generic `action` |
| `name_hint` | emitter-normalized into the final YAML identifier |
| `content` | authored text body or action description |
| `support_level` | provenance status, not belief/probability |
| `confidence` | local formalization confidence, not Gaia prior |
| `status` | local workflow state, not source-language semantics |
| `metadata.structural_role` | article-formalization hint only; not a first-class authored type |

### 10.4 Invariants

- `support_level = explicit | paraphrased` requires at least one `source_span`.
- `support_level = inferred` may omit spans, but the omission should be justified by an issue or metadata note.
- `kind = ref` should not carry free-form claim text; it should carry reference-target metadata in `metadata.target`.
- `kind = infer_action` should describe a reusable reasoning or method step, not a conclusion.

### 10.5 `ref` metadata contract

For `kind = ref`, metadata should include:

```yaml
metadata:
  target:
    package: external_pkg
    version: "1.2.0"
    module: reasoning
    knowledge_name: main_claim
```

If the target cannot be grounded to a package-scoped reference yet, the unit should remain a non-`ref` draft plus an issue, rather than emitting an invalid `ref`.

## 11. Chain Schema

### 11.1 `ChainDraft`

```yaml
chain_id: ch_main
name_hint: main_derivation
conclusion_unit_id: ku_main_claim
support_unit_ids: [ku_p1, ku_c1]
action_unit_id: ku_action_main
support_level: explicit | paraphrased | inferred
reasoning_summary: "..."
support_analysis:
  - unit_id: ku_p1
    why_it_matters: "This assumption is load-bearing for the argument."
  - unit_id: ku_c1
    why_it_matters: "This setting frames the thought experiment."
status: proposed | accepted | rejected | deferred
metadata:
  source_section: "Discussion"
```

### 11.2 Semantics

- `support_unit_ids` are the support points that matter to the conclusion chain before they are classified as `premise` or `context`.
- `support_analysis` records why a support point matters and is where the formalization skill captures article-specific weak points.
- if a reasoning path has multiple semantically meaningful intermediate steps, those steps should usually be promoted into explicit intermediate `claim` units and modeled as multiple chains rather than hidden inside one chain.

### 11.3 Invariants

- `conclusion_unit_id` must exist and must not also appear in `support_unit_ids`.
- `support_unit_ids` must be unique.
- `support_analysis[*].unit_id` must match `support_unit_ids` exactly.
- `action_unit_id` must reference a `KnowledgeUnitDraft` with `kind = infer_action`.
- `support_level = explicit | paraphrased` requires the chain to be grounded by spans on its member units or its own metadata.
- `ChainDraft` must not encode `premise/context` or probability judgments directly.

## 12. Semantic Annotation Schema

`semantic_annotation.json` records the probability-facing judgments that are intentionally delayed until after structural formalization.

### 12.1 Top-level object

```yaml
schema_version: formalize.semantic_annotation.v0.1
bundle_id: src_...
draft_ir_hash: "sha256:..."
chain_annotations: [...]
node_priors: [...]
summary:
  annotated_chain_count: 3
  node_prior_count: 5
  deferred_count: 1
```

### 12.2 `ChainAnnotation`

```yaml
chain_id: ch_main
support_roles:
  - unit_id: ku_p1
    role: premise | context
    rationale: "If this is false, the conclusion largely collapses."
  - unit_id: ku_c1
    role: context
    rationale: "Frames interpretation but does not carry the full burden."
conditional_probability: 0.84
conditional_probability_rationale: "Assuming the support points hold, the argument is fairly strong."
status: proposed | accepted | rejected | deferred
metadata:
  annotation_notes: "..."
```

### 12.3 `NodePriorAnnotation`

```yaml
unit_id: ku_p1
prior: 0.35
rationale: "This inherited background claim is controversial inside the source article."
status: proposed | accepted | rejected | deferred
metadata:
  prior_basis: source_assertion | common_background | external_reference | analyst_judgment
```

### 12.4 Semantics

- `support_roles` classifies each structural support point as either:
  - `premise` — if false, the chain substantially fails
  - `context` — if false, the chain may still stand, but its reliability is materially affected
- `conditional_probability` is the chain-level probability judgment under the assumption that its supports hold in the assigned roles.
- `node_priors` should normally be provided for support units that are not themselves derived as in-package conclusions.
- if a support unit is another in-package conclusion, the semantic annotation should classify its role in the downstream chain, but it need not assign a fresh node prior in v0.1.

### 12.5 Invariants

- every `chain_id` must exist in `draft_ir.chains`.
- for an accepted `ChainAnnotation`, `support_roles[*].unit_id` must cover the corresponding `ChainDraft.support_unit_ids` exactly once.
- `conditional_probability` must be in the current authored-language valid range for chain-level probability annotations.
- `prior` must be in the current authored-language valid range for knowledge priors; `setting` may use `1.0` only if the authored surface permits it.
- `NodePriorAnnotation.unit_id` must refer to a `KnowledgeUnitDraft` that exists in `draft_ir`.

## 13. Issue Schema

### 13.1 `FormalizationIssue`

```yaml
issue_id: issue_unsupported_01
severity: info | warning | blocking
kind: unsupported_claim | weak_chain | missing_source | duplicate_unit | unresolved_ref | schema_gap | missing_annotation
target_type: package | module | unit | chain | annotation
target_id: ku_main_claim
message: "..."
recommended_action: keep_sidecar | revise_ir | revise_annotation | drop_unit | request_user_decision
metadata:
  related_ids: [ku_other]
```

### 13.2 Invariants

- blocking issues must be resolved before a run is marked successful.
- an emitted YAML package may still exist while blocking issues remain, but such a run should not be considered finalized.

## 14. Source Map Schema

`source_map.json` is a projection of the draft and annotation artifacts into emitted source locations.

### 14.1 `SourceMapRecord`

```yaml
emitted_path: reasoning.yaml
emitted_object_type: knowledge | chain | probability
emitted_name: main_claim
source_ir_id: ku_main_claim
annotation_ref:
  kind: node_prior | support_role | conditional_probability
  chain_id: ch_main
  unit_id: ku_p1
source_spans:
  - document_id: doc_main
    block_id: blk_17
    start_char: 12
    end_char: 96
    quote: "..."
support_level: paraphrased
```

This artifact exists so audits do not need to reconstruct provenance and annotation lineage solely from the other sidecars.

## 15. Critic Report Schema

### 15.1 `CriticReport`

```yaml
schema_version: formalize.critic_report.v0.1
bundle_id: src_...
draft_ir_hash: "sha256:..."
semantic_annotation_hash: "sha256:..."
summary: "..."
issues: [...]
metrics:
  total_units: 14
  inferred_units: 2
  annotated_chains: 3
  blocking_issues: 1
```

The critic report reuses `FormalizationIssue` as its issue record.

## 16. Repair Log Schema

### 16.1 `RepairLog`

```yaml
schema_version: formalize.repair_log.v0.1
bundle_id: src_...
steps:
  - repair_id: repair_01
    timestamp: "2026-03-13T12:45:00Z"
    reason: build_error | critic_issue | user_feedback
    input_issue_ids: [issue_01]
    changed_ids: [ku_main_claim, ch_main]
    changed_artifacts: [draft_ir, semantic_annotation]
    summary: "Promoted one weak point into an explicit support node and reclassified another as context."
```

### 16.2 Invariants

- `changed_ids` must refer to IDs present in either the old or new draft or annotation set.
- repair logs should be append-only.

## 17. Policy Schema

### 17.1 `FormalizationPolicy`

```yaml
mode: grounded_only | interpretive
allow_inferred_in_source: false
max_inferred_ratio: 0.15
require_source_span_for_emission: true
require_semantic_annotation: true
default_conclusion_prior: 0.5
prefer_fewer_chains: true
```

### 17.2 Semantics

- `grounded_only` means only `explicit` and `paraphrased` content should be emitted by default.
- `interpretive` allows inferred bridge units to remain in draft IR and, if explicitly permitted, enter source.
- `max_inferred_ratio` is evaluated over emitted units, not all draft units.
- `require_semantic_annotation` means the emitter must not guess `premise/context` or probability values.
- `default_conclusion_prior` is a policy fallback used only if the current authored surface requires a conclusion prior that was not explicitly annotated.

## 18. Deterministic Emission Contract

The emitter takes:

- `FormalizationDraftIR`
- `SemanticAnnotation`
- `SourceBundle`
- `FormalizationPolicy`

And produces:

- package root YAML files
- `source_map.json`

The emitter may:

- normalize names minimally when required by authored-surface identifier rules
- choose file ordering according to `PackageDraft.module_order`
- emit one YAML file per `ModuleDraft`
- translate `ChainAnnotation.support_roles` into authored `dependency: direct/indirect`
- translate `NodePriorAnnotation.prior` into authored knowledge `prior`
- translate `ChainAnnotation.conditional_probability` into the authored chain-application `prior`
- apply a policy-defined fallback for conclusion priors only when the authored surface requires one and no explicit annotation exists

The emitter may **not**:

- invent new modules or regroup existing ones
- invent new units
- change `support_level`
- guess `premise/context` roles absent annotation support
- guess priors or conditional probabilities absent annotation support, except for the explicit policy fallback above
- silently drop blocking issues

## 19. Minimal Example

### 19.1 `draft_ir.json`

```yaml
schema_version: formalize.draft_ir.v0.1
bundle_id: src_galileo
policy:
  mode: grounded_only
  allow_inferred_in_source: false
  max_inferred_ratio: 0.1
  require_semantic_annotation: true
  default_conclusion_prior: 0.5
package_draft:
  name: galileo_tied_balls_formalized
  version: "0.1.0"
  description: "Formalized from source bundle src_galileo"
  module_order: [mod_motivation, mod_reasoning, mod_setting, mod_follow_up]
  exports: [ku_vacuum_claim, ku_air_question]
modules:
  - module_id: mod_motivation
    name: motivation
    role: motivation
    knowledge_unit_ids: [ku_question]
    chain_ids: []
    exports: []
  - module_id: mod_setting
    name: setting
    role: setting
    knowledge_unit_ids: [ku_env]
    chain_ids: []
    exports: []
  - module_id: mod_follow_up
    name: follow_up
    role: follow_up_question
    knowledge_unit_ids: [ku_air_question]
    chain_ids: []
    exports: [ku_air_question]
  - module_id: mod_reasoning
    name: reasoning
    role: reasoning
    knowledge_unit_ids: [ku_heavy, ku_tied_action, ku_vacuum_claim]
    chain_ids: [ch_vacuum]
    exports: [ku_vacuum_claim]
knowledge_units:
  - unit_id: ku_question
    kind: question
    name_hint: falling_rate_question
    content: "Why do bodies of different mass appear to fall differently in ordinary observation?"
    support_level: paraphrased
    source_spans:
      - document_id: doc_01
        block_id: blk_02
        start_char: 0
        end_char: 80
        quote: "..."
    confidence: 0.82
    status: accepted
    metadata:
      structural_role: motivation
  - unit_id: ku_air_question
    kind: question
    name_hint: air_resistance_question
    content: "How should differential fall in air be modeled once resistance is included explicitly?"
    support_level: paraphrased
    source_spans:
      - document_id: doc_01
        block_id: blk_18
        start_char: 0
        end_char: 82
        quote: "..."
    confidence: 0.79
    status: accepted
    metadata:
      structural_role: open_question
  - unit_id: ku_env
    kind: setting
    name_hint: vacuum_env
    content: "Consider the case of free fall in vacuum."
    support_level: paraphrased
    source_spans:
      - document_id: doc_01
        block_id: blk_03
        start_char: 0
        end_char: 42
        quote: "..."
    confidence: 0.84
    status: accepted
    metadata:
      structural_role: support
  - unit_id: ku_heavy
    kind: claim
    name_hint: heavier_falls_faster
    content: "Heavier objects fall faster than lighter ones."
    support_level: explicit
    source_spans:
      - document_id: doc_01
        block_id: blk_07
        start_char: 0
        end_char: 45
        quote: "..."
    confidence: 0.93
    status: accepted
    metadata:
      structural_role: support
  - unit_id: ku_tied_action
    kind: infer_action
    name_hint: tied_balls_analysis
    content: "Analyze the tied-bodies thought experiment under the stated premise and environment."
    support_level: paraphrased
    source_spans:
      - document_id: doc_01
        block_id: blk_11
        start_char: 0
        end_char: 80
        quote: "..."
    confidence: 0.74
    status: accepted
    metadata:
      structural_role: intermediate
  - unit_id: ku_vacuum_claim
    kind: claim
    name_hint: same_rate_in_vacuum
    content: "In vacuum, objects fall at the same rate regardless of mass."
    support_level: paraphrased
    source_spans:
      - document_id: doc_01
        block_id: blk_15
        start_char: 0
        end_char: 66
        quote: "..."
    confidence: 0.88
    status: accepted
    metadata:
      structural_role: conclusion
chains:
  - chain_id: ch_vacuum
    name_hint: vacuum_derivation
    conclusion_unit_id: ku_vacuum_claim
    support_unit_ids: [ku_heavy, ku_env]
    action_unit_id: ku_tied_action
    support_level: paraphrased
    reasoning_summary: "Uses the tied-bodies contradiction to reject the heavier-falls-faster premise under the vacuum setting."
    support_analysis:
      - unit_id: ku_heavy
        why_it_matters: "This is the article's main load-bearing hypothesis under examination."
      - unit_id: ku_env
        why_it_matters: "The conclusion is specifically about the vacuum case."
    status: accepted
    metadata: {}
issues: []
summary:
  package_title: "Galileo Falling Bodies"
  package_description: "Minimal conclusion-first formalized package with follow-up question"
  unresolved_count: 0
```

### 19.2 `semantic_annotation.json`

```yaml
schema_version: formalize.semantic_annotation.v0.1
bundle_id: src_galileo
draft_ir_hash: "sha256:..."
chain_annotations:
  - chain_id: ch_vacuum
    support_roles:
      - unit_id: ku_heavy
        role: premise
        rationale: "If this hypothesis is not the direct target of the reasoning, the contradiction argument no longer has the same force."
      - unit_id: ku_env
        role: context
        rationale: "The vacuum setting frames the interpretation of the conclusion but is not the sole load-bearing premise."
    conditional_probability: 0.88
    conditional_probability_rationale: "Assuming the support points hold in their roles, the tied-bodies reasoning gives strong support to the conclusion."
    status: accepted
    metadata: {}
node_priors:
  - unit_id: ku_heavy
    prior: 0.35
    rationale: "The source presents this as an inherited but ultimately rejected background claim."
    status: accepted
    metadata:
      prior_basis: source_assertion
  - unit_id: ku_env
    prior: 1.0
    rationale: "This is a stipulated thought-experiment setting."
    status: accepted
    metadata:
      prior_basis: analyst_judgment
summary:
  annotated_chain_count: 1
  node_prior_count: 2
  deferred_count: 0
```

## 20. Open Questions

1. Should `infer_action` stay as a separate `kind` in the IR, or should IR use `action` plus subtype metadata?
2. Should citations be first-class records in v0.2 rather than remaining only inside source metadata?
3. Should chain-level source spans be explicit in v0.2, in addition to unit-level spans?
4. Should v0.2 allow a draft unit to appear in multiple modules before emission?
5. Should `semantic_annotation` remain a standalone sidecar in v0.2, or later fold into a richer combined local artifact once the workflow stabilizes?
