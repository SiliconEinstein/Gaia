# Gaia Engine API

> **Status:** Generated reference layer for `gaia.engine.*`.

The `gaia.engine.*` namespace is the canonical Python contract for Gaia in
alpha 0. It packages the inference backend, IR models, authoring DSL,
Bayes hypothesis-data helpers, semantic-inquiry state, ARM Trace primitives, and package-loading helpers
behind seven facade submodules, each with an explicit `__all__`.

The facade pattern lets package authors and downstream tooling import
stable public names without depending on internal file layout. The 225
symbols below are the **only** alpha-0 stable surface — anything reachable
through deeper paths (`gaia.engine.bp.bp.X`, `gaia.engine.lang.dsl.X`, etc.)
is implementation detail.

## Facade modules

| Module | Symbols | Use it for |
|---|---|---|
| [bayes](bayes.md) | 6 | Hypothesis-data model comparison via `model` / `compare` plus `PrecomputedLikelihoods` for external-solver wrappers. Distribution factories live at `lang`. |
| [bp](bp.md) | 24 | Factor-graph lowering, exact inference, joint-query diagnostics, junction tree, TRW-BP, Mean Field VI, and engine results |
| [ir](ir.md) | 36 | Pydantic IR models, graph contracts, strategies, operators, parameterization, and schemas |
| [lang](lang.md) | 97 | Top-level imports exposed to package authors — claims, actions, public-surface helper (`export`), artifact note anchors (`artifact`, `figure`), relations, formula helpers, distribution factories (`Normal`, `Binomial`, `BetaBinomial`, ...), and runtime entities |
| [inquiry](inquiry.md) | 45 | Semantic review / inquiry-loop state, diagnostics, focus, obligations, hypotheses |
| [trace](trace.md) | 7 | ARM Trace schema, manifests, and review primitives |
| [packaging](packaging.md) | 10 | Gaia package loading, compilation, and prior application |

**Grand total: 225 symbols across 7 facades.**

The `lang` facade subdivides further for browsability — see the supplementary
pages under `engine/lang/` for DSL, runtime, formula, compiler, and refs
breakdowns. Legacy v5 DSL helpers and old runtime aliases live under
`gaia.engine.lang.compat` while packages migrate; they are not part of the
recommended top-level facade.

The propositional logic helpers are now IR-level utilities documented under
[IR logic](ir/logic.md). They are available from `gaia.engine.ir.logic`, but
they are not part of the top-level `gaia.engine.ir` facade count.

## Migrating from earlier versions

Alpha 0 makes `gaia.engine.*` the canonical Python contract. The historical
top-level `gaia.lang`, `gaia.bp`, `gaia.ir`, `gaia.logic`, `gaia.inquiry`,
and `gaia.trace` namespaces no longer exist; importing them raises
`ModuleNotFoundError`. A handful of CLI-internal helpers also moved into
the engine. See [Migration to alpha 0](../../migration.md) for the full
import-path migration table.

## Building these docs

Build locally with:

```bash
make docs-build
```

Serve locally with:

```bash
make docs-serve
```
