# Bayes Model Observable Unit Design

## Context

PR #657 introduces the unified Bayes surface around predictive model declarations,
model comparison, and precomputed likelihoods. The current branch names the
model-declaration record `Prediction` and exposes `predict(...)`:

```python
model_h = bayes.predict(
    h,
    target=k_or_distribution,
    distribution=Binomial(...),
)
cmp = bayes.compare(data, models=[model_h, ...])
```

That shape works mechanically, but it leaves two semantic problems:

1. `predict(...)` is really declaring a model, not producing a prediction result.
2. `target: Variable | Distribution` overloads `Distribution` as both a
   probability distribution and an observable identity.

Gaia already has a dedicated unit system through `gaia.unit.q`,
`gaia.unit.Quantity`, and IR `QuantityLiteral`. Unit-bearing continuous
quantities currently rely on `Distribution.metadata["unit"]`, because
`Variable` does not yet declare a canonical unit. Any cleanup must preserve that
unit safety rather than replacing it with ad hoc metadata strings.

## Goal

Make Bayes model declarations reflect the ontology directly:

```python
k = Variable(symbol="k", domain=Nat)
m1 = bayes.model(h1, observable=k, distribution=Binomial("k under h1", n=n, p=theta))
m2 = bayes.model(h2, observable=k, distribution=Binomial("k under h2", n=n, p=theta))
data = observe(k, value=295)
cmp = bayes.compare(data, models=[m1, m2])
```

For unit-bearing continuous observables:

```python
T = Variable(symbol="T", domain=Real, unit="K")
m = bayes.model(
    h,
    observable=T,
    distribution=Normal("T under h", mu=q(200, "K"), sigma=q(50, "K")),
)
data = observe(T, value=q(203, "K"), error=q(5, "K"))
```

The model record stores the observable identity. The distribution stores the
predictive law over that observable.

## Non-Goals

- Do not introduce a new `RandomQuantity` or `Observable` class in this PR.
- Do not remove the existing continuous `observe(distribution, ...)` path.
  It remains for existing predicate/continuous quantity workflows.
- Do not keep `Distribution` as a valid Bayes model observable.
- Do not add a compatibility alias for the removed `predict(...)` surface.
  PR #657 is already a clean break for the Bayes authoring surface.

## Public API

Canonical Bayes API:

```python
from gaia.engine import bayes

model_h = bayes.model(
    hypothesis,
    observable=observable_variable,
    distribution=predictive_distribution,
)
comparison = bayes.compare(data, models=[model_h, other_model])
```

`bayes.__all__` should expose:

- `model`
- `compare`
- `Model`
- `ModelComparison`
- `BayesInference`
- `PrecomputedLikelihoods`

`predict` and `Prediction` should not be canonical public names.

## Runtime Records

Replace the current Bayes model-declaration record with:

```python
class Model(BayesInference):
    hypothesis: Claim | None = None
    observable: Variable | None = None
    distribution: Distribution | None = None
    helper: Claim | None = None
```

Keep comparison as a noun record:

```python
class ModelComparison(BayesInference):
    helper: Claim | None = None
    models: tuple[Claim, ...] = ()
    data: tuple[Claim, ...] = ()
    exclusivity: str = "pairwise_contradiction"
    precomputed: Any | None = None
    log_likelihoods: dict[Claim, float] = field(default_factory=dict)
```

Rationale:

- `model(...)` is an authoring verb.
- `Model` is the graph record declaring `P(observable | hypothesis)`.
- `ModelComparison` is the graph record for comparing model helper claims
  against data.
- `Distribution` is the predictive law, not the observable identity.

## Variable Unit Contract

Extend `Variable` with an optional canonical unit:

```python
class Variable(Knowledge):
    symbol: str
    domain: PrimitiveType | Domain
    value: Any | None
    unit: str | None
```

Constructor behavior:

- Accept `unit: str | None = None`.
- If provided, canonicalize through `gaia.unit.ureg.parse_units(unit)`.
- Store the canonical Pint string, for example `"kelvin"` or `"meter / second"`.
- Do not use arbitrary `metadata["unit"]` as the primary unit contract.

Unit-bearing variables remain Lang-only, like existing `Variable` objects.

## Observe Rules

`observe(variable, value=..., error=...)` should use `Variable.unit` when present.

For `Variable(unit="...")`:

- `value` must be a Gaia `Quantity`.
- `value` is converted to the variable's canonical unit before storing
  `metadata["observation"]["value"]`.
- `metadata["observation"]["unit"]` stores the variable's canonical unit.
- bare scalar values are rejected.
- scalar `error` is rejected; `error` must be either a Gaia `Quantity`, a
  compatible `Distribution`, or `None`.
- Quantity `error` is converted to the variable's canonical unit and sugared
  into anonymous `Normal(mu=0, sigma=...)` noise in that unit.
- Distribution `error` must carry the same canonical unit.

For unitless `Variable(unit=None)`:

- bare scalar values remain valid.
- Quantity values are rejected to avoid silently giving a unitless observable an
  observation-local unit.
- scalar error remains valid and produces unitless anonymous Normal noise.
- unit-typed Distribution error is rejected.

## Model Unit Validation

`bayes.model(..., observable=variable, distribution=dist)` should validate the
observable and predictive distribution units.

Rules:

- `observable` must be a `Variable`; passing a `Distribution` is a `TypeError`.
- If `observable.unit is None`, `distribution.metadata["unit"]` must be absent.
- If `observable.unit is not None`, `distribution.metadata["unit"]` must be
  present and compatible.
- Compatible but non-canonical distribution units should be compared after Pint
  canonicalization. Distribution factories already usually store canonical unit
  strings, but the check should not assume hand-written metadata is canonical.
- If both units are present but incompatible, raise `ValueError`.

Discrete count examples remain unitless:

```python
k = Variable(symbol="k", domain=Nat)
bayes.model(h, observable=k, distribution=Binomial("k under h", n=n, p=theta))
observe(k, value=295)
```

Continuous examples use unit-bearing variables:

```python
T = Variable(symbol="T", domain=Real, unit="K")
bayes.model(h, observable=T, distribution=Normal("T under h", mu=q(200, "K"), sigma=q(50, "K")))
observe(T, value=q(203, "K"), error=q(5, "K"))
```

## Comparison and Lowering

`compare(data, models=[...])` should continue to align data and models by
observable identity:

1. Each model helper must come from a `Model` action.
2. All model actions must reference the same `observable` object.
3. Each observation data claim must carry `metadata["observation"]["target"]`
   pointing to that same `Variable`.
4. Symbol fallback for hand-built variable observations remains, but only for
   `Variable` targets.

Lowering should rename internal helpers from prediction language to model
language:

- `_prediction_action` -> `_model_action`
- `_comparison_prediction_actions` -> `_comparison_model_actions`
- error messages should say `model()` / `Model`, not `predict()` / `Prediction`.

IR metadata must use:

```python
metadata["model"] = {
    "kind": "model",
    "hypothesis": ...,
    "observable": {"kind": "variable", "symbol": ..., "domain": ..., "unit": ...},
    "distribution": ...,
}
```

Do not keep `metadata["prediction"]` for new Bayes model helper claims. This PR
is already a clean-break branch, so the IR-facing metadata should move together
with the public terminology.

## Docs and Examples

Update user-facing and reference docs from:

```python
bayes.predict(h, target=k, distribution=...)
```

to:

```python
bayes.model(h, observable=k, distribution=...)
```

Also update the PR #657 Bayes tutorial examples to use unit-bearing variables for
continuous quantities instead of passing `Distribution` as the target/observable.

## Tests

Add or update tests for:

- `Variable(symbol="T", domain=Real, unit="K")` canonicalizes to `"kelvin"`.
- unit-bearing variable rejects bare scalar `observe(T, value=203)`.
- unit-bearing variable accepts and converts `observe(T, value=q(...))`.
- unitless variable rejects Quantity observations.
- `bayes.model(..., observable=Distribution(...))` raises `TypeError`.
- `bayes.model(..., observable=Variable(unit="K"), distribution=Normal(... q(..., "K")))`
  succeeds.
- model/distribution unit mismatch raises.
- `compare(data, models=[...])` still rejects model/data observable mismatch.
- public surface no longer exports `predict` or `Prediction`.
- public surface exports `model` and `Model`.
- focused Bayes numeric equivalence tests still pass with the new names.

## Migration Notes

This change intentionally makes the PR #657 surface clearer before merge. It is
acceptable to update all in-branch docs, examples, and tests in one sweep because
the branch already removed the older `bayes.model` / `bayes.likelihood` /
`bayes.data` surface. The final public surface should have one canonical model
declaration verb: `bayes.model(...)`.
