# Gaia v6 Likelihood Minimal Design

> Status: implementation note
> Date: 2026-04-20
> Scope: current Python implementation of v6 `compute()` and `likelihood_from()`
> Related PR stack: v6 strategy methods, standard likelihood modules, BP lowering, CLI/rendering surfaces

---

## 1. First principles

Gaia v6 keeps one probability-bearing object:

```text
Claim
```

Everything else explains how claims are connected, computed, reviewed, or rendered.

The likelihood design follows from this rule:

1. A statistical model does not become a probabilistic edge.
2. A computed score is not itself a Claim.
3. Uncertain assumptions about the model, data, or code must be represented as Claims.
4. A likelihood Strategy consumes a score value and applies it to one target Claim.

So the minimal shape is:

```text
data/model/code assumptions  ->  compute correctness Claim
LikelihoodScore value        ->  likelihood update on target Claim
```

The score is a value object. The correctness of computing or using the score is a Claim.

---

## 2. Objects

### `LikelihoodScore`

`LikelihoodScore` is a runtime value object produced by a module function.

It contains:

```python
target: Claim
module_ref: str
score_type: "log_lr" | "bayes_factor" | "likelihood_table" | "custom"
value: Any
query: str | dict | None
rationale: str | None
score_id: str
```

It is not a Claim and does not get a prior or posterior.

Example:

```python
score = two_binomial_ab_test_score(
    target=b_better,
    control_successes=500,
    control_trials=10_000,
    treatment_successes=550,
    treatment_trials=10_000,
    query="theta_B > theta_A",
)
```

This says: under the registered AB-test likelihood module, compute a score for the query
`theta_B > theta_A` against the target Claim `b_better`.

### `compute()`

`compute()` records a deterministic computation and returns:

```python
ComputeResult(output, correctness, strategy)
```

Current semantics:

- `output` is the value/artifact produced by the function, often a `LikelihoodScore`.
- `correctness` is a Claim saying the computation output was correctly produced.
- `strategy` is `Strategy(type="compute")` with `method=ComputeMethod(...)`.

`compute()` does not itself add probability. If the computation might be wrong, that uncertainty
lives in the `correctness` Claim and in any assumption Claims passed to `compute()`.

Example:

```python
score_result = compute(
    "gaia.std.likelihood.two_binomial_ab_test_score",
    inputs={"counts": counts, "target": b_better},
    assumptions=[randomization_valid],
    output=score,
    correctness=score_correct,
)
```

This connects:

```text
counts, b_better, randomization_valid -> score_correct
output = score
```

### `likelihood_from()`

`likelihood_from()` records a likelihood update and returns a `Strategy(type="likelihood")`.

It consumes either:

```python
score=LikelihoodScore(...)
score_correctness=Claim(...)
```

or the preferred bundled form:

```python
score=ComputeResult(...)
```

When passed a `ComputeResult`, it automatically extracts:

```text
score.output       -> score value
score.correctness  -> score_correct premise
```

Example:

```python
likelihood_from(
    target=b_better,
    data=[counts],
    assumptions=[randomization_valid],
    score=score_result,
)
```

This lowers to a `Strategy(type="likelihood")` whose method is:

```python
ModuleUseMethod(
    module_ref="gaia.std.likelihood.two_binomial_ab_test@v1",
    input_bindings={"target": b_better, ...},
    output_bindings={"score": score.score_id},
    premise_bindings={"score_correct": score_correct, ...},
)
```

---

## 3. What `query` means

`query` is the statistical proposition answered by the module score. It is not display text only.

Examples:

```text
theta_B > theta_A
p = 0.75
```

For AB tests, `query="theta_B > theta_A"` means the signed likelihood score should update the
Claim that treatment B has a higher true rate than control A.

For Mendel-style counts, `query="p = 0.75"` means the score measures how well the observed count
fits a binomial model with success probability 0.75 relative to the saturated MLE model.

The current standard modules require non-empty `query` in validated IR because otherwise a score
has no machine-readable statement of what was actually evaluated.

---

## 4. Standard module registry

The first implementation has a small static registry:

```python
gaia.std.likelihood.binomial_model@v1
gaia.std.likelihood.two_binomial_ab_test@v1
```

Each `LikelihoodModuleSpec` declares:

```python
module_ref
input_schema
output_schema
premise_schema
target_role
score_role
score_type
effect
```

Current lowering supports:

```text
score_type = "log_lr"
effect     = "add_log_odds"
```

Future modules may add Bayes factors or likelihood tables, but they must enter through a registered
spec before the validator accepts them.

---

## 5. Validator contract

The IR validator checks the executable contract rather than only checking shapes.

For every registered likelihood score:

- `score.module_ref` must be known.
- `score.score_type` must match the registered module spec.
- `score.target` must exist and be a Claim.
- `score.query` must be non-empty.
- `log_lr` values must be finite numbers.

For every `Strategy(type="likelihood")`:

- `method` must be `ModuleUseMethod`.
- `method.module_ref` must be known.
- `method.output_bindings[spec.score_role]` must reference an existing score record.
- the score module must match the method module.
- the score type must match the module spec.
- `method.input_bindings[spec.target_role]` must point to the Strategy conclusion.
- `score.target` must match the Strategy conclusion and target binding.

This prevents the common failure mode where a likelihood Strategy points at one target while the
score was computed for another target, or where a score value from one statistical module is used
as if it came from another module.

---

## 6. BP lowering

For the current `log_lr` modules, lowering applies a gated likelihood update:

```text
posterior odds(target) = prior odds(target) * exp(log_lr)
```

The gate is the score correctness Claim. If the correctness Claim is false, the likelihood update
is neutral. If it is true, the log-likelihood ratio shifts the target Claim's log-odds.

This is why `compute()` creates or accepts a correctness Claim. The system never treats a numeric
score as automatically trustworthy.

---

## 7. Minimal worked example

```python
from gaia.lang import claim, compute, likelihood_from
from gaia.std.likelihood import two_binomial_ab_test_score

counts = claim("A: 500/10000 conversions; B: 550/10000 conversions.", prior=0.999)
randomization = claim("Users were randomly assigned.", prior=0.999)
score_correct = claim("The AB log-likelihood score was computed correctly.", prior=0.999)
target = claim("Treatment B has a higher true conversion rate than control A.", prior=0.5)

score = two_binomial_ab_test_score(
    target=target,
    control_successes=500,
    control_trials=10_000,
    treatment_successes=550,
    treatment_trials=10_000,
    query="theta_B > theta_A",
)

score_result = compute(
    "gaia.std.likelihood.two_binomial_ab_test_score",
    inputs={"counts": counts, "target": target},
    assumptions=[randomization],
    output=score,
    correctness=score_correct,
)

likelihood_from(
    target=target,
    data=[counts],
    assumptions=[randomization],
    score=score_result,
)
```

Conceptually:

```text
score = statistical model(data, query, target)
score_correct = claim that the score computation is correct
target belief is updated by score only through a likelihood Strategy gated by score_correct
```

This is the smallest working contract. It deliberately avoids a general compute replay engine.
Replay validation for standard modules can be added later without changing the IR shape.
