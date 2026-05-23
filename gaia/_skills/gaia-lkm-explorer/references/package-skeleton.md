# LKM-Explorer Package Layout

> Generic Gaia knowledge-package layout, naming conventions, and file
> templates (`pyproject.toml`, `__init__.py`, `priors.py`,
> `references.json`) are the canonical Gaia spec — see
> `docs/for-users/quick-start.md` and `docs/for-users/language-reference.md`,
> and the shipping walkthroughs `gaia example mendel` /
> `gaia example galileo`. This file documents only the LKM-explorer
> module-routing convention.

## Module routing

`gaia-lkm-explorer` follows the Mendel/Galileo two-module layout. Authoring
follows Gaia's one model, two tiers (`docs/for-users/authoring-workflow.md` is
canonical; run `gaia sdk` once for the reference + cheatsheet before you start):

- **Tier 1 — direct SDK authoring (primary).** Write all DSL emissions for every
  source paper — `claim` / `derive` / `equal` / `contradict` / `exclusive` /
  `observe` / `note` / `question` — **directly into** the scaffolded
  package-root `__init__.py` (`from gaia.engine.lang import ...`).
- **Tier 2 — `gaia author` (optional).** When invoked, the CLI writes the same
  DSL into the package's `authored/` submodule
  (`src/<import>/authored/__init__.py`), and the package-root `__init__.py`
  re-exports it via `from .authored import *`. The CLI never writes the root
  `__init__.py`.
- Leaf-prior records (`register_prior(...)`) go in a sibling `priors.py` — either
  hand-written, or scaffolded with `--imports register_prior` (so the import is
  pre-seeded) for `gaia author register-prior --file priors.py`, which routes
  through `authored/priors.py`.

There is no per-paper `paper_<key>.py` sibling — that pattern is not in
the shipping walkthroughs and is not prescribed here.

```text
<name>-gaia/
├── pyproject.toml
├── references.json
└── src/<import>/
    ├── __init__.py        # hand-authored DSL (Tier 1); re-exports authored/ once the CLI is used
    ├── priors.py          # leaf-prior records
    └── authored/          # present only if the Tier-2 CLI was used
        └── __init__.py     #   CLI-authored DSL, re-exported by the package root
```

`references.json` is a JSON object keyed by citation key, CSL-JSON entry
shape; each entry must include `type` (drawn from the CSL allowlist). See
`docs/specs/2026-04-09-references-and-at-syntax.md` for the full schema.

Scaffold with:

```bash
gaia pkg scaffold \
    --target <name>-gaia \
    --name <name>-gaia \
    --namespace <namespace> \
    --with-uuid \
    --description "<one-line description>"

gaia pkg add-module \
    --name priors \
    --imports register_prior \
    --target <name>-gaia
```

`--namespace` matches the walkthroughs (Mendel/Galileo pass
`--namespace example`); set it to whatever namespace you have
chosen for this run. `--imports register_prior` pre-seeds the
`register_prior` import into `priors.py` so subsequent `gaia author
register-prior --file priors.py` invocations compile without adding the
import by hand.
