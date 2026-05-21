# Phase 2 — Reconstruct the Reasoning Chain

Load this file after Phase 1 is complete. Phase 2 produces the per-conclusion
reasoning chains that will populate the `rationale=` field of each
`derive(...)` in Phase 4.

## Goal

For every Phase 1 conclusion, reconstruct the paper's own reasoning trace
from foundational material (definitions, assumptions, experimental setups,
upstream conclusions, prior cited results) to the conclusion itself.

The trace is held in working notes as an ordered list of step strings per
conclusion. Each step is one logical move. Steps are not claims; they are
prose that becomes part of `derive(...)`'s `rationale=`.

## Topological Ordering

Process conclusions in topological order on the Phase 1 logic graph:

1. If `A → B` is an edge, A is reconstructed before B.
2. Tie-break by id (smaller first).
3. Every conclusion appears exactly once, including isolated ones.

Topological order matters for two reasons:

- When reconstructing B, A's result is already established and can be
  referenced by name in B's chain instead of re-derived.
- The output of Phase 2 will line up with the deduction-emission order in
  Phase 4 so that downstream readers can read the package linearly.

## Per-Conclusion Reconstruction

### Root and isolated conclusions

For a conclusion with no upstream conclusions, reconstruct the full chain
from the paper's foundations:

- Definitions, assumptions, model setups.
- Experimental protocol, dataset construction, sample preparation.
- Theoretical framework or governing equations.
- Cited results explicitly invoked.

Capture every logical move from those foundations to the conclusion. Do not
skip mechanical algebra "for brevity"; redundancy is acceptable, omission is
not.

### Derived conclusions

For a conclusion B with upstream `A_1, A_2, ...`:

- The first one or two steps state what each upstream conclusion's result is
  (treating it as established) and which aspects of it B will use.
- The remaining steps are the **incremental** reasoning that bridges from
  those upstream results to B.
- If the derivation also uses additional definitions, assumptions, or cited
  results outside the upstream conclusions, include those — but only the
  ones the paper itself invokes.

Do not re-derive an upstream conclusion. Do not invent a dependency that the
paper does not use.

## Step-Writing Rules

### 1. Maximize detail and completeness

- One logical move per step.
- Every symbol introduced gets defined inside the same step or an earlier
  step in the same conclusion's chain.
- If the authors rely on a result implicitly, surface that reliance as its
  own step.

### 2. Textualize figures and tables

The paper Markdown does not carry figure pixels. When the paper's argument
relies on what a figure or table shows, **inline that information as prose**:
the specific quantity, the curve shape, the trend, the comparison value.

Avoid: "Fig. 3 shows a direct gap."
Write: "The computed band structure has a direct gap of 1.2 eV at the
$\Gamma$ point, decreasing to 0.8 eV under 5% biaxial strain."

After writing, no step should rely on a reader being able to *see* the
figure to follow the argument.

### 3. Use formalism where the paper uses formalism

- Reproduce equations explicitly with LaTeX in `$...$` or `$$...$$`.
- Do not paraphrase mathematics into prose if the paper itself states the
  formula.
- Define every quantity at first appearance.

### 4. Record logical gaps and heuristic moves explicitly

If the authors skip a derivation, appeal to intuition, or assert without
proof, record the move as such — do not silently repair it:

- "The authors assert without derivation that ..."
- "At this point the argument relies on a heuristic that ..."

These flagged steps inform the deduction warrant intent Phase 4 writes
into the `--rationale` prose; persistent gaps surface as explicit "the
authors assert without derivation" / "the argument relies on a heuristic"
sentences in the rationale (the engine `derive(...)` signature has no
`metadata=` / `warrant_prior` kwarg, so the calibration cannot live as
a number on the deduction itself).

### 5. No paper-internal pointers in step prose

Do not write "Eq. (16)", "Sec. II", "Theorem 2", "Appendix A", or "as derived
above in the paper" inside step text. Resolve every such pointer inline:

- "Using Eq. (16)" → reproduce the equation, with symbols defined.
- "The Hamiltonian defined in Sec. II" → write the explicit Hamiltonian.
- "By the argument in Appendix A" → summarize the relevant argument inline.

Paper-internal structural pointers are not preserved at all. **External
citations** are preserved (the cited work is still credited) but they are
rewritten into the `[@key]` form prescribed in rule 6a — never left in the
paper's original numeric form (`[33]`, `Ref. 5`).

### 6. No external knowledge

Do not invoke "well-known facts", standard theorems, or textbook results
unless the paper explicitly does. If the paper cites such results without
proof, record the citation as the paper presents it — but in the citation
form prescribed in rule 8 below.

### 6a. Citation form in step prose

External citations appearing in step prose use the `[@key]` form, where
`key` matches an entry in `references.json` (`<FirstAuthorSurname><Year>`,
e.g. `[@Smith2020]`). Do **not** leave numeric paper-style citations like
`[33]`, `Ref. 5`, or `Smith et al., 2020` in step prose; convert at write
time. If a key cannot be derived from the paper's bibliography, use
`@unknown_<n>` (bare `@key`, **no brackets** — `gaia build compile` rejects
bracketed `[@unknown_n]` as an unresolvable strict reference; bare `@key`
is opportunistic) and note the gap in the hand-off report. The full
citation contract (allowed prose forms, `refs` whitelist, CSL-JSON /
`references.json` conventions) is documented in
`docs/for-users/language-reference.md`.

### 7. Authorial voice

Use impersonal scientific voice without changing modal force.
"We assume X" → "X is assumed". "The authors observe Y" → "Y is observed".
Do not strengthen ("show" / "prove") or weaken ("suggest" / "indicate")
beyond the paper's own modality.

## Working Notes Schema

```yaml
reasoning_chains:
  - conclusion_id: 1
    title: <repeats Phase 1 title>
    upstreams: []
    steps:
      - "1. <full prose for step 1>."
      - "2. <full prose for step 2>."
      - ...
  - conclusion_id: 2
    title: ...
    upstreams: [1]
    steps:
      - "1. From conclusion 1's result, ... is treated as known: <inlined statement>."
      - "2. <bridging step>."
      - ...
```

Step ids are **local** to each conclusion's chain (1, 2, 3, ... per chain).
The numbered Markdown formatting carries through to the final `derive(...)`
`rationale=` field in Phase 4.

## Phase-Completion Gate

Before moving to Phase 3:

- Every Phase 1 conclusion has a reasoning chain in working notes.
- Each chain processes the conclusion in topological order on the logic
  graph.
- No step contains a paper-internal pointer (Eq./Fig./Table/Sec./Appendix)
  whose content has not been inlined.
- Every flagged logical gap or heuristic move is recorded as such, not
  silently repaired.
- The next todo is marked in progress before loading
  `phase-3-review-weak-points.md`.
