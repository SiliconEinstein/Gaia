# Documentation Restructure Proposal

> **Status:** Proposal — not yet implemented.
> **Context:** Feedback on PR #191 (foundations topic tree scaffold).
> **Goal:** Make docs navigable for three distinct audiences, eliminate naming ambiguity, remove duplication.

## Problem

The current four-layer structure (Foundation / Semantics / Contracts / Runtime) has several issues:

1. **No audience-aware entry point.** A visitor, a CLI user, and a developer all land on the same flat list of 25+ docs. No one knows where to start.
2. **Naming is abstract.** "Contracts" has no concrete meaning for newcomers. "Semantics" vs "Theory" is a distinction even contributors struggle with.
3. **Unnecessary new terminology.** "Gaia Reasoning Model" introduces a new concept when the project already calls itself an LKM. The `reasoning` vs `inference` split doesn't help — reasoning types define factor potentials, BP computes beliefs from them. It's one thing.
4. **Missing developer layer.** No "how to develop" documentation exists. Runtime describes system behavior but not how to run the pipeline, add a test, or contribute code.
5. **No clear boundary between docs.** `for-developers/` vs `implementations/` would overlap if both existed. Pipeline, CLI, and Server all call the same engines but the current structure doesn't reflect this.

## Proposed Structure

### Design Principles

- **Three audience paths** at the top level — visitor, user, developer each get a clear starting point.
- **Foundations as deep reference** — organized by what changes at different rates (theory never changes, concepts change slowly, interfaces change sometimes, implementations change often).
- **Entry points → Engines → Storage** — CLI, Server, and Pipeline are all entry points that call shared engines. This is the real architecture; docs should reflect it.
- **One home per topic** — no duplication between layers.

### Full Tree

```
docs/
  README.md                              ← entry point: "who are you?" → follow your path

  for-visitors/                          ← path 1: understand Gaia in 5 minutes
    what-is-gaia.md                        what problem Gaia solves, how it works
    worked-example.md                      one paper → knowledge graph → BP → beliefs, end to end

  for-users/                             ← path 2: use Gaia to author knowledge packages
    quick-start.md                         10 min: run your first package
    language-reference.md                  claim / setting / question / from / between
    cli-commands.md                        build / infer / publish
    package-examples/                      example packages (galileo, einstein, etc.)

  foundations/                           ← deep reference, consulted as needed
    README.md                              navigation guide for foundations

    theory/                              ← unchanging theoretical basis
      theoretical-foundation.md            Jaynes plausible reasoning, why probabilistic
      scientific-ontology.md               scientific knowledge ontology, terminology
      belief-propagation.md                BP algorithm, loopy BP, convergence, factor potentials

    gaia-concepts/                       ← Gaia's technical choices built on theory
      knowledge-types.md                   claim / setting / question / action / relation
      reasoning-relations.md               deduction / induction / abstraction / contradiction
      factor-design.md                     reasoning type → factor potential mapping
      package-model.md                     package / module / chain / knowledge structure

    interfaces/                          ← contracts between layers
      language-spec.md                     Gaia Language v4 Typst DSL full spec
      graph-ir.md                          Graph IR structural contract
      api.md                               HTTP API contract
      lifecycle.md                         CLI lifecycle (build→infer→publish)
                                           + LKM lifecycle (review→curate→integrate)

    implementations/                     ← how the system is built (architecture + dev guide)
      overview.md                          architecture: entry points → engines → storage

      entry-points/                      ← three callers of the engine layer
        cli.md                             single-package interactive (build/infer/publish)
        server.md                          API server: write side (review, curation)
                                           + read side (publish, recommend, search)
        pipeline.md                        batch orchestration (multi-paper, end to end,
                                           7 stages: xml→typst→graph-ir→bp→persist→curation→global-bp)

      engines/                           ← shared capability layer
        graph-ir-compiler.md               typst → raw graph → local canonical graph
        bp-engine.md                       local BP + global BP
        review-engine.md                   LLM-based review
        curation-engine.md                 clustering, dedup, abstraction, conflict detection
        canonicalization-engine.md         local → global node mapping (TF-IDF / embedding)

      storage.md                         LanceDB + Neo4j + three-write atomicity
      testing.md                         test structure, fixtures, CI, how to add tests

    product-scope.md                       current product boundaries
    documentation-policy.md                doc maintenance rules

  archive/                               ← historical docs, preserved but not navigated
```

### Layer Rationale

| Layer | What it answers | Change frequency |
|-------|----------------|-----------------|
| **theory/** | Why does Gaia reason this way? (Jaynes, BP) | Never — foundations don't change |
| **gaia-concepts/** | What are Gaia's core abstractions? (knowledge types, reasoning relations, factors) | Rarely — core model is stable |
| **interfaces/** | What are the contracts between layers? (language spec, Graph IR, API) | Sometimes — when adding capabilities |
| **implementations/** | How is it built and how do I work on it? (architecture, engines, storage) | Often — code changes frequently |

### Key Differences from PR #191

| PR #191 | This proposal | Why |
|---------|--------------|-----|
| Foundation / Semantics / Contracts / Runtime | **theory / gaia-concepts / interfaces / implementations** | Clearer names. Semantics+Theory merge into two distinct layers (external theory vs Gaia choices). |
| "Gaia Reasoning Model" as separate doc | Merged into `reasoning-relations.md` + `factor-design.md` | Reasoning types and BP are one pipeline; splitting creates confusion. |
| `reasoning` vs `inference` distinction | `reasoning-relations.md` (types) + `belief-propagation.md` (algorithm) | Clean split: what kinds of reasoning exist vs how BP computes beliefs. |
| No audience routing | Three paths: `for-visitors/`, `for-users/`, `foundations/implementations/` | Different people need different things. |
| No developer guide | `implementations/` serves as both architecture doc and dev guide | One home per topic, no duplication. |
| Pipeline / CLI / Server as peers | All three are **entry points** calling shared **engines** | Reflects the real architecture: they're callers, not independent systems. |
| "Contracts" | **"Interfaces"** | More intuitive — these are interface definitions between layers. |
