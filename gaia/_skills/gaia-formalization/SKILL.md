---
name: gaia-formalization
description: |
  Use when formalising a knowledge source (scientific paper, textbook chapter,
  technical report) into a Gaia knowledge package. Walks a six-pass pipeline —
  extract → connect → check completeness → refine strategy types → verify
  structural integrity → polish for standalone readability — with a compile +
  check loop after every pass and a prior-assignment + inference tail. Emits
  the package source, `priors.py`, and `ANALYSIS.md`.
---

# Knowledge-package formalization

Drive an agent through formalising a source (scientific paper, textbook chapter, technical report) into a Gaia knowledge package. The output is DSL source under `src/<pkg>/` — `claim`, `derive`, `infer`, `observe`, `compute`, `equal`, `contradict`, `exclusive`, `decompose`, `note`, `question`, `compose` statements authored either via the `gaia author <verb>` CLI or by hand — plus `priors.py` for leaf-claim priors, plus a critical-analysis `ANALYSIS.md` deliverable. Every CLI verb the skill calls is on `gaia` today; the skill is the methodology that surrounds them.

## Overview

Formalization is a **six-pass** process. Each pass builds on the previous one. Do not skip passes or combine them.

**Key principle: formalization is incremental.** After completing each pass, write code, compile, and check. Do not wait until all passes are done before writing code. Feedback from `gaia build compile` and `gaia build check` is critical input for the next pass.

```
Pass 1: Extract                 → write DSL code
  ↓ gaia build compile + gaia build check
Pass 2: Connect                 → wire premises to conclusions with derive / infer / observe / compute / decompose; add equal / contradict / exclusive
  ↓ gaia build compile + gaia build check
Pass 3: Check completeness      → @labels audit, missing reasoning, isolated nodes
  ↓ gaia build compile + gaia build check
Pass 4: Refine strategy types   → tighten infer → derive / compute / observe / compose
  ↓ gaia build compile + gaia build check
Pass 5: Structural integrity    → operator semantics, double-counting elimination, hidden-evidence-in-reason, shared-dependency extraction
  ↓ gaia build compile + gaia build check
Pass 6: Polish                  → self-containedness, figures, formatting
  ↓ gaia build compile + gaia build check
gaia build check --hole         → write priors.py
  ↓
gaia run infer .                → .gaia/beliefs.json
  ↓ Interpret BP results (see ../_shared/bp-interpretation.md)
  ↓ ┐
    │ structural issues  → back to Pass 1-5
    │ prior issues       → revise priors.py
    └ otherwise          → ANALYSIS.md → gaia run render --target github
```

| Pass | Focus | Core question |
|------|-------|---------------|
| 1 | Content extraction | Are claims and notes extracted? Atomic? |
| 2 | Reasoning connections | Are derivations, inferences, observations, computes, and structural relations modelled? |
| 3 | Content completeness | Any missing premises, orphans, or `@label` errors? |
| 4 | Strategy precision | Is each author verb the right one (`derive` vs `infer` vs `compute` vs `observe` vs `compose`)? |
| 5 | Structural integrity | Is evidence independent? Are `contradict` / `exclusive` semantics correct? |
| 6 | Standalone readability | Can a reviewer understand everything without the source? |

## Scope

Formalize the **complete** source — not just the main result. A partial formalization leaves reasoning gaps: premises without support, alternatives without comparison, intermediate steps without justification. If the source is too large (a full textbook, say), formalize one chapter at a time, each as a separate Gaia package.

## CLI invocations referenced by this skill

The methodology below leans on this fixed set of CLI calls. Drill into `gaia <group> <verb> --help` when you need exact flags.

- `gaia build init <name>-gaia` — fresh package skeleton (`src/<import_name>/__init__.py`, `pyproject.toml`). Does not create `artifacts/` or `references.json` — make those manually.
- `gaia build compile <pkg>` — lower DSL → IR (`.gaia/ir.json`). Run after every pass.
- `gaia build check <pkg>` — structural validation + role classification (independent / derived / structural / background / scaffolded / orphaned). Use between passes:
  - `gaia build check <pkg> --brief` — per-module overview with strategy summaries.
  - `gaia build check <pkg> --show <module-or-label>` — expand a single module / claim / warrant tree.
  - `gaia build check <pkg> --hole` — list independent claims missing priors (with content + QID).
  - `gaia build check <pkg> --gate` — publish-readiness gate (CI-friendly, non-zero on failure).
- `gaia author <verb>` — append a DSL statement and re-check. The verbs you will use most:
  - `gaia author claim` — declare a `claim(...)` knowledge node (use when first surfacing a proposition).
  - `gaia author note` — declare a `note(...)` background statement (use for mathematical definitions, formal setups, fundamental principles).
  - `gaia author question` — declare a `question(...)` research question.
  - `gaia author derive --conclusion ... --given ...` — author a directed implication: premises rigidly support the conclusion. Carry `--rationale` for the natural-language justification; express residual warrant uncertainty by `gaia author register-prior` against the derive's labelled output Claim (or its auto-generated warrant helper).
  - `gaia author infer --evidence ... --hypothesis ... --p-e-given-h ...` — author a Bayesian update on new evidence; the `--p-e-given-h` likelihood is required, `--p-e-given-not-h` defaults to 0.5.
  - `gaia author observe --conclusion ... [--value ... --error ...]` — author a measurement event tied to a Claim, Variable, or Distribution.
  - `gaia author compute --conclusion-type ... --fn ... --given ...` — author a deterministic-computation step (a named callable produces the result Claim).
  - `gaia author decompose --whole ... --parts ... --formula-template and|or|atom` — split a composite claim into atomic parts.
  - `gaia author equal --a ... --b ...` — equate two claims (logical equivalence).
  - `gaia author contradict --a ... --b ...` — assert NOT (A AND B): both cannot be true, but both can be false.
  - `gaia author exclusive --a ... --b ...` — assert A XOR B: exactly one must be true (exhaustive + mutually exclusive).
  - `gaia author compose --from-file pattern.py` — register a `@compose`-decorated reusable reasoning pattern.
  - `gaia author register-prior --claim ... --value ... --justification ... [--file priors.py]` — write a `register_prior(...)` statement; auto-injects the import if the target file is a sibling.
- `gaia run infer <pkg>` — run BP, emit `.gaia/beliefs.json`. Pass `--depth N` (>0) to merge dependency packages' factor graphs for joint cross-package inference.
- `gaia run render <pkg> --target github` — generate `.github-output/` README + narrative outline (handoff to `../gaia-publish/SKILL.md`).
- `gaia run render <pkg> --target docs` — per-module Mermaid graphs in `docs/detailed-reasoning.md`.
- `gaia run render <pkg> --target obsidian` — `gaia-wiki/` skeleton (handoff to `../gaia-obsidian-wiki/SKILL.md`).

Author verbs accept either an existing identifier (`--conclusion my_claim`) or auto-author the conclusion in-line (`--conclusion-content "..."`). Every authored statement supports `--dsl-binding-name` (Python LHS) and `--label` (engine `label=` kwarg) — assign both when the statement needs to appear in `gaia build check --brief` output and be referenceable by downstream verbs.

## Pass 0 — Prepare artifacts

Copy the source materials into the package's `artifacts/` directory, and create a `references.json` for bibliographic citations.

```
my-package-gaia/
├── artifacts/
│   ├── paper.pdf
│   ├── paper.md
│   └── figures/...
├── references.json
├── src/
│   └── my_package/
│       ├── __init__.py
│       ├── motivation.py
│       └── ...
└── pyproject.toml
```

`gaia build init` does not create `artifacts/` or `references.json` — make them manually.

### `references.json`

Bibliographic citations in CSL-JSON format (dict-by-key), shared across the entire package. Start with a minimal skeleton; fill incrementally as citations are needed during Passes 1-4:

```json
{
  "Dias2020": {
    "type": "article-journal",
    "title": "Room-temperature superconductivity in a carbonaceous sulfur hydride"
  }
}
```

Keys must follow Pandoc citation-key grammar (letters, digits, `_`, `-`, `.`, `:`, `/`). Each entry requires `type` (CSL 1.0.2) and `title` at minimum. Add new entries as you hit citations; do not enumerate everything upfront. Complete metadata (authors, DOI, volume, pages) is filled in during Pass 6.

`references.json` is optional — without it, `[@...]` citations are not available.

Both PDF and markdown formats are supported for artifacts. Throughout formalization, refer back to the originals in `artifacts/` to keep numbers, formulas, and reasoning steps consistent with the source.

## Pass 1 — Extract knowledge nodes

Read the source **section by section**. For each section, identify:

| Type | Criterion | Examples | Author verb |
|------|-----------|---------|---|
| **note** | Background facts that cannot be questioned | Mathematical definitions, formal setups, fundamental principles | `gaia author note` |
| **claim** | Propositions that can be questioned or falsified | Computation results, theoretical derivations, predictions, experimental observations | `gaia author claim` |
| **question** | Open research questions | Driving questions for the source | `gaia author question` |

### Organize by module

Each source section corresponds to one Gaia module (Python file):

- Introduction → `motivation.py`
- Section II → `s2_xxx.py`
- ...

The module's docstring serves as the section heading. Each knowledge node should have a `title` parameter.

### Place knowledge in the earliest module

Each knowledge node belongs in the module corresponding to the section where it **first appears** in the source. Content from the Introduction goes into `motivation.py`. Claims in `motivation.py` can be freely referenced as premises or background by later modules — they are not restricted by module membership. Notes and questions are typically referenced via `background=`.

### `note` vs `claim` classification guide

**Principle: when in doubt between `note` and `claim`, mark it as `claim`.**

| Category | Type | Examples |
|----------|------|---------|
| Mathematical definitions / formal setups | **note** | Coordinate system choice, variable decomposition definitions, mathematical form of potentials |
| Established fundamental principles | **note** | Conservation laws, exclusion principle, laws of thermodynamics |
| Standard approximation / method definitions (without applicability assertions) | **note** | Mathematical expression of an approximation (definition only, not asserting applicability) |
| Whether applicability conditions hold | **claim** | Whether an approximation applies to a specific system |
| Theoretical frameworks dependent on conditions | **claim** | "Theorem B holds when A is satisfied" |
| Theoretical derivation results | **claim** | Renormalization relations, scaling laws, asymptotic behaviour |
| Numerical computation results | **claim** | Values from computational methods |
| Experimental observations | **claim** | Measured quantities |

**Key criterion:** can this proposition be questioned? If yes → `claim`. Only mathematical definitions and formal setups qualify as notes.

**Distinguish definitions from assertions.** The mathematical definition of an approximation is a note; "this approximation is unreliable under certain conditions" is a claim. "Decompose the variable into high- and low-frequency parts" is a note (mathematical operation), but "the contribution of the high-frequency part is negligible" is a claim (physical assertion).

**Dependency chains.** If A is a note and B depends on A being true while containing a physical assertion — B is typically a claim.

Content that the source itself derives — even when the derivation is rigorous — should be a claim, because the derivation process itself may contain errors.

### Content format

Claim content supports markdown. Use it for structure:
- Tables: markdown tables for structured data.
- Math: `$...$` for inline, `$$...$$` for display equations.
- Lists: bullet points to enumerate conditions or items.
- Bold / italic: emphasise key values or terms.

### Atomicity principle

Each claim must be an **atomic proposition** — one claim expresses one thing.

**Core rule: theoretical predictions must be separated from experimental results.**

```python
# BAD: mixing theory and experiment
result = claim("The model predicts X, the experimental value is Y, deviation Z%.")

# GOOD: separated into independent claims
prediction = claim("Based on method XX, the model predicts a certain quantity as X.", title="Model prediction")
experiment = claim("The experimental measurement of a certain quantity is Y.", title="Experimental value")
```

Similarly, separate **method descriptions** from **method application results**:

```python
# BAD: method and result mixed
result = claim("Using method XX to compute YY yields ZZ.")

# GOOD: separated
method = claim("Method XX employs ... strategy ...", title="Method description")
result = claim("The numerical result for YY is ZZ +/- delta.", title="Numerical result")
```

### Theory-experiment comparison: extract both sides for `infer`

When a theoretical prediction is compared with experimental data, Pass 2 will connect them with an `infer(evidence=..., hypothesis=...)` step. To make that possible, Pass 1 must extract the prediction and the observation as **two separate claims**:

```python
pred = claim("Theory T predicts Tc = 1.9 K under condition C.", title="Theory prediction")
obs  = claim("Measured Tc = 1.2 K under condition C.", title="Measured Tc")
```

When the source argues that one of several competing theories best explains the observation, extract each competing prediction as its own claim. Pass 2 will model the comparison either by chaining `infer` against each candidate (each gets its own `--p-e-given-h`) or — when the alternatives are mutually exclusive in the paper's framing — by adding an `exclusive(a, b)` relation (for the two-alternative case) or a `decompose --formula-template or` over the candidate claims (for three or more). `exclusive` is strictly binary. The concept that the release/0.4 SKILL labelled "abduction" is preserved as a pattern: see [Pass 4](#pass-4--refine-strategy-types) for the explicit recipe and `../gaia-review/SKILL.md` for the prior-side π(Alt) discussion.

### Repeated-observation pattern: extract every observation

When the source argues that one general rule is confirmed by repeated independent observations (multiple samples, multiple labs, multiple conditions), extract **each observation as its own claim** plus the candidate law as its own claim:

```python
law   = claim("MgB2 universally superconducts below 39 K.", title="Universal Tc law")
obs_a = claim("Sample A: Tc = 39 K.")
obs_b = claim("Sample B: Tc = 39 K.")
obs_c = claim("Sample C: Tc = 39 K.")
```

Pass 2 will chain `derive(law, given=[obs_a, obs_b, obs_c], rationale=...)` (or one `derive` per observation against a shared `compose`'d generalisation step — see Pass 4). What release/0.4 called "induction" is now expressed as `derive` over a `compose`'d pattern; the underlying judgement (each observation must be **independent**) survives intact.

### Figures and tables

When the source contains figures or tables with important data:

**Tables.** Use markdown table format in the claim content. The claim must be self-contained — a reviewer should not need to open the original.

```python
tc_data = claim(
    "Measured superconducting transition temperatures:\n\n"
    "| Material | $T_c$ (K) | Pressure (GPa) |\n"
    "|----------|-----------|----------------|\n"
    "| LaH10    | 250       | 200            |\n"
    "| H3S      | 203       | 150            |\n"
    "| YH6      | 224       | 166            |",
    title="Tc measurements",
    metadata={"source_table": "artifacts/paper.pdf, Table 2"},
)
```

**Figures.** Describe the key quantitative information (values, trends, comparisons) in the claim content. Reference the original figure in metadata for traceability.

```python
phase_diagram = claim(
    "The Tc vs pressure curve shows a dome shape with maximum Tc = 250 K at 200 GPa, "
    "decreasing to 200 K at 250 GPa and 180 K at 150 GPa.",
    title="Tc-pressure phase diagram",
    metadata={
        "figure": "artifacts/images/fig3.png",
        "caption": "Fig. 3 | Tc-pressure phase diagram showing dome-shaped dependence.",
    },
)
```

**Key principle:** the claim content carries all information needed for judgement. The metadata figure/table reference is for traceability, not for conveying information.

### Content must be self-contained

Each node's content must be a complete, independently understandable proposition. A reviewer reading it should not need additional context to make a judgement.

```python
# BAD: requires context to understand
result = claim("The computed result significantly exceeds conventional estimates.")

# GOOD: self-contained proposition
result = claim(
    "Using method XX to compute YY under condition ZZ yields A +/- delta, "
    "compared to the estimate B from conventional method WW, a deviation of approximately C-fold.",
    title="Result description",
)
```

### Pass 1 reflection

After extracting all modules, ask yourself:

- **Theory vs experiment separated?** For every result where the source compares theory to experiment, do I have separate claims for the theoretical prediction and the experimental measurement? If mixed in one claim, Pass 2 cannot wire them with `infer`.
- **Figures and tables transcribed?** Are all key numerical values from figures and tables written into claim content (not just referenced)?
- **Each claim independently judgeable?** Can a reviewer assess each claim without reading any other claim?
- **Contradictory claims identified?** When the source argues "A succeeds where B fails," or compares competing methods / hypotheses, have I extracted both sides as separate claims? These pairs become `contradict(...)` operators in Pass 2, providing strong BP constraints.

### Marking exported conclusions

The source's **core contributions** (new theoretical results, new numerical computation results, new experimental findings, key arguments) should be marked as exported conclusions in `__all__`. These are this knowledge package's external interface — other packages can reference them.

Criterion: if this result were removed from the source, the source would lose its core value.

When you use `gaia author claim` / `gaia author derive` / etc., the verbs default to `--export` on every Knowledge-producing call; explicitly pass `--no-export` for an internal-only binding.

### Pass 1 deliverable

One claim / note / question list per module.

Pass 1 only extracts atomic, self-contained knowledge nodes. **Do not prejudge which are "derived conclusions"** — whether a claim is an independent premise or a derived one depends on how reasoning connections are established in Pass 2, not on the claim itself.

## Pass 2 — Connect: write reasoning relations

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

### Write a detailed `--rationale`

Summarise the derivation process from the source — not a one-sentence stub, but a complete reasoning chain. The rationale should let a domain reader follow "why these premises lead to this conclusion."

### Identify premises and background

- **Claims** used in the derivation → `--given` (the premise list).
- **Notes / questions** used in the derivation → `--background`.

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

Sources often have implicit premises. While writing the rationale, if you discover the derivation depends on a knowledge node already extracted in Pass 1, add it to `--given` or `--background` and reference it with `@label` in the rationale.

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

## Pass 3 — Check completeness

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

## Pass 4 — Refine strategy types

Passes 2-3 produce a graph dominated by `infer` (the general fall-back). Pass 4 tightens each relation into the most specific verb that still fits the source.

### Author-verb reference

| Verb | Semantics | When to use | Author-side cost |
|----------|-----------|-------------|--------------|
| `derive` | Directed implication: premises jointly support conclusion | Step-by-step derivations, theoretical results read off a formal framework, computation-application chains | `register_prior` against the derive's labelled output (or its warrant helper) for residual uncertainty |
| `infer` | Bayesian update: explicit P(E\|H), optional P(E\|~H) | Theory-vs-experiment fit, single-evidence updates to a hypothesis | `--p-e-given-h` (required), `--p-e-given-not-h` (defaults 0.5) |
| `compute` | Deterministic mapping: callable `fn` produces conclusion from premises | Closed-form computations where the function is in code | `--fn` identifier of a callable; conclusion is the function's output Claim |
| `observe` | Measurement event tying Claim / Variable / Distribution to data | Experimental observations that anchor the graph | `--value` / `--error` for quantity form, or discrete observation against a premise list |
| `compose` | Reusable multi-step pattern: `@compose`-decorated function | Recurring derivation patterns that need a named, registered shape | Author the `pattern.py` and register via `gaia author compose --from-file` |
| `decompose` | Structural split: composite → atomic parts via `and`/`or`/`atom` | Aggregate claim is best read as the conjunction of independently judgeable parts | `--formula-template` or `--formula-expr` |

Also available as **structural verbs** (modelled in Pass 2 alongside the rest, not in Pass 4):

| Verb | Semantics | When to use |
|----------|-----------|-------------|
| `contradict(a, b)` | NOT (A AND B) — cannot both be true | Incompatible hypotheses |
| `exclusive(a, b)` | A XOR B — exactly one true | Exhaustive binary choice |
| `equal(a, b)` | A = B — logically equivalent | Two formulations of the same proposition |

### Decision tree

```
For each `infer` relation drafted in Pass 2:

    Is the conclusion a measured datum (or a Variable/Distribution observed at a value)?
        YES → observe
        NO  ↓
    Is the conclusion produced by a closed-form computation in code (named callable f over premises)?
        YES → compute
        NO  ↓
    Does the source present this as a deterministic step-by-step derivation that, given the premises,
    is the intended way to reach the conclusion (with at most residual numerical or approximation uncertainty)?
        YES → derive   (optionally register_prior against the derive's labelled output for warrant uncertainty)
        NO  ↓
    Is this a Bayesian update where the evidence's likelihood under hypothesis and under its negation
    is what carries the inferential weight (e.g. theory predicts X, experiment measured X')?
        YES → infer    (with explicit --p-e-given-h, and --p-e-given-not-h when known)
        NO  ↓
    Is the conclusion best read as the conjunction or disjunction of independently judgeable atomic parts?
        YES → decompose   (--formula-template and|or|atom)
        NO  ↓
    Does the same multi-step pattern recur across multiple conclusions, and is naming intermediate
    propositions worthwhile?
        YES → compose    (extract into a @compose pattern; per-call the wrapper authors a derive over
                          the composition's intermediate Claims)
        NO  → keep infer (with the most informative likelihood you can justify)
```

### Recasting legacy reasoning patterns

The release/0.4 SKILL talked about several named reasoning patterns. Several have clean v0.5 idioms; some do not. Be honest about the gap.

**Strict mathematical deduction** ("if all premises true, conclusion necessarily true"): use `derive` and omit the warrant prior (or set it very close to 1). `derive` carries the same skeleton (conjunction + directed implication); leaving the warrant near 1 expresses determinism. There is no separate "deduction" verb in v0.5.

**Soft / probabilistic support** ("premises usually imply the conclusion, with uncertainty"): use `derive` for the relation, then reach for `gaia author register-prior --claim <warrant_label> --value ... --justification ...` against the `derive`'s labelled output Claim (or its auto-generated warrant helper) to express the residual uncertainty (numerical methods, approximations, omitted conditions). The engine's `derive(...)` signature does not accept an inline `prior=` — warrant priors are attached via `register_prior`.

**Theory-experiment comparison ("abduction")**: extract the theoretical prediction and the experimental observation as separate claims (Pass 1), then use `infer(evidence=obs, hypothesis=pred, --p-e-given-h ...)`. When several alternative theories compete, chain `infer` against each candidate hypothesis with its own likelihoods. When the alternatives are mutually exclusive in the paper's framing, add `exclusive(a, b)` for the two-alternative case or `decompose --formula-template or` for three or more (`exclusive` is strictly binary). The abduction *concept* — the prior on the alternative reflects explanatory power for the specific observation, not the alternative's truth in general — survives intact; that deep guide lives in `../gaia-review/SKILL.md`.

**Repeated-observation generalisation ("induction")**: there is no single v0.5 verb. The recommended idiom is `derive` over a `compose`'d generalisation step. Specifically: author each observation as its own claim, then either (a) for the simple flat case, `derive(law, given=[obs_a, obs_b, obs_c], rationale=...)`, or (b) when the generalisation involves a named pattern, define a `@compose` function that takes the observations and the law and returns the law's `derive` step, and register it via `gaia author compose --from-file`. The underlying judgement — each observation must be **independent**; if dependent, extract the shared dependency as an explicit claim in Pass 5 — still applies.

**Process of elimination, proof by cases, mathematical induction, cross-system analogy, extrapolation beyond measured range:** these patterns **have no single-verb v0.5 form**. The recommended idiom for each:

- *Process of elimination:* `decompose --formula-template or` over the exhaustive option set + `derive(survivor, given=[evidence_eliminating_alt_1, evidence_eliminating_alt_2, ...])`. The disjunctive decomposition guarantees the survivor must be the one true option; the `derive` carries the per-alternative refutation reasoning. (`exclusive(a, b)` is strictly binary — exactly two options — so it only fits the n=2 case; for n≥3 alternatives use `decompose --formula-template or`.)
- *Proof by cases:* one `derive(conclusion, given=[case_k_premise, conclusion_holds_in_case_k])` per case, plus a `decompose --formula-template or` over the case predicates (or `exclusive(a, b)` when there are exactly two cases — `exclusive` is binary only).
- *Mathematical induction:* one `derive` for the base case, one `derive` for the inductive step (`P(n) ⇒ P(n+1)`), and a `derive(for_all_law, given=[base_case, inductive_step])` whose rationale references the inductive schema. **The engine does not enforce the inductive schema** — it treats this as a generic two-premise `derive`. The author must carry the "this is induction over N" framing in the `rationale` text, and the Pass 5 reviewer must verify the base case + step actually warrant the universal. Do not assume the engine guarantees the quantifier reasoning.
- *Analogy* and *extrapolation:* author the structural-similarity / continuity premise as a `claim`, then `derive(target, given=[source, similarity_premise])` or `derive(extrapolated, given=[measured_range_result, continuity_premise])`. The justification quality lives in the premise prior plus the `derive` warrant prior — see `../gaia-review/SKILL.md`.

If your source has a derivation that does not map cleanly onto any of these idioms, that is signal: capture the gap in `ANALYSIS.md` under "unmodelled reasoning" so a reviewer can examine it.

### Strategy variable naming

Every relation that produces a Claim or warrant **must** be assigned to a named public variable (no `_` prefix). This is required so that the relation appears in `gaia build check --brief` output and can be referenced by `priors.py` and downstream verbs.

When using `gaia author <verb>`, set `--dsl-binding-name` (Python LHS) and `--label` (engine `label=` kwarg) together for any relation that needs to be cited downstream. Use descriptive names like `derive_tc_al`, `compose_workflow`, `infer_theory_vs_exp`.

### Claim variable naming

Every Claim **must** be assigned to a named variable (no `_` prefix for claims that need to be visible). Anonymous `claim()` calls or `_`-prefixed claims will not get labels and become invisible in CLI output. The only exception: `__` double-underscore prefix is reserved for compiler-generated helper Claims.

### When to reach for `compose`

`compose` is the v0.5 way to capture **complex reasoning with meaningful intermediate steps**. Two triggers:

1. **3+ premises and no `decompose` fit.** A flat `derive` over 4+ premises suffers the BP multiplicative effect — small uncertainties on each premise compound on the conclusion. If you can name meaningful intermediate propositions (not stubs introduced purely to split the call), refactor into a `@compose` pattern whose intermediate Claims are independently judgeable.
2. **Recurring pattern.** The same shape of derivation appears across multiple conclusions. Register it once via `gaia author compose --from-file` and reuse.

If decomposition would be forced — no meaningful intermediate proposition exists — 3 premises is acceptable to keep as `derive` or `infer`; 4+ premises must decompose, otherwise BP multiplicative effect will severely suppress belief.

### Pass 4 reflection

After refining all relations, verify:

- **Every theory-vs-experiment `infer` has a meaningful alternative?** When the source compares competing hypotheses, did you extract each alternative and either chain `infer` against it or wire `exclusive` across the candidates? Remember: the prior on the alternative reflects its **explanatory power** for the specific observation, not its truth in general — see `../gaia-review/SKILL.md` for the deep guide.
- **Each repeated-observation `derive` over independent observations?** For `derive(law, given=[obs_a, obs_b, ...])`, each observation should provide independent evidence. If observations are dependent (shared sample, shared instrument), extract the shared dependency as an explicit claim in Pass 5.
- **`infer` likelihoods anchored?** Every `infer` call has `--p-e-given-h` from the source. If `--p-e-given-not-h` is left at 0.5, it is a fall-back — when the source's framing supplies a competing-explanation likelihood, set it explicitly.

### Post-refinement check

After refining all relations, check the **verb distribution**:

- If `derive` accounts for more than 70% of relations, review whether some should be `infer` (theory-vs-experiment fit) or `compose`'d (multi-step generalisation).
- Papers with extensive experimental validation typically have many `infer` calls.
- Discussion / conclusion sections that synthesise multiple results often have a `compose`'d generalisation step.

Also check **reasoning chain depth** (hops from leaf to exported conclusion):

- Maximum recommended depth: **3 hops**.
- If a derived conclusion has belief < 0.4, the chain is likely too deep.
- Fix by flattening: make intermediate claims into leaf premises, or restructure into wider (more premises per relation) rather than deeper (more relations in series).

## Pass 5 — Verify structural integrity

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

Each factor in the factor graph represents an **independent constraint**. If the same argument appears as two factors, the model claims two independent constraints exist when there is only one. This inflates beliefs — not because JT miscalculates, but because the model is wrong.

**The unified principle:** every factor must bring genuinely new information that no other factor already provides. When implicit dependencies exist, make them explicit as variables in the graph so JT can correctly reason about them.

**Pattern 1 — Redundant relations (same reasoning expressed twice):**

```python
# 1a. Exact duplicate: standalone derive + a derive inside a compose'd generalisation
derive(law, given=[obs], rationale="law predicts obs")
derive_law_from_obs = derive(law, given=[obs_a, obs_b, obs], rationale="...")  # internally re-uses obs
# FIX: remove the standalone derive, or fold it into the compose pattern.

# 1b. Transitive shortcut: A→B→C chain + A→C that is just the chain compressed
derive(B, given=[A], rationale="A implies B")
derive(C, given=[B], rationale="B implies C")
derive(C, given=[A], rationale="A implies B implies C")  # redundant with the chain
# FIX: remove the shortcut, OR confirm it represents a genuinely different argument.

# 1c. Derived premise redundancy: A→B, then derive(C, given=[A, B]) where A supports C only through B
derive(B, given=[A], rationale="A implies B")
derive(C, given=[A, B], rationale="A leads to B which leads to C")
# FIX: remove A from C's premises → derive(C, given=[B], ...).
```

**Pattern 2 — Hidden evidence in rationale text:**

Two relations with identical premises but different `rationale` text. The different reasoning contains evidence not captured as premises — extract it.

```python
# BEFORE: same premises, different reasoning angles
derive(law, given=[sample, obs_R], rationale="Zero resistance = hallmark of SC")
derive(law, given=[sample, obs_R], rationale="Transition width < 0.5 K = bulk SC")
# The "transition width < 0.5 K" is evidence hidden in the rationale text.

# AFTER: extract hidden evidence as a claim
transition_sharpness = claim("Resistivity transition width < 0.5 K")
derive(law, given=[sample, obs_R], rationale="Zero resistance = hallmark of SC")
derive(law, given=[sample, transition_sharpness], rationale="Sharp transition = bulk SC")
```

**Pattern 3 — Unmodelled shared dependencies:**

Two observations share a common cause (same sample, same instrument) but the cause is not in the graph. The model treats them as unconditionally independent, losing their correlation.

```python
# BEFORE: shared sample quality is implicit — correlation lost
obs_R   = claim("Sample A: Tc = 39 K by resistivity")
obs_chi = claim("Sample A: Tc = 39 K by susceptibility")
derive(law, given=[obs_R, obs_chi], rationale="...")

# AFTER: extract shared dependency — correlation preserved
sample_quality = claim("Sample A is high-quality single crystal, confirmed by XRD")
derive(obs_R,   given=[sample_quality], rationale="Resistivity depends on @sample_quality")
derive(obs_chi, given=[sample_quality], rationale="Susceptibility depends on @sample_quality")
derive(law,     given=[obs_R, obs_chi],
       rationale="Conditionally independent given sample_quality")
```

You cannot create new experiments — you formalize what the paper provides. The table below guides the modelling choice:

| Observation relationship | Modelling approach |
|--------------------------|-------------------|
| Truly independent (different samples, different labs) | `derive(law, given=[obs_a, obs_b, ...])` directly |
| Partially independent (shared dependency + independent components) | Extract shared dependency as an explicit claim |
| Completely redundant (same data rephrased) | Merge into a single claim |

**Pattern 4 — `equal` + separate relations:**

`equal(a, b)` couples two claims. If both sides have relations to the same target, check whether each relation brings information beyond what `equal` already propagates.

```python
equal(claim_A, claim_B)
derive(law, given=[claim_A], rationale="argument from A's perspective")
derive(law, given=[claim_B], rationale="argument from B's perspective")

# Ask: does the B→law relation add information that A→law + equal doesn't already provide?
# If NO: remove B→law.
# If YES: extract the additional information as a new premise.
```

**How to check (procedure):**

1. List every claim with 2+ incoming relations.
2. For each pair of relations: "does each bring genuinely independent new information?"
3. For each `derive` over multiple observations: "do the observations share unmodelled dependencies?"
4. For each `equal`: "do both sides need their own relations to the same target?"
5. For all relations: "does the rationale text contain evidence not captured as premises?"
6. For all `infer` calls: "is `--p-e-given-h` set from a source-supported value, and is `--p-e-given-not-h` the right alternative-likelihood (not a stand-in 0.5 when the source actually argued an alternative)?"

### 5c. Re-compile and verify

After any structural changes in Pass 5, run `gaia build compile` + `gaia build check` + `gaia run infer` and compare beliefs to before. A significant belief drop after removing a relation suggests the previous value was inflated by double counting.

## Pass 6 — Polish for standalone readability

**Prerequisite:** the knowledge graph is structurally correct (Pass 5 complete). Pass 6 ensures that every claim, rationale, and metadata entry is independently understandable without access to the original source.

### 6a. Claim self-containedness

Review every claim for standalone readability:

**Symbols must be self-explanatory.**
- Every mathematical symbol must have a brief explanation on its first appearance in that claim.
- Example: do not write "$\alpha \ll 1$"; write "the parameter $\alpha$ (ratio of XX to YY) is much less than 1".
- The physical meaning of subscripts / superscripts must be explicit.

**Abbreviations must be expanded.**
- Every abbreviation must be expanded on its first appearance in that claim.
- Example: do not write "XXX computes $\lambda$"; write "the such-and-such method (XXX) computes the coupling constant $\lambda$".
- Even if an abbreviation has been expanded in another claim, each claim is independent and must expand it again.

**No comparative assertions without reference.**
- Do not write "significantly larger than X" — the reader does not know what is being compared.
- Do not write "nearly exact agreement" — the reader does not know what it agrees with.
- Numerical comparisons must provide both values.

**Sufficient detail.**
- Can a reader understand what this claim says by reading only this one claim?
- Are conditions and applicable ranges clear?
- Do numerical values include units and error bars?

### 6b. Data formatting

- Tabular data should use markdown tables in claim content.
- Key numerical values from figures must be transcribed into the claim text (not just referenced).
- Trends described in prose should include specific data points.

### 6c. Rationale standalone readability

Review every relation's `rationale` text:

- The rationale should be a complete reasoning chain, not "see Section 3 of the paper."
- Specific numbers, method names, and conditions should be stated, not implied.
- Every `@label` reference should have enough surrounding context that a reader unfamiliar with the label can follow the argument.

### 6d. Figure and table references

Add `metadata={"figure": "...", "caption": "..."}` to every claim whose content comes from a specific figure or table:

1. **Coverage.** Check each module against the source for missing references.
2. **Path validity.** Verify each file path exists in `artifacts/`.
3. **Caption accuracy.** Copy the figure caption from the source (abbreviated OK, but figure number and key content must be correct).
4. **Relation metadata.** Relations whose `rationale` references figure data should also carry `metadata`.

### 6e. Complete citation metadata

During Passes 1-4, `references.json` entries were kept minimal (key + type + title). Now fill in complete metadata for all cited references:

- **author** — full author list (`[{"family": "...", "given": "..."}]`).
- **issued** — publication date (`{"date-parts": [[2020]]}`).
- **container-title** — journal / conference name.
- **volume**, **page**, **DOI** — where applicable.

Verify: every `[@key]` used in claims and rationales has a corresponding entry in `references.json`. Run `gaia build compile .` to catch any missing keys (strict `[@key]` form raises a compile error if the key is not found).

### 6f. Format consistency

- Metadata format should be consistent across all claims (same key names, same path conventions).
- Titles should follow a consistent naming style.
- Cross-module import patterns should be uniform.

## Inner loop: compile + check after every pass

After completing each pass, write code, compile, and check.

```bash
gaia build compile <pkg>          # DSL → .gaia/ir.json
gaia build check <pkg>            # summary with prior annotations on independent claims
gaia build check <pkg> --hole     # detailed hole report: which claims still need priors
gaia build check <pkg> --brief    # overview: all modules with relation summaries
gaia build check <pkg> --show s6_xxx   # expanded view of a specific module
gaia build check <pkg> --show label    # detail view of a specific claim's warrant tree
```

**What to check in default output:**
- Each independent premise shows `prior=X` if set, or `⚠ no prior` if missing.
- The summary shows "Holes (no prior set): N" when any holes remain.

**What to check in `--hole` output:**
- Every hole claim has its content and QID listed — use this to write `priors.py` entries.
- Every covered claim shows its prior value and justification — verify these are reasonable.

**What to check in `--brief` output:**
- Every relation should show named labels (not `_anon_xxx`). If a relation's conclusion shows `_anon_xxx`, the Python LHS was not set — re-author with `--dsl-binding-name`.
- Claims should show their role (independent / derived / structural / background / scaffolded / orphaned) and prior if set.
- Use `--show <module>` to inspect full claim content and warrant trees for review readiness.

## Prior-assignment tail

After Pass 6, you have a structurally complete graph and a passing `gaia build check`. Now assign priors and run inference.

### Write `priors.py`

`priors.py` assigns priors to leaf claims. Warrant priors on `derive` (and `infer` / `compute` where relevant) are set by `gaia author register-prior --claim <warrant_label> --value ... --justification ...` against the verb's labelled output Claim (or its auto-generated warrant helper). The engine's verb signatures do not accept an inline `prior=` kwarg — `register_prior` is the only path.

**Before writing `priors.py`, run `gaia build check --hole .`** to see exactly which independent claims need priors, along with their content and current status. Use this as your checklist — address each hole, then re-run `gaia build check --hole .` to confirm "All independent claims have priors assigned."

The CLI shortcut is:

```bash
gaia author register-prior \
    --claim my_leaf_claim \
    --value 0.85 \
    --justification "Well-established by [@Smith2020] in the same regime." \
    --file priors.py
```

That command appends a `register_prior(...)` statement to `priors.py` and auto-injects the import if the target file is a sibling of `__init__.py`.

**Do NOT set priors for derived claims.** The inference engine automatically assigns uninformative priors (0.5) to derived claims. Their beliefs are determined entirely by BP propagation from leaf premises. Setting an explicit prior on a derived claim double-counts evidence: the reviewer's judgement and the reasoning chain both reflect the same underlying data. Only set priors for independent (leaf) claims that are not the conclusion of any relation.

**The π(Alt) discipline (`infer` alternatives) deserves special attention.** In the abductive pattern (theory-vs-experiment `infer`), the prior on the alternative reflects its **explanatory power for the specific observation**, not whether the alternative's computation is correct in general. The most common and consequential mistake in prior assignment is setting π(Alt) based on "the alternative's calculation is right," rather than "the alternative explains the observation." The deep guide — worked examples, rule-of-thumb checks, the explanatory-power-vs-correctness distinction — lives in `../gaia-review/SKILL.md`. Read it before writing the prior on any abductive alternative.

The full prior-assignment guide (evidence-level → prior-range tables, warrant-prior ranges, iteration loop) also lives in `../gaia-review/SKILL.md`. This skill points at it; do not duplicate the tables here.

### Run inference

```bash
gaia run infer <pkg>             # writes .gaia/beliefs.json
gaia run infer <pkg> --depth 1   # joint cross-package inference (direct deps)
gaia run infer <pkg> --depth -1  # joint cross-package inference (all transitive deps)
```

### Interpret BP results

Read the table in `../_shared/bp-interpretation.md`. Do not duplicate the interpretation table here — that reference is the single canonical copy. The shape of the loop:

```
gaia run infer → .gaia/beliefs.json → interpret per ../_shared/bp-interpretation.md
   ↓
   structural issues  → back to Pass 1-5 (revise graph)
   prior issues       → revise priors.py (revisit ../gaia-review/SKILL.md guide)
   otherwise          → proceed to ANALYSIS.md
```

If results are clearly wrong (a well-supported conclusion has belief < 0.3, or a contradict relation does not pick a side), go back and check:

1. **Structural issue?** (→ revisit Pass 1-5.) Missing premises, wrong relation verb, missing alternative for an `infer`, evidence double-counting.
2. **Parameter issue?** (→ revisit `priors.py`.) Priors too low / high, `--p-e-given-h` miscalibrated, π(Alt) reflecting computational correctness instead of explanatory power.

## Generate the GitHub presentation

After the prior-assignment tail produces beliefs you trust, hand off to `../gaia-publish/SKILL.md`:

```bash
gaia run render <pkg> --target github   # .github-output/ README + narrative outline
gaia run render <pkg> --target docs     # per-module Mermaid graphs in docs/detailed-reasoning.md
gaia run render <pkg> --target obsidian # gaia-wiki/ skeleton (hands off to ../gaia-obsidian-wiki/SKILL.md)
```

`../gaia-publish/SKILL.md` carries the README narrative discipline (per-conclusion evidence assessment, Weak Points framed around internal nodes, Evidence Gaps by theme). `../gaia-obsidian-wiki/SKILL.md` carries the rich-vault discipline (claim pages with full derivations, section pages as narrative chapters).

## `ANALYSIS.md` — critical analysis deliverable

After BP results stabilise, produce a **critical analysis** of the source. This is the analytical payoff of formalization — by building the knowledge graph, you now understand the argument's structure well enough to identify its strengths and weaknesses.

`ANALYSIS.md` lives in the package root and is a **required deliverable** — do not skip it. The required sections:

### 1. Package statistics

Knowledge graph counts (claims by role, relations by verb, structural-verb counts), verb-type distribution, claim role classification, figure reference coverage, BP result summary.

### 2. Summary

One paragraph on the argument's overall structure and strength.

### 3. Weak points (table)

Internal nodes with low belief. **Internal nodes, not exported conclusions** — exported conclusions go in the README's Reasoning Structure section (`../gaia-publish/SKILL.md`); `ANALYSIS.md` Weak Points is for the load-bearing intermediate nodes whose fragility threatens the whole chain.

Columns: claim, belief, issue. Include all derived claims with belief < 0.8 and any `infer`-alternative claims with belief > 0.25.

Vulnerability signals to capture in the "issue" column:

| Signal | What it means |
|--------|---------------|
| Derived conclusion with low belief (< 0.5) | Weak premise support or fragile reasoning chain |
| Long reasoning chain (4+ hops from leaf to conclusion) | Multiplicative effect — small uncertainties compound |
| `infer` alternative π(Alt) ≈ π(H) | Alternative is equally plausible — evidence does not distinguish |
| Leaf claim with low prior and many downstream dependents | Single weak foundation supporting many conclusions |
| `derive` warrant with very low prior (< 0.3) | Reviewer flagged this step as unreliable |
| Claim marked as `note` that could be questioned | Hidden assumption not subject to BP updating |

### 4. Evidence gaps (tables, grouped by theme)

Group by theme: **experimental**, **computational**, **theoretical**. Within each, identify where additional evidence would most strengthen the argument. For each gap: which conclusions improve if filled. Prioritise by impact.

- **Unsupported leaf claims:** claims with no reasoning support that the source takes as given — what evidence could back them up?
- **Weak `infer` alternatives:** where the alternative nearly matches the hypothesis in explanatory power — what new observation could break the tie?
- **Missing comparisons:** theoretical predictions without experimental validation — what experiment could test them?
- **Single-observation generalisations:** laws supported by only one observation — what additional observations would strengthen the `derive`?

### 5. Contradictions

(a) Explicit `contradict(...)` relations modelled and how BP resolved them (which side won). (b) Internal tensions in the source that were not modelled as formal contradictions but are worth flagging.

### 6. Confidence assessment

Tier the exported claims into confidence levels (very high / high / moderate / tentative) with belief ranges.

The critical analysis transforms a qualitative reading of the source into a quantitative structural assessment. Every knowledge package should ship with one.

## Common mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Theoretical prediction and experimental result mixed in one claim | Cannot model the verification relationship with `infer` | Separate into two claims + `infer(evidence=obs, hypothesis=pred)` |
| `infer` without a meaningful alternative or with `--p-e-given-not-h` left at 0.5 when the source argued otherwise | Bayesian update misses the competing-explanation force | Set `--p-e-given-not-h` from the source, or chain `infer` against each alternative hypothesis |
| `infer` alternative's prior reflects "computational correctness" instead of "explanatory power" | π(Alt) too high, weakens evidence's pull toward H | π(Alt) answers "Can Alt independently explain Obs?", not "Is Alt's calculation correct?" (see `../gaia-review/SKILL.md`) |
| Rationale written too briefly (one sentence) | Reasoning process is untraceable | Summarise derivation steps in detail, reference with `@label` |
| 4+ premise flat `derive` | Severe BP multiplicative effect | Use `compose` to decompose into sub-steps with 3 or fewer premises |
| Content not self-contained (symbols / abbreviations unexplained) | Reviewer cannot judge independently | Each claim must independently explain all symbols and abbreviations |
| Marking a questionable proposition as `note` | That proposition cannot be updated via BP | When in doubt, mark as `claim`; only mathematical definitions are `note`s |
| Marking a condition-dependent theoretical framework as `note` | Framework does not participate in BP | Condition-dependent conclusions should be claims |
| Using `derive` for a Bayesian update | Loses the explicit P(E\|H) / P(E\|~H) the source supplied | Use `infer` with `--p-e-given-h` and `--p-e-given-not-h` |
| Using `infer` for a step-by-step deterministic derivation | Forces a Bayesian update where rigid implication is the source's framing | Use `derive` (with optional `register_prior` against the derive's labelled output for residual warrant uncertainty) |
| Using `derive` for a numerical computation whose function is in code | Loses the deterministic-mapping framing | Use `compute --fn ...` with the named callable |
| Anonymous relation (no `--dsl-binding-name`) | Relation invisible in `gaia build check --brief`, cannot be reviewed | Assign via `--dsl-binding-name <name> --label <name>` |
| `_`-prefixed claim or relation | Node invisible in CLI output, gets no label | Use public names (no `_` prefix); only `__` is reserved for compiler |
| Missing prior for orphaned claim | `gaia run infer` errors | All claims (including orphaned) need priors |
| Missing implicit premises in reasoning | Knowledge graph is incomplete | Use `gaia build check` + manual review in Pass 3 |
| Not verifying numerical values | Data errors | Cross-check every value against the source |
| Same claim in multiple paths to same conclusion | Evidence double-counted, inflated belief | Ensure each leaf enters a conclusion through exactly one path (Pass 5) |
| Repeated observations with unmodelled shared dependency | Overcounted evidence | Extract shared dependencies as explicit claims (Pass 5) |
| Wrong `contradict` (claims can both be true) | BP forced to suppress one side incorrectly | Verify structural-verb semantics in Pass 5 |
| Setting prior on derived claim | Double-counts evidence | Do not set priors for derived claims; inference engine defaults to 0.5 |
| Observation claim missing prior (classified as derived because it has incoming supports) | Observation's empirical grounding lost; belief depends entirely on theory relations instead of being anchored by data | Add observation to `priors.py` with high prior (0.9+), or use `observe` to tie it directly to a measurement value |

## See also

- `../_shared/bp-interpretation.md` — single canonical reference for interpreting `.gaia/beliefs.json` (normal vs abnormal patterns for premises, derived conclusions, `contradict` / `exclusive` sides; common problems and fixes).
- `../gaia-review/SKILL.md` — prior-assignment guide (evidence-level → prior-range tables, warrant priors, π(Alt) explanatory-power semantics, iteration loop).
- `../gaia-publish/SKILL.md` — README narrative discipline after `gaia run render --target github`.
- `../gaia-obsidian-wiki/SKILL.md` — rich Obsidian-vault discipline after `gaia run render --target obsidian`.
