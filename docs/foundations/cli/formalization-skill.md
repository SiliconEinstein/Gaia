# Gaia Formalization Skill Architecture

| 文档属性 | 值 |
|---------|---|
| 版本 | 0.1 |
| 日期 | 2026-03-13 |
| 状态 | **Draft — target local skill architecture** |
| 关联文档 | [boundaries.md](boundaries.md), [command-lifecycle.md](command-lifecycle.md), [formalization-ir-schema.md](formalization-ir-schema.md), [../language/gaia-language-spec.md](../language/gaia-language-spec.md), [../language/gaia-language-design.md](../language/gaia-language-design.md), [../graph-ir.md](../graph-ir.md), [../review/publish-pipeline.md](../review/publish-pipeline.md) |

> **Note:** This document defines how an agent should formalize arbitrary input into the **current Gaia authored source surface**. It does **not** introduce a new "gaia script" syntax. In the near term, formalization is a **skill/workflow**, not a new core CLI command.

## 1. Purpose

Gaia needs a local capability that helps an agent turn arbitrary source material into a package that can enter the existing pipeline:

```text
raw input -> formalization skill -> semantic annotation skill -> Gaia YAML source -> gaia build -> graph construction / infer / publish
```

Typical inputs include:

- a paper body or extracted PDF text
- a webpage or article body
- a notebook-style reasoning trace
- a free-form thought chain
- a mixed bundle of notes plus citations

The formalization skill's job is to produce:

- package-authored Gaia source files
- provenance-rich sidecar artifacts explaining how that source was derived
- enough structure to let `gaia build` validate and lower the result into Graph IR

## 2. Core Judgments

### 2.1 Formalization is a skill, not a core CLI command

The task is model-driven, judgment-heavy, and iterative. It belongs in the same layer as self-review and graph-construction, not inside the minimal core CLI.

MVP consequence:

- no new `gaia formalize` command is required
- the capability should first exist as one or more agent skills / workflows
- a CLI wrapper is optional only after the workflow and artifacts stabilize

### 2.2 The output target is current Gaia YAML source

The system should teach the agent to emit the **existing authored language surface**:

- `claim`
- `setting`
- `question`
- `ref`
- `infer_action`
- `chain_expr`
- standard package/module YAML files

The system should **not** first invent a new "gaia script" concrete syntax. The current parser, `gaia build`, Graph IR lowering, and downstream review/infer pipeline already consume the existing YAML surface.

### 2.3 Article formalization should be conclusion-first

For paper- or article-like inputs, the skill should not begin by extracting an undifferentiated bag of propositions. It should proceed from the article's argumentative structure:

1. determine the article's motivation
2. determine its important conclusions
3. summarize the article's open questions or future-work questions
4. group those conclusions into modules
5. reconstruct how each conclusion is argued for
6. extract the reliability-critical support points in those chains

These support points are the later candidates for `premise` or `context`.

### 2.4 One-shot source generation is not reliable enough

The agent should not jump directly from arbitrary raw input to final package YAML in one LLM call. Formalization should be a staged workflow with:

1. ingestion and normalization
2. motivation / conclusion / open-question extraction
3. conclusion-chain reconstruction
4. support-point extraction
5. semantic annotation
6. deterministic source emission
7. build validation
8. critic / repair

### 2.5 Provenance is mandatory

Every emitted knowledge unit and chain should be traceable to source spans or explicitly marked as agent-added interpretation.

Without provenance:

- the package is hard to audit
- unsupported claims are hard to detect
- repair loops degenerate into free-form rewriting

### 2.6 Conservative source inclusion is the default

The system should distinguish:

- `explicit` — directly stated in the source
- `paraphrased` — directly supported by the source, but rewritten for clarity
- `inferred` — hidden premise, bridge, or interpretation added by the agent

Default policy:

- `explicit` and `paraphrased` may enter authored source
- `inferred` stays in formalization sidecars unless explicitly promoted by policy or author choice

This matches the current package discipline elsewhere in Gaia: review-discovered or search-discovered structure should not silently enter the submitted graph without explicit source updates and rebuild.

## 3. Non-Goals

This design does **not** attempt to solve:

- OCR for arbitrary PDFs or images
- browser automation and webpage extraction itself
- automatic publish-time global identity assignment
- automatic cross-package linking to authoritative external packages
- human-grade final editorial quality in the first pass
- a new package-management or runtime command surface

## 4. Pipeline Overview

```text
Input Adapters
    -> Normalized Source Bundle
    -> Motivation Extraction
    -> Conclusion Extraction / Module Grouping
    -> Open-Question Extraction
    -> Chain Reconstruction
    -> Support-Point Extraction
    -> Formalization Draft IR
    -> Semantic Annotation
    -> Deterministic YAML Emitter
    -> gaia build
    -> Formalization Critic
    -> Repair Loop (if needed)
```

### 4.1 Recommended skills

The minimal skill set is:

- `formalize-article`
- `semantic-annotation`
- `formalization-critic`
- `formalization-repair`

Adapter-specific variants such as `formalize-from-paper`, `formalize-from-webpage`, or `formalize-from-text` should be treated as input-specialized front doors into the same `formalize-article` architecture.

## 5. Architecture

### 5.1 Input Adapters

Each adapter normalizes its raw input into a shared `SourceBundle`.

Examples:

- `paper` adapter: title, abstract, section bodies, references, metadata
- `webpage` adapter: URL, title, author/date if available, cleaned body
- `thought-trace` adapter: ordered blocks, step labels, optional external citations

MVP requirement:

- adapters may assume text is already extracted
- adapters should focus on segmentation and metadata normalization, not scraping/OCR

### 5.2 Normalized Source Bundle

The normalized bundle is the common input to all later LLM and deterministic steps.

Suggested structure:

```yaml
bundle_id: src_01...
kind: paper | webpage | thought_trace | mixed
documents:
  - document_id: doc_01
    title: "..."
    uri: "..."
    metadata:
      author: "..."
      published_at: "..."
    blocks:
      - block_id: blk_01
        section: "Introduction"
        text: "..."
```

The key property is stable span identity. Later drafts should point to `document_id` / `block_id` / offsets rather than copying raw text loosely.

### 5.3 Conclusion-first article formalization

For article-like inputs, the recommended workflow is:

1. extract one or more coarse-grained motivation knowledge objects and place them in a `motivation` role module
2. identify the important conclusions of the article
3. summarize the article's explicit or strongly implied open questions and place them in a `follow_up_question` role module
4. order those conclusions by logical dependency, not document order alone
5. split them into modules only when a subgroup has a coherent local semantic unit
6. reconstruct, for each conclusion, the author's reasoning chain
7. identify the reliability-critical steps inside that chain
8. if such a step can be stated as a self-contained proposition, promote it to explicit knowledge

This workflow is intentionally biased toward article structure rather than raw sentence extraction.

### 5.4 Formalization Draft IR

The formalization IR is the central intermediate representation. Models write this IR; deterministic code emits Gaia source from it.

The normative v0.1 schema lives in [formalization-ir-schema.md](formalization-ir-schema.md). The rest of this section gives only the architectural intuition.

Suggested entities:

#### `KnowledgeUnitDraft`

```yaml
unit_id: ku_01
kind: claim | setting | question | action | ref
name_hint: "..."
content: "..."
support_level: explicit | paraphrased | inferred
source_spans:
  - document_id: doc_01
    block_id: blk_07
    quote: "short supporting excerpt"
confidence: 0.82
notes: "..."
```

#### `ChainDraft`

```yaml
chain_id: ch_01
conclusion_unit_id: ku_10
support_unit_ids: [ku_03, ku_04, ku_07]
action_unit_id: ku_09
reasoning_summary: "..."
support_analysis:
  - unit_id: ku_03
    why_it_matters: "..."
support_level: explicit | paraphrased | inferred
```

#### `ModuleDraft`

```yaml
module_id: mod_01
role: reasoning | setting | motivation | follow_up_question | other
knowledge_unit_ids: [ku_...]
chain_ids: [ch_...]
exports: [ku_...]
```

#### `FormalizationIssue`

```yaml
issue_id: issue_01
severity: info | warning | blocking
kind: unsupported_claim | weak_chain | missing_source | duplicate_unit | schema_gap
target_id: ku_01
message: "..."
```

### 5.5 Weak points as support-point extraction

For article formalization, a `weak point` means:

- a reliability-critical step, dependency, or bridge in a conclusion chain
- such that if it fails, the credibility of the conclusion drops materially

If a weak point can be expressed as a self-contained proposition, it should be promoted into explicit knowledge:

- statement-like support -> `claim`
- setup / condition / framing assumption -> `setting`

Those promoted support points are later classified by the semantic annotation skill as:

- `premise` / `dependency: direct`
- `context` / `dependency: indirect`

If a weak point cannot be made into a self-contained proposition, it should remain inside the reasoning/action description rather than being forced into a fake node.

### 5.6 Source-Support Taxonomy

The support label should be preserved throughout the workflow:

| Label | Meaning | Default source emission policy |
|------|---------|-------------------------------|
| `explicit` | Directly stated in the input | emit |
| `paraphrased` | Directly supported but rewritten | emit |
| `inferred` | Agent-added bridge, hidden premise, or interpretation | sidecar only by default |

This taxonomy is central. If the system loses it, formalization quality becomes impossible to audit.

### 5.7 Semantic annotation

After formalization has reconstructed conclusions, chains, and support points, a separate **semantic annotation** skill should process the draft.

Its responsibilities are:

- classify each support point in each chain as `premise` or `context`
- assign a `prior` to non-conclusion support nodes
- assign a conditional probability to each conclusion chain

This skill is intentionally separate from conclusion extraction and chain reconstruction. It should annotate an existing structural draft, not rewrite the package architecture.

Internal order:

1. classify `premise` / `context`
2. assign support-node priors
3. assign chain conditional probabilities

### 5.8 Deterministic YAML Emitter

The emitter converts annotated IR into current Gaia authored source.

For v0.1, it should be deliberately thin.

Responsibilities:

- materialize the already-decided module layout into YAML files
- normalize names minimally when required by authored-surface identifier rules
- emit `infer_action` and `chain_expr`
- emit `dependency: direct/indirect`
- write node priors and chain conditional probabilities from `semantic_annotation`
- keep source formatting stable across repair loops

It should not:

- decide module structure
- create new conclusions, support points, or open questions
- reinterpret weak points
- infer `premise/context` roles or probabilities on its own

The emitter should be deterministic so that repair loops modify IR first, not free-form YAML.

## 6. Mapping Rules

### 6.1 Knowledge-object mapping

Recommended initial mapping:

- declarative proposition -> `claim`
- definition / environment / setup / assumption stated by source -> `setting`
- unresolved research problem -> `question`
- described reasoning or method pattern -> `infer_action`
- external package knowledge reference -> `ref` only when the source clearly names a reusable external unit
- coarse-grained article motivation -> `motivation` role module containing `question`, `claim`, or `setting`
- article open question / future work -> `follow_up_question` role module containing `question`

### 6.2 Reasoning mapping

A `chain_expr` should be emitted only when the source provides enough structure to justify:

- a conclusion
- at least one reliability-relevant support point
- a reasoning step or action description connecting them

Otherwise the result should remain a flat set of knowledge units plus issues, rather than a hallucinated chain.

### 6.3 Module heuristics

MVP module layout should be simple and predictable:

- `setting.yaml` for definitions, assumptions, environments
- `reasoning.yaml` for core claims, actions, and chains
- `follow_up.yaml` for unresolved questions or future work

This default is intentionally boring. Fancy section-driven module splitting can come later.

### 6.4 Dependency mapping

Dependency-role assignment belongs to the semantic annotation skill.

When the emitter writes `chain_expr` args:

- `direct` means the conclusion fails if this input is false
- `indirect` means background or framing context

The emitter should consume an explicit semantic annotation record. It should not guess this distinction from text alone.

## 7. Validation And Repair

### 7.1 Build is the first hard gate

Every formalization run should end by invoking `gaia build`.

Success means:

- authored source is structurally valid
- refs resolve locally as expected
- package can be lowered into Graph IR artifacts

Failure means the workflow returns to repair.

### 7.2 Critic responsibilities

The critic runs after emission and build.

It checks for:

- unsupported or weakly supported claims
- chains whose conclusion is not grounded by listed support points
- overuse of `inferred` content
- duplicate or near-duplicate units
- too many flat claims with too little reasoning structure
- too many hallucinated chains with too little evidence
- semantic-annotation outputs that do not match the chain structure

### 7.3 Repair loop

The repair loop should operate on IR first, not directly on YAML.

Recommended inputs to repair:

- previous IR
- emitted source
- build errors
- critic findings
- source bundle

Recommended outputs:

- updated IR
- updated emitted source
- an append-only repair log

## 8. Artifact Layout

Formalization should write local sidecars under a dedicated folder:

```text
.gaia/
  formalize/
    source_bundle.json
    draft_ir.json
    semantic_annotation.json
    source_map.json
    critic_report.json
    repair_log.json
    run_summary.json
```

Suggested semantics:

- `source_bundle.json` — normalized input
- `draft_ir.json` — current formalization IR
- `semantic_annotation.json` — premise/context roles + priors + conditional probabilities
- `source_map.json` — emitted package object -> source spans
- `critic_report.json` — post-build audit findings
- `repair_log.json` — iterative fixes across rounds
- `run_summary.json` — top-level metadata, policy, model IDs, timestamps

The authored Gaia source itself lives in the package root, not inside `.gaia/formalize/`.

## 9. Policies

### 9.1 Suggested initial policy modes

#### `grounded_only` (default)

- emit only `explicit` and `paraphrased` units
- keep `inferred` units in sidecars
- prefer fewer chains over speculative chains
- require semantic annotation to justify every direct dependency

#### `interpretive`

- allow carefully marked inferred bridge units into draft IR
- require explicit issue entries for every inferred unit
- still require deterministic build success before accepting output

### 9.2 Promotion policy for inferred content

Even in interpretive mode, promotion of inferred content into authored source should be explicit:

- by user/agent confirmation
- by policy threshold
- or by later review/rewrite pass

The system should never silently upgrade a sidecar-only inferred unit into package source.

## 10. MVP Scope

### 10.1 Inputs

Support only:

- plain text
- Markdown
- pre-extracted paper text
- pre-extracted webpage text

Do not support yet:

- raw PDF OCR
- screenshots/images
- browser automation
- multi-document graph assembly across many packages

### 10.2 Output

Produce:

- one package
- a small fixed module layout
- authored YAML files compatible with `gaia build`
- local formalization sidecars

The default fixed layout should usually be:

- `motivation.yaml`
- `setting.yaml`
- `reasoning.yaml`
- `follow_up.yaml`

### 10.3 Explicit deferrals

Defer:

- automatic external package refs and authoritative linking
- automatic export optimization
- full paper-to-package citation normalization
- domain-specific formalizers
- formalization directly into global graph identities

## 11. Evaluation

The first success metrics should be operational, not aspirational:

- `gaia build` pass rate
- percentage of emitted units with source coverage
- percentage of emitted units marked `inferred`
- critic reject rate
- repair rounds per successful package
- source-to-package fidelity on sampled test inputs

## 12. Recommended Implementation Order

1. Define the formalization IR and artifact layout.
2. Build a `formalize-article` reference workflow.
3. Add semantic annotation for dependency roles and probabilities.
4. Add deterministic YAML emission.
5. Add `gaia build` validation and repair.
6. Add critics for unsupported claims, weak chains, and annotation mistakes.
7. Add input adapters for paper and webpage text.
8. Consider a CLI wrapper only after workflow stability is proven.

## 13. Open Questions

1. Should the first critic be rule-based, LLM-based, or hybrid?
2. When should a source section become its own module versus just another set of knowledge units?
3. How much inferred bridge content is acceptable in interpretive mode?
4. Should citation objects become first-class artifacts in MVP or remain provenance metadata only?
5. When the input is a thought trace rather than a paper, how aggressively should the system split "reasoning" from "claims"?
6. Should semantic annotation be allowed to request new support-point extraction, or only annotate an existing draft?
