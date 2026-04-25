---
name: formalization
description: "Formalize a paper, chapter, report, or note set into a Gaia v0.5 package using current action/relation verbs, priors.py, and compile/check/infer iteration."
---

# Knowledge Formalization

Use this skill when converting a source document into a Gaia knowledge package.
Use the `gaia-lang` skill for DSL syntax and the `gaia-cli` skill for commands.

Do not use legacy `support()`, `noisy_and()`, `setting()`, `contradiction()`,
`abduction()`, or `induction()` in new packages. The current surface is:

- `claim(...)` for probabilistic propositions;
- `note(...)` for background context;
- `observe(...)`, `derive(...)`, `compute(...)`, `infer(...)`, `associate(...)`
  for reviewable action links;
- `equal(...)`, `contradict(...)`, `exclusive(...)` for reviewable relations;
- `@compose(...)` for named reusable workflows;
- `priors.py` for independent input priors.

## Operating Principle

Formalization is incremental. After each pass, write code and run:

```bash
gaia compile .
gaia check .
gaia check --hole .
```

Do not wait until the end to compile. Compiler/check output is part of the
formalization process.

## Pass 0: Prepare Source Artifacts

Place source material under `artifacts/` and create `references.json` when the
package needs citations.

```
my-package-gaia/
  artifacts/
    paper.pdf
  references.json
  src/my_package/
    __init__.py
    motivation.py
  pyproject.toml
```

`references.json` is package-root CSL JSON keyed by citation id. Start minimal
and fill metadata as needed.

## Pass 1: Extract Knowledge

Read section by section. For each proposition, choose the smallest useful unit.

| Source item | Gaia object | Rule |
|-------------|-------------|------|
| Debatable assertion, result, prediction, measurement | `claim(...)` | Can carry probability |
| Experimental setup, definition, variable binding, explanatory context | `note(...)` | No probability |
| Open research question | `question(...)` | No BP participation |

When in doubt between `claim` and `note`, use `claim`. If a statement can be
wrong, uncertain, context-dependent, or later contradicted, it is a claim.

Keep theory predictions separate from experimental measurements:

```python
prediction = claim("The model predicts Tc near 39 K.")
measurement = observe(
    "The measured Tc is near 39 K.",
    rationale="Reported in the experiment.",
)
```

## Pass 2: Connect Reasoning

Use current verbs, not legacy strategy patterns.

### Deterministic derivation

```python
derived = derive(
    "The model predicts equal fall speed in vacuum.",
    given=model,
    background=[vacuum_setup],
    rationale="If air resistance explains the in-air difference, removing air removes it.",
)
```

### Empirical observation with grounding

```python
obs = observe(
    "The sample shows zero resistance below Tc.",
    background=[measurement_setup],
    rationale="The reported four-probe measurement shows zero resistance.",
)
```

### Probabilistic evidence link

Use `infer(...)` when the relationship is genuinely probabilistic.

```python
likelihood = infer(
    obs,
    hypothesis=model,
    p_e_given_h=0.9,
    p_e_given_not_h=0.2,
    rationale="This observation is much more likely if the model is correct.",
)
```

### Relation judgments

```python
same = equal(prediction, measurement, rationale="The prediction matches the measurement.")
conflict = contradict(a, b, rationale="Both cannot hold in the same setup.")
choice = exclusive(left, right, rationale="The alternatives form a closed partition.")
```

### Reusable workflow

Use `@compose(...)` when a repeated multi-action pattern should be named and
reviewed as a unit.

```python
@compose(name="paper:likelihood-check", version="1.0", rationale="Prediction-to-observation check.")
def likelihood_check(model, obs):
    pred = derive("The model predicts the observation.", given=model, rationale="Model equations.")
    equal(pred, obs, rationale="Prediction and observation agree.")
    return pred
```

## Pass 3: Check Completeness

Run:

```bash
gaia check --brief .
gaia check --show <module_or_claim> .
```

Look for:

- important source claims not represented;
- orphaned claims that should either be connected or removed;
- anonymous nodes (`_anon_...`) that should be assigned to variables;
- relation helpers or derived claims accidentally exported;
- missing background context that makes a claim unreadable.

## Pass 4: Make Uncertainty Explicit

Do not use broad strategy names as a substitute for uncertainty analysis.

For each uncertain bridge, ask:

- What is the hypothesis?
- What is the evidence?
- What would the evidence probability be if the hypothesis were false?
- Is there a base-rate claim that needs its own prior?

Represent the answer with explicit claims and `infer(...)` or `associate(...)`.

## Pass 5: Verify Structural Integrity

Run:

```bash
gaia check --hole .
```

Confirm:

- independent probabilistic inputs are intentional;
- derived claims do not receive manual priors;
- helper claims from relations, Boolean expressions, `infer(...)`, and
  `associate(...)` do not receive manual priors;
- root `observe(...)` claims that matter to exported goals are covered by
  priors or intentionally left to MaxEnt.

## Pass 6: Write Priors And Infer

Create `src/<package>/priors.py`:

```python
from . import observation, hypothesis

PRIORS: dict = {
    observation: (0.9, "Direct measurement reported in the source."),
    hypothesis: (0.5, "Neutral before this package's evidence is applied."),
}
```

Then run:

```bash
gaia compile .
gaia check --hole .
gaia infer .
```

Interpret the posterior beliefs. If results look wrong, revise structure first,
then priors. Do not fix a modeling error by forcing priors.

## Anti-Double-Counting Checks

- Do not give priors to both an observation and a restatement of the same
  observation unless their dependency is explicit.
- Do not derive `B` from `A` and also use both `A` and `B` as independent
  evidence for `C`.
- Do not export helper claims from `equal(...)`, `contradict(...)`,
  `exclusive(...)`, `infer(...)`, or `associate(...)`.
- If two evidence claims share a source or method, model the shared dependency
  as a claim or note instead of pretending they are independent.

## Standalone Readability

Before finishing:

- every exported claim should be understandable without the original paper;
- every quantitative claim should include units and conditions;
- citations should use `[@key]` entries available in `references.json`;
- module names should follow source structure;
- `__all__` should list only the package interface.

## Removed Legacy

Do not create review sidecars (`review.py`, `reviews/<name>.py`,
`ReviewBundle`, `review_claim`, `review_strategy`). Do not recommend legacy
strategy APIs for new packages. They may appear only in compatibility tests or
old package migration work.
