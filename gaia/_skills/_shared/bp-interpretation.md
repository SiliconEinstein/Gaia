# Interpreting `.gaia/beliefs.json`

Shared reference for interpreting `.gaia/beliefs.json` output from `gaia run infer`. Pointed at by `gaia-formalization`, `gaia-publish`, `gaia-obsidian-wiki`, and `gaia-review` — those skills invoke `gaia run infer` at the end of their workflow and need a single canonical place to read off "is this belief reasonable, or is something miswired?"

This doc is reference, not procedure. It is not itself a skill; it has no frontmatter.

## What `gaia run infer` writes

`gaia run infer [PATH]` reads the compiled IR at `.gaia/ir.json`, lowers it into a factor graph, runs belief propagation, and writes `.gaia/beliefs.json`. Priors come from claim metadata (set during compilation by `priors.py` and inline `prior=` warrant pairing) — `gaia run infer` itself does not edit priors, only propagates them.

The output shape:

```json
{
  "beliefs": [
    {
      "belief": 0.6964624519131176,
      "knowledge_id": "priya:coin_priors::h_informed",
      "label": "h_informed"
    },
    ...
  ],
  "diagnostics": {
    "belief_history": { "<knowledge_id>": [<per-iteration belief>, ...] },
    "converged": true,
    "iterations_run": 2,
    "max_change_at_stop": 0.0,
    "rho": 1.0,
    "treewidth": 2
  },
  "gaia_lang_version": "0.5.0a1",
  "ir_hash": "sha256:..."
}
```

Key fields:

- **`beliefs[*]`** — per-knowledge posterior. `belief` is the marginal P(claim is true) after BP. `label` is the DSL variable name if the node has one; anonymous nodes (operators, intermediate strategy artefacts) show `label: null` and a synthetic `knowledge_id` like `<pkg>::_anon_000`.
- **`diagnostics.converged`** — `true` means BP reached a fixed point within the iteration budget. `false` is a red flag: results are not trustworthy until you find why (usually a loopy structural relation with conflicting evidence).
- **`diagnostics.belief_history`** — per-iteration trajectory of each belief. Useful when `converged: false` to see if the value is oscillating or drifting.
- **`diagnostics.max_change_at_stop`** — final-iteration delta. Near zero with `converged: true` means a clean stationary point.

What to grep for during interpretation:

```bash
# Find low-belief derived conclusions (the symptoms to investigate)
jq '.beliefs[] | select(.label != null and .belief < 0.5)' .gaia/beliefs.json

# Find independent premises whose belief moved far from their prior
jq '.beliefs[] | select(.label == "<leaf_label>")' .gaia/beliefs.json

# Confirm BP converged before trusting any number
jq '.diagnostics.converged' .gaia/beliefs.json
```

Cross-check with `gaia build check --show <label>` whenever a number surprises you — `--show` prints the full warrant tree (premises, strategies, priors) for the target node, which is usually what you need to localise the cause.

### Cross-package inference: `--depth N`

`gaia run infer --depth N` changes what the BP runs over.

- **`--depth 0` (default).** Flat inference. Only the current package's factor graph runs; beliefs of any imported nodes from sibling packages are injected as **fixed priors** read from those packages' precomputed `dep_beliefs/`. Imported nodes appear in `beliefs.json` with their injected value and zero update.
- **`--depth 1`.** Joint inference with direct dependencies. The factor graphs of immediately-imported sibling packages are *merged* with the current package's graph and BP runs over the union. Imported nodes' beliefs can now move — evidence in the current package can update them, and their updated beliefs flow back into the current package's derivations.
- **`--depth -1`.** Joint inference with all transitive dependencies merged. Same mechanics, larger graph.

Implication for interpretation: a leaf claim that is "independent" inside the current package may *not* be a leaf in the joint graph if depth > 0 — it might be derived in an upstream package. When auditing an unexpectedly-low belief at depth > 0, check whether the claim is upstream-derived before assuming a local prior is wrong. The "Normal vs. abnormal" rules below apply to whatever role each node plays in the *effective* graph for the depth you ran.

## Normal vs. abnormal

Three patterns cover almost every interpretation question. For each, "normal" describes the belief BP should produce when the package is wired correctly; "abnormal" is the signature of a specific class of problem.

### Independent premises (leaf claims with priors)

These are claims you assigned a prior to in `priors.py` (or background-only claims). They are not the conclusion of any `derive` / `infer` strategy in the current graph.

- **Normal.** Belief stays close to the assigned prior. BP only nudges leaves slightly (via back-flow from downstream `derive` / `infer` / `contradict` / `exclusive` constraints), so small movements are expected.
- **Abnormal.** Belief significantly pulled *down* from the assigned prior. This means a downstream structural relation is conflicting with the prior — usually a `contradict` or `exclusive` is firing because the prior placed too much mass on a side that conflicts with stronger downstream evidence. Investigate: run `gaia build check --show <leaf-label>` to see which relations touch the leaf, and check whether the prior is genuinely justified or whether the structural relation is miswired.

### Derived conclusions

These are claims that *are* the conclusion of one or more `derive` or `infer` strategies. They have no own prior (setting one would double-count evidence) — their belief is determined entirely by BP propagating up from premises through warrants.

- **Normal.** Belief above 0.5, pulled up by the supporting derivations. The exact value reflects (premise priors) ⊗ (warrant priors on each `derive`) ⊗ (chain depth and breadth).
- **Abnormal.** Belief below 0.5 — the chain is not "pulling up." See common problems and fixes below.

### Contradiction / exclusive pairs

Structural relations that couple two (or more) claim beliefs.

- `contradict(a, b)` — soft NAND, "not both true." Belief mass cannot sit on both sides simultaneously.
- `exclusive(a, b, ...)` — XOR, "exactly one true." Belief mass is redistributed so the sum stays at 1.

Both create strong coupling: when one side's belief goes up, the other(s) must come down.

- **Normal.** One side ends high, the other(s) end low — BP "picks a side" based on which has more (or stronger) downstream evidence.
- **Abnormal.** Both sides end low — prior allocation problem. The priors on the two sides do not reflect the actual evidence-strength difference, so neither side dominates and the constraint pushes both down. Re-examine `priors.py`: the side that should be refuted should have a lower prior, not a symmetric one.

## Common problems and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Derived conclusion belief too low (< 0.3) | Chain too deep — multiplicative attenuation through many `derive` warrants. | Restructure with `compose` to control depth: collapse mechanical intermediate steps into a single composite warrant rather than chaining 5+ atomic `derive` calls. |
| Derived conclusion belief too low (< 0.3) | Premise priors too low for the strength of evidence. | Revisit `priors.py`; the leaf priors may understate well-established facts. |
| Derived conclusion belief too low (< 0.3) | Warrant `prior=` too low on one or more `derive` calls. | Audit warrants on the chain with `gaia build check --show <label>`; raise the `prior=` on any rigid-implication step that was conservatively set. |
| `contradict` doesn't "pick a side" (both ≈ 0.3-0.5) | Priors on both sides symmetric, so BP can't break the tie. | Lower the prior of the side that should be refuted. Keep the side with stronger backing at its informed prior. |
| Derived conclusion belief ≈ 0.5 (no movement at all) | Chain broken — some `derive` missing `prior=`, or an `infer` missing its CPT parameters, so the warrant defaults to uninformative. | Audit with `gaia build check --show <label>`; every warrant in the path should show an explicit prior or parameter set. |
| `exclusive` forces an unexpected branch high | `exclusive` redistributes the full probability mass across its arguments — if you wrote `exclusive(a, b)` but a third possibility exists in the domain, BP will push mass onto `b` whenever `a` is refuted, even if "neither" is the truth. | Either add the missing branches to the `exclusive`, or downgrade to `contradict` (which only forbids "both", not "neither"). |
| Independent premise belief pulled far below prior | Downstream `contradict` or `exclusive` is firing against the prior. | Identify the firing relation with `gaia build check --show <leaf-label>`; either fix the relation's other side or re-examine the leaf's prior. |
| BP `converged: false` | Loopy factor graph with conflicting evidence (rare in well-formed packages). | Inspect `diagnostics.belief_history` for oscillation; check for redundant relations (e.g., two `derive` paths to the same conclusion both with `contradict` partners) that create cycles. |

## Iteration loop

Interpretation is rarely one-shot. The expected loop:

1. `gaia run infer .` (add `--depth 1` if you want sibling-package evidence to participate).
2. Read `.gaia/beliefs.json`, classify each interesting node as normal/abnormal per the rules above.
3. For each abnormal node, localise with `gaia build check --show <label>`.
4. Edit `priors.py`, `derive(..., prior=...)`, or the structural relations as the table prescribes.
5. Re-run from step 1. Stop when every conclusion belief reflects the evidence the package actually carries — not when it hits a target number.
