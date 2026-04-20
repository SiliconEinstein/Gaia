# v6 likelihood examples

These examples exercise the v6 statistical-model path:

1. represent observed data as parameterized Claims,
2. compute a `LikelihoodScore`,
3. attach the score to a `compute()` correctness Claim,
4. feed it through `likelihood_from()`,
5. compile to IR and lower `log_lr` into BP.

Run them from the repository root:

```bash
python -m examples.v6_likelihood.mendel
python -m examples.v6_likelihood.ab_test
```
