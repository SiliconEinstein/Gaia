---
name: gaia-obsidian-wiki
description: |
  Use when the user wants a browsable Obsidian vault (`gaia-wiki/`) from a Gaia
  knowledge package. Generates a skeleton via `gaia run render --target
  obsidian`, then rewrites every page to faithful-reproduction depth (full
  derivations, figure embeds, Review/Supports/Significance/Caveats sections),
  authors narrative section chapters in DSL module order, and specialises Weak
  Points + Open Questions sections.
---

# Gaia Obsidian Wiki

Produce an Obsidian vault from a Gaia knowledge package where each page can
replace reading the paper for its topic. The CLI generates one skeleton in one
shot; the value of this skill is the writing discipline that turns the
skeleton into a faithful, browsable reproduction.

## When to use

Trigger this skill when the user asks for a "wiki", an "Obsidian vault", a
"browsable knowledge base", or any rich per-claim reproduction from a Gaia
package. The output is an Obsidian-compatible directory tree (`gaia-wiki/`)
ready to open as an Obsidian vault.

## CLI invocations

Prerequisites — the package must compile and infer cleanly:

```bash
gaia build compile .
gaia run infer .
```

Generate the vault skeleton:

```bash
gaia run render . --target obsidian
```

`--target obsidian` writes `gaia-wiki/` and enriches pages with belief and
prior values when fresh inference results are available. Beliefs are
optional but strongly recommended — without them, every Review section
collapses to "no belief".

Inputs the agent reads before rewriting:

```bash
cat .gaia/ir.json          # node + strategy graph, exported flags
cat .gaia/beliefs.json     # per-claim posterior beliefs from BP
cat src/<package>/*.py     # the DSL source — the ground truth for derivations
ls artifacts/              # figures, references, source PDFs
```

Read `artifacts/` cover-to-cover before writing any page. The rewrite step
copies derivations and figure captions from the source material; if the
agent hasn't read the source, it can only paraphrase the skeleton, which
violates the faithful-reproduction principle.

## Vault architecture

`gaia run render --target obsidian` writes:

```
gaia-wiki/
├── claims/
│   ├── holes/              # Leaf premises — chain endpoints, no upstream support
│   ├── intermediate/       # Derived but not exported
│   ├── conclusions/        # Exported claims (★) and questions
│   └── context/            # Notes — backgrounding material that anchors the package
├── sections/               # Narrative chapters in DSL module order
│   ├── 01 - Root.md
│   ├── ...
│   ├── NN - weak-points.md
│   └── NN+1 - open-questions.md
├── meta/                   # beliefs.md (full table), holes.md (leaf premises)
├── _index.md               # Claim Index + Sections table + Reading Path
├── overview.md             # Citation + abstract + simplified Mermaid
└── .obsidian/              # Workspace config (graph colour groups, etc.)
```

Conventions baked into the skeleton:

- **Claim filenames use titles** (e.g., `04 - daily observation.md`); the
  frontmatter carries `label:` and `aliases:` so wikilinks can use either the
  human title or the DSL label.
- **Wikilink form is `[[label|#XX title]]`** — the bar-form keeps the label
  stable (Obsidian resolves it regardless of file renames) while showing a
  human-readable display.
- **Claim numbers (`#XX`) follow topological order** — a reader walking the
  numbers walks the reasoning chain.
- **Frontmatter is machine-readable** — fields include `type`, `label`,
  `aliases`, `claim_number`, `qid`, `module`, `exported`, `prior`, `belief`,
  `strategy_type`, `premise_count`, `tags`. Do not modify these by hand;
  later renders overwrite them.

## Claim pages

Each claim file is a self-contained article. The skeleton ships with `Title`,
the verbatim claim statement as a blockquote, a stub `## Review` (prior /
justification / belief), `## Supports` (downstream claims, when relevant),
`## Derivation` (strategy + premises, when the claim has a strategy), and
`## Module`. The agent expands this into the full ordering below.

**Section ordering on a finished claim page:**

1. **Title** — Descriptive in the user's language. Keep the `#XX` prefix
   exactly as the skeleton emits it.
2. **Content** — Full explanation of what the claim says, with all
   numerical values, equations, conditions, and units. This replaces the
   one-line blockquote when the agent expands the page.
3. **Background** — Scientific context from `artifacts/`. What problem is
   being attacked? What's the prior art? What gap does this claim address?
   Embed figures here with `![[file.jpg]]` followed by an italic caption.
4. **Derivation** — Reproduce the source's full argument:
   - All equations with step-by-step explanation
   - Physical reasoning behind each step
   - Why each approximation is justified
   - Numerical validations from the source
   - Appendix material when the source has it
   - Use `[[label|#XX label]]` for cross-references to premises
5. **Review** — From `beliefs.json` and `priors.py`:
   ```
   **Prior**: 0.95
   **Justification**: ω_D / E_F ~ 0.005; Migdal theorem validated.
   **Belief**: 0.71
   ```
   See `../_shared/bp-interpretation.md` for what the prior → belief shift
   reveals. Do not duplicate the interpretation table here.
6. **Supports** — Downstream claims that consume this one (the skeleton
   pre-populates the bullet list; expand each with a one-line description of
   how it gets used).
7. **Significance** — Why the claim matters. What breaks downstream if it
   turns out to be wrong?
8. **Caveats** — Limitations, alternative explanations, uncertainties the
   source itself acknowledges.

**Depth by claim type:**

| Type | Depth |
|------|-------|
| **Conclusions** (★) | Most detailed — full derivation chain, every related claim cross-linked, multiple paragraphs per section, all figures embedded |
| **Holes** | Focus on source provenance — where does this evidence come from? Measurement method, precision, limitations, why no upstream support is possible |
| **Intermediate** | Full step-by-step derivation of this link in the chain |
| **Context** | Brief — what the note anchors (e.g., "this package treats vacuum falling as a counterfactual setup, not as an observed fact"). Context pages correspond to `note(...)` declarations in the v0.5 DSL |

## Section pages — narrative chapters

Section pages are the chapters of a textbook rewrite of the source. A reader
who walks `01 → 02 → … → NN` in order should understand the source's
complete argument without ever opening the original.

Page structure, top to bottom:

1. **Title** — Descriptive narrative title in the user's language. Keep the
   number prefix the skeleton emits.
2. **Overview** (~10%) — Two or three paragraphs setting up the section's
   question, approach, and headline result.
3. **Per-section Mermaid** — Keep the skeleton's Mermaid block verbatim; do
   not rewrite labels (Mermaid stays in English so the renderer can resolve
   wikilinks regardless of UI language).
4. **Claims narrative** (~70% — the main body) — For every claim in the
   section, in topological order, write a `###` heading plus one to three
   paragraphs. This is not optional. The skeleton enumerates the claims as
   `### [[label|#XX title]]` entries; expand each into a full narrative
   paragraph. For each claim:
   - `### [[label|#XX title]]` heading (keep the wikilink as-is)
   - What the claim says in plain language, with key numbers and equations
   - Why the result matters for this section's argument
   - How it connects to the previous and next claims (logical flow)
   - If the claim is exported (★), highlight it as a key conclusion with a
     `[!IMPORTANT]` callout block:
     ```
     ### [[downfolded_bse|#43 下折叠 BSE]] ★

     > [!IMPORTANT] 核心结论
     > 完整的动量-频率 BSE 可以严格化简为仅依赖频率的一维积分方程，
     > 误差仅 0.2%。

     这是本章最重要的结果……
     ```
   - Optional: a one-line belief-shift note (e.g., "prior 0.95 → belief 0.71
     — the chain pulls confidence down via the cross-term suppression
     bottleneck").
5. **Chapter summary** (~10%) — What this chapter established and what it
   sets up for the next chapter.

**Do not write a section page with only the overview and Mermaid.** The
claims narrative is what readers come here to read; without it the section
page is empty.

## Weak Points section

A dedicated section page (the skeleton names it `weak-points`) that reads as
a critical assessment, not a data dump. The skeleton seeds it with a table
of the lowest-belief claims; the agent rewrites it into structured analysis.

1. **Executive summary** (one paragraph) — The single most important
   takeaway. If you had to bet on which claim will fail, which one and why?
2. **Structural analysis** — Group weak points by graph position:
   - **Foundation weaknesses** — leaf premises (holes) whose failure would
     collapse the chain
   - **Bottleneck weaknesses** — single claims that many conclusions depend
     on; a low-belief bottleneck is more dangerous than a low-belief leaf
   - **Propagation effects** — points where the reasoning graph amplifies
     uncertainty (e.g., "the downfolded BSE has belief 0.33 not because it
     is intrinsically unreliable, but because it depends on cross-term
     suppression with belief 0.50, propagated through three derivation
     steps")
3. **Per weak point** (top 3–5), one full paragraph each:
   - What the claim says and where it sits in the chain
   - Why the belief is low — trace the graph backwards to the root cause
   - What the reviewer's justification reveals about the uncertainty
   - What competing explanation or alternative approach exists
   - What specific evidence or experiment would resolve the uncertainty
   - What downstream conclusions would be affected if it fails
4. **Comparison with the source's own assessment** — Does the source
   acknowledge these weaknesses? Does the reasoning graph reveal weaknesses
   the source doesn't discuss?

## Open Questions section

A dedicated section page (the skeleton names it `open-questions`) framed as
a research roadmap derived from the reasoning graph.

1. **Overview** (one or two paragraphs) — What would make this knowledge
   package "complete"? What is the single most impactful improvement?
2. **Questions from the source** — For each `question(...)` node in the IR:
   - What the question asks
   - Why it matters for the overall argument
   - What the source suggests (if anything) as an approach
   - Which conclusions depend on it
3. **Evidence gaps, grouped by theme:**
   - **Experimental** — measurements that are missing or imprecise; which
     claims rely on the weakest experimental evidence; what experiments
     would most reduce uncertainty
   - **Computational** — calculations that are approximate but could be
     made exact; parameters with the largest error bars; what computational
     advances would help
   - **Theoretical** — derivations that rely on uncontrolled approximations;
     where the theory breaks down; what extensions would broaden
     applicability
4. **Impact analysis** — For each gap, trace forward through the reasoning
   graph: if this hole were filled with higher confidence, which
   conclusions would improve? Rank holes by information value — how much
   would filling each reduce overall uncertainty?
5. **Prioritised next steps** — A list of three to five actionable research
   directions, each with what to do, why it's high-impact (which
   conclusions it would strengthen), and rough difficulty / feasibility.

## Overview, _index, meta

The skeleton already populates these; the agent rewrites them lightly.

- **`overview.md`** — Citation + abstract + the package-wide simplified
  Mermaid. Expand the abstract into a one-paragraph framing of what the
  package models and what it concludes.
- **`_index.md`** — Package description + statistics + the Claim Index
  table (with `#XX` numbers and belief column) + Sections table + Reading
  Path. Add a short paragraph above the tables describing the overall
  thrust of the package.
- **`meta/beliefs.md`** — Intro paragraph plus the full belief table.
  Highlight the three or four most surprising belief values (highest holes,
  lowest conclusions) with a one-line gloss.
- **`meta/holes.md`** — Intro paragraph plus the leaf-premise table.
  Group holes by theme when the package has more than a handful.

## Quality standard — faithful reproduction

The principle is **faithful reproduction, not summarisation**. If the source
devotes three pages to a derivation, reproduce it in readable form;
including appendix material is correct, not excessive. Every claim page must
carry:

- All relevant numerical values, with units and error bars
- Key equations, each with a step-by-step explanation
- Derivation steps from the source (appendix included)
- Figure embeds, each with an italic caption:
  ```
  ![[8_0.jpg]]
  *Figure 4: vDiagMC calculation of μ_EF(r_s). Adapted from Cai et al.*
  ```
- Cross-references via `[[label|#XX label]]`
- Review justification where `priors.py` and `beliefs.json` carry one

## Cross-reference audit

Before declaring the vault done, run a sweep:

- **Wikilinks resolve** — Every `[[label]]` and `[[label|...]]` target
  exists as a file (Obsidian's "unresolved links" pane is the fastest
  check; the `aliases:` frontmatter is what makes label-form links
  resolve).
- **Claim numbers consistent** — The `#XX` in a page's title, in
  cross-reference wikilinks, and in `frontmatter.claim_number` all match.
  If they drift, re-run `gaia run render --target obsidian` rather than
  patching by hand.
- **Figure embeds have italic captions** — `![[file]]` without a caption
  is a defect; either add one or remove the embed.
- **Frontmatter intact** — `type`, `label`, `aliases`, `claim_number`,
  `qid`, `module`, `exported`, `prior`, `belief`, `strategy_type`,
  `premise_count`, `tags` are all machine-generated. Don't edit them; if
  they're wrong, the fix is upstream in the DSL.
- **Vocabulary is reader-facing** — No Gaia jargon (`noisy_and`, `factor
  graph`, `BP`, `NAND`) in prose; belief values appear parenthetically or
  in the Review section, never as the headline of a claim.

## Multilingual discipline

- **Page bodies** follow the user's language preference (Chinese, English,
  whatever the source is in).
- **Frontmatter** stays English — field names and machine values are
  resolved by Obsidian's parser, not by readers.
- **Wikilinks** use the DSL `label` (which is English by convention), so
  links resolve regardless of UI language. The display half of the
  bar-form (`[[label|display]]`) is what the user reads.
- **Mermaid blocks** stay English — node IDs and labels in Mermaid must
  match the DSL labels for the renderer to wire them up.

## DO NOT

- Leave skeleton English filler on a page meant to be read in another
  language
- Write thin summaries that paraphrase the source instead of reproducing
  the derivation
- Use Gaia jargon in prose (`noisy_and`, `abduction`, `factor graph`,
  `BP`)
- Modify frontmatter or wikilink targets by hand
- Embed figures without italic captions
- Duplicate full derivations in section pages (the section page narrates;
  the claim page derives)
- List weak points without explaining **why** they're weak

## Cross-refs

- [`../_shared/bp-interpretation.md`](../_shared/bp-interpretation.md) —
  How to read the Review section's `Prior → Belief` shift on each claim
  page.
- [`../gaia-formalize-fine/SKILL.md`](../gaia-formalize-fine/SKILL.md) —
  Upstream skill: produces the DSL source, `priors.py`, and the
  `ANALYSIS.md` that this vault visualises.
- [`../gaia-publish/SKILL.md`](../gaia-publish/SKILL.md) — Alternate
  output channel: a polished GitHub README from the same package, for
  readers who prefer linear prose over a hyperlinked vault.
