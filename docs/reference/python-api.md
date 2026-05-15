# Python API Reference

> **Status:** Generated reference index.

This section is the code-facing reference layer for Gaia developers. Conceptual
contracts still live in the foundational docs; the pages below record what the
active Python modules expose today.

## Module Map

| Page | Python modules | Use it for |
|------|----------------|------------|
| [Gaia Lang Public Surface](gaia-lang.md) | `gaia.engine.lang` | Top-level imports exposed to package authors |
| [Authoring DSL](dsl.md) | `gaia.engine.lang.dsl` | Public authoring functions such as `claim`, `derive`, `observe`, `infer`, and relations |
| [Runtime Models](runtime.md) | `gaia.engine.lang.runtime` | Runtime objects backing the DSL: claims, actions, roles, domains, and composition |
| [Formula AST](formula.md) | `gaia.engine.lang.formula` | Predicate-logic terms, formula nodes, connectives, and quantifiers |
| [Compiler](compiler.md) | `gaia.engine.lang.compiler` | Package compilation entrypoints |
| [References](refs.md) | `gaia.engine.lang.refs` | Reference extraction, resolution, loading, and collision checks |
| [Gaia IR](ir.md) | `gaia.engine.ir` | Pydantic IR models, graph contracts, strategies, operators, parameterization, and schemas |
| [Belief Propagation](bp.md) | `gaia.engine.bp` | Factor graph lowering, exact inference, junction tree, TRW-BP, Mean Field VI, and engine results |
| [CLI Internals](cli.md) | `gaia.cli` | Typer app wiring and command implementation entrypoints |
| [Logic Utilities](logic.md) | `gaia.engine.logic` | Propositional logic helpers used as computation backends |

Alpha 0 introduces `gaia.engine.*` as the canonical Python contract; the
historical top-level `gaia.lang`, `gaia.bp`, `gaia.ir`, `gaia.logic`,
`gaia.inquiry`, and `gaia.trace` namespaces are tombstoned. See
[Migration to alpha 0](../migration.md) for the import-path migration table.

Build it locally with:

```bash
make docs-build
```

Serve it locally with:

```bash
make docs-serve
```
