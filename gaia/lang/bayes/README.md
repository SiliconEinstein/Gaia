# gaia.lang.bayes

`gaia.lang.bayes` provides the lifted Bayes authoring surface:

- distribution literals backed by `scipy.stats`
- `predict(...)` for predictive-model claims
- `likelihood(...)` for comparison-result claims and IR `infer` lowering

The module intentionally keeps distribution recipes as typed values rather than
Knowledge nodes. `PredictiveModel` and `ComparisonResult` are ordinary
claim-shaped Knowledge objects, so the existing IR schema, operators, and BP
factor types stay unchanged.

Use the namespace form in packages:

```python
from gaia.lang import bayes

model = bayes.predict({h_a, h_b}, x, distribution=bayes.Normal(mu=mu, sigma=1.0))
comparison = bayes.likelihood(data, via=model)
```

See `docs/foundations/gaia-lang/bayes.md` for the executable Mendel example and
the lowering contract.
