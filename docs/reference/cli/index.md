# Gaia CLI

> **Status:** Reference layer for the `gaia` command-line app.

The installed entrypoint is `gaia`. The current v0.5 command surface is
organized into explicit top-level groups:

| Group | Members | Purpose |
|---|---|---|
| [sdk](sdk.md) | no leaf commands | Primary authoring entrypoint — generate the SDK reference and `CHEATSHEET.md` for direct Python DSL authoring |
| [author](author.md) | 20 statement-emitting verbs + 2 composition registration verbs + read-only `list` | Optional structured helper over direct SDK authoring; writes into the package's `authored/` submodule |
| [build](build.md) | `init` / `compile` / `check` | Create and validate a knowledge package |
| [run](run.md) | `infer` / `render` | Execute inference and emit presentation outputs |
| [inspect](inspect.md) | `starmap` / `starmap-replay` | Visualize the compiled package graph |
| [review](review.md) | *(skeleton — no commands in alpha 0)* | Reserved for downstream reviewer tooling |
| [inquiry](inquiry.md) | `focus` / `context` / `review` / `obligation [add\|list\|close]` / `hypothesis [add\|list\|remove]` / `tactics log` / `reject` | Local semantic-inquiry loop *(unchanged)* |
| [pkg](pkg.md) | `add` / `add-import` / `add-module` / `register` / `scaffold` | Install dependencies, manage package modules/imports, publish, and bootstrap packages |
| [search](search.md) | `lkm [knowledge\|reasoning\|nodes\|package\|auth]` | Retrieve remote knowledge candidates for Gaia authoring; future home for local package search |
| [bayes](bayes.md) | `model` / `compare` / distribution literals | Bayesian model and distribution authoring helpers |
| [example](example.md) | `galileo` / `mendel` | Print or save runnable walkthrough scripts for shipping examples |
| [skill](skill.md) | `register` / `list` | Materialize bundled Gaia skills into the current project |
| [trace](trace.md) | `verify` / `review` / `show` | ARM Trace tooling *(independent sub-app; unchanged)* |

## Public CLI Coverage

This matrix is the doc-maintenance checklist for public leaf commands. Hidden
compatibility aliases are documented inside their group pages when they matter,
but they are not promoted as primary command surface.

| Command family | Public leaves | Reference |
|---|---|---|
| `gaia sdk` | none | [sdk](sdk.md) |
| `gaia build` | `init`, `compile`, `check` | [build](build.md) |
| `gaia run` | `infer`, `render` | [run](run.md) |
| `gaia inspect` | `starmap`, `starmap-replay` | [inspect](inspect.md) |
| `gaia review` | none in alpha 0 | [review](review.md) |
| `gaia inquiry` | `focus`, `context`, `review`, `reject`, `obligation add/list/close`, `hypothesis add/list/remove`, `tactics log` | [inquiry](inquiry.md) |
| `gaia pkg` | `add`, `add-import`, `add-module`, `register`, `scaffold` | [pkg](pkg.md) |
| `gaia author` | `claim`, `artifact`, `figure`, `note`, `question`, `equal`, `contradict`, `exclusive`, `decompose`, `derive`, `observe`, `compute`, `infer`, `associate`, `parameter`, `register-prior`, `variable`, `depends-on`, `candidate-relation`, `materialize`, `compose`, `composition`, `list` | [author](author.md) |
| `gaia bayes` | `model`, `compare`, `binomial`, `beta-binomial`, `poisson`, `normal`, `log-normal`, `beta`, `exponential`, `gamma`, `student-t`, `cauchy`, `chi-squared` | [bayes](bayes.md) |
| `gaia example` | `galileo`, `mendel` | [example](example.md) |
| `gaia skill` | `register`, `list` | [skill](skill.md) |
| `gaia search lkm` | `knowledge`, `reasoning`, `nodes`, `package`, `auth login/status/logout/rotate` | [search](search.md) |
| `gaia trace` | `verify`, `review`, `show` | [trace](trace.md) |

The pre-alpha-0 leaf verbs keep their original internal logic, semantics,
and option flags under grouped paths. `gaia sdk` is the primary entrypoint for
direct DSL authoring; the `author`, `bayes`, `pkg scaffold`, `pkg add-import`,
and `pkg add-module` surfaces are v0.5 helper additions rather than old
flat-verb redirects.

## Migrating from earlier versions

Alpha 0 removed the 9 historical flat verbs (`gaia compile`, `gaia infer`,
`gaia starmap`, etc.); invoking them now fails with typer's standard
`No such command` usage error and exits with code 2. See
[Migration to alpha 0](../../releases/migration-alpha-0.md) for the full old-to-new
mapping and the related Python import-path changes.

## Internals

For Typer wiring and command implementation entry points, see
[CLI Internals](internals.md).

For end-user workflow examples, see
[CLI Workflow Command Guide](../../for-users/cli-commands.md).
