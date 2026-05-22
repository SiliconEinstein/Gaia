# Evidence independence — no double counting

Shared reference for `gaia-formalize-coarse` and `gaia-formalize-fine`. Both
skills must ensure each reasoning relation they emit encodes a genuinely
independent constraint. This file is the canonical statement of the
independence check. Reference, not procedure — no frontmatter, not itself a
skill.

## The principle

Gaia runs exact inference (Junction Tree) — given any factor graph it computes
correct posteriors. There is no algorithmic double counting. Every issue here
is about whether the **model** matches reality: each relation must represent a
constraint that brings genuinely new information no other relation already
provides. When the same evidence enters a conclusion twice, the model claims
two independent constraints where only one exists, and beliefs inflate.

When an implicit dependency exists, make it **explicit** as a node in the
graph so inference can reason about it correctly.

The independence check applies to whatever relation verbs a skill emits — a
`derive`-only reduced model and a full `derive` / `infer` / `compute` /
`decompose` model are both subject to it. Patterns below that name a specific
verb apply only to skills that emit that verb.

## Pattern 1 — Redundant relations (same reasoning expressed twice)

```python
# 1a. Exact duplicate — the same support stated standalone and inside a wider relation
derive(law, given=[obs])
derive(law, given=[obs_a, obs_b, obs])   # re-uses obs
# FIX: drop the standalone relation, or fold it into the wider one.

# 1b. Transitive shortcut — an A→B→C chain plus an A→C that is just the chain compressed
derive(B, given=[A]); derive(C, given=[B]); derive(C, given=[A])
# FIX: drop the shortcut, OR confirm it is a genuinely different argument.

# 1c. Derived-premise redundancy — A→B, then C given [A, B] where A reaches C only through B
derive(B, given=[A]); derive(C, given=[A, B])
# FIX: drop A from C's premises → derive(C, given=[B]).
```

## Pattern 2 — Hidden evidence in rationale text

Two relations with identical premises but different `rationale` prose: the
differing prose contains evidence not captured as a premise. Extract it.

```python
# BEFORE — same premises, different reasoning angles
derive(law, given=[sample, obs_R], rationale="Zero resistance = SC hallmark")
derive(law, given=[sample, obs_R], rationale="Transition width < 0.5 K = bulk SC")

# AFTER — the hidden "transition width" evidence becomes its own claim
transition_sharpness = claim("Resistivity transition width < 0.5 K")
derive(law, given=[sample, obs_R], rationale="Zero resistance = SC hallmark")
derive(law, given=[sample, transition_sharpness], rationale="Sharp transition = bulk SC")
```

## Pattern 3 — Unmodelled shared dependencies

Two observations share a common cause (same sample, same instrument) but the
cause is not in the graph: the model treats them as unconditionally
independent and loses their correlation.

```python
# BEFORE — shared sample quality implicit, correlation lost
derive(law, given=[obs_R, obs_chi])

# AFTER — extract the shared cause; correlation preserved
sample_quality = claim("Sample A is a high-quality single crystal, confirmed by XRD")
derive(obs_R,   given=[sample_quality])
derive(obs_chi, given=[sample_quality])
derive(law,     given=[obs_R, obs_chi], rationale="Conditionally independent given sample_quality")
```

You cannot create new experiments — you formalize what the paper provides:

| Observation relationship | Modelling approach |
|---|---|
| Truly independent (different samples / labs) | Use the observations directly as parallel premises |
| Partially independent (shared dependency + independent components) | Extract the shared dependency as an explicit claim |
| Completely redundant (same data rephrased) | Merge into a single claim |

## Pattern 4 — `equal` plus separate relations (structural-verb skills only)

When `equal(a, b)` couples two claims and both sides also relate to the same
target, check each relation brings information beyond what `equal` already
propagates.

```python
equal(claim_A, claim_B)
derive(law, given=[claim_A]); derive(law, given=[claim_B])
# Does B→law add anything A→law + equal does not already give?
# NO  → drop B→law.   YES → extract the extra information as a new premise.
```

## Shared-factor extraction

If two supports on the same target share an underlying factor — same
approximation, same dataset, same lemma, same external assumption — extract
the shared factor as its own claim and let both supports depend on that one
factor, rather than letting the factor's uncertainty enter the target twice.

## Repeated observations must be independent

When a general rule is supported by several observations, each must provide
**independent** evidence. If they share a sample, instrument, or pipeline,
that shared dependency is a Pattern 3 case — extract it as an explicit claim
before treating the observations as parallel support.

## How to check

1. List every claim with 2+ incoming relations.
2. For each pair of relations into it: does each bring genuinely independent
   new information?
3. For each relation over multiple observations: do the observations share an
   unmodelled dependency?
4. For each `equal`: do both sides need their own relation to the same target?
5. For every relation: does the `rationale` prose contain evidence not
   captured as a premise?

After any independence fix, re-run inference and compare beliefs. A
significant belief drop after removing a relation confirms the previous value
was inflated by double counting. For reading the resulting beliefs, see
`bp-interpretation.md`.
