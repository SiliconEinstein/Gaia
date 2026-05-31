# Reconstructing reasoning chains

Shared reference for `gaia-formalize-coarse` and `gaia-formalize-fine`. After
the paper's conclusions are extracted, both skills reconstruct how the paper
argues each one. This file is the canonical statement of that reconstruction.
Reference, not procedure — no frontmatter, not itself a skill.

This file owns the **logic graph**, the **per-conclusion reasoning trace**,
and the **step-writing rules**. It does not own which DSL verb carries the
relation (a `derive`-only reduced model vs the full `derive` / `infer` /
`observe` / `compute` / `decompose` set) — verb choice is a coarse-vs-fine
divergence owned by each skill. The independence of the resulting premises has
its own file, `formalize-independence.md`.

## The logic graph

Before reconstructing any chain, map the dependency edges among the extracted
conclusions. For each ordered pair `(A, B)`, add an edge `A → B` if and only
if:

- the reasoning that establishes B explicitly or implicitly relies on A's
  result as a premise or intermediate step, **and**
- the reliance is traceable to the paper text, not to your own reasoning about
  the subject.

Rules:

- The graph must be **acyclic**.
- Independent conclusions have no edges; that is expected.
- Edges must be **direct** — if `A → B` and `B → C`, do not also add `A → C`
  unless the paper uses A directly in deriving C without going through B.
- Topical similarity is not a derivation dependency.
- Two conclusions appearing in the same downstream application is not a
  derivation dependency.

## Topological ordering

Reconstruct conclusions in topological order on the logic graph:

1. If `A → B` is an edge, reconstruct A before B.
2. Tie-break by extraction order / id (smaller first).
3. Every conclusion is reconstructed exactly once, including isolated ones.

Order matters: when reconstructing B, A's result is already established and
can be referenced by name instead of re-derived, and the reconstruction order
lines up with a linearly readable emitted package.

## Per-conclusion reconstruction

For every conclusion, reconstruct the paper's own reasoning trace from
foundational material to the conclusion, as an ordered list of steps. Each
step is one logical move. **Steps are not claims** — they are the prose that
becomes the relation's `rationale`.

### Root and isolated conclusions

For a conclusion with no upstream conclusions, reconstruct the full chain from
the paper's foundations:

- definitions, assumptions, model setups;
- experimental protocol, dataset construction, sample preparation;
- the theoretical framework or governing equations;
- cited results explicitly invoked.

Capture every logical move. Do not skip mechanical algebra "for brevity" —
redundancy is acceptable, omission is not.

### Derived conclusions

For a conclusion B with upstream `A_1, A_2, ...`:

- the first one or two steps state each upstream conclusion's result (treating
  it as established) and which aspect B will use;
- the remaining steps are the **incremental** reasoning bridging the upstream
  results to B;
- include additional definitions, assumptions, or cited results only where the
  paper itself invokes them.

Do not re-derive an upstream conclusion. Do not invent a dependency the paper
does not use.

## Premises vs background

When wiring a relation, split what the reasoning rests on:

- **Claims** used in the derivation → **premises** (the support set).
- **Definitions, formal setups, fundamental principles, open questions** used
  in the derivation → **background**.

## Do not miss implicit premises

Papers often leave premises implicit. While writing the chain, if the
derivation depends on a knowledge node that was already extracted, add it to
the premise or background set and reference it in the rationale. If it depends
on something not yet extracted, go back and extract it — a fact the reasoning
uses must be a node in the graph, never an unstated assumption.

## Step-writing rules

1. **Maximize detail.** One logical move per step. Every symbol introduced is
   defined inside the same step or an earlier step of the same chain.
2. **Textualize figures and tables.** When the argument relies on what a
   figure shows, inline the quantity / shape / trend / comparison. Not
   "Fig. 3 shows a direct gap" but "the computed band structure has a direct
   gap of 1.2 eV at the $\Gamma$ point, falling to 0.8 eV under 5% biaxial
   strain". No step should require *seeing* a figure.
3. **Use formalism where the paper does.** Reproduce equations in `$...$` /
   `$$...$$`; do not paraphrase mathematics the paper states as a formula.
   Define every quantity at first appearance.
4. **Record logical gaps and heuristic moves explicitly.** If the authors
   skip a derivation, appeal to intuition, or assert without proof, record it
   as such ("the authors assert without derivation that ...", "the argument
   relies on a heuristic that ...") — do not silently repair it. These flagged
   steps inform the warrant-strength intent the calling skill writes into the
   rationale.
5. **No paper-internal pointers in step prose.** Resolve `Eq. (16)`,
   `Sec. II`, `Theorem 2`, `Appendix A`, "as derived above" by inlining the
   content. External citations are preserved but rewritten into `[@key]` form
   (see `formalize-extract-conclusions.md`).
6. **No external knowledge.** Do not invoke "well-known facts" or textbook
   results unless the paper explicitly does.
7. **Authorial voice.** Impersonal scientific voice without changing modal
   force: "We assume X" → "X is assumed"; do not strengthen ("show" / "prove")
   or weaken ("suggest" / "indicate") beyond the paper's own modality.

## The chain becomes the rationale

The ordered step list is the raw material for the relation's `rationale`
field. A rationale is a complete reasoning chain a domain reader can follow —
not a one-sentence stub. Keep the numbered-step structure; it carries through
to the emitted relation. Reference knowledge nodes by `@label` and bibliography
entries by `[@key]`; every `@label` in a rationale must appear in that
relation's premise or background set, and vice versa.
