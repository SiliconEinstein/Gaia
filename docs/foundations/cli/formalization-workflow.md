# Gaia Formalization Workflow

> **Status: Current direct-YAML workflow.** This document defines the current `conclusion-first` formalization workflow for turning a paper, webpage, note set, or article into Gaia-authored YAML. It intentionally avoids draft IR, emitter, or sidecar-first architecture.

## Purpose

This document defines how an agent should formalize free-form source material into a buildable Gaia package.

It answers one workflow question:

> What step-by-step process should an agent follow to convert an article into current Gaia YAML source?

## Scope

This workflow applies to local, agent-driven formalization.

It covers:

- extracting article motivation
- extracting and grouping important conclusions
- reconstructing reasoning chains
- extracting reliability-critical weak points
- classifying support as premise or context
- assigning local prior and conditional-probability judgments
- authoring Gaia YAML files directly
- running `gaia build` and repairing the package until it passes

It does not cover:

- a new formalization CLI command
- draft IR or intermediate formalization schema
- server-side ingestion
- publish-time peer review
- global graph integration

## Core Judgment

Formalization should be `conclusion-first` and should write Gaia YAML directly.

The intended flow is:

```text
source material
-> motivation extraction
-> conclusion extraction and grouping
-> open-question extraction
-> per-conclusion chain reconstruction
-> weak-point extraction
-> premise/context classification
-> prior and conditional-probability assignment
-> direct Gaia YAML authoring
-> gaia build
-> repair until build passes
```

Not:

```text
source material
-> draft IR
-> emitter
-> sidecar-first workflow
```

## Workflow

### Stage 0: Prepare Source Material

Start from a cleaned local source, typically Markdown or other readable text.

The agent should:

- read the whole source before deciding package structure
- identify the title, topic, and broad claim family
- note where quantitative contributions, assumptions, and future-work statements appear

If the source is noisy or incomplete, the agent should still prefer a conservative package over speculative completion.

### Stage 1: Extract Motivation

Extract the article's motivation first.

This stage should answer:

- what problem is the paper trying to solve?
- why is that problem important?
- what gap, limitation, or tension is motivating the work?

Output expectations:

- write one or more coarse-grained motivation knowledge objects
- place them in a dedicated motivation module
- keep this stage relatively coarse; do not spend most of the formalization budget here

The motivation module exists to anchor the package, not to absorb the paper's main technical content.

### Stage 2: Extract Important Conclusions

Identify the paper's important conclusions next.

This stage should:

- list important conclusions in logical order, not merely document order
- separate core conclusions from minor supporting observations
- preserve article-specific contribution detail rather than collapsing conclusions into generic summaries

When grouping conclusions into modules, use this rule:

- if several conclusions form one coherent semantic block, keep them in one module
- if a subgroup has its own clear local reasoning arc, split it into a separate module

Typical signals that a conclusion deserves explicit preservation include:

- a new theorem or derived principle
- a new mechanism or explanation
- a new algorithmic method
- a benchmark or scaling result
- a strong quantitative performance improvement
- a new physical prediction or parameter-range claim

### Stage 3: Extract Open Questions

Extract explicit or strongly supported open questions and future-work questions.

This stage should:

- identify unresolved questions stated by the authors
- identify follow-up directions that are clearly suggested by the paper's own results
- avoid inventing speculative questions that are not grounded in the source

Output expectations:

- place these questions in a dedicated follow-up module
- keep them separate from the main conclusion modules

### Stage 4: Reconstruct Reasoning Chains

For each important conclusion, reconstruct how the paper derives it.

This stage should answer:

- what steps does the author actually use to support this conclusion?
- which intermediate steps are load-bearing?
- which transitions are compact enough to keep implicit, and which need explicit structure?

Guidelines:

- use a single-step chain only when the argument is genuinely that compact
- otherwise preserve meaningful intermediate reasoning structure
- model the author's argument, not an idealized argument from scratch

The goal is not maximal granularity. The goal is enough structure that the main support path is inspectable.

### Stage 5: Extract Reliability-Critical Weak Points

For each conclusion chain, inspect its reliability-critical weak points.

A weak point is a step or bridge whose failure would materially change the conclusion's reliability.

For each chain step, ask:

- if this step were false or unjustified, would the conclusion's reliability drop significantly?

If the answer is yes, treat it as a weak point.

Then ask:

- can this weak point be written as a self-contained proposition?

If yes:

- extract it into an explicit `claim` or `setting`
- make the chain reference it

If no:

- keep it inside the reasoning step
- do not invent an unnatural node just to force graph structure

The purpose of weak-point extraction is to surface load-bearing support, not to atomize every sentence.

### Stage 6: Check Cross-Conclusion Dependencies

After extracting local weak points, check whether a conclusion chain depends on another conclusion.

This stage should:

- detect when one conclusion is used as support for another
- represent that support explicitly with `ref`
- judge whether the referenced conclusion functions as `premise` or `context`

This matters especially when the paper builds a hierarchy such as:

- framework conclusion -> method conclusion -> prediction conclusion

Cross-conclusion support should be explicit rather than hidden in prose.

### Stage 7: Perform Semantic Annotation

For every non-conclusion support node used by a conclusion chain, decide whether it is `premise` or `context`.

Use this rule:

- `premise`: if the support is false, the chain substantially fails
- `context`: if the support is false, the chain may still stand, but its reliability drops materially

Apply the same judgment to referenced conclusions when they are used as support in another chain.

Then assign:

- a `prior` to every non-conclusion support node
- a conditional probability to every conclusion chain, interpreted as `P(conclusion | premise, context)`

This stage does not change package structure.
It annotates the support semantics of the structure already chosen.

### Stage 8: Author Gaia YAML Directly

Write the package directly as Gaia-authored YAML.

Typical output files are:

- `package.yaml`
- `motivation.yaml`
- one or more reasoning modules such as `reasoning.yaml`, `results.yaml`, `analysis.yaml`
- `setting.yaml` if shared setup is load-bearing
- `follow_up.yaml` if the paper contains real open questions

Use current Gaia surface forms:

- `claim`
- `setting`
- `question`
- `ref`
- `premises`
- `chains`

Use these authoring rules:

- for reasoning-heavy modules, prefer `premises:` plus `chains:` over one flat `knowledge:` list
- put reusable strong support nodes in `premises:`
- write one reasoning chain per `chains:` block
- keep intermediate steps inline inside each chain instead of listing every intermediate claim at module top level
- author the package as a self-contained Gaia-native reformulation of the source, not as article notes or a summary
- do not let conclusion-bearing nodes become thinner than the source; keep conclusion content, conditions, and quantitative details when the source makes them explicit
- if a chain step depends on a premise or a previous step, add a `ref` in that step's `refs:` list
- use `ref` in `premises:` when a chain depends on knowledge from another module
- use `dependency: direct` for premise-like support
- use `dependency: indirect` for context-like support
- encode priors and conditional probability where the current Gaia surface supports them

### Stage 9: Preserve Quantitative Detail

Do not compress contribution-specific results into vague prose.

When the source provides them, preserve:

- benchmark names
- datasets
- metrics
- effect sizes
- ablation outcomes
- theorem assumptions
- approximation regimes
- orders of expansion or convergence
- critical temperatures
- parameter ranges
- complexity or scaling results
- quantitative gains such as speedups

If a number or condition is load-bearing for a conclusion, it should usually remain in the emitted claim or in an explicit support node.

### Stage 10: Run `gaia build` And Repair

After authoring the YAML package, run `gaia build`.

Repair until the package passes.

Typical repair targets include:

- YAML syntax
- malformed `chains` or normalized `chain_expr`
- broken or missing refs
- naming collisions
- missing module declarations
- unsupported probability annotations
- conclusions that are too weakly grounded and should be downgraded to `question`

The package returned to the user should be buildable, not merely illustrative.

## Judgment Rules

### Grounding Rule

Prefer explicit support or careful paraphrase.

If support is too weak:

- omit the statement
- or downgrade it to a `question`

Do not silently promote speculative hidden premises into authoritative claims.

### Granularity Rule

Prefer a few strong chains over many weak chains.

Create explicit nodes when they are semantically useful and load-bearing.
Do not split every sentence into a node.

### Module Rule

Each module should have one clear semantic role or one tight conclusion group.

Do not mix:

- motivation
- main technical conclusions
- open questions

unless the source is too small to justify separation.

## Outputs

The final result of formalization should be:

- a real Gaia package directory
- real YAML source files
- a package that passes `gaia build`

The final report back to the user should say:

- which files were created
- whether `gaia build` passed
- any unresolved grounding or modeling uncertainties

## Relationship To Other Docs

- [boundaries.md](boundaries.md) defines the CLI layering within which formalization skills operate
- [command-lifecycle.md](command-lifecycle.md) defines where skill-driven formalization sits relative to `build`, `infer`, and `publish`

## Current Skill Location

The current Codex skill that follows this workflow lives outside the repository at:

`/Users/kunchen/.codex/skills/formalize-article-to-gaia/`
