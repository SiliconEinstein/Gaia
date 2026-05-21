# LKM-Explorer Package Layout

> Generic Gaia knowledge-package layout, naming conventions, and file
> templates (`pyproject.toml`, `__init__.py`, `priors.py`,
> `references.json`) are the canonical Gaia spec — see
> `docs/for-users/quick-start.md` and `docs/for-users/language-reference.md`,
> and the shipping walkthroughs `gaia example mendel` /
> `gaia example galileo`. This file documents only the LKM-explorer
> module-routing convention.

## Module routing

`gaia-lkm-explorer` follows the Mendel/Galileo two-module layout:

- All DSL emissions for every source paper — `claim` / `derive` / `equal`
  / `contradict` / `exclusive` / `observe` / `note` / `question` — go in
  the scaffolded `__init__.py` (the default `--file` target when
  `gaia author <verb>` is invoked without `--file`).
- Leaf-prior records (`register_prior(...)`) go in a sibling `priors.py`,
  scaffolded explicitly with `--imports register_prior` so the import is
  pre-seeded.

There is no per-paper `paper_<key>.py` sibling — that pattern is not in
the shipping walkthroughs and is not prescribed here.

```text
<name>-gaia/
├── pyproject.toml
├── references.json
└── src/<import>/
    ├── __init__.py
    └── priors.py
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
