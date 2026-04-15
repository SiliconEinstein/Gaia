# Gaia Lang v6: Actions and Warrant Claims

## Motivation

Gaia Lang v5 carries too much semantic load in named strategy interfaces such as
`deduction`, `support`, `induction`, `abduction`, `IBE`, `equivalence`, and
`contradiction`. Those names are intuitive, but they are not orthogonal. In real
scientific papers, the same reasoning fragment is often written in multiple
directions:

- a theory predicts an observation;
- an observation supports a theory;
- several fits jointly support a law;
- one explanation is better than another.

This creates pressure to overload low-level semantics, especially around priors,
directionality, and composite structure.

Gaia Lang v6 fixes this by freezing `Knowledge` and introducing a small set of
orthogonal `Action` objects. Traditional strategy names are still useful, but
they move to a pattern library built on top of the primitive actions.

## Design Goals

- Keep `Knowledge` unchanged unless strictly necessary.
- Make the primitive reasoning interfaces orthogonal and few.
- Preserve warrant review as a first-class part of the language.
- Let warrant probabilities stay attached to warrants, not actions.
- Allow existing named strategies to survive as sugar or composition patterns.
- Cover both scientific prose and numerical experiments.

## Core Objects

### Knowledge

`Knowledge` remains the only node object. No new `Warrant` node type is added.

Warrants are represented as ordinary `Knowledge(type="claim")` objects.
Each warrant claim is reviewable and therefore should also link to a reviewer
question.

Recommended warrant claim conventions:

- `type == "claim"`
- `prior` stores the reviewer-estimated credibility of the warrant
- `metadata["question"]` points to a `Knowledge(type="question")`
- `metadata["action"]` points to the action this warrant justifies
- `metadata["kind"] = "warrant"` is recommended

### Action

All reasoning steps are modeled as `Action` objects. `Action` is the common base
class for five primitive reasoning moves:

- `Derive`
- `Compute`
- `Observe`
- `Relate`
- `Compose`

All primitive actions share the same minimal schema:

```python
Action(
    inputs,
    output,
    background=None,
    warrant=None,
    metadata=None,
)
```

Field meanings:

- `inputs`: the direct upstream objects consumed by the action
- `output`: the main resulting `Knowledge`; `Compose` may use `None`
- `background`: graph-active context, assumptions, or setup conditions
- `warrant`: one warrant claim or a list of warrant claims
- `metadata`: existing Gaia-style side information such as method, tool, or run info

All probabilistic parameters associated with a reasoning step live in the warrant
claims, not on the action itself.

## Primitive Actions

### Derive

Use `Derive` when some existing claims produce a new claim by reasoning.

This primitive covers what older Gaia versions called:

- deduction
- prediction
- support
- explanation

Minimal form:

```python
Derive(
    inputs=[...],
    output=...,
    background=[...],
    warrant=...,
    metadata={...},
)
```

### Compute

Use `Compute` when a result is produced by a numerical or algorithmic method.

This is necessary for first-principles simulation, fitted models, numerical scans,
and other code-driven workflows.

`Compute` uses the same schema as `Derive`; the difference is semantic, not structural.

Recommended metadata fields include:

- `method`
- `program`
- `version`
- `reproduced`

### Observe

Use `Observe` when external data, experiment, or measurement enters the graph.

Observations are exogenous inputs. Their trustworthiness should be handled by
their warrant claim and its prior.

### Relate

Use `Relate` when the step judges a relation among existing objects.

Typical uses:

- prediction fits observation
- one explanation is better than another
- two claims contradict each other
- a value lies inside a predicted interval
- two systems are relevantly similar

`Relate` always produces a relation claim as `output`.

### Compose

Use `Compose` when several existing actions or claims are assembled into a higher-level
reasoning structure.

Typical uses:

- induction
- abduction
- IBE
- analogy
- case analysis
- elimination

`Compose` is recursive. Its `inputs` may include both `Knowledge` and `Action`
objects. Only one `Compose` type is needed.

`Compose.output` should usually be a single summary claim. It may be `None` for
pure grouping, but list outputs are discouraged.

## Warrant Review Model

Each warrant is a reviewable claim with an attached question.

Example shape:

```python
w = claim(
    "A deviation of 0.02 from 3:1 is acceptable under the stated experimental error",
    metadata={
        "kind": "warrant",
        "question": q.id,
        "action": action_id,
    },
)
```

The linked question provides the exact review prompt:

```python
q = question(
    "How plausible is it that 2.98:1 should count as fitting 3:1 in this experiment?"
)
```

The warrant claim's `prior` is the reviewer's estimate for the warrant itself.

This keeps the system uniform:

- claim priors for exogenous claims
- claim priors for warrant claims
- no separate action-level probability field

## Pattern Library

The following traditional strategy names are no longer primitive. They are
composition patterns over the primitive actions.

### Induction

```text
induction = Compose(Derive, Observe, Relate)
```

### Abduction

```text
abduction = Compose(Derive, Observe, Relate)
```

### IBE

```text
IBE = Compose(Relate)
```

### Analogy

```text
analogy = Compose(Relate, Derive)
```

### Case Analysis

```text
case_analysis = Compose(Derive)
```

### Elimination

```text
elimination = Compose(Relate, Derive)
```

## Worked Examples

### Mendel: Segregation and F2 Ratios

```python
segregation = claim("Mendel's law of segregation")
shape_pred = claim("Seed shape ratio should be 3:1")
shape_obs = claim("Observed seed shape ratio is 2.98:1")
shape_fit = claim("Observed shape ratio fits the segregation prediction")

q_pred = question("How plausible is it that segregation predicts a 3:1 F2 ratio here?")
w_pred = claim(
    "Segregation predicts a 3:1 F2 ratio for a monohybrid trait",
    metadata={"kind": "warrant", "question": q_pred.id},
)

d1 = Derive(
    inputs=[segregation],
    output=shape_pred,
    background=[],
    warrant=w_pred,
)
w_pred.metadata["action"] = id(d1)

q_obs = question("How plausible is it that the shape-cross measurement is reliable?")
w_obs = claim(
    "The shape-cross measurement is reliable",
    metadata={"kind": "warrant", "question": q_obs.id},
)

o1 = Observe(
    inputs=[claim("Shape experiment")],
    output=shape_obs,
    background=[claim("Sample quality is adequate")],
    warrant=w_obs,
)
w_obs.metadata["action"] = id(o1)

q_fit = question("How plausible is it that 2.98:1 counts as fitting 3:1 here?")
w_fit = claim(
    "A deviation of 0.02 from 3:1 is acceptable under the stated experimental error",
    metadata={"kind": "warrant", "question": q_fit.id},
)

r1 = Relate(
    inputs=[shape_pred, shape_obs],
    output=shape_fit,
    background=[claim("Accepted error model for ratio comparison")],
    warrant=w_fit,
)
w_fit.metadata["action"] = id(r1)
```

An inductive step over multiple fits is then just:

```python
ind_support = claim("Segregation law is inductively supported")
q_ind = question("How plausible is it that successful fits across traits jointly support the same law?")
w_ind = claim(
    "Independent trait-level fits jointly support the same segregation law",
    metadata={"kind": "warrant", "question": q_ind.id},
)

ind = Compose(
    inputs=[shape_fit],  # plus other trait fits
    output=ind_support,
    background=[claim("The considered traits are independent")],
    warrant=w_ind,
)
w_ind.metadata["action"] = id(ind)
```

### Electron Liquid: First-Principles Tc for Al

```python
fp_model_Al = claim("First-principles Coulomb pseudopotential model for Al")
Al_params = claim("Material parameters for Al")
tc_Al_fp = claim("Computed Tc for Al")
tc_Al_obs = claim("Observed Tc for Al")
tc_Al_fit = claim("Computed Tc for Al fits experiment")

q_comp = question("How plausible is it that this computational setup yields a reliable Tc for Al?")
w_comp = claim(
    "The first-principles Coulomb pseudopotential solver is valid for Al in this regime",
    metadata={"kind": "warrant", "question": q_comp.id, "method": "first_principles_solver"},
)

c1 = Compute(
    inputs=[fp_model_Al, Al_params],
    output=tc_Al_fp,
    background=[claim("The LDA-like approximation is valid in this regime")],
    warrant=w_comp,
    metadata={"method": "first_principles_solver"},
)
w_comp.metadata["action"] = id(c1)

q_obs_tc = question("How plausible is it that the reported Tc measurement for Al is reliable?")
w_obs_tc = claim(
    "The Al Tc measurement is reliable",
    metadata={"kind": "warrant", "question": q_obs_tc.id},
)

o_tc = Observe(
    inputs=[claim("Al superconducting transition experiment")],
    output=tc_Al_obs,
    background=[claim("Sample preparation is adequate")],
    warrant=w_obs_tc,
)
w_obs_tc.metadata["action"] = id(o_tc)

q_fit_tc = question("How plausible is it that the discrepancy between predicted and observed Tc is acceptable?")
w_fit_tc = claim(
    "The discrepancy between computed and observed Tc is acceptable under the stated error assumptions",
    metadata={"kind": "warrant", "question": q_fit_tc.id},
)

r_tc = Relate(
    inputs=[tc_Al_fp, tc_Al_obs],
    output=tc_Al_fit,
    background=[claim("Accepted Tc comparison criterion")],
    warrant=w_fit_tc,
)
w_fit_tc.metadata["action"] = id(r_tc)
```

### Phenomenological Tc Range vs Observation

```python
pheno_model_Al = claim("Phenomenological model for Al")
tc_Al_range = claim("Predicted Tc for Al lies in [0.1, 0.2)")
tc_Al_obs_013 = claim("Observed Tc for Al is 0.13")
tc_range_fit = claim("Observed Tc lies inside the predicted interval")

q_range = question("How plausible is it that 0.13 should count as fitting the predicted interval [0.1, 0.2)?")
w_range = claim(
    "The observed Tc lies within the phenomenologically predicted interval",
    metadata={"kind": "warrant", "question": q_range.id},
)

r_range = Relate(
    inputs=[tc_Al_range, tc_Al_obs_013],
    output=tc_range_fit,
    background=[claim("Interval-fit criterion for Tc comparison")],
    warrant=w_range,
)
w_range.metadata["action"] = id(r_range)
```

## Alignment with Current Gaia Concepts

- `Knowledge` stays unchanged
- old named strategies become v6 patterns or sugar over primitive actions
- warrants remain graph objects rather than being demoted to plain metadata
- action-specific probability parameters move into warrant claims
- `Compose` replaces the need for multiple primitive high-level strategy categories

## Summary

Gaia Lang v6 keeps the existing node model and simplifies the reasoning layer.
Instead of proliferating strategy primitives, it uses a small number of `Action`
objects plus reviewable warrant claims.

This keeps the authoring model compact while preserving the ability to formalize
scientific prose, numerical experiments, and higher-order reasoning patterns.
