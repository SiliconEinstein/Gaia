# Author With CLI Helper

> **Status:** Optional Tier-2 helper (alpha 0 grouped CLI)

Use `gaia author` when you want machine-checked appends, identifier guards, and
JSON envelopes for a subset of Gaia DSL statements. The primary authoring path
is still direct Python DSL: run `gaia sdk`, read `CHEATSHEET.md`, and write the
package source directly. See [Authoring Workflow](../authoring-workflow.md).

## Basic Flow

```bash
gaia author claim "A mechanism is plausible." \
  --target ./my-first-gaia \
  --dsl-binding-name mechanism_claim \
  --label mechanism_claim
gaia author note "Experimental context." \
  --target ./my-first-gaia \
  --dsl-binding-name experiment_context
gaia author derive \
  --target ./my-first-gaia \
  --conclusion-content "A measurable prediction follows." \
  --given mechanism_claim \
  --background experiment_context \
  --dsl-binding-name mechanism_prediction \
  --label mechanism_prediction_path
gaia author list --target ./my-first-gaia --human
gaia build check ./my-first-gaia
```

The write commands append Python DSL statements under
`src/<import_name>/authored/`, which the package root re-exports.
`gaia author list` is read-only: it scans source files with Python AST and
shows current bindings, file locations, and export state.

## When To Use Module Plumbing

Use `gaia pkg add-module` before writing into a sibling file under `authored/`:

```bash
gaia pkg add-module --target ./my-first-gaia --name priors --imports register_prior
gaia author register-prior --claim mechanism_claim --value 0.7 \
  --justification "External review." \
  --target ./my-first-gaia \
  --file priors.py
```

Use `gaia pkg add-import` when a source file needs names from a sibling module.

## What To Read Next

- [CLI Reference: author](../../reference/cli/author.md) for every author verb.
- [CLI Reference: pkg](../../reference/cli/pkg.md) for `add-module` and `add-import`.
- [Authoring Workflow](../authoring-workflow.md) for the SDK-first model.
- [Language Reference](../language-reference.md) for the Python DSL semantics.
