# Language Spec

> **Status:** Current canonical

This document summarizes the Gaia Language v4 Typst DSL -- the authoring surface for knowledge packages. For full details, see `docs/foundations_archive/language/gaia-language-spec.md`.

## Overview

Gaia Language v4 is a Typst-based DSL. Authors write knowledge packages as standard Typst documents; the compiler extracts a structured knowledge graph via `typst query`. The language provides five declaration functions plus a cross-package bibliography mechanism.

## Declarations

All declarations produce `figure(kind: "gaia-node")` elements with hidden metadata, enabling extraction via a single query.

| Function | Purpose | Parameters |
|---|---|---|
| `#setting[content]` | Contextual assumption | Content body only |
| `#question[content]` | Open inquiry | Content body only |
| `#claim[content][proof]` | Truth-apt assertion | `from:` (premises), `kind:` (subtype) |
| `#action[content][proof]` | Procedural step | `from:` (premises), `kind:` (subtype) |
| `#relation[content][proof]` | Structural constraint | `type:` ("contradiction" or "equivalence"), `between:` (endpoints) |

The optional second content block `[proof]` contains the natural-language justification with `@ref` cross-references.

## Key Parameters

**`from:`** -- a tuple of label references declaring load-bearing premises:
```typst
#claim(from: (<setting.vacuum_env>, <obs.measurement>))[conclusion][proof]
```
Single-element tuples require a trailing comma: `from: (<label>,)`.

**`between:`** -- required on `#relation`, names the two constrained nodes:
```typst
#relation(type: "contradiction", between: (<claim_a>, <claim_b>))[description]
```

**`kind:`** -- optional scientific subtype on claims and actions (e.g., `"observation"`, `"hypothesis"`, `"python"`). Records evidence type; does not change Graph IR topology.

## Labels

Labels follow `<filename.label_name>` convention:
```typst
#setting[...] <setting.vacuum_env>
#claim[...]   <reasoning.main_conclusion>
```

The `filename.` prefix is a naming convention for uniqueness across modules. In-text references use `@label` syntax.

## Cross-Package References

External knowledge is declared via `gaia-deps.yml` and registered with `#gaia-bibliography`:

**`gaia-deps.yml`:**
```yaml
vacuum_prediction:
  package: "galileo_falling_bodies"
  version: "4.0.0"
  node: "vacuum_prediction"
  type: claim
  content: "In a vacuum, objects of different weights fall at the same rate."
```

**Usage:**
```typst
#gaia-bibliography(yaml("gaia-deps.yml"))
#claim(from: (<local_derivation>, <vacuum_prediction>))[...][...]
```

`#gaia-bibliography` creates hidden `figure(kind: "gaia-ext")` elements that make external labels resolvable by Typst's reference system and the extraction pipeline.

## Extraction

Graph IR is extracted via Typst's built-in query mechanism:

```bash
# Local nodes
typst query --root <repo-root> lib.typ 'figure.where(kind: "gaia-node")'

# External references
typst query --root <repo-root> lib.typ 'figure.where(kind: "gaia-ext")'
```

The Python loader (`libs/lang/typst_loader.py::load_typst_package_v4`) processes query results into `{package, version, nodes, factors, constraints, dsl_version: "v4"}`.

## Package Layout

Two supported layouts:

**Vendored (default for new packages, created by `gaia init`):**
```
my_package/
  typst.toml          # manifest: name, version, entrypoint
  lib.typ             # entrypoint: #import "_gaia/lib.typ": *
  _gaia/              # vendored runtime (copied by gaia init)
    lib.typ
    ...
  motivation.typ      # module file
  reasoning.typ       # module file
  gaia-deps.yml       # (optional) cross-package references
```

**Repo-relative (fixtures and development inside the Gaia repo):**
```
my_package/
  typst.toml          # manifest: name, version, entrypoint
  lib.typ             # entrypoint: #import "/libs/typst/gaia-lang-v4/lib.typ": *
  motivation.typ      # module file
  reasoning.typ       # module file
  gaia-deps.yml       # (optional) cross-package references
```

The vendored layout is recommended for standalone packages. The repo-relative layout is used in `tests/fixtures/` and development workflows within the Gaia repository.

## Runtime Library

Lives at `libs/typst/gaia-lang-v4/`. Exports:

| Symbol | Source | Purpose |
|---|---|---|
| `setting`, `question`, `claim`, `action`, `relation` | `declarations.typ` | Declaration functions |
| `gaia-bibliography` | `bibliography.typ` | Cross-package reference registration |
| `gaia-style` | `style.typ` | Document show rules and visual styling |

## Source

- `libs/typst/gaia-lang-v4/` -- runtime Typst function definitions
- `libs/lang/typst_loader.py` -- Python extraction loader
- `docs/foundations_archive/language/gaia-language-spec.md` -- full specification
- `docs/foundations_archive/language/gaia-language-design.md` -- design rationale
