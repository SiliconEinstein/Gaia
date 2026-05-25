# Bayes hypothesis types

> **Status:** Current user guide for authoring `bayes.compare` model
> distributions.

This guide explains the two kinds of hypothesis you can model with
`bayes.compare`, why the choice matters, and how to avoid the
Lindley–Jeffreys trap that produces over-confident posteriors.

## The mechanism

`bayes.compare(observation, models=[m_1, m_2, ...])` is exact Bayesian
model comparison:

```
posterior(M_i | data) ∝ prior(M_i) × P(data | M_i)
```

where `P(data | M_i)` is the marginal likelihood of the observation under the
predictive distribution attached to `M_i`. The engine does nothing but
evaluate the user-provided distributions at the observation and renormalise.

The choice of distribution is therefore a load-bearing epistemological
commitment, not a matter of taste. A wrong distribution produces a
mathematically correct but practically misleading posterior.

## Two kinds of hypothesis

### Point hypothesis

The theory uniquely determines the value of the parameter. Classic example:
Mendel's segregation model entails `P(dominant) = 3/4` for a single-factor
cross.

Model with a distribution that pins the parameter to its theoretical value:

```python
Binomial("Mendel 3:1", n=395, p=3/4)
```

### Composite hypothesis

The theory commits only to a direction or to a region of parameter space.
"Drug X reduces mortality" entails some `p_X < p_control` without specifying
which `p_X`. "Marker M is associated with outcome" entails some non-trivial
dependence without specifying its strength.

Model with a compound distribution that integrates over the region the
hypothesis allows:

```python
BetaBinomial("elevated rate", n=N, alpha=10, beta=40)
# Equivalent to: p ~ Beta(10, 40); mean = 20%, with mass over roughly 5–40%
```

For each composite hypothesis you pick `α` and `β` (or the analogous
parameters for non-Binomial models) to reflect two things:

- the **central tendency** the hypothesis predicts — encoded in the mean
- the **spread** the hypothesis allows — encoded in the concentration

A wider spread makes the model robust to choosing the "wrong" central value,
at the cost of weaker evidence even when the hypothesis is correct.

## The Lindley–Jeffreys trap

When you compare a **point** hypothesis against a **diffuse** alternative
(e.g. `BetaBinomial(n, 1, 1)`), the diffuse model spreads probability mass
uniformly across all possible counts. The point model concentrates all its
mass near one value.

If the observation is even slightly off the point's predicted value, the
point model assigns it very low probability while the diffuse model assigns
it ordinary probability. The Bayes factor against the point hypothesis
explodes — often 10²–10⁵ from a single Gaia observation claim. For a
`Binomial(n=...)` observation, that claim may itself summarize many
underlying trials; "single observation" here means one `observe(...)` input
to `bayes.compare`, not one Bernoulli trial.

This is mathematically correct: a sharp prediction that misses is strong
evidence against the sharp prediction. But the same data may still
qualitatively support the broader hypothesis the user actually meant — they
just wrote a too-sharp distribution.

### Symptom

A single observation produces:

- posterior on the hypothesis > 0.99, or
- posterior on the hypothesis < 0.01

If this surprises you given the data, you have likely committed too strongly.

### Diagnosis

Ask: does my theory really predict this exact parameter value, or only this
direction / region?

If the theory only predicts direction (most empirical hypotheses), the point
distribution is wrong. Switch to a compound distribution.

### Fix

Use compound distributions on **both** sides of the comparison:

```python
m_elevated = bayes.model(H_elevated, observable=k,
    distribution=BetaBinomial("elevated", n=N, alpha=10, beta=40),
    rationale="H entails p above baseline ~5%, central ~20%.")
m_baseline = bayes.model(H_no_effect, observable=k,
    distribution=BetaBinomial("baseline", n=N, alpha=1, beta=20),
    rationale="Without H, p matches baseline.")
```

The `α / β` choices must reflect what each hypothesis honestly predicts.
A useful sanity check: simulate from each distribution and verify the
simulated data look like what the hypothesis would expect to see.

## Choosing α and β for a BetaBinomial

For a directional composite hypothesis where the theory predicts "rate is
elevated":

- **Mean rate**: `α / (α + β)` should equal your best estimate of the rate
  under the hypothesis.
- **Concentration**: `α + β` controls spread. Higher concentration means a
  sharper distribution. Recommended ranges:
  - `α + β ≈ 10` for vague directional hypotheses
  - `α + β ≈ 50–100` when theory or prior data narrows the range
  - `α + β ≈ 1000` only with strong prior data

If unsure, prefer lower concentration. Over-precise priors trip the Lindley
trap from the prior side.

## When point-vs-diffuse IS the right setup

The Mendel-vs-blending comparison in the example packages is genuinely
point-vs-diffuse, and the math behaves as intended:

- `H_Mendel`: `Binomial(395, p=3/4)`. Mendel's theory gives this point.
- `H_blending`: `BetaBinomial(395, 1, 1)`. The alternative is genuinely
  diffuse — blending inheritance does not predict any particular ratio.

This setup is appropriate **only when** the theoretical prediction is a
parsimony commitment: you want to reward the theory for being specific and
right, and penalise it for being specific and wrong.

For most empirical hypotheses, both sides should be composite.

## Diagnostic checklist before calling `bayes.compare`

1. **Hypothesis kind**: is each model a point or a composite hypothesis?
2. **Matched commitment**: if one side is point, is the other also point? If
   not, are you intentionally invoking parsimony?
3. **Spread realism**: does each compound distribution allow values that the
   hypothesis would not contradict?
4. **Single-observation-claim log-LR**: does the resulting `|log LR|` per
   Gaia observation claim exceed roughly 3? If so, sanity-check that the
   distributions are not over-precise.

If check 4 fires, return to check 1.
