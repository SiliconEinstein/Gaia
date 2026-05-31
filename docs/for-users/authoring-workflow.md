# Authoring workflow

> **Status:** Current v0.5 canonical. The single source of truth for how a
> Gaia knowledge package is authored — for both humans and agents.

Gaia has **one** authoring model with two tiers. This page states it and
closes the gaps that earlier docs left ambiguous.

## The model

**Tier 1 — direct SDK authoring (recommended).** Write the DSL directly in
Python. Run `gaia sdk` once to drop a self-contained reference plus a
one-page `CHEATSHEET.md` next to your work, read the cheat sheet, then
author your statements in `src/<pkg>/__init__.py` (and your own modules).
This is the primary path for everyone — humans and agents alike.

```bash
gaia sdk                       # writes ./gaia-sdk/CHEATSHEET.md + full reference
# read CHEATSHEET.md, then author directly:
#   src/my_package/__init__.py
gaia build compile ./my-package-gaia
gaia run infer ./my-package-gaia
```

**Tier 2 — the `gaia author` CLI (optional convenience).** `gaia author
<verb>` CRUDs DSL statements through structured, JSON-enveloped commands.
It is a convenience layer over Tier 1 — useful when you want machine-checked
appends, identifier-collision guards, and a post-write compile check — not a
separate or "agent-first" authoring path. Use it when it helps; skip it when
you'd rather write Python directly.

## What this resolves

1. **Recommended path = direct SDK authoring (Tier 1).** `gaia author` is
   Tier 2, optional. Start with `gaia sdk`, not the CLI.
2. **One on-disk format.** A Gaia package is plain Python (`.py`). There is
   no second serialized format. CLI output is confined to the package's
   re-exported `authored/` submodule (see below).
3. **`gaia author` APPENDS and is NOT idempotent.** Re-running the same
   `gaia author` command writes the statement again; a later binding of the
   same name shadows the earlier one. `gaia author list` reports shadowing
   (the earlier binding is stamped `shadowed_by`). If you re-run a command,
   expect a duplicate — edit the source or rename rather than relying on
   dedup.
4. **No "agent-first" framing.** Both humans and agents author directly
   first; the CLI is optional for either. There is no privileged agent entry
   point — `gaia sdk` is the shared starting move.
5. **Auxiliary files live under `authored/`.** When the CLI manages priors
   or reviews, they land in `authored/priors.py` / `authored/reviews/…`
   (created via `gaia pkg add-module`, routed there by `gaia author <verb>
   --file <name>.py`). Hand-authored packages may keep a top-level
   `priors.py`; both are loaded by the engine.
6. **Mixing contract.** Hand-authored DSL lives in your own modules (the
   package root `__init__.py` and any siblings you write). CLI-authored DSL
   lives in `authored/`. The two **compose by import**, never by interleaving
   in one file: the package-root `__init__.py` carries
   `from .authored import *` and merges `authored.__all__` into its own
   `__all__`, so the complete DSL loads as one package.

## The `authored/` submodule

`gaia build init` / `gaia pkg scaffold` create:

```
my-package-gaia/
  src/my_package/
    __init__.py          # hand-authored DSL + `from .authored import *`
    authored/
      __init__.py         # CLI-authored statements land here (__all__ literal)
      priors.py           # optional CLI-managed sibling (gaia pkg add-module)
```

The package-root `__init__.py` ends with:

```python
__all__: list[str] = [...]               # your hand-authored exports

from .authored import *                  # CLI-authored statements
from . import authored as _authored
__all__ = [*__all__, *_authored.__all__]
```

`gaia author` never writes the package-root `__init__.py`; every CLI write
goes into `authored/`. This keeps hand-authored and CLI-authored statements
in separate files that compose cleanly.

> **Pre-canon alpha packages.** You do **not** add the re-export block by
> hand. On the **first** `gaia author <verb>` write, the CLI automatically
> creates `authored/` and appends the re-export block (the
> `from .authored import *` import plus the `__all__` merge) to your
> package-root `__init__.py`. The only manual step for an alpha-era package
> is relocating any pre-existing CLI-style statements that currently live in
> the root `__init__.py` into `authored/` if you want them CLI-managed there.
> There is no migration tooling: CLI-authored and hand-authored `.py` are
> byte-identical, so a detector would false-positive — hence the move is
> manual and the appended block is byte-identical to the scaffolded one. If
> your root `__all__` is a tuple, the merge preserves it as a tuple.

## See also

- **`gaia sdk`** — generates a self-contained SDK reference plus a top-tier
  `CHEATSHEET.md` into its `--out` directory at runtime (see [the
  model](#the-model)).
- [Language reference](language-reference.md) — the static DSL surface
  reference.
- [`gaia author` / `gaia pkg scaffold`](../reference/cli/author.md) — the
  optional Tier-2 CLI.
