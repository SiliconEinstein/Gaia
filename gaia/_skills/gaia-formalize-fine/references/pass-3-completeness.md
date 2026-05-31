# Pass 3 — Check completeness

Load this file after Pass 2 is complete and its compile + check loop passes.
When this pass is done, run the inner loop again and load
`pass-4-strategy-types.md`.

**Prerequisite:** code from Pass 1-2 has been written and passes `gaia build compile` and `gaia build check`. Pass 3 combines `gaia build check` feedback with manual review.

### 3a. Check `@label` and `[@citation]` reference consistency

Review each relation's rationale one by one:

1. **Re-read the rationale.** Carefully read every sentence.
2. **Check `@label` coverage.** Every `@label` in the rationale must appear in `--given` or `--background`.
3. **Reverse check.** Every node in `--given` / `--background` should be referenced by `@label` in the rationale (otherwise, why is it a premise?).
4. **Check if additional knowledge is needed.** If the rationale mentions an important fact without a corresponding `@label`, go back to Pass 1 to add it.
5. **Check `[@citation]` coverage.** Key claims and reasoning steps from the source should cite the original via `[@key]`. Ensure `references.json` contains all referenced keys.

### 3b. Check for claims missing reasoning

Use `gaia build check` output to see if any claim should have reasoning support but lacks a relation:

- `gaia build check` reports claims that are not the conclusion of any relation (leaf nodes).
- Review each leaf node: is it truly an independent premise? Or should it have an `infer` / `derive` / `compute` / `observe` relation?
- Criterion: if the source provides an argument for this claim (not just a statement), it should have one.

### 3c. Check for isolated nodes

- Are there claims that are neither premise / background of any relation nor conclusion of any relation?
- Isolated nodes indicate they do not participate in the reasoning graph — either they should not exist, or a relation referencing them was missed.

The most common mistake at this step is **assuming certain knowledge does not need explicit references.** In Gaia, if the reasoning process depends on a fact, that fact must be a node in the knowledge graph.
