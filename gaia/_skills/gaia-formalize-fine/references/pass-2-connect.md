# Pass 2 — Connect: write reasoning relations

Load this file after Pass 1 is complete and its compile + check loop passes.
When this pass is done, run the inner loop again and load
`pass-3-completeness.md`.

Pass 2 wires the knowledge graph. The default starting verb is `infer` (`gaia author infer`) — it is the **most general** way to say "this evidence updates the belief in that hypothesis." Specific strategy types are refined in Pass 4.

For each claim "supported by other claims," choose one of these author verbs:

- `gaia author derive --conclusion C --given P1,P2,...` — rigid implication: premises jointly support the conclusion. Use when the source presents a step-by-step derivation that, given the premises, is the intended way to reach the conclusion. To express warrant uncertainty (numerical methods, approximations, omitted conditions), label the `derive` with `--dsl-binding-name`/`--label` and then `gaia author register-prior --claim <warrant_label> --value ... --justification ...`.
- `gaia author infer --evidence E --hypothesis H --p-e-given-h ...` — Bayesian update: explicit P(E|H) and (optional) P(E|~H). Use when the source argues "observing E updates belief in H," especially when comparing competing hypotheses against the same observation.
- `gaia author observe --conclusion C [--value ... --error ...]` — raw measurement: ties a Claim, Variable, or Distribution to an observed value. Use for experimental measurements that anchor the graph in data.
- `gaia author compute --conclusion-type T --fn f --given P1,P2,...` — deterministic mapping: a named callable produces the result from the premises. Use when the source presents a closed-form computation whose function is captured by code.
- `gaia author decompose --whole W --parts A,B,... --formula-template and|or|atom` — structural split: composite claim → atomic parts. Use when an aggregate claim is best read as a conjunction (or disjunction) of independently judgeable atoms.
- `gaia author compose --from-file pattern.py` — register a reusable multi-step pattern as a `@compose`-decorated function. Use Pass 4 to refine flat `derive`/`infer` calls into compositions when meaningful intermediate propositions appear.

Plus the structural-relation verbs (no `--given`; these state a logical constraint between claims):

- `gaia author equal --a A --b B` — A = B (logically equivalent).
- `gaia author contradict --a A --b B` — NOT (A AND B): both cannot be true, but both can be false.
- `gaia author exclusive --a A --b B` — A XOR B: exactly one must be true (exhaustive + mutually exclusive).

When in doubt at this pass, reach for `infer` first; Pass 4 will tighten it.

### Reasoning-chain reconstruction

How to reconstruct each conclusion's reasoning trace — the detailed
`--rationale`, the premise (`--given`) vs background (`--background`) split,
surfacing implicit premises, and the seven step-writing rules — is **shared
with `gaia-formalize-coarse`**:

- [`../../_shared/formalize-reasoning-chains.md`](../../_shared/formalize-reasoning-chains.md)

In this skill's terms: claims used in the derivation go to `--given`; notes
and questions go to `--background`. The `--rationale` is a complete reasoning
chain a domain reader can follow, not a one-sentence stub.

### Use `@label` and `[@citation]` references in rationales

In the rationale text, use `@label` to reference knowledge nodes and `[@key]` to cite bibliography entries from `references.json`:

```python
rationale=(
    "Based on the XX framework (@framework_claim), under condition YY (@condition_claim), "
    "conclusion ZZ can be derived. The derivation uses the property of WW (@property_note). "
    "This follows the approach in [@Dias2020]."
)
```

**Knowledge refs** (`@label`): must appear in the verb's `--given` or `--background` list. Verified in Pass 3.

**Citations** (`[@key]`): must match a key in `references.json`. The strict `[@...]` form raises a compile error if the key is not found. Supports Pandoc group syntax: `[@Bell1964; @CHSH1969]`, `[see @Bell1964, pp. 33-35]`.

**Rule.** A single `[...]` group must be homogeneous — all knowledge refs or all citations, never mixed. `[@lemma_a; @Bell1964]` is a compile error.

Citations can also appear in **claim content** to provide traceability:

```python
tc_measurement = claim(
    "The measured superconducting transition temperature is 287.7 K at 267 GPa [@Dias2020].",
    title="CSH Tc measurement",
)
```

### Do not miss implicit premises

Surface every implicit premise per the step-writing rules in
[`../../_shared/formalize-reasoning-chains.md`](../../_shared/formalize-reasoning-chains.md):
a fact the derivation uses must be a node in the graph (a `--given` premise or
`--background`), never an unstated assumption. Reference it with `@label` in
the rationale.

### Model contradictions and exclusives

After wiring derivation / inference relations, model logical constraints between claims using structural verbs. These claim pairs were identified in Pass 1 reflection; now formalize them.

**Key distinction — get this right, it matters for BP:**

- `contradict(a, b)` = NOT (A AND B): both cannot be true, but both **can** be false.
- `exclusive(a, b)` = A XOR B: exactly one must be true (exhaustive + mutually exclusive).

**When to use `contradict`:** the source argues two claims are incompatible — they cannot both hold. Example: two competing hypotheses about a mechanism, where accepting one rules out the other, but a third option might exist.

```python
not_both = contradict(
    claim("The pairing mechanism is phonon-mediated"),
    claim("The pairing mechanism is magnon-mediated"),
    rationale="Phonon and magnon mechanisms produce incompatible signatures; the data matches only one.",
)
```

**When to use `exclusive`:** exactly two exhaustive, mutually exclusive options. One **must** be true.

```python
one_of = exclusive(
    claim("RFdiffusion outperforms Hallucination on this benchmark"),
    claim("Hallucination outperforms or matches RFdiffusion on this benchmark"),
    rationale="On the same benchmark with the same metric, one must be better or equal.",
)
```

**When to use `equal`:** two formulations express the same proposition.

```python
same = equal(
    claim("Energy is conserved in the closed system."),
    claim("dE/dt = 0 in the closed system."),
    rationale="Word form and differential form of the same statement.",
)
```

**When NOT to use either contradict or exclusive:** two claims that are "in tension" but can both be true. Example: "comprehensive improvement across all areas" and "enzyme scaffolding lacks experimental validation" — both can be true (comprehensive improvement does not require every area to have wet-lab validation). Do not model these as `contradict`. Flag them in the critical analysis as unmodelled tensions instead.

Contradictions and exclusives are especially valuable in BP because they create strong coupling between nodes — when one side's belief goes up, the other must go down. But a **wrong** contradiction silently distorts all downstream beliefs, so always verify semantics in Pass 5.

### Pass 2 reflection

Before moving to Pass 3, verify:

- **Theory-experiment pairs use `infer`?** Every place the source compares a theoretical prediction against an experimental observation should be connected via `infer(evidence=obs, hypothesis=pred, --p-e-given-h ..., --p-e-given-not-h ...)`. The relationship is explanatory ("does the observation support the prediction?"), not a rigid step-by-step derivation.
- **Multiple observations confirming one law?** If several independent observations all support the same general rule, the conclusion claim (the law) should be a `derive(...)` over those observations — and in Pass 4 you will likely refactor that to a `compose`'d pattern that names the generalisation step explicitly.
- **No missing alternatives?** When the source compares competing hypotheses against one observation, every alternative should be extracted as a claim and either chained as additional `infer` evidence or wired with `exclusive` if the source treats the alternatives as exhaustive.
- **Contradictions modelled?** Every contradictory claim pair identified in Pass 1 should now have a `contradict(...)` (or `exclusive(...)`) operator. Also check: did any new contradictions emerge while writing relations?
