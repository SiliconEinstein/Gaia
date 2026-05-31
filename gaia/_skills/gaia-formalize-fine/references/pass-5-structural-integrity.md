# Pass 5 — Verify structural integrity

Load this file after Pass 4 is complete and its compile + check loop passes.
When this pass is done, run the inner loop again and load `pass-6-polish.md`.

**Prerequisite:** Pass 4 is complete — all relation types are finalised. This pass checks that the factor graph correctly represents the source's reasoning. It must happen after Pass 4 because verb refinement (especially `compose`'d patterns) changes the graph topology.

**Background.** Gaia uses Junction Tree (exact inference). There is no algorithmic double-counting — given any factor graph, JT computes correct posteriors. All issues in this pass are about whether the **model** correctly represents reality: each factor (relation / structural verb) should represent a genuinely independent constraint, and each structural verb's logical semantics should match the actual relationship.

### 5a. Verify structural-verb semantics

Check structural verbs first — if the graph's hard constraints are wrong, everything downstream is wrong too.

Review every `contradict(...)`, `exclusive(...)`, and `equal(...)` call:

**`contradict(a, b)` = NOT (A AND B)**: both cannot be true, but both **can** be false.

```python
# WRONG: these can both be true — no contradiction!
contradict(
    claim("RFdiffusion succeeds at designing large proteins"),
    claim("Hallucination fails at designing large proteins"),
)

# CORRECT: these cannot both be true
contradict(
    claim("RFdiffusion is inferior to Hallucination on this task"),
    claim("RFdiffusion outperforms Hallucination on this task"),
)
```

**`exclusive(a, b)` = A XOR B**: exactly one must be true. Stronger than `contradict`.

**Three-question checklist for each structural verb call:**
1. Can both claims be true simultaneously? If yes → not a `contradict`, remove it.
2. Can both claims be false simultaneously? If no → should be `exclusive` (XOR), not `contradict` (NAND).
3. Is this just "in tension" rather than logically exclusive? Informal tension should NOT be modelled as `contradict` — flag in critical analysis instead.

### 5b. Eliminate double counting

Every factor in the factor graph must encode a **genuinely independent
constraint**; the same evidence entering a conclusion twice inflates belief —
not because Junction Tree miscalculates, but because the model is wrong. The
double-counting patterns (redundant relations, hidden evidence in rationale
text, unmodelled shared dependencies, `equal` plus separate relations), the
shared-factor extraction rule, the modelling-choice table, and the check
procedure are **shared with `gaia-formalize-coarse`**:

- [`../../_shared/formalize-independence.md`](../../_shared/formalize-independence.md)

All four patterns apply to this skill — it emits the full relation-verb set,
including `equal`. One Pass-5-specific addition to the shared check: for every
`infer` call, confirm `--p-e-given-h` is a source-supported value and
`--p-e-given-not-h` is the right alternative-likelihood (not a stand-in 0.5
when the source actually argued an alternative). Run the shared file's check
procedure over every claim with 2+ incoming relations before 5c.

### 5c. Re-compile and verify

After any structural changes in Pass 5, run `gaia build compile` + `gaia build check` + `gaia run infer` and compare beliefs to before. A significant belief drop after removing a relation suggests the previous value was inflated by double counting.
