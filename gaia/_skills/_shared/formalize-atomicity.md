# Claim atomicity

Shared reference for `gaia-formalize-coarse` and `gaia-formalize-fine`. Both
skills decompose a paper into atomic claims; this file is the single canonical
statement of what "atomic" means and how to test for it. Reference, not
procedure — it has no frontmatter and is not itself a skill.

A claim's *mechanics* — whether it is held in working notes or written
straight to DSL, what label it gets, which module it lands in — belong to the
calling skill. This file owns only the question: **is this one claim, or
several?**

## The principle

Each claim states **exactly one thing**: it answers exactly one citable
epistemic question about the paper — one new bound, one new relation, one new
procedure, one new measured value, one new comparison outcome, one new causal
attribution, one new generalization result. If a candidate body answers two,
split it into two claims.

The rule is **field-agnostic**. The same one-question-per-claim discipline
applies whether the paper is a theorem in pure mathematics, a clinical-trial
endpoint in medicine, a benchmark result in machine learning, a causal
estimate in social science, or a measurement in experimental physics.

## Two corollaries that catch most violations

The most common atomicity failures are two specific fusion patterns. Each is
just the one-question test applied to a recurring shape.

### Separate theory from experiment

A theoretical prediction and the experimental measurement it is compared
against are **two claims, never one**. They answer different citable
questions, carry different evidence, and have different weak points. A claim
that fuses them also cannot be wired to a verification relation later.

```python
# BAD — theory and experiment fused
result = claim("The model predicts X, the experimental value is Y, deviation Z%.")

# GOOD — two independently judgeable claims
prediction  = claim("Based on method M, the model predicts quantity Q = X.")
measurement = claim("The experimental measurement of quantity Q is Y.")
```

### Separate method from result

A method or procedure description and the value that applying it produced are
**two claims**. The method is a contribution a later paper could reuse for a
different outcome; the value is an empirical result a different method could
equally have produced.

```python
# BAD — method and result fused
result = claim("Using method M to compute Q yields Z.")

# GOOD
method = claim("Method M employs ... strategy ...")
result = claim("The numerical result for Q is Z ± δ.")
```

## Common under-splitting traps

Each trap is illustrated with examples from different fields to make clear
that the trap is structural, not domain-specific.

- **Definition + headline result.** A new bound (e.g. "the scheme is
  parametrically valid when $\omega_D \ll E_F$, $\omega_c^2 \ll \omega_p^2$,
  $T \ll \omega_c$") and the downstream result that uses it are *two* claims —
  the bound is a citable regime claim on its own. Outside physics, the same
  trap appears in a clinical RCT that introduces a new operational criterion
  alongside its prevalence: "the protocol's prespecified no-disease-activity
  criterion at week 24 (combining OCT central-subfield thickness, BCVA,
  hemorrhage status, and investigator judgment) is met by 65% of treated
  participants" is two claims — the criterion is a methodological
  contribution citable by anyone designing a similar regimen, separate from
  the empirical prevalence it yielded in this cohort.
- **Procedure + the value it produced.** "Cluster-DiagMC achieves
  γ~$10^5$ at $n=6$ and reproduces $P(0,0)=0.0504(3)$" is two claims: the
  algorithm's measured speedup, and the agreement with the polarization
  baseline. Each has different evidence and different weak points. Outside
  physics, the same trap appears in a clinical RCT conclusion that bundles
  regimen with outcome: "faricimab dosed every 16 weeks after a four-monthly
  loading phase produces +11.4 ETDRS letters at week 52 with a mean of 6.2
  injections" is two — the dosing regimen is a methodological contribution
  downstream trials could reuse for a different outcome, and the measured
  BCVA change is an empirical efficacy result a different regimen could
  equally have produced.
- **Theorem + worked example.** A general formal claim and the explicit
  worked-example calculation that motivates it (e.g. "the third-order
  four-diagram cancellation drops by $\sim 3.48 \times 10^{-3}$") are two
  claims when the worked example is a separate quantitative finding. Outside
  physics, the same trap appears in causal-inference methodology papers: a
  new identifiability theorem for an estimand under stated assumptions, and a
  worked example applying the resulting estimator to a specific
  competing-events dataset to produce a numerical estimate, are two claims —
  the theorem is a formal contribution citable by anyone working with that
  estimand class, and the worked example is an empirical instantiation.
- **Mechanism + benchmark.** "The downfolded Migdal–Eliashberg equation
  reproduces the toy-model $T_c$ to within $0.2\%$" — the mechanism (the
  equation) is one claim; the benchmark agreement is another. Outside
  physics, the same trap appears in algorithmic system papers: "DVL
  pre-integration is linearized in the rotation update, avoiding full
  re-integration inside the nonlinear solver, and AQUA-SLAM achieves lower
  translation RMSE than five baselines on the WaveTank dataset" is two — the
  linearization mechanism is a methodological contribution downstream SLAM
  systems could adopt with a different baseline set, and the WaveTank RMSE
  comparison is an empirical benchmark result.

## Two tests

**Split test.** After writing a candidate body, ask: *if I deleted any one
clause, would I lose an answer to a distinct citable question?* If yes, split
that clause off. If the body merely loses an aside that does not answer its
own citable question, it is one claim.

**Standalone-citation test.** Would each candidate stand on its own as a
sentence the paper could have published as a stand-alone bullet in the
abstract? If yes, it is atomic. If two candidates can only be cited together
(one is an aside of the other), they are one.

## Do not pre-classify while splitting

Atomicity is only about the one-question split. While splitting, do **not**
pre-classify a claim by "type" (analytical / empirical / methodological) and
do **not** pre-assign it a weak-point pattern. A single claim typically rests
on several reasoning patterns at once; type and weak-point classification
happen later, per the calling skill's own workflow. Atomicity work has
exactly one job: enforce the one-question-per-claim split.
