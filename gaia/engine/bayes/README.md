# gaia.engine.bayes

`gaia.engine.bayes` provides the unified Bayes authoring surface:

- `model(hypothesis, observable=..., distribution=...)` — declare a
  predictive distribution for one hypothesis.
- `compare(data, models=[...], exclusivity=...)` — compare
  equal-positioned predictive models against observation data. The
  default `exclusivity` is `"exhaustive_pairwise_complement"` — the
  standard Bayesian model-selection contract for two hypotheses — and
  is currently restricted to 2 hypotheses pending an N-ary Exclusive
  operator. The other accepted mode is `"pairwise_contradiction"`
  (at-most-one for open-world model sets). `compare()` deduplicates
  against same-type external `exclusive(...)` / `contradict(...)`
  declarations over the same hypothesis pair, so no explicit "skip
  auto-emission" flag is required. See the `compare()` docstring for
  the full trade-off.
- `PrecomputedLikelihoods` — audit-bearing Claim subclass for plugging
  external-solver output (PyMC / Stan / NumPyro / scipy quadrature /
  custom MCMC) into `compare(precomputed=...)`. This is a Bayes-specific
  log-likelihood record, not the future common evidence-artifact layer.

Predictive distributions are :class:`Distribution` Knowledge objects
created through :mod:`gaia.engine.lang` factories (``Normal``,
``Binomial``, ``BetaBinomial``, ...). The pydantic ``_BaseDistribution``
implementations in this subpackage's ``distributions/`` directory are
internal scipy-backend details — authors should not import them
directly.

Use the namespace import:

```python
import gaia.engine.bayes as bayes
from gaia.engine.lang import Binomial, BetaBinomial, observe

data = observe(k, value=295)
mendel_pred = bayes.model(h_a, observable=k,
                          distribution=Binomial("k under A", n=395, p=0.75))
diffuse_pred = bayes.model(h_b, observable=k,
                           distribution=BetaBinomial("k under B", n=395, alpha=1, beta=1))
comparison = bayes.compare(data, models=[mendel_pred, diffuse_pred])
```

See `docs/foundations/gaia-lang/bayes.md` for the tutorial,
`docs/specs/2026-05-17-bayes-unified-design.md` for the design, and
`scripts/demo_v06_pymc_integration.py` for an end-to-end PyMC
integration example.
