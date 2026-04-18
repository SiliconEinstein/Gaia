# Obsidian Wiki Backend — IR-to-Wiki Knowledge Rendering

> **Status:** Proposal
>
> **Date:** 2026-04-10
>
> **Note (2026-04-18):** References to "review sidecar" in this spec are outdated. Since gaia-lang 0.4.2, priors are assigned via `priors.py` and inline `reason+prior` pairing. See `docs/foundations/gaia-lang/package.md`.
>
> **Depends on:** [gaia render command](../plans/2026-04-09-gaia-render-command.md), [hole-fills design](2026-04-08-gaia-lang-hole-fills-design.md)
>
> **Inspired by:** [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), [nvk/llm-wiki](https://github.com/nvk/llm-wiki), [Graphify](https://github.com/safishamsi/graphify)

## 1. Problem

Gaia IR (`ir.json`) is the canonical representation of a knowledge package's reasoning structure. It is precise, versioned, and machine-queryable. It is also **unreadable by humans**.

Current rendering options (`gaia render --target docs`, `--target github`) produce static documents — a single long markdown file or a React SPA. These are better than raw JSON, but they are:

- **Linear, not navigable** — you read top-to-bottom, you can't drill into a single claim and explore its reasoning chain interactively
- **Monolithic** — one file (docs) or one build (github), not a collection of interlinked pages
- **Static** — rendered once, no interactive exploration
- **Require inference** — the github target strictly requires beliefs; docs degrades without them but loses significant content

What's missing is a **browsable, interlinked knowledge wiki** — one page per claim, wikilinks between premises and conclusions, visual graph of the reasoning structure, and YAML frontmatter for structured queries. Think: a personal wiki of everything the package knows, how it knows it, and how confident it is.

## 2. Proposed Solution

### Two-layer architecture

```
.gaia/                          Machine layer (search, query, inference)
├── ir.json                     Source of truth — structural + reasoning topology
├── ir_hash
├── compile_metadata.json
├── manifests/                  Package interface (exports/holes/bridges)
└── reviews/
    └── self_review/
        ├── beliefs.json        BP results
        └── parameterization.json

gaia-wiki/                     Human layer (browsing, reading, navigation)
├── _index.md                   Global navigation (3-hop entry point)
├── overview.md                 Package overview + Mermaid
├── modules/                    One page per module (chapter-level view)
├── conclusions/                One page per exported claim
├── evidence/                   One page per leaf premise
├── reasoning/                  One page per complex strategy
├── review/                     Review sidecar readable view
└── meta/                       Cross-cutting summaries
    ├── beliefs.md
    ├── contradictions.md
    └── holes.md
```

**IR is the source of truth. Wiki is a derived view.**

The wiki can always be regenerated from IR + original sources. It is never manually edited (the LLM maintains it). This mirrors Karpathy's principle: "You read it; the LLM writes it."

### Three-phase generation

```
Phase 1: Mechanical skeleton    (gaia render --target obsidian, pure Python, deterministic)
    → frontmatter, wikilinks, Mermaid graphs, _index.md

Phase 2: LLM narrative filling  (/gaia:publish --obsidian, LLM-driven, non-deterministic)
    → rich explanations, context from original sources, expanded reasoning

Phase 3: Cross-reference audit  (pure Python, deterministic)
    → validate wikilinks, update _index.md summaries, generate meta/ pages
```

Phase 1 is cheap and fast (~seconds). Phase 2 is expensive (~minutes, LLM calls). Phase 3 is cheap.

Phase 2 is optional — Phase 1 alone produces a usable (if thin) wiki. This matches the existing `gaia render` → `/gaia:publish` separation where render produces a skeleton and publish fills narrative.

## 3. Wiki Structure

### Directory layout

```
gaia-wiki/
├── .obsidian/                          Obsidian vault config (graph view settings, etc.)
│   └── graph.json                      Graph view color groups by node type
├── _index.md                           Master index
├── overview.md                         Package overview
├── modules/
│   ├── _index.md                       Module listing
│   ├── motivation.md                   One page per module
│   ├── s2_method.md
│   └── ...
├── conclusions/
│   ├── _index.md                       Exported claims listing
│   ├── binder_success_rate.md          One page per exported claim
│   ├── rfdiffusion_broad_success.md
│   └── ...
├── evidence/
│   ├── _index.md                       Leaf premises listing
│   ├── denoising_process.md            One page per leaf premise (local hole)
│   └── ...
├── reasoning/
│   ├── _index.md                       Strategies listing
│   ├── induction_comprehensive.md      One page per complex strategy
│   └── ...
├── review/
│   ├── _index.md
│   └── self_review.md                  Review sidecar readable view
└── meta/
    ├── beliefs.md                      Full belief table (prior → posterior)
    ├── contradictions.md               Contradiction operators summary
    └── holes.md                        Local holes / leaf premises summary
```

### IR entity → wiki page mapping

| IR entity | Has own page? | Page location | Condition |
|---|---|---|---|
| Knowledge (exported claim) | Yes | `conclusions/{label}.md` | Always |
| Knowledge (non-exported, has strategy support) | Section in module page | `modules/{module}.md#{label}` | Inlined |
| Knowledge (leaf premise / local hole) | Yes | `evidence/{label}.md` | Always |
| Knowledge (setting) | Section in module page | `modules/{module}.md#{label}` | Inlined |
| Knowledge (question) | Yes | `conclusions/{label}.md` | Always (questions are interesting) |
| Strategy (complex: induction, elimination, case_analysis) | Yes | `reasoning/{strategy_id_or_label}.md` | When strategy connects 3+ nodes |
| Strategy (simple: single noisy_and, deduction) | Inlined in conclusion's page | `conclusions/{label}.md#derivation` | When strategy connects ≤2 premises |
| Operator (contradiction, equivalence, ...) | Aggregated | `meta/contradictions.md` | Always |
| Module | Yes | `modules/{module}.md` | Always |
| Review sidecar | Yes | `review/{name}.md` | Always |

### Frontmatter schema

Every wiki page has YAML frontmatter that Obsidian reads natively (tags, aliases) and that Dataview can query:

#### Claim page frontmatter

```yaml
---
type: claim
label: binder_success_rate
qid: "github:watson_rfdiffusion_2023::binder_success_rate"
module: s7_binder_design
exported: true
prior: 0.9                    # from review (null if no review)
belief: 1.0                   # from infer (null if no infer)
strategy_type: induction      # type of the supporting strategy (null if leaf)
premise_count: 3              # how many premises support this
alternative_count: 1          # how many abduction alternatives exist
tags: [claim, exported, s7-binder-design]
aliases: [binder success rate, 19% binder success]
---
```

#### Module page frontmatter

```yaml
---
type: module
label: s7_binder_design
title: "Binder Design"
claim_count: 18
strategy_count: 7
exported_count: 2
tags: [module, s7-binder-design]
---
```

#### Strategy page frontmatter

```yaml
---
type: strategy
strategy_type: induction
label: induction_comprehensive
premise_count: 3
conclusion: comprehensive_improvement
tags: [strategy, induction]
---
```

### Page content structure

#### Claim page (e.g., `conclusions/binder_success_rate.md`)

Phase 1 (skeleton) produces:

```markdown
---
(frontmatter as above)
---

# 19% binder success rate — 100× improvement over Rosetta

> The overall experimental success rate for RFdiffusion binders
> was 19% across five targets...

## Derivation
- **Strategy**: [[induction_comprehensive]] (induction)
- **Premises**:
  - [[outperforms_hallucination]]
  - [[benchmark_performance]]
  - [[binder_specificity]]

## Supports
- → [[comprehensive_improvement]] via [[induction_comprehensive]]
- → [[rfdiffusion_broad_success]] (transitive)

## Alternatives
- [[alt_binder_other_explanation]] (prior: 0.15)

## Review
- **Prior**: 0.9 (judgment: "strong")
- **Belief**: 1.00
- **Justification**: "Direct experimental measurement across 5 targets"
- **Review**: [[self_review]]

## Module
[[s7_binder_design]]
```

Phase 2 (LLM narrative) enriches each section:

```markdown
(same frontmatter)

# 19% binder success rate — 100× improvement over Rosetta

> The overall experimental success rate for RFdiffusion binders
> was 19% across five targets...

## Context

The authors tested RFdiffusion-designed binders against five protein targets
of therapeutic interest (insulin receptor, SARS-CoV-2 spike, IL-7Rα, PD-L1,
and TrkA). For each target, fewer than 100 candidate binders were screened
using bio-layer interferometry (BLI), yielding an overall success rate of 19%.
This represents approximately a 100-fold improvement over the previous
state-of-the-art Rosetta-based pipeline on the same targets.

![[figure-4-binder-results.png]]

> [!NOTE]
> Context expanded from Watson et al. 2023, Extended Data Fig. 5 and
> Supplementary Table 3. See `artifacts/paper.pdf` pp. 8-10.

## Derivation
(same as Phase 1 but with prose explanations of WHY each premise supports
this conclusion, drawn from the paper's discussion section)

...
```

#### Module page (e.g., `modules/s7_binder_design.md`)

```markdown
---
type: module
label: s7_binder_design
title: "Binder Design"
claim_count: 18
strategy_count: 7
exported_count: 2
tags: [module, s7-binder-design]
---

# Binder Design

## Overview

This module covers RFdiffusion's application to de novo protein binder
design, the most therapeutically relevant result in the paper.

```mermaid
graph TD
    binder_specificity["Binder specificity (0.99)"]:::premise
    ...
```

## Claims

### [[binder_success_rate]] ★
> 19% binder success rate — 100× improvement over Rosetta

Prior: 0.9 → Belief: 1.00

### [[ha20_atomic_accuracy]] ★
> RFdiffusion achieves atomic-level accuracy in binder design

Prior: 0.85 → Belief: 0.83

### binder_specificity
> Six binders showed high specificity with no detectable cross-reactivity...

Prior: 0.9 → Belief: 0.99

(... more claims, non-exported ones inlined here ...)
```

#### `_index.md` (master index)

Follows nvk's pattern — the LLM's primary navigation aid:

```markdown
# watson-rfdiffusion-2023-gaia

> De novo design of protein structure and function with RFdiffusion (Nature)

Last rendered: 2026-04-10
IR hash: sha256:4c03ba068...
Review: self_review

## Statistics

| Metric | Count |
|--------|-------|
| Knowledge nodes | 128 (97 claims, 19 settings, 12 questions) |
| Strategies | 42 (15 noisy_and, 12 abduction, 8 deduction, 7 induction) |
| Operators | 0 |
| Modules | 8 |
| Exported conclusions | 7 |
| Leaf premises (holes) | 32 (20 evidence + 12 alternatives) |

## Navigation

### Modules
| Module | Claims | Strategies | Exported |
|--------|--------|------------|----------|
| [[motivation]] | 8 | 0 | 0 |
| [[s2_method]] | 12 | 4 | 0 |
| ... | ... | ... | ... |
| [[s7_binder_design]] | 18 | 7 | 2 |

### Exported Conclusions
| Conclusion | Belief | Module |
|------------|--------|--------|
| [[binder_success_rate]] | 1.00 | [[s7_binder_design]] |
| [[rfdiffusion_broad_success]] | 0.72 | [[s8_discussion]] |
| ... | ... | ... |

### Quick Links
- [[overview]] — Mermaid reasoning graph
- [[meta/beliefs]] — Full belief table
- [[meta/contradictions]] — Contradiction operators
- [[meta/holes]] — Leaf premises / local holes
- [[review/self_review]] — Review sidecar details
```

## 4. LLM Narrative Protocol

### What the LLM reads

For each wiki page, the LLM receives:

1. **IR data** for the specific node (content, type, label, strategies, operators)
2. **Beliefs** from `beliefs.json` (if available)
3. **Review justifications** from `parameterization.json` (if available)
4. **Original sources** from `artifacts/` — the LLM should search the original paper/document for relevant context
5. **The skeleton page** generated by Phase 1 (knows the wikilinks and structure)

### What the LLM writes

For each claim page:
- **Context section**: 2-3 paragraphs explaining the claim in the context of the original work. Include relevant data, figures, experimental conditions.
- **Derivation prose**: For each premise → conclusion link, explain WHY the premise supports the conclusion (not just that it does).
- **Significance**: Why this claim matters for the package's overall argument.
- **Image embeds**: If `artifacts/` has relevant figures, embed them with `![[filename.png]]`.

For each module page:
- **Overview paragraph**: What this module/chapter covers and how it fits in the larger argument.
- **Transition**: How this module connects to previous and next modules.

For the overview page:
- **Package abstract**: 1-2 paragraphs summarizing the entire knowledge package.
- **Key findings**: The exported conclusions in narrative form.

### What the LLM does NOT write

- Frontmatter (generated mechanically from IR)
- Wikilinks in the Derivation/Supports/Alternatives sections (generated mechanically)
- Mermaid graphs (generated mechanically)
- Statistics in `_index.md` (generated mechanically)

### Handling incomplete IR

When the IR lacks information, the LLM follows these rules:

| Missing information | LLM action | Annotation |
|---|---|---|
| Claim content is terse (< 20 words) | Search `artifacts/` for the full context, expand | `> [!NOTE] Content expanded from source` |
| Strategy has no `reason` field | Reconstruct reasoning from premises → conclusion logic + original source | `> [!NOTE] Reasoning reconstructed from source` |
| Review has no `justification` | Infer justification from the claim type + evidence strength | `> [!NOTE] Justification inferred` |
| No beliefs available (infer not run) | Write structural description only, note that beliefs are unavailable | `> [!WARNING] Beliefs not available — run gaia infer` |
| Original source not in `artifacts/` | Write from IR content only, note the gap | `> [!WARNING] Original source not available` |

All LLM-generated annotations use Obsidian callout syntax (`> [!NOTE]`, `> [!WARNING]`) so they're visually distinct from mechanical content.

## 5. Search Architecture

### IR layer (machine search)

The IR layer supports three query interfaces:

1. **MCP server** (`gaia serve`): LLM tools query the graph via `query_claims`, `get_reasoning_chain`, `find_contradictions`, `what_if`. Results include `label` which maps 1:1 to wiki page filenames.

2. **CLI** (future `gaia query`): Human queries from terminal. Example: `gaia query --where "belief < 0.7"` → lists claims with weak beliefs.

3. **Programmatic** (Python API): `from gaia.ir import LocalCanonicalGraph; graph = LocalCanonicalGraph(**ir); graph.knowledges_by_label["binder_success_rate"]`.

### Wiki layer (human search)

The wiki layer supports:

1. **Obsidian search**: native full-text search across all pages.
2. **Obsidian Dataview**: structured queries over frontmatter. Example:
   ```dataview
   TABLE prior, belief, strategy_type
   FROM "conclusions"
   WHERE belief < 0.7
   SORT belief ASC
   ```
3. **Obsidian graph view**: visual exploration of the wikilink graph (which IS the reasoning graph).
4. **grep**: `grep -r "binder" gaia-wiki/` always works.

### IR → Wiki bridging

Every IR node's `label` is also the wiki page's filename (slug). This means:
- MCP query returns `label: "binder_success_rate"` → human opens `gaia-wiki/conclusions/binder_success_rate.md`
- Dataview query returns a row → clicking opens the page → page has `qid` in frontmatter → links back to IR
- Obsidian graph view shows the same topology as the IR reasoning graph (because wikilinks mirror strategy edges)

## 6. Integration with Existing Tools

### `gaia render --target obsidian` (Phase 1 + 3)

New render target added to `gaia/cli/commands/render.py`. Produces the mechanical skeleton.

```bash
gaia render --target obsidian          # skeleton only
gaia render --target obsidian --review self_review  # skeleton + beliefs from review
gaia render                            # default 'all' now includes obsidian? or keep separate?
```

Design decision: `obsidian` should be **opt-in** (not part of `all`) because it creates a directory tree, not a single file. Users who don't use Obsidian shouldn't get an extra directory.

Implementation: a new `gaia/cli/commands/_obsidian.py` module (~200-300 lines) with `generate_obsidian_vault(ir, pkg_path, beliefs_data, param_data, pkg_metadata) -> Path`.

### `/gaia:publish` extension (Phase 2)

Extend the existing publish skill to support Obsidian output:

```bash
/gaia:publish              # existing: fill .github-output/ narrative
/gaia:publish --obsidian   # new: fill gaia-wiki/ narrative
/gaia:publish --all        # both
```

The skill reads the skeleton pages, reads `artifacts/`, and fills in the narrative sections. The LLM writing protocol (Section 4) is encoded in the skill's prompt.

### Strictness by target

Consistent with the existing differentiated strictness model:

| Target | Review required? | Beliefs required? | Behavior when missing |
|---|---|---|---|
| `obsidian` (Phase 1 skeleton) | No | No | Skeleton without beliefs — frontmatter has `prior: null, belief: null` |
| `obsidian` + `/gaia:publish` (Phase 2 narrative) | Recommended | Recommended | LLM writes structural descriptions only, callout warns about missing beliefs |

## 7. Relation to Existing Backends

| Backend | Output | LLM involved? | Interactive? | When to use |
|---|---|---|---|---|
| `--target docs` | Single `detailed-reasoning.md` | No | No (linear read) | Quick structural check after compile |
| `--target github` | `.github-output/` (React SPA + wiki + README) | Yes (via `/gaia:publish`) | Yes (React SPA) | Publishing to GitHub for external readers |
| `--target obsidian` | `gaia-wiki/` (Obsidian vault) | Yes (via `/gaia:publish --obsidian`) | Yes (Obsidian native) | Personal/team browsing, iterative exploration |

`docs` is the lightweight check. `github` is the public-facing publication. `obsidian` is the working knowledge base.

## 8. Example: watson-rfdiffusion-2023-gaia

### Phase 1 output (skeleton)

```
gaia-wiki/
├── .obsidian/graph.json          (4 lines — color groups)
├── _index.md                     (~50 lines — stats + navigation tables)
├── overview.md                   (~30 lines — Mermaid + package abstract stub)
├── modules/
│   ├── _index.md                 (8 rows)
│   ├── motivation.md             (~20 lines per module)
│   ├── s2_method.md
│   ├── s3_unconditional.md
│   ├── s4_oligomers.md
│   ├── s5_motif_scaffolding.md
│   ├── s6_symmetric_motif.md
│   ├── s7_binder_design.md
│   └── s8_discussion.md
├── conclusions/
│   ├── _index.md                 (7 rows)
│   ├── binder_success_rate.md
│   ├── rfdiffusion_broad_success.md
│   ├── symmetric_high_success.md
│   ├── rfdiffusion_benchmark_performance.md
│   ├── ha20_atomic_accuracy.md
│   ├── comprehensive_improvement.md
│   └── generality_claim.md
├── evidence/
│   ├── _index.md                 (32 rows)
│   ├── denoising_process.md
│   ├── binder_specificity.md
│   ├── alt_binder_other_explanation.md
│   └── ... (29 more)
├── reasoning/
│   ├── _index.md
│   └── induction_comprehensive.md  (+ a few more complex strategies)
├── review/
│   └── self_review.md
└── meta/
    ├── beliefs.md
    └── holes.md
```

Total: ~60-80 pages, all mechanically generated, browsable in Obsidian immediately.

### Phase 2 output (after `/gaia:publish --obsidian`)

Same files, but each page now has 2-5 paragraphs of LLM-written narrative, embedded figures from `artifacts/`, and expanded reasoning explanations. Total word count goes from ~5K (skeleton) to ~15-20K (rich wiki).

## 9. Implementation Plan

### Phase 1: `gaia render --target obsidian` (~2-3 days)

1. Create `gaia/cli/commands/_obsidian.py`
2. Add `obsidian` to `RenderTarget` enum
3. Implement `generate_obsidian_vault()`:
   - Page generation for each entity type (claim, module, strategy, review)
   - Frontmatter generation from IR
   - Wikilink generation from strategy topology
   - Mermaid generation (reuse existing helpers)
   - `_index.md` generation
   - `.obsidian/` config
4. Wire into `render_command` dispatch
5. Tests: verify watson generates expected page count, wikilinks resolve, frontmatter is valid YAML
6. E2E: open watson vault in Obsidian, verify graph view shows reasoning structure

### Phase 2: `/gaia:publish --obsidian` (~1 week)

1. Extend publish skill to support `--obsidian` flag
2. Write the LLM narrative protocol as skill prompt sections
3. Implement per-module and per-claim narrative generation
4. Handle `artifacts/` source lookup (paper PDF → relevant sections)
5. Image embedding support (`![[figure.png]]`)
6. Test on watson: verify narrative quality, callout annotations, figure embeds

### Phase 3: Polish (~few days)

1. `.obsidian/` graph view configuration (color-code nodes by type)
2. Dataview compatibility testing
3. `meta/beliefs.md` with sortable tables
4. `meta/contradictions.md` for packages with operators

## 10. Open Questions

1. **Should `obsidian` be part of `--target all`?** Currently `all` = `docs` + `github`. Adding `obsidian` would create a directory tree every time. Recommendation: keep it opt-in (`--target obsidian` explicit).

2. **Where does `gaia-wiki/` live?** Inside the package directory (committed to git) or outside (personal/ephemeral)? Recommendation: inside, but add to `.gitignore` template — it's a derived view, not source.

3. **Should we support incremental wiki updates?** Currently `gaia render` regenerates everything. For large packages, incremental would be valuable. Recommendation: defer to v2 — regeneration is fast for Phase 1, and Phase 2 (LLM) can be incremental by checking which pages' IR data has changed.

4. **How does this relate to the FOL/predicate logic proposal (#400)?** If Gaia adds predicates, each predicate definition would become a wiki page in a `predicates/` directory. The two-layer architecture (IR for search, wiki for reading) is compatible regardless of IR extensions.

5. **Should the LLM narrative be cached?** Phase 2 output is expensive (LLM calls). If IR hasn't changed, the narrative shouldn't need regeneration. Recommendation: use `ir_hash` + `review_content_hash` as cache key — only regenerate when either changes.
