# Curated Package Exports Design

> **Status:** Accepted
>
> **Date:** 2026-05-31
>
> **Related:**
>
> - GitHub issue #724 — Knowledge package `exported` semantics: four
>   interfaces, no single convention
> - [Gaia Lang v5 Python DSL Design](2026-04-02-gaia-lang-v5-python-dsl-design.md)
> - [Module Narrative Design](2026-04-04-module-narrative-design.md)
>
> **Scope:** Lock a single, curated meaning for a knowledge package's
> `exported` public surface across the Python `__all__`, the runtime
> `CollectedPackage`, the compiled IR, and the `gaia author` CLI, and define
> the load-time validation that enforces it.

## 1. Problem

Per #724, the `exported` concept lived in four interfaces that disagreed:

1. **Python `__all__`** in the root `<import_name>/__init__.py` — read by
   `load_gaia_package` as a loose string set.
2. **`pkg._exported_labels`** — the runtime set populated from (1).
3. **`pkg.exported` property vs. the IR `exported` field** — these disagreed on
   the most common case. With an empty `_exported_labels`, the property fell
   back to "all labeled knowledge" while the IR recorded `exported=False` for
   everything. The IR is what every downstream tool persists and reads, so the
   property's fallback was effectively dead, but the inconsistency was
   undocumented.
4. **`gaia author <verb> --export` defaults** — permissive (`--export=True` for
   claims / derives / relations), so every BP-participating node landed in
   `__all__` by default.

Every downstream consumer (`gaia register` manifest, README Mermaid, `gaia
inquiry`, `check` boundary analysis, `_dot`, `starmap`, `lkm_explorer`
`exported_ids`, and the `gaia-formalize-fine` / `gaia-publish` skills) assumes
`exported` means **"this paper's headline conclusions"** — a curated surface.
The permissive author default produced the opposite, so intermediate derivations
and relations leaked into rendered "headline" surfaces.

## 2. Decision

Adopt **curated** semantics everywhere (Option A from #724):

- The root `__all__` is the **single source of truth** for the public surface.
- A knowledge is exported **iff** its label is explicitly listed in root
  `__all__`. Notes, `register_prior`, strategies, bridge relations, and
  intermediate derivations are not exported unless the author lists them.
- `gaia author` defaults to `--no-export`: being **referenceable inside** the
  package is independent of being a **public export**.

## 3. Contract

### 3.1 Root `__all__` resolved by attribute + object identity

`load_gaia_package` resolves every name in the root module's `__all__` to a
concrete `Knowledge` object via `_record_root_exports`
(`gaia/engine/packaging.py`). It records both `_exported_knowledge_ids` (object
identity) and `_exported_labels` (names), so the compiler keys exports off the
exact objects, not off label-string coincidence.

### 3.2 Validation rules

Each name in root `__all__` must:

1. be a root-module attribute — catches typos;
2. resolve to a `Knowledge` object — rejects strategies (`deduction`,
   `support`, composites), `fills`/bridge relations, and helper
   functions/constants;
3. point to a **local** package `Knowledge` — rejects dependency re-exports;
4. have `.label == name` — the export name is the QID basis, so aliasing under a
   different name is rejected;
5. be unique.

Any violation raises `GaiaPackagingError` at load/compile time with an
actionable message (see §4).

### 3.3 Empty `__all__` exports nothing

Both `CollectedPackage.exported` and the IR `exported` field now agree: an empty
or missing root `__all__` exports nothing. The property's old "all labeled
knowledge" fallback is removed — this resolves #724's core inconsistency.

### 3.4 Author CLI default is `--no-export`

`ProposedAuthorOp.export` defaults to `False`. `gaia author <verb> --export` is
the opt-in for the curated surface. Referenceability inside the package comes
from the runtime bindings (§3.5), not from `__all__`.

### 3.5 `authored/` composition: runtime bindings vs. exports

The package-root `__init__.py` composes CLI-authored statements by importing the
`authored` submodule, copying its public names into root globals for
package-local references, and merging only the curated `authored.__all__` into
the root `__all__`:

```python
from . import authored as _authored

for _gaia_name, _gaia_value in vars(_authored).items():
    if not _gaia_name.startswith("_"):
        globals()[_gaia_name] = _gaia_value
del _gaia_name, _gaia_value

__all__ = [*__all__, *_authored.__all__]
```

This is the structural separation that makes §3.4 safe: every authored statement
stays referenceable through the runtime-binding loop, while only the names the
author opted into via `--export` reach the public `__all__`.

### 3.6 The `export()` helper

`from gaia.engine.lang import export`. Writing `__all__ = export(main,
secondary)` resolves each `Knowledge` object to its caller-scope public name (or
accepts a plain string), returning a `list[str]` with no hidden state. It raises
on an ambiguous object (bound to multiple public names), an object with no public
caller-scope name, a non-`Knowledge` value, or a duplicate name — so `__all__`
stays a literal, statically analyzable list while avoiding label typos.

## 4. Migration (breaking change)

Before this change the root `__all__` was a loose string set: names that did not
match a knowledge label were silently ignored. It is now strictly validated, so
an existing package fails to compile if its root `__all__` contains:

| `__all__` entry | Error |
| --- | --- |
| a strategy (`deduction(...)`, `support(...)`, composites) | `... resolves to Strategy, not a Gaia Knowledge object.` |
| a `fills(...)` / bridge relation | `... resolves to <type>, not a Gaia Knowledge object.` |
| a name imported from a dependency package | `... points to Knowledge from another package.` |
| a `Knowledge` aliased under a different name | `... points to Knowledge labeled '<label>'.` |
| a typo'd / missing name | `... the package root has no such attribute.` |

To migrate: remove every non-`Knowledge` name and every alias from the root
`__all__`, leaving only the package's headline `Knowledge` labels. Strategies and
bridges remain fully functional and referenceable — they are simply not part of
the public surface. Run `gaia build compile <pkg>` to surface any remaining
violations. Packages that still carry the legacy `from .authored import *` block
are upgraded in place on the next `gaia author` write.

## 5. Affected consumers

All of the following already assumed curated semantics; with this change the
**producer** finally matches them, so no consumer logic changes:

- `gaia register` — the exported-beliefs release manifest.
- `_manifest.py` — `exported_conclusions`.
- `_github.py` — README "leaf premises → exported conclusions" Mermaid.
- `_inquiry.py` / `check.py` — dependency trees and boundary claims walk back
  from exported goals.
- `_dot.py` — `exported` node class (★).
- `lkm_explorer` / `starmap.py` — `exported_ids` as the public surface.
- `gaia-formalize-fine` / `gaia-publish` skills — "exported conclusions" vs.
  internal nodes.
