# Migration to alpha 0

Alpha 0 introduces the `gaia.engine.*` Python contract and reorganizes the
CLI into 6 logical groups plus the independent `trace` sub-app. This guide
covers the three migration layers you may need to update:

1. **CLI verb migration** — how to update `gaia <verb>` invocations.
2. **Import path migration** — how to update `from gaia.<sub> import ...`
   in your DSL files, your packages, and your own tooling.
3. **Legacy DSL verb migration** — how to move old named reasoning helpers
   onto the v0.5 action/relation surface.

If you have an existing Gaia knowledge package built on a pre-alpha version,
this is the work needed to get it green again.

> **Note on tombstones (v0.5.x, post-alpha-0):** The alpha-0 release
> shipped explicit "tombstone" stubs that intercepted old import paths and
> flat-verb invocations with friendly redirect messages. Those stubs were
> always intended as a short-lived migration aid and have since been
> removed. Old paths now fail with plain Python `ModuleNotFoundError` and
> typer's standard `No such command` usage error rather than the
> hand-written redirect messages. The migration tables below remain the
> authoritative old-to-new mapping.

---

## Layer 1: CLI verb migration

The historical 9 flat top-level verbs have been reorganized into 6 groups.
`inquiry` and `trace` are sub-apps and were already groups; their internal
subcommands are **unchanged**.

| Old (flat — removed) | New (grouped) |
|---|---|
| `gaia init` | `gaia build init` |
| `gaia compile` | `gaia build compile` |
| `gaia check` | `gaia build check` |
| `gaia infer` | `gaia run infer` |
| `gaia render` | `gaia run render` |
| `gaia starmap` | `gaia inspect starmap` |
| `gaia starmap-replay` | `gaia inspect starmap-replay` |
| `gaia add` | `gaia pkg add` |
| `gaia register` | `gaia pkg register` |

### Group cheat-sheet

| Group | Members | Purpose |
|---|---|---|
| `build` | `init` / `compile` / `check` | Create and validate a knowledge package |
| `run` | `infer` / `render` | Execute inference + emit presentation outputs |
| `inspect` | `starmap` / `starmap-replay` | Visualize the compiled graph |
| `review` | *(skeleton — no commands yet)* | Reserved for downstream reviewer tooling |
| `inquiry` | `focus` / `review` / `obligation [add\|list\|close]` / `hypothesis [add\|list\|remove]` / `tactics log` / `reject` | Local semantic inquiry loop *(unchanged)* |
| `pkg` | `add` / `register` | Install and publish packages |
| `trace` | `verify` / `review` / `show` | ARM Trace tooling *(unchanged, independent)* |

> **Note on `review` vs. `inquiry review` / `trace review`**: the new
> top-level `gaia review` group is a help-visible empty skeleton in alpha 0;
> it is **different** from the pre-existing `gaia inquiry review` and
> `gaia trace review` inner subcommands, which keep their behavior and
> invocation paths.

### What happens if I run an old flat verb?

Old flat verbs are no longer registered. Typer surfaces its standard
usage error and exits with code 2 — no side effects, no partial work:

```console
$ gaia compile ./my-pkg
Usage: gaia [OPTIONS] COMMAND [ARGS]...
Try 'gaia --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ No such command 'compile'.                                                   │
╰──────────────────────────────────────────────────────────────────────────────╯
$ echo $?
2
```

There is no warn-and-execute alias window — the cutover is direct. If you
have CI / shell aliases / Makefiles / docs invoking the flat form, update
them using the mapping above.

> Alpha 0 originally shipped each flat verb as a hidden tombstone stub
> whose stderr message named the new grouped form (e.g. *"`gaia compile`
> was removed in alpha 0. Use `gaia build compile` instead."*). Those
> stubs were removed in v0.5.x; the typer-default `No such command`
> response shown above is the current behavior.

### `check` option flags are unchanged

`gaia build check` keeps the full historical option surface from
`gaia check`:

```
--brief / --show / --hole / --warrants / --blind / --inquiry / --gate
```

All flags accept the same values, in the same order, with the same defaults.

---

## Layer 2: Import path migration

Alpha 0 makes `gaia.engine.*` the canonical Python import path for engine
code. The historical top-level `gaia.<sub>` packages no longer exist; any
import against them raises `ModuleNotFoundError`. A handful of symbols
that used to live under `gaia.cli.*` have also moved into the engine.

### Namespace-level moves (6)

Move every `from gaia.<sub> import X` to `from gaia.engine.<sub> import X`:

| Old (removed) | New |
|---|---|
| `from gaia.bp import X` | `from gaia.engine.bp import X` |
| `from gaia.ir import X` | `from gaia.engine.ir import X` |
| `from gaia.lang import X` | `from gaia.engine.lang import X` |
| `from gaia.logic import X` | `from gaia.engine.ir.logic import X` |
| `from gaia.inquiry import X` | `from gaia.engine.inquiry import X` |
| `from gaia.trace import X` | `from gaia.engine.trace import X` |

Importing any of the 6 old namespaces raises a standard
`ModuleNotFoundError: No module named 'gaia.<sub>'`.

> Alpha 0 originally installed each old namespace as a tombstone shim
> whose `__getattr__` raised a redirect `ImportError` naming the new
> path (e.g. *"`gaia.lang.claim` has moved to `gaia.engine.lang.claim`
> …"*). The shims were removed in v0.5.x; the plain
> `ModuleNotFoundError` shown above is the current behavior.

### Bayes peer-module move

The Bayes authoring surface is now a peer engine module. v0.5 was not released
with the earlier `gaia.engine.lang.bayes` development path, so there is no
compatibility alias; update Bayes imports to the canonical path:

| Old | New |
|---|---|
| `from gaia.engine.lang import bayes` | `import gaia.engine.bayes as bayes` |
| `from gaia.engine.lang.bayes import X` | `from gaia.engine.bayes import X` |
| `from gaia.engine.lang.bayes.compiler import X` | `from gaia.engine.bayes.compiler import X` |
| `from gaia.engine.lang.bayes.verbs import X` | `from gaia.engine.bayes.dsl import X` |

### Symbol-level moves (12)

Some CLI-internal helpers were promoted into `gaia.engine.*` so the engine
contract is self-contained and the CLI is a thin facade. Update these
specific imports:

| Old | New |
|---|---|
| `from gaia.cli._packages import GaiaCliError` | `from gaia.engine.packaging import GaiaPackagingError` *(renamed)* |
| `from gaia.cli._packages import apply_package_priors` | `from gaia.engine.packaging import apply_package_priors` |
| `from gaia.cli._packages import collect_foreign_node_priors` | `from gaia.engine.packaging import collect_foreign_node_priors` |
| `from gaia.cli._packages import compile_loaded_package_artifact` | `from gaia.engine.packaging import compile_loaded_package_artifact` |
| `from gaia.cli._packages import ensure_package_env` | `from gaia.engine.packaging import ensure_package_env` |
| `from gaia.cli._packages import load_dependency_compiled_graphs` | `from gaia.engine.packaging import load_dependency_compiled_graphs` |
| `from gaia.cli._packages import load_gaia_package` | `from gaia.engine.packaging import load_gaia_package` |
| `from gaia.cli.commands._review_manifest import load_or_generate_review_manifest` | `from gaia.engine.inquiry import load_or_generate_review_manifest` |
| `from gaia.cli.commands.check_core import KnowledgeBreakdown` | `from gaia.engine.inquiry import KnowledgeBreakdown` |
| `from gaia.cli.commands.check_core import analyze_knowledge_breakdown` | `from gaia.engine.inquiry import analyze_knowledge_breakdown` |
| `from gaia.cli.commands.check_core import find_possible_duplicate_claims` | `from gaia.engine.inquiry import find_possible_duplicate_claims` |
| `from gaia.cli.commands.check_core import HoleEntry` | `from gaia.engine.inquiry import HoleEntry` |

**Rename detail**: `GaiaCliError` is now `GaiaPackagingError`. Catch sites
need both the module path *and* the class name updated:

```python
# Before
from gaia.cli._packages import GaiaCliError
try:
    ...
except GaiaCliError as exc:
    ...

# After
from gaia.engine.packaging import GaiaPackagingError
try:
    ...
except GaiaPackagingError as exc:
    ...
```

---

## Layer 3: Legacy DSL verb migration

The old v5 named-strategy DSL is no longer the recommended authoring surface.
It remains available only under `gaia.engine.lang.compat` while existing
packages migrate. Direct access through `gaia.engine.lang.<legacy_name>` emits
a `DeprecationWarning`.

| Legacy helper | Recommended v0.5 shape |
|---|---|
| `setting(...)` / `context(...)` | `note(...)` |
| `support([P], C, prior=...)` | `derive(C, given=[P])` for deterministic support, or `infer(...)` / `bayes.likelihood(...)` for probabilistic evidence links |
| `deduction([P], C)` | `derive(C, given=[P])` |
| `infer([premises], conclusion, ...)` | `infer(evidence, hypothesis=..., given=..., p_e_given_h=..., p_e_given_not_h=...)` |
| `compare(...)` / `abduction(...)` | Declare observations, alternatives, relations, and likelihood links explicitly |
| `induction(...)` | Author each evidence step with `derive(...)`, `observe(...)`, or `infer(...)`; let graph topology accumulate evidence |
| `analogy(...)` / `extrapolation(...)` / `elimination(...)` / `case_analysis(...)` / `mathematical_induction(...)` | Author the deterministic skeleton with `derive(...)` plus relation verbs |
| `noisy_and(...)` | `derive(...)` for deterministic conjunction, or `infer(...)` / `bayes.likelihood(...)` for probabilistic evidence links |
| `contradiction(a, b)` / `equivalence(a, b)` / `complement(a, b)` | `contradict(a, b)` / `equal(a, b)` / `exclusive(a, b)` |
| `disjunction(*claims)` / `and_(...)` / `or_(...)` / `not_(...)` | Formula claims such as `claim(..., formula=lor(...))`, `claim(..., formula=land(...))`, and `claim(..., formula=lnot(...))`; `a \| b`, `a & b`, and `~a` are Formula-returning sugar |

See `docs/foundations/gaia-lang/knowledge-and-reasoning.md` §7 for the fuller
compatibility surface and the reasoning contract behind each replacement.

---

## Notes for users with existing packages

If you have a Gaia knowledge package created with an earlier version, these
migration notes apply:

### 1. Imports in your DSL files

Every `__init__.py` / `*.py` under `src/<your_pkg>/` that imports from the
gaia DSL needs its top-of-file import path swapped:

```python
# Before
from gaia.lang import claim, derive, note

# After
from gaia.engine.lang import claim, derive, note
```

A simple sed sweep over your package is usually enough:

```bash
find src -name '*.py' -exec sed -i \
  -e 's/^from gaia\.lang /from gaia.engine.lang /' \
  -e 's/^from gaia\.bp /from gaia.engine.bp /' \
  -e 's/^from gaia\.ir /from gaia.engine.ir /' \
  -e 's/^from gaia\.logic /from gaia.engine.ir.logic /' \
  -e 's/^from gaia\.inquiry /from gaia.engine.inquiry /' \
  -e 's/^from gaia\.trace /from gaia.engine.trace /' \
  {} +
```

After updating, `gaia build compile ./your-pkg` should succeed against the
alpha-0 install.

### 2. CLI invocations in CI scripts, Makefiles, and docs

Anywhere you call `gaia <verb>` in automation, prefix the new group name:

```diff
- gaia compile ./pkg
+ gaia build compile ./pkg

- gaia infer ./pkg
+ gaia run infer ./pkg

- gaia starmap ./pkg --out site.html
+ gaia inspect starmap ./pkg --out site.html
```

If you forget which group a verb landed in, consult the Layer 1 table
above — the old form now fails with typer's generic
`No such command '<verb>'` rather than naming the new form for you.

### 3. Newly scaffolded packages already use the new paths

`gaia build init <name>-gaia` emits a DSL template using
`from gaia.engine.lang import ...` out of the box. You only need step 1 for
packages that pre-date alpha 0.

### 4. Legacy strategy helpers should move off compat

If your package imports from `gaia.engine.lang.compat`, keep that import only
as a short migration bridge. New package code should use `claim(...)`,
`note(...)`, `derive(...)`, `compute(...)`, `infer(...)`, and the relation
verbs from `gaia.engine.lang`.

---

## Reference

- The Layer 1 and Layer 2 tables above are the authoritative old-to-new
  mappings.
- The alpha-0 release of this repository included tombstone stubs that
  enforced these mappings at runtime; they were removed in v0.5.x as part
  of normal cleanup. See the repository history for the original
  implementation (PR #607 added them, the follow-up branch removed them).
