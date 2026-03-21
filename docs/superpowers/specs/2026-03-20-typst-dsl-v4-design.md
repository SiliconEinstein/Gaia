# Gaia Typst DSL v4 Design Spec

## Goal

Redesign the Gaia Typst DSL to be maximally Typst-native: use Typst labels for identity, Typst `#import` for code reuse, `typst.toml` for package metadata, and a bibliography-like mechanism for cross-package knowledge references. Eliminate all custom infrastructure that duplicates Typst-native capabilities.

## Background

The current v3 DSL uses string-based identifiers (`#claim("name")[...]`), global state accumulation, and custom functions (`#package()`, `#module()`, `#use()`, `#export-graph()`, `#premise()`) that parallel Typst's native systems. This creates a learning burden and prevents leveraging Typst's built-in tooling (cross-referencing, package system, introspection).

A prototype (see `proto/test_label_api.typ`) validated that Typst's `query()`, `figure.where()`, label system, and metadata extraction can fully support Gaia's knowledge graph construction.

## Design

### Knowledge Declarations

Five declaration functions, each returning a single `figure` element that can receive a Typst label:

```typst
#setting[content] <label>
#question[content] <label>
#claim(from: (), kind: none)[statement][proof?] <label>
#action(from: (), kind: none)[description][proof?] <label>
#relation(type: "contradiction", between: (<a>, <b>))[description?][proof?] <label>
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | `array` of `label` | Premises — intra-package labels or gaia-bibliography keys |
| `kind` | `str` or `none` | Single-value subtype classification (e.g., `"observation"`, `"python"`) |
| `type` | `str` | For `#relation` only: `"contradiction"` or `"equivalence"` |
| `between` | `array` of `label` | For `#relation` only: the nodes involved in the relation |

**Knowledge types and semantics:**

| Function | Storage type | Belief measures | Default prior (review) |
|----------|-------------|-----------------|----------------------|
| `#setting` | `setting` | Whether assumption holds | Typically ~1.0 |
| `#question` | `question` | Well-posedness, not truth | 0.5 |
| `#claim` | `claim` | Truth of the assertion | 0.5 |
| `#action` | `action` | Admissibility/feasibility | 0.5 |
| `#relation` | `contradiction` / `equivalence` | Whether the relation holds | 0.5 |

**`kind` values (open, but known kinds trigger system behavior):**

For `#claim`:
- `"observation"` — empirical fact, reviewer should verify data source
- `"conjecture"` — speculative, typically low prior
- `"theorem"` — has formal proof, reviewer should verify
- `"hypothesis"` — awaiting verification

For `#action`:
- `"python"` — executable Python code, CI verification → belief ≈ 1.0
- `"lean4"` — Lean 4 formal proof, verification → belief ≈ 1.0
- `"infer"` — NL reasoning method, inherently probabilistic

### Identity: Typst Labels

Node identity uses Typst's native label system — no string identifiers:

```typst
// <label> attached to the figure element
#claim[Dark energy is 68%] <dark_energy>

// @label for cross-referencing in prose
As shown in @dark_energy, ...

// <label> as value in from: parameter
#claim(from: (<dark_energy>,))[Further conclusion...] <next_step>
```

**Properties:**
- Compile-time checked (Typst reports unknown labels)
- Document-scoped (intra-package)
- Same `@label` syntax for both intra-package refs and gaia-bibliography refs

### Dependency Structure: `from:` Parameter

Replaces `#premise()`. Dependencies declared as an array of labels on the declaration itself:

```typst
#claim(from: (<obs_1>, <obs_2>, <assumption>))[Conclusion...][
  Proof explanation referencing @obs_1 and @obs_2...
] <result>
```

**Design rationale:**
- Declarative — all premises visible at the declaration site
- No special functions inside proof blocks
- Proof block is pure content (rendering only), graph structure is in `from:`

### Proof Blocks

Optional second positional argument on `#claim` and `#action`:

```typst
#claim(from: (<a>, <b>))[Statement][
  Proof content — free-form Typst content.
  Can reference @a and @b naturally.
  This is purely for human-readable explanation.
  Graph structure comes from the from: parameter, not from proof content.
] <result>
```

**v4 scope:** No nested declarations inside proof blocks. Intermediate lemmas are declared outside, then referenced via `from:`. Nested proofs deferred to future version (requires proof context stack).

### Package Metadata: `typst.toml`

Use Typst's native package manifest — no `#package()` function:

```toml
[package]
name = "dark-energy"
version = "1.0.0"
entrypoint = "lib.typ"
authors = ["Researcher Name"]
description = "Dark energy knowledge package"
```

The Python compiler reads `typst.toml` directly for package name, version, etc.

### File Organization: Typst Native

Use Typst's native `#include` and `#import` — no `#module()` function:

```typst
// lib.typ — entrypoint
#import "@gaia/lang:1.0.0": *
#show: gaia-style

#include "motivation.typ"
#include "setting.typ"
#include "reasoning.typ"
```

Each `.typ` file is a natural organizational unit. No formal "module" concept in v4 — file structure is the grouping mechanism. Module concept deferred; if needed later, it can be added without breaking intra-package label references (which remain flat within a package).

### Cross-Package References: `#gaia-bibliography()`

Analogous to Typst's `#bibliography()` for academic citations. Declares external knowledge dependencies:

```yaml
# gaia-deps.yml
dark_energy_fraction:
  package: "dark-energy"
  version: "1.0.0"
  node: "dark_energy_fraction"
  type: claim
  content: "Dark energy accounts for ~68% of total energy density"

cmb_result:
  package: "cmb-analysis"
  version: "2.0.0"
  node: "cmb_result"
  type: claim
```

Usage in Typst — **identical syntax to intra-package references:**

```typst
#import "@gaia/lang:1.0.0": *
#show: gaia-style

// Load external knowledge dependencies
#gaia-bibliography("gaia-deps.yml")

// Cross-package ref uses same from: and @ref syntax
#claim(from: (<dark_energy_fraction>, <flat_universe>))[
  Building on @dark_energy_fraction, ...
] <my_conclusion>
```

**Resolution:** The Python compiler distinguishes local labels (resolved at compile time) from gaia-bibliography keys (resolved at publish/integration time against the knowledge store).

### Graph Extraction: Python Compiler

No `#export-graph()` function. The Python compiler extracts the graph externally:

```bash
# Query all knowledge nodes
typst query doc.typ "figure.where(kind: 'gaia-node')"

# Query all metadata (contains from:, kind:, between:, etc.)
typst query doc.typ "metadata"
```

**Compiler responsibilities:**
1. Read `typst.toml` for package metadata
2. Run `typst query` to extract nodes, edges, and metadata
3. Parse `gaia-deps.yml` to resolve cross-package references
4. Build Graph IR (factor graph) from extracted data
5. Pass to review → inference → publish pipeline

### Gaia Runtime Package

The declaration functions are distributed as a standard Typst package:

```typst
#import "@gaia/lang:1.0.0": *
```

**Package exports:**
- `setting`, `question`, `claim`, `action`, `relation` — knowledge declarations
- `gaia-style` — show rule for document styling
- `gaia-bibliography` — external knowledge dependency loader

No vendored `_gaia/` directory needed in knowledge packages.

### Show Rule: `gaia-style`

Applies document-level styling and configures how Gaia elements render:

```typst
#show: gaia-style
```

Responsibilities:
- Page layout, font, language settings
- `figure.where(kind: "gaia-node")` → styled knowledge cards with type badge and colored left border
- `@ref` to Gaia nodes → rendered with node name (not just "Claim 4")
- Numbering and spacing for Gaia figures

### Storage Layer Changes

**Knowledge model addition:**

```python
class Knowledge(BaseModel):
    # Existing fields unchanged
    type: Literal["claim", "question", "setting", "action", "contradiction", "equivalence"]
    kind: str | None = None  # NEW — subtype classification from Typst kind: parameter
    # ...
```

No other storage model changes required.

## Complete API Summary

| Function | Purpose |
|----------|---------|
| `#setting[content] <label>` | Definitional assumption |
| `#question[content] <label>` | Open inquiry |
| `#claim(from:, kind:)[stmt][proof?] <label>` | Truth-apt assertion |
| `#action(from:, kind:)[desc][proof?] <label>` | Procedural knowledge |
| `#relation(type:, between:)[desc?][proof?] <label>` | Contradiction / equivalence |
| `#gaia-bibliography("file.yml")` | External knowledge dependencies |
| `#show: gaia-style` | Document styling |

## Removed from v3

| v3 | v4 | Reason |
|----|-----|--------|
| `#observation()` | `#claim(kind: "observation")` | Observations are claims that need supporting evidence |
| `#claim_relation()` | `#relation()` | Cleaner name, relation is first-class |
| `#premise()` | `from:` parameter | Declarative, no special proof-block functions |
| `#module()` | Typst file structure | Typst files are natural modules |
| `#package()` | `typst.toml` | Typst native package manifest |
| `#use()` | `#gaia-bibliography()` | Bibliography-like mechanism for cross-package refs |
| `#export-graph()` | `typst query` (compiler-side) | Authors don't need to know about graph export |
| `corroboration` type | removed | Semantics unclear; supporting evidence = normal premise |
| String identifiers | Typst `<label>` | Compile-time checked, Typst-native |

## Deferred to Future Versions

- **Nested proof declarations** — `#claim` inside proof blocks (requires proof context stack)
- **Module concept** — formal module grouping with roles (currently: file structure is enough)
- **Tag system** — multi-value metadata on knowledge nodes (currently: single `kind`)
- **`#gaia-bibliography` auto-generation** — tooling to generate deps file from published knowledge store

## Example: Complete Knowledge Package

```toml
# typst.toml
[package]
name = "dark-energy"
version = "1.0.0"
entrypoint = "lib.typ"
authors = ["Physics Research Group"]
```

```typst
// lib.typ
#import "@gaia/lang:1.0.0": *
#show: gaia-style

#include "setting.typ"
#include "evidence.typ"
#include "reasoning.typ"
```

```typst
// setting.typ
#import "@gaia/lang:1.0.0": *

= Assumptions

#setting[The universe is spatially flat on large scales.] <flat_universe>

#setting[General relativity is valid at cosmological scales.] <gr_valid>

#question[What is the physical nature of dark energy?] <main_question>
```

```typst
// evidence.typ
#import "@gaia/lang:1.0.0": *

= Observational Evidence

#claim(kind: "observation")[
  Type Ia supernovae data shows the universe's expansion is accelerating.
] <sn_observation>

#claim(kind: "observation")[
  CMB anisotropy data is consistent with a flat universe model.
] <cmb_data>
```

```typst
// reasoning.typ
#import "@gaia/lang:1.0.0": *

= Main Result

#claim(from: (<sn_observation>, <cmb_data>, <flat_universe>, <gr_valid>))[
  Dark energy accounts for approximately 68% of the total energy density of the universe.
][
  Based on independent observations from @sn_observation and @cmb_data,
  under the assumptions of @flat_universe and @gr_valid,
  the Friedmann equations constrain the dark energy fraction to ~68%.
] <dark_energy_fraction>

#relation(type: "contradiction", between: (<dark_energy_fraction>,))[
  The cosmological constant interpretation of dark energy differs from
  quantum field theory's vacuum energy prediction by 120 orders of magnitude.
] <vacuum_catastrophe>

#action(kind: "python", from: (<sn_observation>,))[
  MCMC fitting of Type Ia supernovae data using emcee to obtain
  the posterior distribution of $Omega_Lambda$.
] <mcmc_fit>
```
