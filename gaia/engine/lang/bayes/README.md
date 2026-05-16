# gaia.engine.lang.bayes

`gaia.engine.lang.bayes` provides the lifted Bayes authoring surface:

- distribution literals backed by `scipy.stats`
- `model(...)` for one-hypothesis predictive-model helpers
- `likelihood(...)` for model-preference helpers and IR `infer` lowering

The module intentionally keeps distribution recipes as typed values rather than
Knowledge nodes. `PredictiveModel` and `Likelihood` are `BayesInference`
reasoning records whose helper claims compile through the existing IR schema,
operators, and BP factor types.

Use the namespace form in packages:

```python
from gaia.engine.lang import bayes

model_a = bayes.model(h_a, observable=x, distribution=bayes.Normal(mu=mu, sigma=1.0))
model_b = bayes.model(h_b, observable=x, distribution=bayes.Normal(mu=mu, sigma=1.0))
comparison = bayes.likelihood(data, model=model_a, against=[model_b])
```

See `docs/foundations/gaia-lang/bayes.md` for the executable Mendel example and
the lowering contract.
