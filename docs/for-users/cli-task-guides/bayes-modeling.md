# Bayes Modeling

> **Status:** Current canonical (alpha 0 grouped CLI)

Use `gaia bayes` when you want structured CLI appends for Bayesian model
snippets. The full native surface is still the Python DSL exposed by
`gaia.engine.bayes`; run `gaia sdk` when you need the complete API.

## Typical Flow

Assume the package already has hypothesis/model Claims such as
`mendelian_hypothesis` and `null_model`, plus an observation Claim such as
`observed_count`.

```bash
gaia author variable --target ./my-first-gaia \
  --symbol k --domain Nat --dsl-binding-name k_count
gaia bayes binomial --target ./my-first-gaia \
  --n 395 --p 0.75 --label mendel_binomial
gaia bayes model \
  --target ./my-first-gaia \
  --hypothesis mendelian_hypothesis \
  --observable k_count \
  --distribution mendel_binomial \
  --label mendel_model
gaia bayes compare \
  --target ./my-first-gaia \
  --data observed_count \
  --model mendel_model \
  --against null_model \
  --label count_comparison
gaia build check ./my-first-gaia
```

`gaia bayes compare` defaults to
`exhaustive_pairwise_complement` for two models. For three or more models, pass
`--exclusivity pairwise_contradiction` until N-ary exclusive support lands.

## What To Read Next

- [CLI Reference: bayes](../../reference/cli/bayes.md) for model, compare, and distribution verbs.
- [Bayes Semantics](../../foundations/gaia-lang/bayes.md) for the lowering contract.
- [Language Reference](../language-reference.md#model-based-bayesian-soft-constraints-prefer-this-for-real-data-likelihoods) for Python-side examples.
