# Check and Review

> **Status:** Current canonical (alpha 0 grouped CLI)

Use this path after authoring statements and before publishing or trusting a
package's outputs.

## Structural Check

```bash
gaia build compile .
gaia build check .
gaia build check --hole .
gaia build check --warrants .
gaia build check --refs .
gaia build check --gate .
```

`gaia build check` validates structure and artifact freshness. It also exposes
review-oriented views for prior coverage, warrants, citation/local-reference/
artifact diagnostics, inquiry state, and publish gates.

## Semantic Inquiry

```bash
gaia inquiry focus <claim-or-qid> --path .
gaia inquiry context .
gaia inquiry review . --mode publish --markdown --strict
gaia inquiry obligation list --path .
gaia inquiry tactics log --path .
```

Inquiry commands manage local review state under `.gaia/inquiry/`. They do not
edit Python source.

## What To Read Next

- [CLI Reference: build](../../reference/cli/build.md) for `check` flags.
- [CLI Reference: inquiry](../../reference/cli/inquiry.md) for focus, context, review, obligations, hypotheses, tactics, and reject.
- [Review Pipeline](../../foundations/review/review-pipeline.md) for the review manifest contract.
