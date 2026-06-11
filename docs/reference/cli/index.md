# Gaia CLI

> **Status:** Reference layer for the `gaia` command-line app.

The installed entrypoint is `gaia`. The current v0.5 command surface is
organized into explicit top-level groups:

| Group | Members | Purpose |
|---|---|---|
| [author](author.md) | 18 statement-emitting verbs + 2 composition registration verbs (`note` / `claim` / `derive` / `variable` / ... / `compose`) | Agent-first authoring surface — append DSL statements through the cli without hand-editing source |
| [build](build.md) | `init` / `compile` / `check` | Create and validate a knowledge package |
| [run](run.md) | `infer` / `render` | Execute inference and emit presentation outputs |
| [inspect](inspect.md) | `starmap` | Visualize the compiled package graph |
| [review](review.md) | *(skeleton — no commands in alpha 0)* | Reserved for downstream reviewer tooling |
| [inquiry](inquiry.md) | `focus` / `review` / `obligation [add\|list\|close]` / `hypothesis [add\|list\|remove]` / `tactics log` / `reject` | Local semantic-inquiry loop *(unchanged)* |
| [pkg](pkg.md) | `add` / `add-import` / `add-module` / `register` / `scaffold` | Install dependencies, manage package modules/imports, publish, and bootstrap packages |
| [search](search.md) | `lkm [docs\|knowledge\|reasoning\|nodes\|package\|auth]` | Retrieve remote knowledge candidates for Gaia authoring; future home for local package search |
| [bayes](bayes.md) | `model` / `compare` / distribution literals | Bayesian model and distribution authoring helpers |
| [trace](trace.md) | `verify` / `review` / `show` | ARM Trace tooling *(independent sub-app; unchanged)* |

The pre-alpha-0 leaf verbs keep their original internal logic, semantics,
and option flags under grouped paths. The `author`, `bayes`, `pkg scaffold`,
`pkg add-import`, and `pkg add-module` surfaces are v0.5 cli-as-client
additions rather than old flat-verb redirects.

## Migrating from earlier versions

Alpha 0 removed the 9 historical flat verbs (`gaia compile`, `gaia infer`,
`gaia starmap`, etc.); invoking them now fails with typer's standard
`No such command` usage error and exits with code 2. See
[Migration to alpha 0](../../migration.md) for the full old-to-new
mapping and the related Python import-path changes.

## Internals

For Typer wiring and command implementation entry points, see
[CLI Internals](internals.md).

For end-user CLI invocation reference (option flags, examples, workflow),
see [CLI Commands](../../for-users/cli-commands.md).
